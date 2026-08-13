from transformers import pipeline

# Load model Bahasa Indonesia
sentiment_model = pipeline(
    "text-classification",
    model="w11wo/indonesian-roberta-base-sentiment-classifier"
)

def analyze_sentiment(text: str):
    """
    Analisis sentimen menggunakan model bahasa Indonesia.
    Output: 'positif', 'negatif', 'netral'
    """
    if not text or text.strip() == "":
        return "netral"
    
    result = sentiment_model(text[:512])[0]  
    label = result['label'].lower()

    if "positive" in label:
        return "positif"
    elif "negative" in label:
        return "negatif"
    else:
        return "netral"
