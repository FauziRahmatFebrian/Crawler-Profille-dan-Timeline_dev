import os
import re
import json
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from transformers import pipeline
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import matplotlib.pyplot as plt

# Load environment variables
load_dotenv()
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL")
ELASTICSEARCH_USERNAME = os.getenv("ELASTICSEARCH_USERNAME")
ELASTICSEARCH_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
COMMENT_INDEX = "socmed-instagram-comments"

# Load zero-shot classification model
model = pipeline(
    "zero-shot-classification",
    model="joeddav/xlm-roberta-large-xnli"
)

# Initialize Gemini AI
genai.configure(api_key=GEMINI_API_KEY)

# Define possible topics for classification
TOPICS = [
    "Politik", "Ekonomi", "Pendidikan", "Hukum", "Sosial",
    "Teknologi", "Kesehatan", "Lingkungan", "Agama",
    "Transportasi", "Hiburan", "Olahraga", "Umum"
]

# Define keyword rules for each topic
RULES = {
    "Politik": ["politik", "presiden", "jokowi", "prabowo", "anies", "ganjar",
                "pilpres", "pemilu", "dpr", "kpk", "menteri", "koalisi", "partai",
                "korupsi", "kabinet", "istana", "politik uang", "caleg", "buzzer", "gubernur"],
    "Ekonomi": ["ekonomi", "uang", "harga", "mahal", "murah", "beli", "jual",
                "dagang", "bisnis", "investasi", "gaji", "bank", "inflasi", "krisis", "subsidi"],
    "Hukum": ["hukum", "penjara", "polisi", "pengadilan", "vonis", "kasus",
              "tersangka", "kejaksaan", "pasal", "penegakan hukum", "dana"],
    "Pendidikan": ["sekolah", "kuliah", "guru", "murid", "kampus",
                   "belajar", "ujian", "universitas", "mahasiswa"],
    "Lingkungan": ["banjir", "sampah", "iklim", "pohon", "alam",
                   "bencana", "hujan", "longsor"],
    "Teknologi": ["teknologi", "ai", "artificial", "robot", "internet",
                  "startup", "data", "gadget", "aplikasi", "hp"],
    "Kesehatan": ["sakit", "sehat", "vaksin", "covid", "rumah sakit",
                  "dokter", "virus", "obat", "imun"],
    "Agama": ["allah", "tuhan", "doa", "islam", "innalillahi", "masjid",
              "ibadah", "syukur", "shalat", "amin"],
    "Transportasi": ["mobil", "motor", "macet", "angkot", "jalan",
                     "bandara", "kereta", "pesawat", "transportasi"],
    "Hiburan": ["film", "artis", "musik", "lagu", "konser", "drama",
                "tiktok", "kpop", "hiburan"],
    "Olahraga": ["bola", "futsal", "timnas", "gol", "pemain", "pertandingan", "liga", "sport"],
    "Sosial": ["rakyat", "bantu", "donasi", "masyarakat", "sosial",
               "kemiskinan", "relawan", "pemerintah daerah"],
}

# Classify the topic of a given text
def classify_topic(text: str):
    text_low = text.lower()

    # Rule-based classification
    for topic, keywords in RULES.items():
        if any(re.search(rf"\b{kw}\b", text_low) for kw in keywords):
            return topic, 0.95

    # Zero-shot classification
    res = model(text, TOPICS)
    topic = res["labels"][0]
    conf = res["scores"][0]

    # If the topic is "Umum", replace it with the most relevant topic
    if topic == "Umum":
        # We select the topic with the highest confidence score that is not "Umum"
        highest_conf_topic = max(zip(res["labels"], res["scores"]), key=lambda x: x[1] if x[0] != "Umum" else -1)
        return highest_conf_topic[0], highest_conf_topic[1]

    # If it's not "Umum", return the topic and confidence score
    return topic, conf

# Update Elasticsearch with new classifications
def bulk_update(index, updates):
    if not updates:
        return
    payload = ""
    for doc_id, data in updates.items():
        payload += json.dumps({"update": {"_id": doc_id}}) + "\n"
        payload += json.dumps({"doc": {"topic.trans": data["topic"]}}) + "\n"  # Updated field name here

    res = requests.post(
        f"{ELASTICSEARCH_URL.rstrip('/')}/{index}/_bulk",
        auth=(ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD),
        headers={"Content-Type": "application/x-ndjson"},
        data=payload.encode("utf-8"),
        verify=False
    )

    if res.status_code == 200:
        print(f"{len(updates)} documents updated successfully")
    else:
        print(f"Error: {res.status_code} - {res.text[:200]}")

# Fetch all documents from Elasticsearch
def get_data_all(index):
    query = {
        "query": {
            "match_all": {}
        }
    }
    res = requests.post(
        f"{ELASTICSEARCH_URL.rstrip('/')}/{index}/_search",
        auth=(ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD),
        headers={"Content-Type": "application/json"},
        data=json.dumps(query),
        verify=False
    )

    if res.status_code == 200:
        return res.json()["hits"]["hits"]
    else:
        print(f"Error: {res.status_code} - {res.text[:200]}")
        return []

# Main processing function to classify topics and update Elasticsearch
def process_all():
    docs = get_data_all(COMMENT_INDEX)
    updates = {}

    # Run classification in parallel using 5 threads
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(classify_topic, doc["_source"]["text"]): doc["_id"]
            for doc in docs if doc["_source"].get("text")
        }

        for future in as_completed(futures):
            doc_id = futures[future]
            try:
                topic, conf = future.result()
                updates[doc_id] = {
                    "topic": topic,
                    "topic_confidence": float(conf),
                    "topic_processed_at": datetime.now(timezone.utc).isoformat()
                }
                print(f"{doc_id} → {topic} ({conf:.2f})")
            except Exception as e:
                print(f"Error in processing {doc_id}: {e}")

    # Bulk update Elasticsearch with the valid topics
    bulk_update(COMMENT_INDEX, updates)

    # Visualize the distribution of topics (excluding "Umum")
    print("\nGenerating barplot of topic distribution (excluding 'Umum')...")
    df = pd.DataFrame(updates).T
    if not df.empty:
        topic_counts = df["topic"].value_counts().sort_values(ascending=True)

        if not topic_counts.empty:
            plt.figure(figsize=(10, 6))
            topic_counts.plot(kind="barh", color="#3b82f6")
            plt.title("Topic Distribution After Classification (Excluding 'Umum')")
            plt.xlabel("Number of Comments")
            plt.ylabel("Topic")
            plt.tight_layout()

            os.makedirs("output", exist_ok=True)
            plt.savefig("output/topic_barplot.jpg", dpi=300)
            plt.show()
            print("Barplot saved as output/topic_barplot.jpg")
        else:
            print("No topics other than 'Umum'.")
    else:
        print("No data to visualize.")

if __name__ == "__main__":
    print("Starting topic classification process...")
    process_all()
    print("\nAll data processed successfully")
