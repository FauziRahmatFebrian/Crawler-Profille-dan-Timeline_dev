import os
import matplotlib.pyplot as plt
from collections import Counter

def plot_sentiment_bar(comment_data, output_path="output/barplot/sentiment_barplot.png"):
    """
    Membuat barplot sentimen dari list komentar dan menyimpannya sebagai PNG.
    
    Parameters:
    - comment_data: list of dict, harus punya key 'sentiment'
    - output_path: lokasi untuk menyimpan hasil barplot
    """
    if not comment_data:
        print("[WARNING] Data komentar kosong, barplot tidak dibuat.")
        return None

    # Hitung jumlah masing-masing sentimen
    sentiments = [c.get("sentiment", "netral") for c in comment_data]
    sentiment_counts = Counter(sentiments)

    # Buat folder output jika belum ada
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Plot
    plt.figure(figsize=(6, 4))
    plt.bar(sentiment_counts.keys(), sentiment_counts.values())
    plt.title("Distribusi Sentimen Komentar")
    plt.xlabel("Sentimen")
    plt.ylabel("Jumlah Komentar")
    plt.tight_layout()

    # Simpan hasil plot
    plt.savefig(output_path, format="png", dpi=300)
    plt.close()

    print(f"[INFO] Barplot sentimen berhasil disimpan: {output_path}")
    return output_path
