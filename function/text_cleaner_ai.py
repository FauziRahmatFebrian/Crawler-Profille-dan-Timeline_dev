import re
import emoji
from deep_translator import GoogleTranslator
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from function.stopword import get_custom_stopwords

# Stemmer & stopwords
factory = StemmerFactory()
stemmer = factory.create_stemmer()
stopwords = get_custom_stopwords()

# Kamus slang Indonesia
slang_dict = {
    "gpp": "tidak apa apa",
    "ga": "tidak",
    "nggak": "tidak",
    "gak": "tidak",
    "jakbar": "jakarta barat",
    "jaksel": "jakarta selatan",
    "jakpus": "jakarta pusat",
    "jaktim": "jakarta timur",
    "jakut": "jakarta utara",
    "btw": "ngomong ngomong",
    "bgt": "banget",
    "bngt": "banget",
    "beneran": "benar benar",
    "cmn": "cuma",
    "tp": "tapi",
    "tpi": "tapi",
    "yg": "yang",
    "pdhl": "padahal",
    "pke": "pakai",
    "pake": "pakai",
    "udh": "sudah",
    "sdh": "sudah",
    "udah": "sudah",
    "dr": "dari",
    "td": "tadi",
    "tdk": "tidak",
    "tdak": "tidak",
    "org": "orang",
    "bbrp": "beberapa",
}

# ---------------------------
# 1. Keep emoji
# ---------------------------
def keep_emoji(text):
    return emoji.replace_emoji(
        text,
        replace=lambda e, d: f" {e} "
    )

# ---------------------------
# 2. Remove URL
# ---------------------------
def remove_url(text):
    return re.sub(r"http\S+|www\.\S+", " ", text)

# ---------------------------
# 3. Remove username @
# ---------------------------
def remove_username(text):
    return re.sub(r"@\w+", " ", text)

# ---------------------------
# 4. Remove hashtag
# ---------------------------
def remove_hashtag(text):
    return re.sub(r"#\w+", " ", text)

# ---------------------------
# 5. Normalize slang
# ---------------------------
def normalize_slang(text):
    words = text.split()
    new_words = []
    for w in words:
        new_words.append(slang_dict.get(w.lower(), w))
    return " ".join(new_words)

# ---------------------------
# 6. Clean symbols
# ---------------------------
def clean_symbol(text):
    return re.sub(r"[^a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF\s\U0001F600-\U0001F64F]", " ", text)

# ---------------------------
# 7. Remove multiple spaces
# ---------------------------
def remove_multiple_spaces(text):
    return re.sub(r"\s+", " ", text).strip()

# ---------------------------
# 8. Remove stopwords
# ---------------------------
def remove_stopwords(text):
    words = text.split()
    filtered = [w for w in words if w.lower() not in stopwords]
    return " ".join(filtered)

# ---------------------------
# 9. Stemming
# ---------------------------
def stem_text(text):
    return stemmer.stem(text)

# ---------------------------
# 10. FULL CLEANER + RETURN TOKEN DENGAN KOMA
# ---------------------------
def clean_text_ai(text):
    if text is None:
        return ""

    text = str(text)
    text = keep_emoji(text)
    text = remove_url(text)
    text = remove_username(text)
    text = remove_hashtag(text)
    text = normalize_slang(text)
    text = clean_symbol(text)
    text = text.lower()
    text = remove_stopwords(text)
    text = stem_text(text)
    text = remove_multiple_spaces(text)

    # 👉 RETURN TOKEN DIPISAH KOMA
    return ", ".join(text.split())

# ---------------------------
# 11. Translate (optional)
# ---------------------------
def translate_to_indonesian(text):
    if not text or text.strip() == "":
        return ""
    try:
        result = GoogleTranslator(source='auto', target='id').translate(text)
        return result
    except Exception:
        return text


# Test manual
if __name__ == "__main__":
    sample = "Gokil bgt tempatnya @ozifebrian 🤣🤣 #jaksel www.test.com"
    print(clean_text_ai(sample))
