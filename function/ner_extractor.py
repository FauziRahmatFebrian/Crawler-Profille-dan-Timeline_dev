import torch
import os
from transformers import AutoTokenizer, AutoModelForTokenClassification
import warnings

# =====================================================
# NER MODEL CONFIGURATION
# =====================================================

NER_MODEL = "cahya/bert-base-indonesian-NER"

# Menonaktifkan peringatan terkait bobot yang tidak digunakan
warnings.filterwarnings("ignore", message="Some weights of the model checkpoint at cahya/bert-base-indonesian-NER were not used")

# Load model
ner_tokenizer = AutoTokenizer.from_pretrained(NER_MODEL)
ner_model = AutoModelForTokenClassification.from_pretrained(NER_MODEL)
id2label = ner_model.config.id2label

label_map = {
    "PER": "person",
    "LOC": "location",
    "ORG": "organization",
}

# =====================================================
# LOAD NAMA ORANG (TXT)
# =====================================================

def load_nama_orang(path="function/NER/nama.txt"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(line.strip().lower() for line in f if line.strip())
    except:
        print("[WARNING] nama.txt tidak ditemukan")
        return set()

custom_nama_orang = load_nama_orang()

# =====================================================
# LOAD TEMPAT (TXT) - From multiple files
# =====================================================

def load_tempat_txt(folder="function/NER/nama_tempat"):
    tempat_set = set()
    files = [
        "daerah.txt",
        "provinsi.txt",
        "kecamatan.txt",
        "kelurahan.txt"
    ]

    for file in files:
        full_path = os.path.join(folder, file)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                for line in f:
                    name = line.strip().lower()  # Normalisasi ke lowercase
                    if name:
                        tempat_set.add(name)

        except Exception as e:
            print(f"[WARNING] Gagal load {file}: {e}")

    return tempat_set

custom_tempat = load_tempat_txt()

# =====================================================
# MAIN NER FUNCTION
# =====================================================

def ner_extract_custom(text):
    output = {
        "person": [],
        "location": [],
        "organization": []
    }

    # --- 1. BERT NER ---
    encoded = ner_tokenizer(text, return_tensors="pt", truncation=True, max_length=512)

    with torch.no_grad():
        logits = ner_model(**encoded).logits

    preds = logits.argmax(dim=-1).squeeze().tolist()
    tokens = ner_tokenizer.convert_ids_to_tokens(encoded["input_ids"].squeeze())

    # Menggabungkan token yang terpisah
    words = []
    current_word = []
    for tok, pred in zip(tokens, preds):
        label = id2label[pred]
        if label == "O":  # Tidak perlu diproses jika labelnya O (Other)
            if current_word:
                words.append("".join(current_word))  # Gabungkan token yang terpisah
                current_word = []
            continue
        
        ent = label.split("-")[-1]
        if ent in label_map:
            current_word.append(tok.replace("##", "").lower())  # Gabungkan token berturut-turut

    if current_word:
        words.append("".join(current_word))  # Gabungkan kata terakhir yang terdeteksi

    # Menambahkan hasil NER yang sudah digabungkan ke dalam output
    for word in words:
        if word in custom_nama_orang:
            output["person"].append(word)
        elif word in custom_tempat:
            output["location"].append(word)
        else:
            output["organization"].append(word)

    # --- 2. Nama orang TXT ---
    words = text.lower().split()
    output["person"].extend([w for w in words if w in custom_nama_orang])

    # --- 3. Tempat TXT --- (Improved location handling)
    t_low = text.lower()
    for tempat in custom_tempat:
        if tempat in t_low and len(tempat.split()) > 1:  # Menangani multi-kata lokasi
            output["location"].append(tempat)

    # --- 4. Filter untuk hanya lokasi yang valid ---
    output["location"] = list(set(output["location"]))  # Unik (remove duplicates)

    # --- Filter hanya entitas yang valid dalam custom_nama_orang dan custom_tempat ---
    output["person"] = list(set([p for p in output["person"] if p in custom_nama_orang]))  # Unik dan valid
    output["location"] = list(set(output["location"]))  # Unique (remove duplicates)

    # --- Pastikan tidak ada duplikasi dalam output ---
    output["person"] = list(dict.fromkeys(output["person"]))  # Menghapus duplikasi pada 'person'
    output["location"] = list(dict.fromkeys(output["location"]))  # Menghapus duplikasi pada 'location'

    # --- 5. Menghindari duplikasi entitas pada lokasi dan organisasi ---
    output["organization"] = list(set(output["organization"]))  # Menghapus duplikasi pada 'organization'

    return output

# Contoh pemanggilan
text = "Budi pergi ke Jakarta untuk menghadiri acara di Universitas Indonesia. Sementara itu, Siti berada di Bandung."
result = ner_extract_custom(text)

print(result)
