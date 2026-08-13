import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message, parse_mode=None):
    """
    Kirim pesan ke Telegram menggunakan BOT API.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("[INFO] Telegram message sent")
    except requests.exceptions.RequestException as e:
        print(f"[WARNING] Telegram message failed: {e}")
