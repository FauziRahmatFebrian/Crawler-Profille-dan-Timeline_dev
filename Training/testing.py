# ==============================================
# 🔧 Import Library
# ==============================================
from transformers import pipeline
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# ==============================================
# 🧾 Contoh Teks (bisa diganti dengan data kamu)
# ==============================================
text = """
Polri menangkap pelaku di Jakarta pada tahun 2025.
Indonesia hebat! Warga berharap harga turun di tahun 2024.
KPK bekerja sama dengan Polri dan DPR di Jakarta.
"""

# ==============================================
# 🧠 Named Entity Recognition (NER)
# ==============================================
ner = pipeline("ner", model="dslim/bert-base-NER", grouped_entities=True)

# Jalankan NER
results = ner(text)

# Ambil entitas yang dikenali
entities = [res["word"] for res in results]

# Gabungkan jadi satu string untuk WordCloud
ner_text = " ".join(entities)

# ==============================================
# ☁️ Generate WordCloud dari entitas NER
# ==============================================
wordcloud_ner = WordCloud(
    width=1000,
    height=500,
    background_color='black',
    colormap='spring',
    collocations=False
).generate(ner_text)

# ==============================================
# 🎨 Tampilkan WordCloud
# ==============================================
plt.figure(figsize=(12,6))
plt.imshow(wordcloud_ner, interpolation='bilinear')
plt.axis("off")
plt.title("Word Cloud Berdasarkan Hasil NER", fontsize=18)
plt.show()

# ==============================================
# 📊 (Opsional) Lihat hasil entitas NER di console
# ==============================================
print("\n===== Hasil Entitas NER =====")
for r in results:
    print(f"{r['word']:15} → {r['entity_group']}")
