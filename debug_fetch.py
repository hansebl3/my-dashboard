from modules.news_manager import NewsFetcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_fetch():
    fetcher = NewsFetcher()
    # Test with a GeekNews URL which is usually reliable, or Maeil if available.
    # Let's try a Maeil URL since that's a major source.
    # Actually, let's fetch the feed first to get a real current URL.
    
    print("Fetching feed...")
    items = fetcher.fetch_feeds("Maeil Business")
    if not items:
        print("Feed fetch failed.")
        return

    url = items[0]['link']
    print(f"Testing URL: {url}")
    
    import requests
    from bs4 import BeautifulSoup
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        print("Searching for potential content containers:")
        # Common MK structure candidates
        candidates = soup.find_all('div', class_=lambda x: x and ('txt' in x or 'content' in x or 'article' in x))
        for c in candidates:
            print(f"Found div class='{c.get('class')}': Length {len(c.get_text())}")
            
        print("-" * 20)
        # Check if article tag exists
        article = soup.find('article')
        print(f"Article tag found: {bool(article)}")
        
        print("-" * 20)
        # Check itemprop
        body = soup.find(attrs={"itemprop": "articleBody"})
        if body:
             print(f"Found itemprop='articleBody': Length {len(body.get_text())}")
             print("Snippet:", body.get_text()[:200])
        else:
             print("No itemprop='articleBody' found.")

        # Check news_content specific
        nc = soup.find('div', class_='news_content')
        if nc:
             print(f"Found div.news_content: Length {len(nc.get_text())}")
             print("Snippet:", nc.get_text()[:200])
             
        # Check art_txt
        at = soup.find('div', class_='art_txt')
        if at:
             print(f"Found div.art_txt: Length {len(at.get_text())}")
        
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_fetch()
