import os
import re
import json
import time
import random
import logging
import requests
import pandas as pd
import contextlib
import sys
import pymysql
import torch
from datetime import datetime, timezone
from urllib.parse import quote
from dotenv import load_dotenv
from instagrapi import Client
from elasticsearch import Elasticsearch, helpers


# FUNCTION IMPORTS
from function.telegram import send_telegram_message
from function.sentiment import analyze_sentiment
from function.sentiment_plot import plot_sentiment_bar
from function.db import save_comment_to_db, save_post_to_db
from function.topic_model_keybert import generate_topic_wordcloud_advanced
from function.text_cleaner_ai import clean_text_ai, translate_to_indonesian
from function.ner_extractor import ner_extract_custom
import warnings
import matplotlib.pyplot as plt


# LOAD ENVIRONMENT
load_dotenv()

SESSIONID = os.getenv("IG_SESSIONID_PROFILLE")
MAX_POSTS = int(os.getenv("MAX_POSTS", 3))
MAX_COMMENTS = int(os.getenv("MAX_COMMENTS", 50))

# OUTPUT
OUTPUT_CSV = "output/vocabulary/vocabulary_profile.csv"
OUTPUT_JSON = "output/database/database_profile.json"
IMAGE_DIR = "downloaded_images"

# MYSQL CONFIG
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")

# ELASTICSEARCH CONFIG
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL")    
ELASTICSEARCH_USERNAME = os.getenv("ELASTICSEARCH_USERNAME")
ELASTICSEARCH_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD")
POST_INDEX = "socmed-instagram-posts"
COMMENT_INDEX = "socmed-instagram-comments"

# PROXY CONFIG
PROXY_USER = os.getenv("PROXY_USER_MAIN")
PROXY_PASS_RAW = os.getenv("PROXY_PASS_MAIN")
PROXY_IP = os.getenv("PROXY_IP_MAIN")
PROXY_PORT = os.getenv("PROXY_PORT_MAIN")

# FOLDER
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", message="Some weights of the model checkpoint at cahya/bert-base-indonesian-NER were not used")


# INITIALIZE ELASTICSEARCH CLIENT
def create_es_client():
    try:
        es_client = Elasticsearch(
            ELASTICSEARCH_URL,
            basic_auth=(ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD),
            verify_certs=False,
            timeout=60
        )
        if es_client.ping():
            print("[SUCCESS] Connected to Elasticsearch")
        else:
            print("[ERROR] Cannot ping Elasticsearch")
        return es_client
    except Exception as e:
        print("[ERROR] Failed to connect ES:", e)
        return None

es = create_es_client()

# PROXY
PROXY_URL = None
if PROXY_IP and PROXY_PORT:
    if PROXY_USER and PROXY_PASS_RAW:
        PROXY_PASS = quote(PROXY_PASS_RAW, safe="")
        PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_IP}:{PROXY_PORT}"
    else:
        PROXY_URL = f"http://{PROXY_IP}:{PROXY_PORT}"

logging.getLogger("instagrapi").setLevel(logging.ERROR)

@contextlib.contextmanager
def suppress_instagrapi_logs():
    with open(os.devnull, "w") as devnull:
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = devnull, devnull
        try:
            yield
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr


# AMBIL TARGET USERNAME (ENV → jika kosong → DB)
CRAWL_PROFILE_LIST = os.getenv("CRAWL_PROFILE_LIST", "").strip()
target_usernames = []

if CRAWL_PROFILE_LIST:
    print("[INFO] Menggunakan username dari ENV")
    target_usernames = [
        u.strip().replace("@", "")
        for u in CRAWL_PROFILE_LIST.split(",")
        if u.strip()
    ]

else:
    print("[INFO] ENV kosong → mengambil username dari database...")

    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()

        cursor.execute("""
            SELECT crawler_source 
            FROM ref_crawler_source 
            WHERE source = 'instagram'
            GROUP BY crawler_source
        """)
        result = cursor.fetchall()

        for row in result:
            name = row["crawler_source"].strip()
            if not name or "#" in name:
                continue
            if name.startswith("@"):
                name = name[1:]
            target_usernames.append(name)

        target_usernames = target_usernames[:5]

        if not target_usernames:
            msg = "[WARNING] Tidak ada akun Instagram di database!"
            print(msg)
            send_telegram_message(msg)
            exit()

    except Exception as e:
        print(f"[ERROR] Gagal ambil target dari database: {e}")
        send_telegram_message(f"[ERROR] Gagal ambil target dari database: {e}")
        exit()

print(f"[INFO] Total akun untuk crawling = {len(target_usernames)} → {target_usernames}")


#   LOOP
all_comments_global = []

for TARGET_USERNAME in target_usernames:
    print(f"\nCrawling akun: {TARGET_USERNAME}")

    cl = Client()

    def try_login(use_proxy=False):
        try:
            if use_proxy and PROXY_URL:
                cl.set_proxy(PROXY_URL)
                print(f"Proxy: {PROXY_URL}")
            else:
                cl.set_proxy(None)

            with suppress_instagrapi_logs():
                cl.login_by_sessionid(SESSIONID)

            print("Login berhasil")
            return True
        except Exception as e:
            print(f"Login gagal (proxy={use_proxy}): {e}")
            return False

    print("Login menggunakan proxy...")

    if not try_login(use_proxy=True):
        send_telegram_message("Login gagal (proxy).")
        continue

    # PROFIL
    try:
        with suppress_instagrapi_logs():
            user_info = cl.user_info_by_username(TARGET_USERNAME)
        print(f"[INFO] Profil {TARGET_USERNAME} berhasil diambil")
    except Exception as e:
        send_telegram_message(f"[ERROR] Profil gagal: {e}")
        continue

    profile_data = {
        "username": TARGET_USERNAME,
        "fullname": user_info.full_name,
        "bio": user_info.biography,
        "post_count": user_info.media_count,
        "followers": user_info.follower_count,
        "following": user_info.following_count,
    }

    # POSTINGAN
    try:
        with suppress_instagrapi_logs():
            medias = cl.user_medias_v1(user_info.pk, MAX_POSTS)
    except:
        with suppress_instagrapi_logs():
            medias = cl.user_medias(user_info.pk, MAX_POSTS)

    if not medias:
        send_telegram_message(f"Tidak ada postingan dari {TARGET_USERNAME}")
        continue

    elastic_posts = []
    elastic_comments = []

    # LOOP POST
    for i, media in enumerate(medias, start=1):

        current_url = f"https://www.instagram.com/p/{media.code}/"
        print(f"\n[INFO] Post {i}: {current_url}")

        caption = media.caption_text or ""
        hashtags = re.findall(r"#\w+", caption)
        likes = media.like_count
        comments_count = media.comment_count
        upload_time = media.taken_at.isoformat()

        original_token = clean_text_ai(caption)
        translated_full = translate_to_indonesian(caption) if caption else ""
        translated_token = clean_text_ai(translated_full)

        post_obj = {
            "id": str(media.pk),
            "url": current_url,
            "username": TARGET_USERNAME,
            "caption": caption,
            "token": original_token,
            "translated_caption_full": translated_full,
            "translated_caption_token": translated_token,
            "hashtags": hashtags,
            "likes": likes,
            "upload_time": upload_time,
            "comment_count": comments_count,
            "source": TARGET_USERNAME,
            "sentiment": analyze_sentiment(caption),
            "topic": "",
            "created_at": upload_time,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }

        elastic_posts.append(post_obj)
        try:
            with suppress_instagrapi_logs():
                comments = cl.media_comments(media.pk, amount=MAX_COMMENTS)

            for c in comments:

                original_token = clean_text_ai(c.text)
                translated_full = translate_to_indonesian(c.text)
                translated_token = clean_text_ai(translated_full)

                try:
                    ner_custom = ner_extract_custom(translated_token) if translated_token else {"person": [], "location": [], "organization": []}
                except:
                    ner_custom = {"person": [], "location": [], "organization": []}

                comment_obj = {
                    "id": str(c.pk),
                    "post_id": str(media.pk),
                    "post_url": current_url,
                    "sender": c.user.username,
                    "sender_fullname": getattr(c.user, "full_name", ""),
                    "text": c.text,
                    "token": original_token,
                    "translated_text": translated_full,
                    "token": translated_token,
                    "sentiment": analyze_sentiment(c.text),
                    "topic_trans": "",
                    "ner_custom": ner_extract_custom(translated_token),
                    "like_count": c.like_count,
                    "created_at": c.created_at_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z",
                    "source": TARGET_USERNAME,
                    "hashtags": "#papua",
                }

                elastic_comments.append(comment_obj)
                all_comments_global.append(comment_obj)
        except Exception as e:
            print("[WARNING] Komentar gagal:", e)

        time.sleep(random.uniform(2, 5))

    pd.DataFrame(elastic_comments).to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    final_data = {
        "profile": profile_data,
        "posts": elastic_posts,
        "comments": elastic_comments,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)

    print("[INFO] JSON Tersimpan")

    # SEND DATA KE ES
    def send_bulk_es(data_list, crawl_username, index_name):
        if not data_list:
            return

        actions = []
        for item in data_list:
            item["account_for_crawl"] = crawl_username
            actions.append({
                "_index": index_name,
                "_id": item["id"],
                "_source": item
            })

        try:
            helpers.bulk(es, actions, raise_on_error=False)
            print(f"[SUCCESS] {len(actions)} docs inserted ke → {index_name}")
        except Exception as e:
            print("[ERROR] Bulk insert failed:", e)

    # === PENEMPATAN YANG BENAR ===
    send_bulk_es(elastic_posts, TARGET_USERNAME, POST_INDEX)
    send_bulk_es(elastic_comments, TARGET_USERNAME, COMMENT_INDEX)

    # CREATE INDEX WITH MAPPING
    POST_MAPPING = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "url": {"type": "keyword"},
                "username": {"type": "keyword"},
                "caption": {"type": "text"},
                "translated_caption_full": {"type": "text"},
                "hashtags": {"type": "keyword"},
                "likes": {"type": "integer"},
                "comment_count": {"type": "integer"},
                "upload_time": {"type": "date"},
                "sentiment": {"type": "keyword"},
                "topic": {"type": "keyword"},
                "indexed_at": {"type": "date"},
                "account_for_crawl": {"type": "keyword"}
            }
        },
        "settings": {
            "index": {
                "max_result_window": 500000
            }
        }
    }

    COMMENT_MAPPING = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "post_id": {"type": "keyword"},
                "post_url": {"type": "keyword"},
                "sender": {"type": "keyword"},
                "text": {"type": "text"},
                "translated_text": {"type": "text"},
                "sentiment": {"type": "keyword"},
                "ner_custom": {"type": "object"},
                "like_count": {"type": "integer"},
                "created_at": {"type": "date"},
                "source": {"type": "keyword"},
                "account_for_crawl": {"type": "keyword"},
                "hashtags": {"type": "keyword"}
            }
        },
        "settings": {
            "index": {
                "max_result_window": 500000
            }
        }
    }


    def create_index_if_not_exist(index_name, mapping):
        try:
            if not es.indices.exists(index=index_name):
                es.indices.create(index=index_name, body=mapping)
                print(f"[SUCCESS] Index dibuat: {index_name}")
            else:
                print(f"[INFO] Index sudah ada: {index_name}")
        except Exception as e:
            print(f"[ERROR] Create index gagal: {e}")


    create_index_if_not_exist(POST_INDEX, POST_MAPPING)
    create_index_if_not_exist(COMMENT_INDEX, COMMENT_MAPPING)


    plot_sentiment_bar(elastic_comments, "output/sentimen_barplot.jpg")

    # TELEGRAM REPORT
    try:
        now = datetime.now().strftime("%d %B %Y • %H:%M:%S")
        header = f"<b>Laporan Crawler Instagram</b>\n<i>{now}</i>\n\n"

        if elastic_posts:
            lines = []
            for idx, p in enumerate(elastic_posts, 1):
                lines.append(
                    f"<b>{idx}. {p['username']}</b>\n"
                    f"<a href='{p['url']}'>Link Post</a>\n"
                    f"Komentar: {p['comment_count']}\n"
                    f"Likes: {p['likes']}\n"
                    f"Upload: {p['upload_time']}\n"
                )

            summary = (
                f"\n<b>Crawling Summary</b>\n"
                f"• Total Postingan: <b>{len(elastic_posts)}</b>\n"
                f"• Total Komentar: <b>{len(elastic_comments)}</b>\n"
            )

            send_telegram_message(header + "\n".join(lines) + summary, parse_mode="HTML")

    except Exception as e:
        print("[ERROR] Telegram Fail:", e)


# BARPLOT TOP 5 KOMENTAR
try:
    df_comments = pd.DataFrame(all_comments_global)
    if not df_comments.empty:
        counts = (
            df_comments.groupby("source")
            .size()
            .reset_index(name="total_comments")
            .sort_values("total_comments", ascending=False)
        )

        top5 = counts.head(5)
        plt.figure(figsize=(8, 5))
        plt.bar(top5["source"], top5["total_comments"])
        plt.xlabel("Username")
        plt.ylabel("Total Komentar")
        plt.title("Top 5 Akun dengan Komentar Terbanyak")
        plt.xticks(rotation=30, ha="right")
        out = "output/top5_comments_barplot.jpg"
        plt.tight_layout()
        plt.savefig(out, dpi=300)
        plt.close()

        print("[SUCCESS] Barplot disimpan:", out)

except Exception as e:
    print("[ERROR] Barplot gagal:", e)

