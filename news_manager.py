import feedparser
import requests
from bs4 import BeautifulSoup
import mysql.connector
import json
import logging
from datetime import datetime
import openai
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsDatabase:
    def __init__(self, config_file='config.json'):
        self.config = self._load_config(config_file)
        self.db_config = self.config.get('news_db')
        self.ensure_table_exists()

    def _load_config(self, config_file):
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        return {}

    def ensure_table_exists(self):
        try:
            # First try connecting to the specific DB
            conn = self.get_connection()
            if not conn:
                # If connection fails, maybe DB doesn't exist. Try connecting to server root.
                if not self._create_database():
                    return
                conn = self.get_connection()
            
            if conn:
                cursor = conn.cursor()
                create_table_query = """
                CREATE TABLE IF NOT EXISTS tb_news (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    link VARCHAR(500) NOT NULL,
                    published_date VARCHAR(100),
                    summary TEXT,
                    content TEXT,
                    source VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_link (link)
                )
                """
                cursor.execute(create_table_query)
                conn.commit()
                cursor.close()
                conn.close()
                logger.info("Table tb_news checked/created.")
        except Exception as e:
            logger.error(f"Table setup error: {e}")

    def _create_database(self):
        try:
            # Connect without database
            conn = mysql.connector.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )
            cursor = conn.cursor()
            db_name = self.db_config['database']
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            cursor.close()
            conn.close()
            logger.info(f"Database {db_name} created.")
            return True
        except Exception as e:
            logger.error(f"Database creation error: {e}")
            return False

    def get_connection(self):
        try:
            conn = mysql.connector.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database=self.db_config['database']
            )
            return conn
        except mysql.connector.Error as err:
            logger.error(f"DB Connection Error: {err}")
            return None

    def save_article(self, article):
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            query = """
            INSERT INTO tb_news (title, link, published_date, summary, content, source)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE title=%s
            """
            # Duplicate key update to avoid errors, though usually we might skip
            params = (
                article['title'], article['link'], article['published'], 
                article.get('summary', ''), article.get('content', ''), article['source'],
                article['title']
            )
            cursor.execute(query, params)
            conn.commit()
            return True
        except mysql.connector.Error as err:
            logger.error(f"Save Error: {err}")
            return False
        finally:
            cursor.close()
            conn.close()

    def get_saved_articles(self):
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM tb_news ORDER BY created_at DESC")
            return cursor.fetchall()
        finally:
            if conn:
                conn.close()

class NewsFetcher:
    def __init__(self, config_file='config.json'):
        self.config = self._load_config(config_file)
        self.sources = {
            "Maeil Business": "https://www.mk.co.kr/rss/30000001/",
        }

    def _load_config(self, config_file):
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        return {}

    def fetch_feeds(self, source_name):
        url = self.sources.get(source_name)
        if not url:
            return []
        
        # Use requests to fetch with headers to avoid blocking (especially YTN)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as e:
            logger.error(f"Error fetching feed for {source_name}: {e}")
            return []

        entries = []
        for entry in feed.entries[:20]: # Limit to 20
            entries.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.get('published', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                'source': source_name
            })
        return entries

    def get_full_text(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            
            # Handle Google News Redirects (JS Redirect)
            if "news.google.com" in response.url or "news.google.com" in url:
                # Try to find the real URL in the response content
                import re
                # Pattern often used: window.location.replace("..."); or <a href="...">
                # Simple attempt to find the main redirect link
                match = re.search(r'window\.location\.replace\("(.+?)"\)', response.text)
                if match:
                    real_url = match.group(1).replace('\\u003d', '=').replace('\\x3d', '=')
                    logger.info(f"Redirecting Google URL to: {real_url}")
                    response = requests.get(real_url, headers=headers, timeout=10)
                else:
                    # Fallback: look for generic hrefs if the above fails
                    soup_redirect = BeautifulSoup(response.content, 'html.parser')
                    # This is risky but sometimes works for noscript blocks
                    links = soup_redirect.find_all('a')
                    if links and len(links) < 5: # If page is bare bones
                        real_url = links[0].get('href')
                        if real_url:
                             response = requests.get(real_url, headers=headers, timeout=10)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()

            # Improved Extraction Logic
            # 1. Look for 'article' tag
            article = soup.find('article')
            if article:
                paragraphs = article.find_all('p')
            else:
                # Fallback to all p tags
                paragraphs = soup.find_all('p')
            
            # Filter paragraphs
            text_content = []
            for p in paragraphs:
                txt = p.get_text().strip()
                if len(txt) > 40: # slightly lower threshold
                    text_content.append(txt)
            
            text = '\n\n'.join(text_content)
            
            if not text and "news.google.com" in url:
                return "⚠️ Content extraction failed. Google News often blocks full-text extraction tools. Please use the 'Link' button to read the original article."

            return text if text else "Could not extract text content. Site structure might be complex."
        except Exception as e:
            logger.error(f"Error fetching text: {e}")
            return f"Error fetching content: {e}"

    def summarize_text(self, text):
        # Local LLM (Ollama) configuration
        # Assuming 2080ti host from config or hardcoded for now based on user context
        # Better to get from config, but let's default to the known IP
        ollama_host = "http://2080ti:11434"
        model = "gpt-oss:20b" # Using one of the available models

        if len(text) < 100:
            return "Text too short to summarize."

        try:
            payload = {
                "model": model,
                "prompt": f"Summarize the following text in 3 bullet point lines in Korean:\n\n{text[:3000]}",
                "stream": False
            }
            logger.info(f"Sending request to Ollama: {model}")
            response = requests.post(f"{ollama_host}/api/generate", json=payload, timeout=120) 
            response.raise_for_status()
            result = response.json()
            return result.get("response", "No summary generated.")
        except Exception as e:
            logger.error(f"Ollama Error for {model}: {e}")
            return f"Error generating summary: {e}"

    def check_ollama_connection(self):
        ollama_host = "http://2080ti:11434"
        try:
            resp = requests.get(f"{ollama_host}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m['name'] for m in resp.json().get('models', [])]
                return True, f"Connected. Available models: {', '.join(models)}"
            return False, f"Status Code: {resp.status_code}"
        except Exception as e:
            return False, str(e)
