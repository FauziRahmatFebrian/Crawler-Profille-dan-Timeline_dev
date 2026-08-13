# Instagram Crawler & Analisis Sentimen

Crawler Instagram untuk mengumpulkan postingan dan komentar berdasarkan **hashtag** maupun **profil/username**, lalu memprosesnya dengan pipeline NLP bahasa Indonesia:

- **Pembersihan & normalisasi teks** — slang, stopword, stemming, emoji, terjemahan ke Bahasa Indonesia
- **Analisis sentimen** — model `w11wo/indonesian-roberta-base-sentiment-classifier` (positif / negatif / netral)
- **NER (Named Entity Recognition)** — model `cahya/bert-base-indonesian-NER` + kamus nama & tempat lokal
- **Klasifikasi topik** — rules + zero-shot (`joeddav/xlm-roberta-large-xnli`) + Gemini
- **Wordcloud & barplot** — visualisasi topik, sentimen, dan tren

Data hasil crawl disimpan ke **Elasticsearch**, **MySQL**, dan file lokal (`output/`, `reports/`), serta dikirim sebagai laporan ke **Telegram**.

---

## Struktur Proyek

```
crawler-instagram-dev/
├── .env.example            # Template variabel environment
├── utils.py                # Util pembersih emoji
├── function/
│   ├── db.py               # Koneksi & simpan ke MySQL
│   ├── telegram.py         # Kirim laporan ke Telegram
│   ├── sentiment.py        # Analisis sentimen (RoBERTa Indo)
│   ├── sentiment_plot.py   # Barplot sentimen
│   ├── text_cleaner_ai.py  # Cleaning + stemming + terjemahan
│   ├── ner_extractor.py    # NER BERT + kamus nama/tempat
│   ├── stopword.py         # Daftar stopword Bahasa Indonesia
│   ├── topic_model_keybert.py  # Wordcloud TF-IDF
│   ├── top5_barplot.py     # Barplot top 5 akun
│   └── user_agents.py      # Rotasi user-agent
├── Training/
│   ├── hastag.py           # Crawler berdasarkan hashtag
│   ├── profille.py         # Crawler berdasarkan profil
│   ├── trending.py         # Discovery hashtag trending
│   ├── topic_clasification.py  # Klasifikasi topik komentar
│   └── dashboard_instagram.py  # Dashboard Streamlit
├── chromedriver*/          # ChromeDriver (Windows / Linux)
├── data/                   # Data mentah hasil crawl
├── output/                 # Output olahan (CSV, JSON, plot)
├── reports/                # Laporan
└── logs/                   # Log crawling
```

---

## Prasyarat

- Python 3.9+
- Chrome/Chromium + [ChromeDriver](https://chromedriver.chromium.org/) (sesuai versi Chrome kamu)
- Akses ke salah satu: **Elasticsearch**, **MySQL**, atau keduanya
- Cookie `sessionid` Instagram (akun aktif — gunakan dengan bijak dan patuhi ToS Instagram)
- *(Opsional)* Token Bot Telegram, API key Gemini

---

## Instalasi

```bash
# 1. Clone / masuk ke direktori proyek
cd crawler-instagram-dev

# 2. Buat virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Siapkan environment
cp .env.example .env            # Linux/macOS
copy .env.example .env          # Windows
```

> Jika `requirements.txt` belum tersedia, install secara manual:
> `pip install instagrapi selenium pymysql elasticsearch python-dotenv pandas matplotlib transformers torch google-generativeai deep-translator Sastrawi emoji streamlit wordcloud scikit-learn`

---

## Konfigurasi (.env)

Salin `.env.example` menjadi `.env` lalu isi sesuai kebutuhan. Rincian semua variabel ada di dalam file tersebut. Yang paling penting:

| Variabel | Fungsi |
|---|---|
| `IG_SESSIONID_MAIN` / `IG_SESSIONID_PROFILLE` / `IG_SESSIONID` | Cookie `sessionid` Instagram untuk masing-masing crawler |
| `DRIVER_PATH_local` | Path ChromeDriver (dipakai `hastag.py`) |
| `HASTAG_URL` / `START_URL` / `CRAWL_PROFILE_LIST` | Sumber target crawl (hashtag / profil) |
| `MAX_POSTS`, `MAX_COMMENTS` | Batas jumlah post & komentar |
| `ELASTICSEARCH_URL/USERNAME/PASSWORD` | Penyimpanan ke Elasticsearch |
| `MYSQL_HOST_masuk`, `MYSQL_USER_masuk`, dll. | Koneksi MySQL (modul `db.py`) |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | Notifikasi laporan ke Telegram |
| `GEMINI_API_KEY` | Klasifikasi topik dengan Gemini |

---

## Cara Menjalankan

### 1. Crawler Hashtag — `Training/hastag.py`

Mengambil postingan + komentar dari halaman tagar Instagram (Selenium + instagrapi).

```bash
python Training/hastag.py
```

Sumber hashtag (prioritas): `HASTAG_URL` → tabel `ref_crawler_source` di MySQL → `START_URL`.
Hasil: JSON/CSV lokal, dikirim ke Elasticsearch (`socmed-instagram-posts`, `socmed-instagram-comments`), plus laporan Telegram.

### 2. Crawler Profil — `Training/profille.py`

Mengambil profil, postingan, dan komentar dari akun tertentu (instagrapi).

```bash
python Training/profille.py
```

Sumber akun: `CRAWL_PROFILE_LIST` (dipisah koma) → jika kosong, dari tabel `ref_crawler_source`.
Hasil: `output/database/database_profile.json`, `output/vocabulary/vocabulary_profile.csv`, data ke Elasticsearch, barplot sentimen, laporan Telegram.

### 3. Trending Hashtag — `Training/trending.py`

Menemukan hashtag yang sedang tren secara otomatis tanpa daftar awal.

```bash
python Training/trending.py
```

Membutuhkan `IG_SESSIONID` saja. Output berupa daftar trending hashtag di terminal.

### 4. Klasifikasi Topik — `Training/topic_clasification.py`

Mengklasifikasikan semua komentar yang sudah ada di Elasticsearch ke 13 topik (Politik, Ekonomi, dll.) lalu meng-update field `topic.trans`.

```bash
python Training/topic_clasification.py
```

Membutuhkan `ELASTICSEARCH_*` dan `GEMINI_API_KEY`. Model zero-shot `xlm-roberta` diunduh otomatis saat pertama kali dijalankan.

### 5. Dashboard — `Training/dashboard_instagram.py`

Dashboard Streamlit yang membaca komentar dari Elasticsearch.

```bash
streamlit run Training/dashboard_instagram.py
```

---

## Alur Data

```
Instagram (hashtag / profil)
        │
        ▼
  hastag.py / profille.py ──► JSON/CSV (output/, data/)
        │
        ├──► Elasticsearch (socmed-instagram-posts, socmed-instagram-comments)
        ├──► MySQL (comments, posts)
        └──► Telegram (laporan ringkas)

Elasticsearch ──► topic_clasification.py ──► update topic.trans
Elasticsearch ──► dashboard_instagram.py  ──► dashboard Streamlit
```

---

## Troubleshooting

- **`IG_SESSIONID` tidak ditemukan / login gagal** — pastikan cookie `sessionid` masih valid (tidak expired). Ambil ulang dari browser.
- **ChromeDriver error** — samakan versi ChromeDriver dengan versi Chrome, lalu perbaiki `DRIVER_PATH_local` di `.env`.
- **Rate limit / login check dari Instagram** — jangan jalankan terlalu sering; gunakan proxy (`PROXY_*`) jika tersedia.
- **Model download lama** — model HuggingFace (BERT NER, RoBERTa sentimen, XLM-R) diunduh otomatis saat pertama kali dipakai.

---

## Disclaimer

Proyek ini untuk keperluan **analisis data / riset**. Crawling otomatis dapat melanggar [Terms of Service Instagram](https://help.instagram.com/581066165581870) — gunakan dengan tanggung jawab, hormati batas rate, dan jangan memakai data untuk tujuan yang melanggar privasi.
