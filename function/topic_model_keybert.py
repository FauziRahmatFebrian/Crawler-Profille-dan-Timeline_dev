import os
import re
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from sklearn.feature_extraction.text import TfidfVectorizer

# ============================================================
# STOPWORDS MANUAL (TANPA NLTK)
# ============================================================
STOPWORDS = {
    "yang", "untuk", "dengan", "dan", "di", "ke", "dari", "atau", "ini", "itu",
    "jadi", "karena", "pada", "ada", "saat", "jika", "dalam", "lebih", "agar",
    "juga", "tidak", "bukan", "kami", "kita", "mereka", "saya", "aku", "kamu",
    "sebuah", "seperti", "buat",
    "nih", "dong", "ya", "bang", "gue", "aja", "deh", "amp", "min", "yg", "lagi",
    "bgt", "bikin", "udah", "gua", "gw", "tuh", "kak", "admin", "om", "mbak",
    "bro", "sis",
    "https", "http"
}

# GENERATE WORD
def generate_topic_wordcloud_advanced(comments, output_path="output/topic_wordcloud.jpg", num_topics=None):
    """
    Membuat wordcloud dari daftar komentar menggunakan TF-IDF global.
    Fungsi menerima parameter num_topics untuk kompatibilitas namun
    tidak menggunakannya (karena ini single global wordcloud).

    Args:
        comments (list): daftar string komentar
        output_path (str): lokasi file hasil wordcloud
        num_topics (int|None): optional, hanya untuk kompatibilitas pemanggilan
    """

    # Pembersihan teks dasar
    def clean_text(text):
        if not isinstance(text, str):
            return ""

        text = text.lower()

        # Hilangkan URL
        text = re.sub(r"http\S+", "", text)

        # Hilangkan simbol
        text = re.sub(r"[^a-zA-Z\s]", " ", text)

        # Hilangkan spasi berlebihan
        text = re.sub(r"\s+", " ", text).strip()

        # Hilangkan stopwords & kata sangat pendek
        tokens = [w for w in text.split() if w not in STOPWORDS and len(w) > 1]

        return " ".join(tokens)

    # Bersihkan semua komentar

    cleaned_comments = [
        clean_text(c) for c in comments
        if isinstance(c, str) and len(c.strip()) > 0
    ]

    cleaned_comments = [c for c in cleaned_comments if len(c.split()) > 1]

    if not cleaned_comments:
        print("[WARNING] Tidak ada komentar valid setelah pembersihan.")
        return

    # ============================================================
    # Hitung TF-IDF global
    # ============================================================
    vectorizer = TfidfVectorizer(
        max_features=400,
        ngram_range=(1, 2)
    )

    X = vectorizer.fit_transform(cleaned_comments)

    tfidf_scores = X.toarray().sum(axis=0)
    feature_names = vectorizer.get_feature_names_out()

    freq_dict = {
        feature_names[i]: float(tfidf_scores[i])
        for i in range(len(feature_names))
    }

    # Hilangkan token umum jika masih muncul
    for bad in ["rt", "amp"]:
        freq_dict.pop(bad, None)

    # Ambil top 150 kata
    top_items = dict(
        sorted(freq_dict.items(), key=lambda x: x[1], reverse=True)[:150]
    )

    # ============================================================
    # Pastikan direktori output ada
    # ============================================================
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # ============================================================
    # Generate WordCloud
    # ============================================================
    wc = WordCloud(
        width=1200,
        height=500,
        background_color="black",
        colormap="plasma",
        prefer_horizontal=1.0,
        collocations=False,
        max_words=150
    ).generate_from_frequencies(top_items)

    plt.figure(figsize=(12, 6))
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.tight_layout(pad=0)
    plt.savefig(output_path, bbox_inches="tight", dpi=200)
    plt.close()

    print(f"[SUCCESS] WordCloud tersimpan di {output_path}")
