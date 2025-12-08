import feedparser
import subprocess
from modules.llm_manager import LLMManager
from modules.metrics_manager import DataUsageTracker
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
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_link (link)
                )
                """
                cursor.execute(create_table_query)
                
                # Migration: Add comment column if not exists
                try:
                    cursor.execute("SELECT comment FROM tb_news LIMIT 1")
                except:
                    logger.info("Adding comment column...")
                    cursor.execute("ALTER TABLE tb_news ADD COLUMN comment TEXT")
                    
                conn.commit()
                cursor.close()

                # Cache Table
                cursor = conn.cursor()
                create_cache_table_query = """
                CREATE TABLE IF NOT EXISTS tb_summary_cache (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    link_hash VARCHAR(255) NOT NULL, 
                    link TEXT NOT NULL,
                    summary TEXT,
                    model VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_link_hash (link_hash)
                )
                """
                cursor.execute(create_cache_table_query)
                conn.commit()
                cursor.close()
                
                conn.close()
                logger.info("Tables checked/created.")
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
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Save error: {e}")
            return False

    def get_summary_from_cache(self, link):
        """Get cached summary for a link"""
        import hashlib
        link_hash = hashlib.md5(link.encode('utf-8')).hexdigest()
        
        conn = self.get_connection()
        if not conn: return None
        
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT summary FROM tb_summary_cache WHERE link_hash = %s", (link_hash,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            if result:
                return result['summary']
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    def save_summary_to_cache(self, link, summary, model="unknown"):
        """Save summary to cache"""
        import hashlib
        link_hash = hashlib.md5(link.encode('utf-8')).hexdigest()
        
        conn = self.get_connection()
        if not conn: return False
        
        try:
            cursor = conn.cursor()
            # Upsert
            query = """
            INSERT INTO tb_summary_cache (link_hash, link, summary, model)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE summary=%s, model=%s, created_at=NOW()
            """
            cursor.execute(query, (link_hash, link, summary, model, summary, model))
            conn.commit()
            
            # Simple cleanup: keep only last 100 entries
            # This is a bit expensive to run every time, maybe random chance or dedicated cleanup
            # User asked for recent 100, let's do it simply.
            cursor.execute("SELECT count(*) FROM tb_summary_cache")
            count = cursor.fetchone()[0]
            if count > 100:
                # Delete oldest, keeping 100
                delete_query = """
                DELETE FROM tb_summary_cache 
                WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id FROM tb_summary_cache ORDER BY created_at DESC LIMIT 100
                    ) foo
                )
                """
                cursor.execute(delete_query)
                conn.commit()

            cursor.close()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Cache save error: {e}")
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
            INSERT INTO tb_news (title, link, published_date, summary, content, source, comment)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                title=%s, published_date=%s, summary=%s, content=%s, source=%s, comment=%s, created_at=NOW()
            """
            values = (
                article.get('title'),
                article.get('link'),
                article.get('published'),
                article.get('summary', ''),
                article.get('content', ''),
                article.get('source', ''),
                article.get('comment', ''),
                
                article.get('title'),
                article.get('published'),
                article.get('summary', ''),
                article.get('content', ''),
                article.get('source', ''),
                article.get('comment', '')
            )
            cursor.execute(query, values)
            conn.commit()
            return True
        except mysql.connector.Error as err:
            logger.error(f"Save Error: {err}")
            return False
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if conn:
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
            "GeekNews": "https://news.hada.io/rss/news",            
        }
        self.llm_manager = LLMManager()

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
            
            # Track Usage
            tracker = DataUsageTracker()
            tracker.add_rx(len(resp.content))
            
            feed = feedparser.parse(resp.content)
        except Exception as e:
            logger.error(f"Error fetching feed for {source_name}: {e}")
            return []

        entries = []
        for entry in feed.entries[:10]: # Limit to 10
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
                             DataUsageTracker().add_rx(len(response.content))
            
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

    def generate_summary(self, text, model, link=None, force_refresh=False):
        """Generate summary with optional caching"""
        # 1. Check Cache if link provided AND NOT forced
        if link and not force_refresh:
            db = NewsDatabase()
            cached = db.get_summary_from_cache(link)
            if cached:
                return cached
        
        if not text or len(text) < 100:
            return "Text too short to summarize."
        
        prompt = f"Summarize the following text in 3 bullet point lines in Korean:\n\n{text[:3000]}"
        summary = self.llm_manager.generate_response(prompt, model)
        
        # 2. Save Cache if link provided (Update if exists)
        if link and summary:
            db = NewsDatabase()
            db.save_summary_to_cache(link, summary, model)
            
        return summary

    def check_ollama_connection(self):
        return self.llm_manager.check_connection()

    def get_gpu_info(self):
        return self.llm_manager.get_gpu_info()
