import pymysql
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MYSQL CONFIG
MYSQL_HOST = os.getenv("MYSQL_HOST_masuk")
MYSQL_USER = os.getenv("MYSQL_USER_masuk")
MYSQL_PASSWORD = os.getenv("MYSQL_PASS_masuk")
MYSQL_DB = os.getenv("MYSQL_DB_masuk")

# Fungsi untuk membuat koneksi ke MySQL
def connect_to_mysql():
    try:
        connection = pymysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor
        )
        print(f"[SUCCESS] Connected to MySQL at {MYSQL_HOST}")
        return connection
    except pymysql.MySQLError as e:
        print(f"[ERROR] MySQL Connection Error: {e}")
        return None

# Fungsi untuk menyimpan komentar ke MySQL
def save_comment_to_db(comment_obj):
    connection = connect_to_mysql()
    if not connection:
        print("[ERROR] Tidak bisa terhubung ke database!")
        return

    try:
        with connection.cursor() as cursor:
            # Query SQL untuk menyimpan komentar
            insert_query = """
                INSERT INTO comments (id, post_id, post_url, sender, sender_fullname, text, token, translated_text, sentiment, topic_trans, ner_custom, like_count, created_at, source, hashtags)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                comment_obj['id'],
                comment_obj['post_id'],
                comment_obj['post_url'],
                comment_obj['sender'],
                comment_obj['sender_fullname'],
                comment_obj['text'],
                comment_obj['token'],
                comment_obj['translated_text'],
                comment_obj['sentiment'],
                comment_obj['topic_trans'],
                json.dumps(comment_obj['ner_custom']),  # Convert dictionary to JSON string
                comment_obj['like_count'],
                comment_obj['created_at'],
                comment_obj['source'],
                comment_obj['hashtags']
            ))

            connection.commit()
            print(f"[INFO] Data komentar dengan ID {comment_obj['id']} berhasil disimpan.")
            print(f"[INFO] Last Inserted ID: {cursor.lastrowid}")  # Log ID terakhir yang disimpan

    except pymysql.MySQLError as e:
        print(f"[ERROR] Gagal menyimpan komentar: {e}")

    finally:
        connection.close()

# Fungsi untuk menyimpan postingan ke MySQL
def save_post_to_db(post_obj):
    connection = connect_to_mysql()
    if not connection:
        print("[ERROR] Tidak bisa terhubung ke database!")
        return

    try:
        with connection.cursor() as cursor:
            # Query SQL untuk menyimpan postingan
            insert_query = """
                INSERT INTO posts (id, url, username, caption, token, translated_caption_full, translated_caption_token, hashtags, likes, upload_time, comment_count, source, sentiment, topic, created_at, indexed_at, account_for_crawl)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                post_obj['id'],
                post_obj['url'],
                post_obj['username'],
                post_obj['caption'],
                post_obj['token'],
                post_obj['translated_caption_full'],
                post_obj['translated_caption_token'],
                post_obj['hashtags'],
                post_obj['likes'],
                post_obj['upload_time'],
                post_obj['comment_count'],
                post_obj['source'],
                post_obj['sentiment'],
                post_obj['topic'],
                post_obj['created_at'],
                post_obj['indexed_at'],
                post_obj['account_for_crawl']
            ))

            connection.commit()
            print(f"[INFO] Data postingan dengan ID {post_obj['id']} berhasil disimpan.")
            print(f"[INFO] Last Inserted ID: {cursor.lastrowid}")  # Log ID terakhir yang disimpan

    except pymysql.MySQLError as e:
        print(f"[ERROR] Gagal menyimpan postingan: {e}")

    finally:
        connection.close()
