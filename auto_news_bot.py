print("✅ Script started running with OpenAI GPT-3.5")

import os
import hashlib
import requests
import html
import cv2
import numpy as np
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
from openai import OpenAI

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

posted_hashes = set()


def hash_text(text):
    return hashlib.md5(text.encode()).hexdigest()


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

        # ✅ Blur top-center area (where KannadaNewsNow logo is)
        center_x = w // 2
        logo_width = 300   # Approx width of watermark
        logo_height = 50   # Approx height of watermark
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
        print("✅ Watermark removed from top-center")
        return cleaned_path
    except Exception as e:
        print("❌ Watermark removal failed:", e)
        return None


def fetch_articles(url):
    try:
        print(f"🌐 Fetching articles from {url}")
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        articles = []

        if "kannadanewsnow.com" in url:
            for article in soup.select('h3.entry-title.td-module-title a'):
                link = article['href']
                img_tag = article.find_parent('div.td-module-thumb').find('img')
                img_url = img_tag['src'] if img_tag else ""
                articles.append((link, img_url))

        elif "kannadadunia.com" in url:
            for a in soup.select("div.td-image-container a"):
                link = a["href"]
                img = a.find("img")
                img_url = img["src"] if img else ""
                articles.append((link, img_url))

        print(f"✅ Found {len(articles)} article(s)")
        return articles[:5]

    except Exception as e:
        print("❌ Fetch error:", e)
        return []


def extract_article_content(url):
    print(f"📄 Extracting content from: {url}")
    try:
        res = requests.get(url, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(res.text, 'html.parser')

        if "kannadadunia.com" in url:
            title_tag = soup.find("h1", class_="s-title")
            content_divs = soup.select("div.elementor-widget-container p")
            img_tag = soup.select_one("div.featured-lightbox-trigger img")
        else:
            title_tag = soup.title
            content_divs = soup.find_all("p")
            container = soup.find('div', class_='td-post-content') or soup.find('article') or soup.find('div', class_='entry-content')
            img_tag = None
            if container:
                for img in container.find_all('img'):
                    src = img.get("src", "")
                    if "uploads" in src and not "300x" in src and not "150x" in src:
                        img_tag = img
                        break

        title = title_tag.get_text(strip=True) if title_tag else "News"
        text = ' '.join([p.get_text(strip=True) for p in content_divs])
        image_url = img_tag["src"] if img_tag and img_tag.get("src") else ""
        print(f"🖼️ Using article image: {image_url}")
        return title, text, image_url
    except Exception as e:
        print("❌ Extract failed:", e)
        return "", "", ""


def rewrite_content(title, content):
    print(f"🧠 Rewriting with OpenAI: {title[:30]}...")
    prompt = f"""
Title: {title}

Content: {content}

Rewrite the above Kannada news into:

1. A Kannada summary that is **at least 370 characters and no more than 400 characters**. It should cover all key points briefly.
2. A short title in Kannada (within 6 words, no subtitles or punctuation).

Format your response like this exactly:
Title: <your short title here>
Summary: <your 370 to 400-character summary here>
"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        reply = response.choices[0].message.content.strip()
        lines = reply.split('\n')
        short_title = ""
        short_summary = ""

        for line in lines:
            if line.lower().startswith("title:"):
                short_title = line.split(":", 1)[1].strip()
            elif line.lower().startswith("summary:"):
                short_summary = line.split(":", 1)[1].strip()

        if not short_title or not short_summary:
            print("⚠️ OpenAI output missing required parts.")
            return title, ""

        print("✅ OpenAI rewrite successful")
        return short_title, short_summary
    except Exception as e:
        print("❌ OpenAI Error:", e)
        return title, ""


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
    websites = [
        "https://kannadanewsnow.com/kannada/",
        "https://kannadadunia.com/category/latest-news/"
    ]

    def is_breaking_news_image(image_url):
        if not image_url:
            return False
        return "breaking" in image_url.lower()

    for site in websites:
        print(f"🔎 Processing website: {site}")
        articles = fetch_articles(site)

        for link, homepage_image in articles:
            title, full_content, img_url = extract_article_content(link)

            # ✅ Use article image if available, else homepage image
            final_img = img_url or homepage_image

            # ✅ Replace breaking news image with clean hosted image
            if is_breaking_news_image(final_img):
                print("⚠️ Detected breaking news image. Replacing with your clean image...")
                final_img = "https://i.ibb.co/1cZbWPH/breaking-news-clean.jpg"

            # ✅ Skip if duplicate or content too short
            content_hash = hash_text(full_content)
            if content_hash in posted_hashes:
                print("⚠️ Duplicate post skipped.")
                continue
            if len(full_content.strip()) < 50:
                print("⚠️ Skipped short content.")
                continue

            # ✅ Rewrite using OpenAI
            short_title, short_news = rewrite_content(title, full_content)
            if not short_news.strip():
                print("⚠️ Skipping post due to empty rewritten content.")
                continue

            # ✅ Remove watermark and post to Blogger
            img_cleaned = remove_watermark_from_url(final_img) if final_img else None
            upload_to_blogger(short_title, short_news, img_cleaned)
            posted_hashes.add(content_hash)

    print("✅ Script finished!")


if __name__ == "__main__":
    main()
