print("✅ Script started running with OpenAI GPT-3.5")

import os
import hashlib
import requests
import html
import cv2
import numpy as np
import pickle
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
from openai import OpenAI

# ✅ Functions to prevent duplicate posting
def load_posted_urls():
    if not os.path.exists("posted_urls.txt"):
        return set()
    with open("posted_urls.txt", "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_posted_url(url):
    with open("posted_urls.txt", "a", encoding="utf-8") as f:
        f.write(url + "\n")

load_dotenv()

# ✅ Load OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("❌ ERROR: OPENAI_API_KEY is not set!")
    exit()

client = OpenAI(api_key=OPENAI_API_KEY)

HEADERS = {
    'User-Agent': 'Mozilla/5.0'
}

# ✅ Load previously posted hashes
HASH_FILE = "posted_hashes.pkl"
if os.path.exists(HASH_FILE):
    with open(HASH_FILE, "rb") as f:
        posted_hashes = pickle.load(f)
else:
    posted_hashes = set()

def save_posted_hash(hash_val):
    posted_hashes.add(hash_val)
    with open(HASH_FILE, "wb") as f:
        pickle.dump(posted_hashes, f)

def hash_text(text):
    return hashlib.md5(text.encode()).hexdigest()

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os

def get_blogger_service():
    try:
        creds = Credentials(
            token=None,
            refresh_token=os.getenv("BLOGGER_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("BLOGGER_CLIENT_ID"),
            client_secret=os.getenv("BLOGGER_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/blogger"],
        )
        if creds.expired or not creds.valid:
            creds.refresh(Request())
        return build('blogger', 'v3', credentials=creds)
    except Exception as e:
        print("❌ Failed to initialize Blogger service:", e)
        exit(1)

def remove_watermark_from_url(image_url):
    try:
        print("🖼️ Downloading image to remove watermark...")
        response = requests.get(image_url)
        image_array = np.array(Image.open(BytesIO(response.content)).convert("RGB"))
        h, w, _ = image_array.shape
        center_x = w // 2
        logo_width = 300
        logo_height = 50
        top = 5
        bottom = top + logo_height
        left = center_x - (logo_width // 2)
        right = center_x + (logo_width // 2)
        if bottom <= h and right <= w and left >= 0:
            watermark_area_top_center = image_array[top:bottom, left:right]
            blurred_area = cv2.GaussianBlur(watermark_area_top_center, (25, 25), 30)
            image_array[top:bottom, left:right] = blurred_area
        cleaned_path = "cleaned_image.jpg"
        cv2.imwrite(cleaned_path, cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR))
        print("✅ Watermark removed")
        return cleaned_path
    except Exception as e:
        print("❌ Watermark removal failed:", e)
        return None

def fetch_articles(url):
    print(f"🌐 Fetching articles from {url}")
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    articles = []

    if "kannadanewsnow.com" in url:
        # ✅ Selector based on <article> blocks
        blocks = soup.select("article.l-post.grid-overlay a.image-link")
        for a in blocks:
            link = a.get("href")
            img = a.find("img")
            img_url = img["src"] if img else ""
            if link:
                articles.append((link, img_url))

    elif "kannadadunia.com" in url:
        # ✅ Selector based on div.p-featured > a.p-flink
        blocks = soup.select("div.p-featured a.p-flink")
        for a in blocks:
            link = a.get("href")
            img = a.find("img")
            img_url = img["src"] if img else ""
            if link:
                articles.append((link, img_url))

    print(f"✅ Found {len(articles)} article(s)")
    return articles

    except Exception as e:
        print("❌ Error fetching articles:", e)
        return []

def extract_article_content(url):
    print(f"📄 Extracting content from: {url}")
    try:
        res = requests.get(url, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(res.text, 'html.parser')

        # Skip video-only articles
        if soup.find("iframe") or soup.find("video"):
            print("⚠️ Skipping video news article.")
            return "", "", ""

        title = "News"
        full_content = ""
        image_url = ""

        # ✅ Logic for kannadadunia.com
        if "kannadadunia.com" in url:
            title_tag = soup.find("h1", class_="s-title")
            container = soup.find("div", class_="post-content") or soup.find("article")
            img_tag = soup.select_one("div.featured-lightbox-trigger img")

        # ✅ Logic for kannadanewsnow.com
        else:
            title_tag = soup.find("title") or soup.find("h1")
            container = (
                soup.find("div", class_="td-post-content")
                or soup.find("div", class_="entry-content")
                or soup.find("article")
            )
            # Select first good image (skip thumbnails)
            img_tag = None
            if container:
                for img in container.find_all("img"):
                    src = img.get("src", "")
                    if "uploads" in src and not any(x in src for x in ["300x", "150x", "100x"]):
                        img_tag = img
                        break

        # ✅ Extract title
        if title_tag:
            title = title_tag.get_text(strip=True)

        # ✅ Extract paragraphs
        if container:
            paragraphs = container.find_all("p")
            full_content = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # ✅ Validate content
        if len(full_content.strip()) < 50:
            print("⚠️ Skipped short content.")
            return title, "", image_url

        # ✅ Extract image URL
        if img_tag and img_tag.get("src"):
            image_url = img_tag["src"]
            print(f"🖼️ Using article image: {image_url}")

        return title, full_content.strip(), image_url

    except Exception as e:
        print("❌ Extract failed:", e)
        return "", "", ""

def rewrite_content(title, content):
    print(f"🧠 Rewriting with OpenAI: {title[:30]}...")

    prompt = f"""
Title: {title}

Content: {content}

Rewrite the above Kannada news article into:

1. A **short title in Kannada** within 6 words, without punctuation or subtitles.
2. A **summary in Kannada** between **370 to 400 characters**, covering only the news in the article clearly and professionally.

Do not add opinions or guess missing info.

Output format:
Title: <short title>
Summary: <370-400 character summary>
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            temperature=0.7,
            messages=[
                {"role": "system", "content": "You are a Kannada news editor rewriting short summaries for a mobile app."},
                {"role": "user", "content": prompt}
            ]
        )
        reply = response.choices[0].message.content.strip()

        short_title = ""
        short_summary = ""

        # Handle both "Title:" and "title:" etc
        for line in reply.splitlines():
            if line.lower().startswith("title:"):
                short_title = line.split(":", 1)[1].strip()
            elif line.lower().startswith("summary:"):
                short_summary = line.split(":", 1)[1].strip()

        if not short_title or not short_summary:
            print("⚠️ OpenAI output missing parts. Using fallback.")
            return title[:50], content[:380]

        print("✅ OpenAI rewrite successful")
        return short_title, short_summary

    except Exception as e:
        print("❌ OpenAI Error:", e)
        return title[:50], content[:380]

def upload_image_to_imgbb(image_path):
    try:
        print("📄 Uploading image to imgbb...")
        api_key = os.getenv("IMGBB_API_KEY")
        if not api_key:
            print("⚠️ IMGBB API key is not set.")
            return None
        if not os.path.exists(image_path):
            print("⚠️ Image file not found:", image_path)
            return None
        with open(image_path, "rb") as f:
            res = requests.post("https://api.imgbb.com/1/upload", data={"key": api_key}, files={"image": f})
            res.raise_for_status()
            data = res.json()
            if "data" in data and "url" in data["data"]:
                print("✅ Uploaded to imgbb:", data["data"]["url"])
                return data["data"]["url"]
            else:
                print("⚠️ imgbb response missing 'data.url'", data)
                return None
    except Exception as e:
        print("❌ Image upload failed:", e)
        return None

def upload_to_blogger(title, content, image_path):
    print("📰 Uploading to Blogger...")
    try:
        blogger = get_blogger_service()
        blogs = blogger.blogs().listByUser(userId='self').execute()
        blog_id = blogs['items'][0]['id']
        image_url = upload_image_to_imgbb(image_path) if image_path else None
        post_content = f"<p>{html.escape(content)}</p>"
        if image_url:
            post_content = f'<img src="{image_url}" width="100%"><br>' + post_content
        post = {
            'kind': 'blogger#post',
            'blog': {'id': blog_id},
            'title': title,
            'content': post_content
        }
        blogger.posts().insert(blogId=blog_id, body=post).execute()
        print("✅ Posted to Blogger:", title)
    except HttpError as err:
        print(f"❌ Blogger error: {err}")

def main():
    MAX_POSTS = 5
    post_count = 0
    print("✅ Script started running with OpenAI GPT-3.5")

    websites = [
        "https://kannadanewsnow.com/kannada/",
        "https://kannadadunia.com/category/latest-news/"
    ]

    posted_urls = load_posted_urls()

    for site in websites:
        print(f"🔎 Processing website: {site}")
        articles = fetch_articles(site)

        for link, img_url in articles:
            if link in posted_urls:
                print("⚠️ Duplicate post skipped.")
                continue

            title, full_content, extracted_img = extract_article_content(link)
            if not full_content or len(full_content.strip()) < 80:
                print("⚠️ Skipped short content.")
                continue

            image_url = extracted_img or img_url

            short_title, short_summary = rewrite_content(title, full_content)

            # Optional: Remove watermark if needed
            # image_url = remove_watermark(image_url)

            success = post_to_blogger(short_title, short_summary, image_url)

            if success:
                save_posted_url(link)
                post_count += 1
                if post_count >= MAX_POSTS:
                    print("🚫 Post limit reached for this run.")
                    return

    print("✅ Script finished!")

if __name__ == "__main__":
    main()
