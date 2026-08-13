import os
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASS = os.getenv("MYSQL_PASS")
MYSQL_DB = os.getenv("MYSQL_DB")

# MYSQL CONNECTION
def get_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASS,
        database=MYSQL_DB
    )

def execute_query(query, params=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        conn.commit()
        return cursor
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] MySQL query gagal: {e}")
    finally:
        cursor.close()
        conn.close()

def insert_post_to_db(post):
    """
    Insert post dan comment ke database.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        try:
            upload_time = datetime.fromisoformat(post['upload_time'].replace("Z", "+00:00"))
        except:
            upload_time = None

        cursor.execute("""
            INSERT IGNORE INTO posts (url, username, caption, likes, upload_time)
            VALUES (%s, %s, %s, %s, %s)
        """, (post['url'], post['username'], post['caption'], post['likes'], upload_time))

        for c in post.get("comments", []):
            try:
                created_at = datetime.fromisoformat(c['created_at'].replace("Z", "+00:00"))
            except:
                created_at = None
            cursor.execute("""
                INSERT INTO comments (post_url, username, text, likes, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (c['post_url'], c['username'], c['text'], c['likes'], created_at))

        conn.commit()
        print("[INFO] Data berhasil disimpan ke MySQL")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Gagal simpan data: {e}")
    finally:
        cursor.close()
        conn.close()