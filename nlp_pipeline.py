from transformers import pipeline
import re
import warnings

warnings.filterwarnings("ignore")


# ============================================================
# BAGIAN 1: Load Model (di-cache supaya tidak berulang kali load)
# ============================================================

_summarizer = None
_sentiment_analyzer = None


def load_summarizer():
    global _summarizer
    if _summarizer is None:
        # Import explicit untuk avoid task name issues
        from transformers import BartForConditionalGeneration, BartTokenizer
        
        model_name = "facebook/bart-large-cnn"
        
        # Load model dan tokenizer secara manual
        tokenizer = BartTokenizer.from_pretrained(model_name)
        model = BartForConditionalGeneration.from_pretrained(model_name)
        
        # Buat pipeline dari model + tokenizer
        _summarizer = pipeline(
            "summarization",
            model=model,
            tokenizer=tokenizer,
            device=-1  # -1 = CPU
        )
    return _summarizer


def load_sentiment_analyzer():
    """Load model sentiment analysis bahasa Indonesia."""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        try:
            # Coba model Indonesia dulu
            _sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model="w11wo/indonesian-roberta-base-sentiment-classifier",
                device=-1
            )
        except Exception:
            # Fallback ke model Inggris kalau gagal
            _sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=-1
            )
    return _sentiment_analyzer


# ============================================================
# BAGIAN 2: Text Summarization
# ============================================================

def summarize_text(text: str, max_length: int = 130, min_length: int = 30) -> str:
    """
    Summarize text menggunakan BART.
    Kalau text terlalu pendek, kosong, atau error message, return text asli atau placeholder.
    """
    # Skip kalau text kosong atau error message
    if not text or len(text.strip()) < 100:
        return "-"
    
    # Deteksi error message
    if text.startswith("[") and "]" in text:
        return "-"
    
    if "gagal" in text.lower() or "error" in text.lower() or "not found" in text.lower():
        return "-"

    # Clean text: hapus whitespace berlebihan
    text_clean = re.sub(r"\s+", " ", text).strip()
    
    # BART max input ~1024 tokens, potong kalau terlalu panjang
    # Estimasi: 1 token ≈ 4 karakter
    if len(text_clean) > 3000:
        text_clean = text_clean[:3000]

    try:
        summarizer = load_summarizer()
        result = summarizer(
            text_clean,
            max_length=max_length,
            min_length=min_length,
            do_sample=False,
            truncation=True  # Penting: truncate kalau input terlalu panjang
        )
        return result[0]["summary_text"]
    except Exception as e:
        return f"[Gagal summarize: {str(e)[:100]}]"


# ============================================================
# BAGIAN 3: Sentiment Analysis
# ============================================================

def analyze_sentiment(text: str) -> dict:
    """
    Analisis sentimen dari text.
    Return: dict berisi 'label' dan 'score'.
    """
    # Skip kalau text kosong atau error message
    if not text or len(text.strip()) < 20:
        return {"label": "Netral", "score": 0.0}
    
    if text.startswith("[") or "error" in text.lower() or "gagal" in text.lower():
        return {"label": "Netral", "score": 0.0}

    # Potong text (model sentiment limit: 512 tokens)
    text_clean = re.sub(r"\s+", " ", text).strip()
    if len(text_clean) > 512:
        text_clean = text_clean[:512]

    try:
        analyzer = load_sentiment_analyzer()
        result = analyzer(text_clean, truncation=True)[0]

        label_raw = result["label"].upper()
        score = round(result["score"], 3)

        # Normalize label
        # Model Indonesia biasanya: positive, negative, neutral
        # Model Inggris: POSITIVE, NEGATIVE
        if "POS" in label_raw:
            label = "Positif"
        elif "NEG" in label_raw:
            label = "Negatif"
        else:
            label = "Netral"

        return {"label": label, "score": score}

    except Exception as e:
        return {"label": "Netral", "score": 0.0}


# ============================================================
# BAGIAN 4: Topic Modelling (Keyword Extraction)
# ============================================================

from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np


# Stopwords Bahasa Indonesia (extended list)
STOPWORDS_ID = {
    "yang", "dan", "di", "ke", "dari", "adalah", "untuk", "pada", "dengan",
    "dalam", "tidak", "atau", "ini", "itu", "akan", "sudah", "juga", "ada",
    "oleh", "karena", "secara", "saat", "setelah", "hingga", "tetapi",
    "namun", "kalau", "jika", "maka", "sementara", "sedang", "pernah",
    "telah", "bisa", "dapat", "harus", "boleh", "perlu", "semua", "setiap",
    "masing", "tiap", "satu", "dua", "lebih", "banyak", "sangat", "hanya",
    "selalu", "sering", "kadang", "paling", "terlalu", "cukup", "masih",
    "lagi", "juga", "sama", "seperti", "antara", "tentang", "terhadap",
    "menurut", "berdasarkan", "melalui", "kepada", "bagi", "atas", "bawah",
    "sebelum", "sesudah", "selama", "karena", "sebagai", "bahwa", "sehingga",
    "mana", "apa", "siapa", "dimana", "kapan", "bagaimana", "mengapa",
    "tapi", "begitu", "lalu", "pun", "ya", "oh", "oke", "ayo", "hey",
    "nya", "kita", "mereka", "dia", "saya", "aku", "mu", "kami", "kalian",
    "ia", "hal", "sebuah", "suatu", "agar", "supaya", "maupun", "yakni",
    "yaitu", "kembali", "kali", "belum", "pula", "tanpa", "via", "kata",
    "bisa", "meski", "baik", "berita", "artikel", "tulisan", "konten",
    # Tambahan kata teknis yang sering muncul di error/metadata
    "url", "https", "http", "www", "com", "html", "error", "gagal",
    "failed", "tidak", "berhasil", "extract", "download", "found",
    "client", "server", "status", "code", "response"
}


def extract_topics(text: str, n_topics: int = 3) -> str:
    """
    Extract keyword/topik utama dari artikel menggunakan TF-IDF.
    Return: string berisi topik, dipisahkan koma.
    """
    # Skip kalau text kosong, error, atau terlalu pendek
    if not text or len(text.strip()) < 100:
        return "-"
    
    # Deteksi error message
    if text.startswith("[") or "error" in text.lower() or "gagal" in text.lower():
        return "-"
    
    if "not found" in text.lower() or "failed" in text.lower():
        return "-"

    text_clean = re.sub(r"\s+", " ", text).strip().lower()

    # Tokenize sederhana: ambil kata alfanumerik
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text_clean)  # Min 3 huruf, cuma huruf
    
    # Filter stopwords dan kata pendek
    words_filtered = [w for w in words if w not in STOPWORDS_ID and len(w) > 3]

    if len(words_filtered) < 5:
        return "-"

    try:
        # Buat kalimat dari text untuk TF-IDF
        sentences = re.split(r"[.!?]", text_clean)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]

        if len(sentences) < 2:
            # Kalau cuma 1 kalimat, ambil kata paling sering
            from collections import Counter
            word_counts = Counter(words_filtered)
            top_words = [w.title() for w, _ in word_counts.most_common(n_topics)]
            return ", ".join(top_words) if top_words else "-"

        # TF-IDF
        vectorizer = TfidfVectorizer(
            stop_words=list(STOPWORDS_ID),
            max_features=50,
            ngram_range=(1, 2),  # unigram dan bigram
            min_df=1,
            token_pattern=r"\b[a-zA-Z]{3,}\b"  # Cuma kata huruf, min 3 karakter
        )

        tfidf_matrix = vectorizer.fit_transform(sentences)
        feature_names = vectorizer.get_feature_names_out()

        # Ambil kata dengan score TF-IDF tertinggi (rata-rata)
        mean_scores = tfidf_matrix.mean(axis=0).A1
        top_indices = np.argsort(mean_scores)[::-1][:n_topics]

        topics = [feature_names[i].title() for i in top_indices]
        
        # Filter out kata yang masih mencurigakan (URL remnants, dll)
        topics_clean = []
        for topic in topics:
            if not any(bad_word in topic.lower() for bad_word in ["http", "www", "url", "com", "html", "error"]):
                topics_clean.append(topic)
        
        return ", ".join(topics_clean[:n_topics]) if topics_clean else "-"

    except Exception as e:
        return "-"


# ============================================================
# BAGIAN 5: Pipeline Utama — Proses Semua Artikel
# ============================================================

def process_nlp(articles: list[dict], streamlit_progress=None) -> list[dict]:
    """
    Jalankan full NLP pipeline pada list artikel.
    Return: list artikel dengan tambahan fields summary, sentiment, topics.
    """
    total = len(articles)
    processed = []

    for i, article in enumerate(articles):
        content = article.get("content", "")

        # Skip kalau content kosong atau error
        if (not content or 
            content.startswith("[Gagal") or 
            content.startswith("[Error") or
            content.startswith("[newspaper3k") or
            content.startswith("[Konten tidak") or
            len(content) < 100):
            
            article["summary"] = "-"
            article["sentiment"] = "Netral"
            article["sentiment_score"] = 0.0
            article["topics"] = "-"
            processed.append(article)

        else:
            # Summarization
            article["summary"] = summarize_text(content)

            # Sentiment Analysis
            sentiment_result = analyze_sentiment(content)
            article["sentiment"] = sentiment_result["label"]
            article["sentiment_score"] = sentiment_result["score"]

            # Topic Extraction
            article["topics"] = extract_topics(content)

            processed.append(article)

        # Update progress bar
        if streamlit_progress is not None:
            streamlit_progress.progress((i + 1) / total, text=f"Processing artikel {i+1}/{total}...")

    return processed