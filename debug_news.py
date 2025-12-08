import feedparser
import requests
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_feed(name, url):
    print(f"--- Testing {name} ---")
    print(f"URL: {url}")
    feed = feedparser.parse(url)
    print(f"Entries found: {len(feed.entries)}")
    if len(feed.entries) > 0:
        entry = feed.entries[0]
        print(f"First Entry Title: {entry.title}")
        print(f"First Entry Link: {entry.link}")
        print(f"First Entry Keys: {entry.keys()}")
        if 'published' in entry:
            print(f"Published: {entry.published}")
        else:
            print("No 'published' field found.")
        
        # Test Fetching Content
        print("Attempting to fetch content for first link...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(entry.link, headers=headers, timeout=10, allow_redirects=True)
            print(f"Final URL: {response.url}")
            print(f"Status Code: {response.status_code}")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            paragraphs = soup.find_all('p')
            text = '\n\n'.join([p.get_text() for p in paragraphs if len(p.get_text()) > 50])
            print(f"Extracted Text Length: {len(text)}")
            if len(text) == 0:
                print("--- DEBUG: Response Content (First 1000 chars) ---")
                print(response.text[:1000])
                print("--------------------------------------------------")
            print(f"Snippet: {text[:200]}")
        except Exception as e:
            print(f"Error fetching content: {e}")
    else:
        print("No entries found!")
    print("-" * 30)

sources = {
    "Google Science": "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=ko&gl=KR&ceid=KR:ko",
    "Maeil Business": "https://www.mk.co.kr/rss/30000001/",
    "YTN": "https://www.ytn.co.kr/_ln/rss/rss_general.xml"
}

for name, url in sources.items():
    test_feed(name, url)
