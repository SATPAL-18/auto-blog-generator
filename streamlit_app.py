import os
import json
import time
import hashlib
import requests
import sqlite3
import zipfile
import io
import streamlit as st
from datetime import datetime
from pathlib import Path
import google.generativeai as genai
#this is my code
# Configure paths
BLOG_DIR = "blogs"
os.makedirs(BLOG_DIR, exist_ok=True)
PROCESSED_FILE = "processed_trends.json"
DB_PATH = "blog_database.db"

# Set page config
st.set_page_config(
    page_title="Auto Blog Generator",
    page_icon="📝",
    layout="wide"
)


# Password protection
def check_password():
    """Returns `True` if the user had the correct password."""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    password = st.text_input("Enter password", type="password")
    if password == "theaimart":
        st.session_state.password_correct = True
        return True
    elif password:
        st.error("Incorrect password")
        return False
    else:
        return False


# Initialize SQLite database
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS blogs (
        id INTEGER PRIMARY KEY,
        title TEXT,
        topic TEXT,
        filename TEXT,
        created_date TEXT,
        downloaded INTEGER
    )
    ''')
    conn.commit()
    conn.close()


# Load processed trends
def load_processed_trends():
    """Load previously processed trends to avoid duplication"""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            return json.load(f)
    return {}


# Save processed trends
def save_processed_trends(trends):
    """Save processed trends"""
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(trends, f)


# Fetch trending topics
def get_trending_topics(api_key):
    """Fetch trending topics from NewsAPI"""
    st.info("Fetching trending topics...")
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={api_key}"

    try:
        response = requests.get(url)

        if response.status_code != 200:
            st.error(f"Error fetching trends: {response.status_code}")
            return []

        data = response.json()
        topics = []

        for article in data.get('articles', []):
            title = article.get('title', '')
            if title and 'null' not in title.lower():
                # Extract main topic from title
                topic = ' '.join(title.split()[:5])
                topics.append(topic)

        return topics[:5]  # Return top 5 trending topics
    except Exception as e:
        st.error(f"Error fetching trending topics: {str(e)}")
        return []


# List available models
def list_available_models(api_key):
    try:
        genai.configure(api_key=api_key)
        models = genai.list_models()
        return [model.name for model in models]
    except Exception as e:
        st.error(f"Error listing models: {str(e)}")
        return []


# Generate SEO content
def generate_seo_content(topic, api_key, model_name):
    """Generate SEO optimized blog content using Google Gemini"""
    st.info(f"Generating content for: {topic}")

    try:
        # Configure Google Generative AI
        genai.configure(api_key=api_key)

        # Get model
        model = genai.GenerativeModel(model_name)

        # First get keyword research
        keyword_prompt = f"""
        Perform keyword research for the topic: '{topic}'
        Identify primary keyword and 5 related secondary keywords with good search volume and low competition.
        Format as JSON with fields: primary_keyword, secondary_keywords
        """

        keyword_response = model.generate_content(keyword_prompt)
        keyword_text = keyword_response.text.strip()

        # Extract JSON from response
        if keyword_text.startswith('```json'):
            keyword_text = keyword_text[7:-3]
        elif keyword_text.startswith('```'):
            keyword_text = keyword_text[3:-3]

        keyword_data = json.loads(keyword_text)

        primary_keyword = keyword_data.get('primary_keyword', topic)
        secondary_keywords = keyword_data.get('secondary_keywords', [])

        # Now generate the blog content
        blog_prompt = f"""
        Write a comprehensive, SEO-optimized blog post about '{primary_keyword}'.

        Include these elements:
        1. An engaging H1 title that includes the primary keyword: '{primary_keyword}'
        2. A meta description of 150-160 characters
        3. An introduction that hooks the reader
        4. At least 3 H2 subheadings
        5. Relevant H3 subheadings where appropriate
        6. 1000-1500 words of informative, high-quality content
        7. Naturally incorporate these secondary keywords: {', '.join(secondary_keywords)}
        8. A conclusion with a call to action
        9. Optimize for readability with short paragraphs and bulleted lists where appropriate

        Format the response as JSON with these fields:
        - title (H1)
        - meta_description
        - content (full HTML formatted blog content)
        """

        # Generate the SEO content
        response = model.generate_content(blog_prompt)
        response_text = response.text.strip()

        # Extract JSON from response
        if response_text.startswith('```json'):
            response_text = response_text[7:-3]
        elif response_text.startswith('```'):
            response_text = response_text[3:-3]

        blog_data = json.loads(response_text)
        return blog_data
    except Exception as e:
        st.error(f"Error generating content: {str(e)}")
        return None


# Create HTML page
def create_html_page(blog_data, topic):
    """Create HTML page for the blog post"""
    if not blog_data:
        return None

    # Create a sanitized filename
    filename = ''.join(e for e in topic if e.isalnum() or e.isspace()).replace(' ', '-').lower()
    filename = f"{filename}.html"
    filepath = os.path.join(BLOG_DIR, filename)

    # Generate HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{blog_data.get('meta_description', '')}">
    <title>{blog_data.get('title', 'Blog Post')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #444; margin-top: 30px; }}
        h3 {{ color: #555; }}
        p {{ margin-bottom: 15px; }}
        .date {{ color: #888; margin-bottom: 20px; }}
    </style>
    <script type="text/javascript" src="//www.highperformanceformat.com/723666a37c2b6efc2fac71afcff8596e/invoke.js"></script>
</head>
<body>
    <h1>{blog_data.get('title', 'Blog Post')}</h1>
    <div class="date">Published on {datetime.now().strftime('%B %d, %Y')}</div>
    {blog_data.get('content', '')}
    <hr>
    <footer>
        <p>© {datetime.now().year} Auto Blog Generator. All rights reserved.</p>
    </footer>
</body>
</html>"""

    # Write to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

    # Add to database
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO blogs (title, topic, filename, created_date, downloaded) VALUES (?, ?, ?, ?, ?)",
        (blog_data.get('title', 'Blog Post'), topic, filename, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0)
    )
    conn.commit()
    conn.close()

    return filename


# Process trending topic
def process_trending_topic(api_keys, model_name):
    """Main function to process trending topics"""
    processed_trends = load_processed_trends()
    trending_topics = get_trending_topics(api_keys['newsapi'])

    if not trending_topics:
        st.warning("No trending topics found.")
        return

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, topic in enumerate(trending_topics):
        status_text.text(f"Processing: {topic}")

        # Create a hash of the topic to track it
        topic_hash = hashlib.md5(topic.encode()).hexdigest()

        # Skip if we've already processed this topic recently
        if topic_hash in processed_trends:
            status_text.text(f"Already processed: {topic}")
            progress_bar.progress((i + 1) / len(trending_topics))
            continue

        # Generate blog content
        blog_data = generate_seo_content(topic, api_keys['google'], model_name)

        if blog_data:
            # Create HTML page
            filename = create_html_page(blog_data, topic)
            if filename:
                # Mark as processed
                processed_trends[topic_hash] = {
                    "topic": topic,
                    "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                status_text.text(f"Created blog: {filename}")

        progress_bar.progress((i + 1) / len(trending_topics))

    # Save processed trends
    save_processed_trends(processed_trends)
    status_text.text("Finished processing trending topics")
    progress_bar.progress(100)


# Get blog files from database
def get_blog_files(downloaded=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if downloaded is None:
        c.execute("SELECT * FROM blogs ORDER BY created_date DESC")
    else:
        c.execute("SELECT * FROM blogs WHERE downloaded = ? ORDER BY created_date DESC", (downloaded,))

    blogs = [dict(row) for row in c.fetchall()]
    conn.close()
    return blogs


# Mark blogs as downloaded
def mark_as_downloaded(blog_ids):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for blog_id in blog_ids:
        c.execute("UPDATE blogs SET downloaded = 1 WHERE id = ?", (blog_id,))

    conn.commit()
    conn.close()


# Create zip file of blogs
def create_zip_file(blog_filenames):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename in blog_filenames:
            file_path = os.path.join(BLOG_DIR, filename)
            if os.path.exists(file_path):
                zip_file.write(file_path, filename)

    zip_buffer.seek(0)
    return zip_buffer


# Demo data generation
def generate_demo_blog_content():
    blog_data = {
        "title": "Top 10 Tech Trends to Watch in 2025",
        "meta_description": "Discover the most important technology trends that will shape the future in 2025 and beyond. From AI to quantum computing, stay ahead of the curve.",
        "content": """
        <p>The technology landscape is evolving faster than ever before. As we move through 2025, several groundbreaking technologies are reshaping how we live and work. This article explores the most significant tech trends that you should keep an eye on this year.</p>

        <h2>1. Artificial Intelligence Revolution</h2>
        <p>Artificial Intelligence continues to advance at an unprecedented pace. In 2025, we're seeing AI systems that can perform complex reasoning tasks that were previously thought to require human intelligence.</p>
        <p>Key developments include:</p>
        <ul>
            <li>More sophisticated large language models that can understand and generate nuanced content</li>
            <li>AI systems that can explain their reasoning process</li>
            <li>Greater integration of AI into everyday applications and devices</li>
        </ul>

        <h2>2. Quantum Computing Goes Mainstream</h2>
        <p>After years of research and development, quantum computing is finally beginning to solve real-world problems that classical computers cannot handle efficiently.</p>

        <h2>3. Extended Reality (XR) Transforms Work and Entertainment</h2>
        <p>The lines between physical and digital realities continue to blur as extended reality technologies mature.</p>

        <h3>Virtual Workspaces</h3>
        <p>Companies are increasingly adopting virtual workspaces that allow remote teams to collaborate as if they were in the same physical space.</p>

        <h3>Immersive Entertainment</h3>
        <p>Entertainment experiences are becoming more interactive and personalized through XR technologies.</p>

        <h2>Conclusion</h2>
        <p>The technological landscape of 2025 offers incredible opportunities for businesses and individuals who stay informed and adapt quickly. By understanding these key trends, you can position yourself to take advantage of the next wave of digital transformation.</p>

        <p>Want to learn more about how these technologies can benefit your business? Contact our team of experts today for a personalized consultation.</p>
        """
    }
    return blog_data


# Generate demo blogs
def create_demo_blogs():
    demo_topics = [
        "Latest smartphone technology trends 2025",
        "Future of remote work post-pandemic",
        "Sustainable energy solutions worldwide",
        "Digital marketing strategies for startups",
        "Healthy nutrition tips for busy professionals"
    ]

    for topic in demo_topics:
        blog_data = generate_demo_blog_content()
        filename = create_html_page(blog_data, topic)

        if filename:
            st.success(f"Created demo blog: {filename}")


# Main app function
def main():
    if not check_password():
        # Password check failed
        return

    # Initialize database
    init_db()

    # Create sidebar
    st.sidebar.title("Auto Blog Generator")

    # API configuration
    st.sidebar.header("API Configuration")

    # Initialize API keys in session state if not present
    if 'api_keys' not in st.session_state:
        st.session_state.api_keys = {
            'google': "",
            'newsapi': ""
        }

    # API key inputs
    google_api_key = st.sidebar.text_input(
        "Google Gemini API Key",
        value=st.session_state.api_keys['google'],
        type="password"
    )

    newsapi_key = st.sidebar.text_input(
        "NewsAPI Key",
        value=st.session_state.api_keys['newsapi'],
        type="password"
    )

    # Update session state
    st.session_state.api_keys['google'] = google_api_key
    st.session_state.api_keys['newsapi'] = newsapi_key

    # Model selection
    available_models = []
    if google_api_key:
        with st.sidebar.expander("Advanced Settings"):
            if st.button("List Available Models"):
                available_models = list_available_models(google_api_key)
                if available_models:
                    st.session_state.available_models = available_models
                    st.success(f"Found {len(available_models)} available models")
                else:
                    st.error("No models found or API key invalid")

    if 'available_models' in st.session_state and st.session_state.available_models:
        model_name = st.sidebar.selectbox(
            "Select Model",
            options=st.session_state.available_models,
            index=0
        )
    else:
        model_name = st.sidebar.text_input(
            "Model Name (e.g., gemini-1.0-pro)",
            value="gemini-1.0-pro"
        )

    # Show downloaded blogs in sidebar
    st.sidebar.header("Downloaded Blogs")
    downloaded_blogs = get_blog_files(downloaded=1)

    if downloaded_blogs:
        downloaded_options = {f"{blog['title']} ({blog['filename']})": blog for blog in downloaded_blogs}
        st.sidebar.write(f"Total downloaded blogs: {len(downloaded_blogs)}")

        for blog in downloaded_blogs:
            st.sidebar.markdown(f"📄 **{blog['title']}** - *{blog['created_date']}*")
    else:
        st.sidebar.write("No downloaded blogs yet.")

    # Main content area
    st.title("Auto Blog Generator")

    # Generate buttons
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Generate Blogs from Trending Topics"):
            if not google_api_key or not newsapi_key:
                st.error("Please enter both API keys to continue.")
            else:
                process_trending_topic(
                    {
                        'google': google_api_key,
                        'newsapi': newsapi_key
                    },
                    model_name
                )

    with col2:
        if st.button("Generate Demo Blogs (No API needed)"):
            create_demo_blogs()
            st.success("Demo blogs created successfully!")

    # Display available blogs
    st.header("Available Blogs")
    available_blogs = get_blog_files(downloaded=0)

    if available_blogs:
        # Create a multiselect for blogs
        blog_options = {f"{blog['title']} ({blog['filename']})": blog for blog in available_blogs}
        selected_blogs = st.multiselect(
            "Select blogs to download",
            options=list(blog_options.keys())
        )

        # Display blogs
        for i, blog in enumerate(available_blogs):
            with st.expander(f"{blog['title']} - {blog['created_date']}"):
                st.write(f"**Topic:** {blog['topic']}")
                st.write(f"**Filename:** {blog['filename']}")

                file_path = os.path.join(BLOG_DIR, blog['filename'])
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                        st.download_button(
                            "Download HTML",
                            html_content,
                            file_name=blog['filename'],
                            mime="text/html"
                        )
                        st.components.v1.html(html_content, height=300, scrolling=True)

        # Download button for multiple blogs
        if selected_blogs:
            selected_blog_objs = [blog_options[blog] for blog in selected_blogs]
            blog_ids = [blog['id'] for blog in selected_blog_objs]
            blog_filenames = [blog['filename'] for blog in selected_blog_objs]

            zip_buffer = create_zip_file(blog_filenames)

            if st.download_button(
                    label="Download Selected Blogs as ZIP",
                    data=zip_buffer,
                    file_name="blogs.zip",
                    mime="application/zip"
            ):
                # Mark blogs as downloaded
                mark_as_downloaded(blog_ids)
                st.success(f"Downloaded {len(selected_blogs)} blogs and moved to Downloaded section.")
                # Force refresh by rerunning the app
                st.experimental_rerun()
    else:
        st.info("No blogs available for download. Generate some blogs first!")


if __name__ == "__main__":
    main()
