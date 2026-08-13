# function/top5_barplot.py
import matplotlib.pyplot as plt

def plot_top_words(counter, output_path, top_n=5):
    """Buat barplot top N kata dan simpan ke file"""
    top_words = counter.most_common(top_n)
    if not top_words:
        print("[WARNING] Tidak ada kata untuk dibuat barplot.")
        return

    words, counts = zip(*top_words)

    plt.figure(figsize=(8, 5))
    plt.bar(words, counts)
    plt.title(f"Top {top_n} Kata Terbanyak", fontsize=14)
    plt.ylabel("Frekuensi")
    plt.xlabel("Kata")
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"[INFO] Barplot Top {top_n} Kata disimpan: {output_path}")
