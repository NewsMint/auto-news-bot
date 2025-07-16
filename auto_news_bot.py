print("✅ Script started running with Google Gemini")

import os
from dotenv import load_dotenv
load_dotenv()

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
from google_auth_oauthlib.flow import InstalledAppFlow
import google.generativeai as genai

# ✅ Load Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ ERROR: GEMINI_API_KEY is not set!")
    exit()

genai.configure(api_key=GEMINI_API_KEY)

HEADERS = {
    'User-Agent': 'Mozilla/5.0'
}

def get_blogger_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', ['https://www.googleapis.com/auth/blogger']
            )
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('blogger', 'v3', credentials=creds)

def remove_watermark_from_url(image_url):
    try:
        print("🖼️ Downloading image to remove watermark...")
        response = requests.get(image_url)
        image_array = np.array(Image.open(BytesIO(response.content)).convert("RGB"))
        h, w, _ = image_array.shape
        watermark_area = image_array[h-50:h-5, w-120:w-5]
        blurred_area = cv2.GaussianBlur(watermark_area, (23, 23), 30)
        image_array[h-50:h-5, w-120:w-5] = blurred_area
        cleaned_path = "cleaned_image.jpg"
        cv2.imwrite(cleaned_path, cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR))
        print("✅ Watermark removed")
        return cleaned_path
    except Exception as e:
        print("❌ Watermark removal failed:", e)
        return None

def fetch_articles(url, limit=5):
    print(f"🌐 Fetching articles from {url}")
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        articles = []

        if "kannadanewsnow.com" in url:
            # 🎯 For kannadanewsnow.com
            links = soup.select("div.jeg_postblock_content a")
            for link in links:
                href = link.get("href")
                if href and href.startswith("http") and href not in articles:
                    articles.append(href)

        elif "kannadadunia.com" in url:
            # 🎯 For kannadadunia.com
            links = soup.select("h2.entry-title a")
            for link in links:
                href = link.get("href")
                if href and href.startswith("http") and href not in articles:
                    articles.append(href)

        print(f"✅ Found {len(articles)} article(s)")
        return articles[:limit]
    except Exception as e:
        print("❌ Fetch failed:", e)
        return []

def extract_article_content(url):
    print(f"📄 Extracting content from: {url}")
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Extract title
        title = soup.title.string.strip() if soup.title else "News"

        # Extract article text
        paragraphs = soup.find_all('p')
        text = ' '.join([p.get_text() for p in paragraphs])

        # ✅ Try to get image inside the post content
        # Find <div> or <article> that contains the news
        article_container = soup.find('div', class_='td-post-content') or soup.find('article') or soup.find('div', class_='entry-content')
        image_url = ''

        if article_container:
            image_tag = article_container.find('img')
            if image_tag and 'src' in image_tag.attrs:
                image_url = image_tag['src']

        return title, text, image_url
    except Exception as e:
        print("❌ Extract failed:", e)
        return "", "", ""

def rewrite_content(title, content):
    print(f"🧠 Rewriting with Gemini: {title[:30]}...")
    prompt = f"""
Title: {title}

Content: {content}

Rewrite the above Kannada news into:

1. A short 400-character summary in Kannada.
2. A short title in Kannada (within 6 words, no subtitles or punctuation).

Format your response like this exactly:
Title: <your short title here>
Summary: <your 400-character summary here>
"""

    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        response = model.generate_content(prompt)
        lines = response.text.strip().split('\n')

        short_title = ""
        short_summary = ""

        for line in lines:
            if line.lower().startswith("title:"):
                short_title = line.split(":", 1)[1].strip()
            elif line.lower().startswith("summary:"):
                short_summary = line.split(":", 1)[1].strip()

        if not short_title or not short_summary:
            print("⚠️ Gemini output missing required parts.")
            return title, ""  # fallback

        print("✅ Gemini rewrite successful")
        return short_title, short_summary
    except Exception as e:
        print("❌ Gemini Error:", e)
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
            data = res.json()
            if "data" in data and "url" in data["data"]:
                return data["data"]["url"]
            else:
                print("⚠️ imgbb response missing 'data.url'")
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

        image_url = None
        if image_path:
            image_url = upload_image_to_imgbb(image_path)

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
    websites = ["https://www.kannadanewsnow.com", "https://www.kannadadunia.com"]
    for site in websites:
        print(f"🔎 Processing website: {site}")
        articles = fetch_articles(site)
        for link in articles:
            title, full_content, img_url = extract_article_content(link)
            if len(full_content.strip()) < 50:
                print("⚠️ Skipped short content.")
                continue

            short_title, short_news = rewrite_content(title, full_content)
            if not short_news.strip():
                print("⚠️ Skipping post due to empty rewritten content.")
                continue

            img_cleaned = remove_watermark_from_url(img_url) if img_url else None
            upload_to_blogger(short_title, short_news, img_cleaned)

    print("✅ Script finished!")

if __name__ == "__main__":
    main()
