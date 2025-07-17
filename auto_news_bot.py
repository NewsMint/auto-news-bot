import requests
from bs4 import BeautifulSoup
import openai
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import os

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
BLOGGER_CLIENT_ID = os.getenv("BLOGGER_CLIENT_ID")
BLOGGER_CLIENT_SECRET = os.getenv("BLOGGER_CLIENT_SECRET")
BLOGGER_REFRESH_TOKEN = os.getenv("BLOGGER_REFRESH_TOKEN")
BLOGGER_BLOG_ID = os.getenv("BLOGGER_BLOG_ID")

# Initialize OpenAI
openai.api_key = OPENAI_API_KEY

def fetch_articles(url):
    print(f"🌐 Fetching articles from {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = []

        if "kannadanewsnow.com" in url:
            blocks = soup.select("article.l-post.grid-overlay a.image-link")
            for a in blocks:
                link = a.get("href")
                img = a.find("img")
                img_url = img["src"] if img else ""
                if link:
                    articles.append((link, img_url))

        elif "kannadadunia.com" in url:
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
        print(f"❌ Error fetching articles: {e}")
        return []

def get_article_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.select("p")  # Adjust selector based on site structure
        content = " ".join(p.get_text() for p in paragraphs)
        return content[:2000]  # Limit to 2000 chars to avoid token limits
    except Exception as e:
        print(f"❌ Error fetching content from {url}: {e}")
        return ""

def summarize_article(content):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a news summarizer. Rewrite the given article into a 400-character summary with a catchy title (6-7 words). Return JSON with 'title' and 'summary'."},
                {"role": "user", "content": f"Summarize this article into 400 characters and provide a catchy title (6-7 words):\n{content}"}
            ]
        )
        result = response.choices[0].message.content
        return json.loads(result)
    except Exception as e:
        print(f"❌ Error summarizing article: {e}")
        return {"title": "", "summary": ""}

def upload_image_to_imgbb(image_url):
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        image_data = base64.b64encode(response.content).decode('utf-8')
        payload = {
            "key": IMGBB_API_KEY,
            "image": image_data
        }
        response = requests.post("https://api.imgbb.com/1/upload", data=payload)
        response.raise_for_status()
        return response.json()["data"]["url"]
    except Exception as e:
        print(f"❌ Error uploading image to ImgBB: {e}")
        return ""

def post_to_blogger(title, content, image_url):
    try:
        credentials = Credentials(
            None,
            refresh_token=BLOGGER_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=BLOGGER_CLIENT_ID,
            client_secret=BLOGGER_CLIENT_SECRET
        )
        blogger_service = build("blogger", "v3", credentials=credentials)
        post_body = {
            "kind": "blogger#post",
            "title": title,
            "content": f'<img src="{image_url}" alt="{title}" /><br>{content}'
        }
        blogger_service.posts().insert(blogId=BLOGGER_BLOG_ID, body=post_body).execute()
        print(f"✅ Posted to Blogger: {title}")
    except HttpError as e:
        print(f"❌ Error posting to Blogger: {e}")

def main():
    news_sources = [
        "https://kannadanewsnow.com",
        "https://kannadadunia.com"
    ]
    for source in news_sources:
        articles = fetch_articles(source)
        for article_url, image_url in articles[:3]:  # Limit to 3 articles per source
            content = get_article_content(article_url)
            if content:
                summary_data = summarize_article(content)
                if summary_data["title"] and summary_data["summary"]:
                    imgbb_url = upload_image_to_imgbb(image_url) if image_url else ""
                    post_to_blogger(summary_data["title"], summary_data["summary"], imgbb_url)

if __name__ == "__main__":
    main()