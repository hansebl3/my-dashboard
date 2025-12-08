import mysql.connector
import json
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def setup_database():
    config = load_config()
    db_config = config.get('news_db')
    
    if not db_config:
        logger.error("DB Config not found in config.json")
        return

    # Connect to MySQL server (without specifying DB first to create it)
    try:
        conn = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password']
        )
        cursor = conn.cursor()
        
        # Create Database if not exists
        db_name = db_config['database']
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        logger.info(f"Database '{db_name}' check/creation completed.")
        
        # Connect to the specific database
        conn.database = db_name
        
        # Create Table
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
        logger.info("Table 'tb_news' check/creation completed.")
        
        cursor.close()
        conn.close()
        logger.info("Database setup finished successfully.")
        
    except mysql.connector.Error as err:
        logger.error(f"Error: {err}")

if __name__ == "__main__":
    setup_database()
