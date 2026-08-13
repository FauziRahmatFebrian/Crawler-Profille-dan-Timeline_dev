import os
import re
import json
import time
import tempfile
import random
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timezone
from dotenv import load_dotenv
from instagrapi import Client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pymysql
from function.telegram import send_telegram_message
from function.sentiment import analyze_sentiment
from function.sentiment_plot import plot_sentiment_bar
from function.text_cleaner_ai import clean_text_ai, translate_to_indonesian
from function.ner_extractor import ner_extract_custom

# ===================== LOAD ENV =====================
load_dotenv()

SESSIONID = os.getenv("IG_SESSIONID_MAIN")
DRIVER_PATH = os.getenv("DRIVER_PATH_local")
START_URL = os.getenv("START_URL")
MAX_COMMENTS = int(os.getenv("MAX_COMMENTS", 50))
MAX_POSTS = int(os.getenv("MAX_POSTS", 5))
OUTPUT_CSV = os.getenv("OUTPUT_VOCAB_CSV_post", "output_posts.csv")
OUTPUT_JSON = os.getenv("OUTPUT_JSON_post", "output_posts.json")
OUTPUT_VOCAB_CSV = os.getenv("OUTPUT_VOCAB_CSV", "vocab.csv")
IMAGE_DIR = os.getenv("IMAGE_DIR", "downloaded_images")
WORDCLOUD_PATH = os.getenv("WORDCLOUD_PATH_post", os.path.join(IMAGE_DIR, "output", "wordcloud_post.png"))
USERNAME_CRAWLING = os.getenv("USER", "unknown")
HASHTAG_SOURCE = os.getenv("HASTAG_URL") or os.getenv("HASTAG_URL".upper())  # keep old key if exists
PROXY_URL = os.getenv("PROXY_URL")
os.makedirs(os.path.dirname(WORDCLOUD_PATH), exist_ok=True)

# ===================== ELASTICSEARCH CONFIG =====================
ELASTICSEARCH_URL = os.getenv('ELASTICSEARCH_URL')
ELASTICSEARCH_USERNAME = os.getenv('ELASTICSEARCH_USERNAME')
ELASTICSEARCH_PASSWORD = os.getenv('ELASTICSEARCH_PASSWORD')
POST_INDEX = "socmed-instagram-posts"
COMMENT_INDEX = "socmed-instagram-comments"

# ===================== MYSQL CONFIG =====================
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")

# ===================== AMBIL DAFTAR HASHTAG =====================
hashtag_list = []
if HASHTAG_SOURCE:
    # split by comma, keep non-empty, strip spaces, ensure leading '#'
    raw = [t.strip() for t in HASHTAG_SOURCE.split(",")]
    parsed = []
    for t in raw:
        if not t:
            continue
        s = t
        # remove internal spaces (e.g. "# java" -> "#java")
        s = s.replace(" ", "")
        if not s.startswith("#"):
            s = "#" + s.lstrip("#")
        parsed.append(s.lower())
    if parsed:
        hashtag_list = parsed
        print(f"[INFO] Menggunakan hashtag dari ENV: {hashtag_list}")

# 2. Jika ENV kosong → mengambil dari DB
if not hashtag_list and MYSQL_HOST and MYSQL_USER and MYSQL_DB:
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        cursor = conn.cursor()

        query = """
            SELECT crawler_source 
            FROM ref_crawler_source 
            WHERE source = 'instagram' 
            AND crawler_source LIKE '#%' 
            GROUP BY crawler_source
        """
        cursor.execute(query)
        results = cursor.fetchall()

        for row in results:
            tag = row.get("crawler_source", "").strip()
            if tag:
                hashtag_list.append(tag.lower())

        if hashtag_list:
            print(f"[INFO] Ditemukan {len(hashtag_list)} hashtag dari DB: {hashtag_list[:5]}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"[ERROR] Gagal mengambil hashtag dari database: {e}")
        try:
            send_telegram_message(f"[ERROR] Gagal ambil hashtag dari MySQL: {e}")
        except Exception:
            pass

# 3. Jika ENV & DB kosong → fallback START_URL
if not hashtag_list and START_URL and "/tags/" in START_URL:
    try:
        candidate = START_URL.rstrip("/").split("/")[-1]
        if candidate:
            hashtag_list = [f"#{candidate.lower()}"]
            print(f"[INFO] Mengambil hashtag dari START_URL: {hashtag_list}")
    except Exception as e:
        print(f"[WARNING] Gagal parse START_URL: {e}")

# 4. Cek final
if not hashtag_list:
    print("[WARNING] Tidak ada hashtag ditemukan dari ENV/DB/START_URL")
    try:
        send_telegram_message("[WARNING] Tidak ada hashtag ditemukan.")
    except Exception:
        pass
else:
    print(f"[READY] Final hashtag list: {hashtag_list}")

# ===================== SETUP SELENIUM ============================
service = Service(DRIVER_PATH)
options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--disable-extensions")
options.add_argument("--disable-notifications")
options.add_argument("--disable-infobars")
options.add_argument("--log-level=3")
options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")

if PROXY_URL:
    options.add_argument(f'--proxy-server={PROXY_URL}')
    print(f"[INFO] Menggunakan proxy Selenium: {PROXY_URL}")

driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(30)

# ===================== LOGIN INSTAGRAM via instagrapi =====================
cl = Client()
if PROXY_URL:
    cl.set_proxy(PROXY_URL)
    print(f"[INFO] Proxy diatur untuk Instagrapi: {PROXY_URL}")

try:
    cl.login_by_sessionid(SESSIONID)
    # juga set cookie di selenium agar tampak login
    driver.get("https://www.instagram.com")
    time.sleep(3)
    driver.add_cookie({"name": "sessionid", "value": SESSIONID, "domain": ".instagram.com"})
    driver.refresh()
    time.sleep(2)
    print("[INFO] Instagrapi sessionid login berhasil.")
except Exception as e:
    print(f"[ERROR] Gagal login Instagrapi dengan sessionid: {e}")
    # tetap lanjutkan; beberapa fungsi akan gagal jika tidak login

# ===================== PREPARE GLOBAL VARS =====================
post_count = 0
report_data = []
total_comments = 0
all_post_data = []
comment_data_all = []
all_comments_text = []
start_total = time.time()
hashtag_summary = {}

# ===================== HELPER: SAFE NER CALL =====================
def safe_ner(text):
    try:
        return ner_extract_custom(text) or {"person": [], "location": [], "organization": []}
    except Exception:
        return {"person": [], "location": [], "organization": []}

# ===================== HELPER: SEND TO ELASTICSEARCH (IMPROVED) ====
def send_to_elasticsearch(data_list, crawl_username, index_name):
    try:
        if not data_list:
            print(f"[WARNING] Tidak ada data untuk dikirim ke index '{index_name}'.")
            return

        # build bulk ndjson
        request_body = ""
        for d in data_list:
            data_id = str(d.get("id") or d.get("pk") or "")
            if not data_id:
                data_id = f"gen-{int(time.time()*1000)}-{random.randint(1,9999)}"
            # add metadata fields
            d["account_for_crawl"] = crawl_username
            d["indexed_at"] = datetime.now(timezone.utc).isoformat()
            request_body += json.dumps({"index": {"_id": data_id}}) + "\n"
            # ensure serializable
            request_body += json.dumps(d, ensure_ascii=False, default=str) + "\n"

        res = requests.post(
            f"{ELASTICSEARCH_URL.rstrip('/')}/{index_name}/_bulk",
            data=request_body.encode("utf-8"),
            auth=(ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD) if ELASTICSEARCH_USERNAME else None,
            headers={"Content-Type": "application/x-ndjson"},
            timeout=60
        )

        if res is None:
            print(f"[ERROR] Tidak menerima response dari Elasticsearch untuk index {index_name}.")
            return

        # coba parse json response untuk deteksi error per-item
        try:
            rj = res.json()
        except Exception:
            print(f"[ERROR] Tidak dapat parse response ES: {res.status_code} - {res.text[:1000]}")
            return

        if rj.get("errors"):
            print(f"[ERROR] Bulk insert returned errors for index {index_name}. Inspecting items...")
            # print up to first 10 item errors
            err_count = 0
            for item in rj.get("items", []):
                op = list(item.keys())[0]
                info = item[op]
                if info.get("error"):
                    err_count += 1
                    print(json.dumps(info.get("error"), indent=2, ensure_ascii=False))
                    if err_count >= 10:
                        break
            print(f"[WARNING] Total errors in bulk: {err_count}")
        else:
            took = rj.get("took")
            items = len(rj.get("items", []))
            print(f"[SUCCESS] Data berhasil dikirim ke {index_name} ✅ (took={took}ms, items={items})")

    except Exception as e:
        print(f"[ERROR] Exception saat kirim ke {index_name}: {e}")

# ===================== LOOP UNTUK SETIAP HASHTAG =====================
for tag in hashtag_list:
    current_hashtag = tag  # use local var, do not overwrite global env var
    tag_no_hash = current_hashtag.lstrip("#")
    current_start_url = f"https://www.instagram.com/explore/tags/{tag_no_hash}/"

    print(f"\n[START] Crawling target: {current_hashtag} -> {current_start_url}")
    hashtag_comment_count = 0

    try:
        driver.get(current_start_url)
        time.sleep(4)
    except Exception as e:
        print(f"[WARNING] Gagal buka {current_start_url}: {e}")
        continue

    post_count = 0

    while post_count < MAX_POSTS:
        start_post = time.time()
        try:
            # klik postingan pertama (hanya saat post_count == 0)
            if post_count == 0:
                try:
                    first_post = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH, '//article//a'))
                    )
                    driver.execute_script("arguments[0].click();", first_post)
                except Exception:
                    # fallback: cari img clickable
                    first_post = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH, '//div[contains(@class,"_aagv")]/img | //article//a'))
                    )
                    driver.execute_script("arguments[0].click();", first_post)

                time.sleep(2)

            # Ambil URL/current_url
            try:
                current_url = driver.current_url
            except Exception:
                current_url = ""
            print(f"[INFO] Post {post_count+1}: {current_url}")

            # Ambil media_pk via instagrapi
            try:
                media_pk = cl.media_pk_from_url(current_url) if current_url else None
            except Exception:
                media_pk = None

            # Ambil caption via selenium (UI) sebagai fallback
            try:
                caption_el = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH,
                        "//div[@role='dialog']//div[contains(@class,'C4VMK')]/span | //article//h1 | //div[@class='_a9zs']"))
                )
                caption = caption_el.text or ""
            except Exception:
                caption = ""

            # Ambil hashtags dari caption
            hashtags = re.findall(r'#\w+', caption)

            # ===================== POST DATA (sesuai struktur script yang berhasil) =====================
            try:
                if media_pk:
                    try:
                        # ambil media info via instagrapi (dict)
                        media_info = cl.media_info(media_pk).dict()
                    except Exception:
                        media_info = {}

                    post_obj = {
                        "id": str(media_pk),
                        "url": current_url,
                        "caption": caption or media_info.get("caption", ""),
                        "token": clean_text_ai(caption or media_info.get("caption", "")),
                        "translated_caption_full": translate_to_indonesian(caption or media_info.get("caption", "")),
                        "translated_caption_token": clean_text_ai(translate_to_indonesian(caption or media_info.get("caption", ""))) if (caption or media_info.get("caption", "")) else "",
                        "hashtags": hashtags,
                        "likes": media_info.get("like_count") or 0,
                        "upload_time": (media_info.get("taken_at").isoformat() if hasattr(media_info.get("taken_at"), "isoformat") else media_info.get("taken_at")) if media_info.get("taken_at") else None,
                        "comment_count": media_info.get("comment_count") or 0,
                        "media_type": media_info.get("media_type"),
                        "thumbnail_url": media_info.get("thumbnail_url") or media_info.get("preview_url"),
                        "username": media_info.get("user", {}).get("username") if isinstance(media_info.get("user"), dict) else None,
                        "source": current_hashtag,
                        "sentiment": analyze_sentiment(caption or media_info.get("caption", "")),
                        "topic": "",
                        "created_at": (media_info.get("taken_at").isoformat() if hasattr(media_info.get("taken_at"), "isoformat") else media_info.get("taken_at")) if media_info.get("taken_at") else None,
                        "indexed_at": datetime.now(timezone.utc).isoformat(),
                    }

                    all_post_data.append(post_obj)
                    print(f"[INFO] Post data ditambahkan untuk media_pk: {media_pk}")
                else:
                    print(f"[WARNING] media_pk tidak ditemukan untuk URL: {current_url}")
            except Exception as e:
                print(f"[WARNING] Gagal mengambil data post: {e}")

            # ===================== KOMENTAR (disamakan dengan script yang berhasil) =====================
            comment_data = []
            try:
                if media_pk:
                    comments = cl.media_comments(media_pk, amount=MAX_COMMENTS)
                else:
                    comments = []

                for c in comments:
                    original_text = c.text or ""
                    translated_full = translate_to_indonesian(original_text) if original_text else ""
                    original_token = clean_text_ai(original_text)
                    translated_token = clean_text_ai(translated_full) if translated_full else ""

                    ner_custom = safe_ner(translated_token) if translated_token else {"person": [], "location": [], "organization": []}
                    sentiment = analyze_sentiment(original_text)

                    comment_obj = {
                        "id": str(getattr(c, "pk", "") or ""),
                        "post_id": str(media_pk) if media_pk else None,
                        "post_url": current_url,
                        "sender": getattr(getattr(c, "user", None), "username", ""),
                        "sender_fullname": getattr(getattr(c, "user", None), "full_name", "") or "",
                        "text": original_text,
                        "token": original_token,
                        "translated_text": translated_full,
                        "translated_text_token": translated_token,
                        "sentiment": sentiment,
                        "topic": "",
                        "topic.trans": "",
                        "ner_custom": ner_custom,
                        "likes": getattr(c, "like_count", 0) or 0,
                        "created_at": (getattr(c, "created_at_utc", None).isoformat() if getattr(c, "created_at_utc", None) else datetime.now(timezone.utc).isoformat()),
                        "source": current_hashtag,
                        "hashtags": "#papua",
                    }

                    comment_data.append(comment_obj)
                    all_comments_text.append(original_text)

                comment_data_all.extend(comment_data)
                total_comments += len(comment_data)
                hashtag_comment_count += len(comment_data)

                print(f"[INFO] {len(comment_data)} komentar diambil untuk post {post_count+1}")

            except Exception as e:
                print(f"[WARNING] Gagal ambil komentar: {e}")

            post_count += 1

            # coba klik next post (arrow). various selectors for resiliency
            # NEXT POST (bukan next slide)
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ARROW_RIGHT)   # ini benar untuk next POST
                time.sleep(2)
            except Exception:
                pass


        except Exception as e:
            print(f"[ERROR] Gagal mengambil postingan ke-{post_count+1}: {e}")
            post_count += 1
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ARROW_RIGHT)
                time.sleep(1)
            except Exception:
                pass
            continue

    hashtag_summary[current_hashtag] = hashtag_comment_count
    print(f"[DONE] Total komentar untuk {current_hashtag}: {hashtag_comment_count}")

# tutup selenium
try:
    driver.quit()
except Exception:
    pass

elapsed_total = time.time() - start_total

# ===================== SIMPAN DATA KE FILE =====================
try:
    with open(OUTPUT_JSON, 'w', encoding="utf-8") as f:
        json.dump(all_post_data, f, indent=4, ensure_ascii=False)
    print(f"[INFO] Saved posts JSON to {OUTPUT_JSON}")
except Exception as e:
    print(f"[WARNING] Gagal simpan JSON: {e}")

# ===================== VISUALISASI BARPLOT HASHTAG =====================
try:
    if hashtag_summary:
        df_summary = pd.DataFrame(list(hashtag_summary.items()), columns=["hashtag", "total_comments"])
        df_summary = df_summary.sort_values(by="total_comments", ascending=False)

        plt.figure(figsize=(10, 6))
        plt.bar(df_summary["hashtag"], df_summary["total_comments"])
        plt.xticks(rotation=45, ha="right")
        plt.title("Jumlah Komentar per Hashtag")
        plt.xlabel("Hashtag")
        plt.ylabel("Total Komentar")
        plt.tight_layout()
        plt.show()

        print("[SUCCESS] Barplot hashtag berhasil ditampilkan.")
    else:
        print("[INFO] Tidak ada data hashtag untuk divisualisasi.")
except Exception as e:
    print(f"[ERROR] Gagal membuat barplot: {e}")

# ===================== KIRIM KE ELASTICSEARCH =====================
send_to_elasticsearch(all_post_data, USERNAME_CRAWLING, POST_INDEX)
send_to_elasticsearch(comment_data_all, USERNAME_CRAWLING, COMMENT_INDEX)

# ===================== KIRIM LAPORAN TELEGRAM =====================
try:
    if hashtag_summary:
        summary_text = "📊 Jumlah Komentar per Hashtag:\n\n"
        for h, c in hashtag_summary.items():
            summary_text += f"{h}: {c} komentar\n"
        summary_text += f"\nTotal waktu crawling: {int(elapsed_total//60)}m {int(elapsed_total%60)}s"
        send_telegram_message(summary_text)
    else:
        send_telegram_message("Tidak ada komentar yang berhasil diambil.")
except Exception:
    print("[INFO] Telegram message sent or failed silently.")

print("[FINISH] Proses crawling selesai.")
