from transformers import pipeline
import re
import warnings

warnings.filterwarnings("ignore")


# ============================================================
# BAGIAN 1: Load Model (di-cache supaya tidak berulang kali load)
# ============================================================

# Model yang dipakai:
# - Summarization : facebook/bart-large-cnn (multilingual, works ok untuk Indo)
# - Sentiment     : cahya/bert2bert-indonlu-sentiment (spesifik Bahasa Indonesia)
#                   Fallback: distilbert-base-uncased-finetuned-sst-2-english (English)

_summarizer = None
_sentiment_analyzer = None


def load_summarizer():
    global _summarizer
    if _summarizer is None:
        _summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    return _summarizer


def load_sentiment_analyzer():
    """
    Coba load model Indonesia dulu.
    Kalau gagal (misalnya belum di-download atau ada issue), fallback ke model Inggris.
    """
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        try:
            _sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model="cahya/bert2bert-indonlu-sentiment",
                tokenizer="cahya/bert2bert-indonlu-sentiment"
            )
        except Exception:
            # Fallback ke model Inggris
            _sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english"
            )
    return _sentiment_analyzer


# ============================================================
# BAGIAN 2: Text Summarization
# ============================================================

def summarize_text(text: str, max_length: int = 150, min_length: int = 40) -> str:
    """
    Summarize text menggunakan BART.
    Kalau text terlalu pendek atau kosong, return text aslinya.
    """
    if not text or len(text.strip()) < 50:
        return text.strip() if text else "-"

    # BART max input ~1024 tokens, potong kalau terlalu panjang
    text_clean = re.sub(r"\s+", " ", text).strip()
    if len(text_clean) > 3000:
        text_clean = text_clean[:3000]

    try:
        summarizer = load_summarizer()
        result = summarizer(
            text_clean,
            max_length=max_length,
            min_length=min_length,
            do_sample=False
        )
        return result[0]["summary_text"]
    except Exception as e:
        return f"[Gagal summarize: {str(e)}]"


# ============================================================
# BAGIAN 3: Sentiment Analysis
# ============================================================

def analyze_sentiment(text: str) -> dict:
    """
    Analisis sentimen dari text.
    Return: dict berisi 'label' dan 'score'.
    Label akan di-normalize ke: Positif / Negatif / Netral
    """
    if not text or len(text.strip()) < 10:
        return {"label": "Netral", "score": 0.0}

    # Potong text karena model sentiment ada limit token (biasanya 512)
    text_clean = re.sub(r"\s+", " ", text).strip()
    if len(text_clean) > 500:
        text_clean = text_clean[:500]

    try:
        analyzer = load_sentiment_analyzer()
        result = analyzer(text_clean)[0]

        label_raw = result["label"].upper()
        score = round(result["score"], 3)

        # Normalize label
        # Model Indonesia (cahya) biasanya output: positive, negative, neutral
        # Model Inggris (sst-2) output: POSITIVE, NEGATIVE
        if "POS" in label_raw:
            label = "Positif"
        elif "NEG" in label_raw:
            label = "Negatif"
        else:
            label = "Netral"

        return {"label": label, "score": score}

    except Exception as e:
        return {"label": f"[Error: {str(e)}]", "score": 0.0}


# ============================================================
# BAGIAN 4: Topic Modelling (Keyword Extraction)
# ============================================================
# Catatan: BERTopic butuh banyak dokumen dan resources.
# Untuk versi awal ini, kita pakai pendekatan simpler:
# KeyBERT-style keyword extraction menggunakan TF-IDF + cosine similarity
# Ini lebih ringan dan cukup untuk mendapatkan topik/isu utama per artikel.
# Kalau nanti mau upgrade ke BERTopic bisa dilakukan setelah data
# yang dikumpulkan cukup banyak.

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


# Stopwords Bahasa Indonesia (basic list)
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
    "sebelum", "sesudah", "selama", "kerana", "sebagai", "bahwa", "sehingga",
    "mana", "apa", "siapa", "dimana", "kapan", "bagaimana", "mengapa",
    "tapi", "begitu", "lalu", "pun", "ya", "oh", "oke", "ayo", "hey",
    "yang", "nya", "kita", "mereka", "dia", "saya", "aku", "mu", "tu",
    "kami", "kalian", "ia", "hal", "bagai", "mana", "sebuah", "suatu",
}


def extract_topics(text: str, n_topics: int = 3) -> str:
    """
    Extract keyword/topik utama dari sebuah artikel menggunakan TF-IDF.
    Return: string berisi topik, dipisahkan koma.
    Contoh: "BPS, Surabaya, Inflasi"
    """
    if not text or len(text.strip()) < 50:
        return "-"

    text_clean = re.sub(r"\s+", " ", text).strip().lower()

    # Tokenize sederhana dan filter stopwords + kata pendek
    words = re.findall(r"\b[a-zA-Z0-9_]+\b", text_clean)
    words_filtered = [w for w in words if w not in STOPWORDS_ID and len(w) > 2]

    if len(words_filtered) < 3:
        return "-"

    # Buat n-grams (unigram dan bigram) untuk topik yang lebih bermakna
    unigrams = words_filtered
    bigrams = [f"{words_filtered[i]} {words_filtered[i+1]}" for i in range(len(words_filtered) - 1)]
    all_terms = unigrams + bigrams

    if not all_terms:
        return "-"

    try:
        # TF-IDF pada satu dokumen: kita treat setiap sentence sebagai dokumen terpisah
        sentences = re.split(r"[.!?]", text_clean)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if len(sentences) < 2:
            # Kalau hanya 1 kalimat, langsung ambil kata yang paling sering
            from collections import Counter
            word_counts = Counter(words_filtered)
            top_words = [w.title() for w, _ in word_counts.most_common(n_topics)]
            return ", ".join(top_words) if top_words else "-"

        vectorizer = TfidfVectorizer(
            stop_words=list(STOPWORDS_ID),
            max_features=100,
            ngram_range=(1, 2),  # unigram dan bigram
            min_df=1
        )

        tfidf_matrix = vectorizer.fit_transform(sentences)
        feature_names = vectorizer.get_feature_names_out()

        # Ambil kata dengan TF-IDF score tertinggi (rata-rata di semua kalimat)
        mean_scores = tfidf_matrix.mean(axis=0).A1  # convert ke 1D array
        top_indices = np.argsort(mean_scores)[::-1][:n_topics]

        topics = [feature_names[i].title() for i in top_indices]
        return ", ".join(topics) if topics else "-"

    except Exception as e:
        return f"[Error topic: {str(e)}]"


# ============================================================
# BAGIAN 5: Pipeline Utama — Proses Semua Artikel
# ============================================================

def process_nlp(articles: list[dict], streamlit_progress=None) -> list[dict]:
    """
    Jalankan full NLP pipeline pada list artikel.
    Setiap artikel diharapkan sudah memiliki 'content' dari scraper.

    Kalau streamlit_progress diberikan (st.progress object), 
    akan di-update progress bar-nya.

    Return: list artikel dengan tambahan fields:
        - summary
        - sentiment
        - sentiment_score
        - topics
    """
    total = len(articles)
    processed = []

    for i, article in enumerate(articles):
        content = article.get("content", "")

        # --- Skip kalau content kosong atau error ---
        if not content or content.startswith("[Gagal") or content.startswith("[Error"):
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

        # Update progress bar kalau ada
        if streamlit_progress is not None:
            streamlit_progress.progress((i + 1) / total, text=f"Processing artikel {i+1}/{total}...")

    return processed
