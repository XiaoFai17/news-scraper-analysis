import os
import json
import time
from dotenv import load_dotenv
from groq import Groq

# Memuat environment variables dari file .env
load_dotenv()

_client = None

def get_groq_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key or api_key == "masukkan_api_key_disini":
            raise ValueError("GROQ_API_KEY belum di-set di file .env")
        _client = Groq(api_key=api_key)
    return _client

# Pattern konten tidak valid (halaman error, sosial media, dsb.)
GARBAGE_CONTENT_PATTERNS = [
    'javascript is not available',
    'javascript is disabled',
    'please enable javascript',
    'switch to a supported browser',
    'continue using x.com',
    'continue using twitter.com',
    'access denied',
    '403 forbidden',
    'halaman tidak ditemukan',
    'page not found',
    'cookies are disabled',
]


def _is_garbage_content(content: str) -> bool:
    """Cek apakah content adalah garbage (error page, sosmed, dsb.)."""
    content_lower = content.lower()
    return any(p in content_lower for p in GARBAGE_CONTENT_PATTERNS)


def process_single_article(content: str) -> dict:
    """Mengirim satu teks artikel ke Groq untuk Summarization, Sentiment, dan Topic."""
    if not content or len(content.strip()) < 100 or content.startswith("["):
        return {"summary": "-", "sentiment": "Netral", "topic": "-"}
    
    # Cek garbage content (halaman error JavaScript, cookie notice, dll.)
    if _is_garbage_content(content):
        return {"summary": "-", "sentiment": "Netral", "topic": "-"}
        
    try:
        client = get_groq_client()
    except ValueError as e:
        return {"summary": f"[Error: {str(e)}]", "sentiment": "Netral", "topic": "-"}
    
    # Potong content jika terlalu panjang (menghemat token context window)
    if len(content) > 6000:
        content = content[:6000]
        
    prompt = f"""
    Kamu adalah asisten pengolah berita AI Bahasa Indonesia. Analisis teks berita berikut.
    Berikan output strictly DALAM FORMAT JSON tanpa teks pengantar tambahan apapun. 
    Kunci JSON yang harus digunakan:
    - "summary": Ringkas berita ini dalam 2-3 kalimat yang padat dan informatif.
    - "sentiment": Tentukan sentimen dari isi berita, pilih salah satu persis hurufnya: "Positif", "Negatif", atau "Netral".
    - "topic": Ekstrak topik atau isu utama dari teks dalam wujud satu kalimat pendek atau frasa singkat (maksimal 10 kata), contoh: "Pertumbuhan ekonomi Surabaya 2025" atau "Evaluasi dana bantuan sosial".
    
    Teks Berita:
    {content}
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Model terpadu JSON LLaMA 3.3
            messages=[
                {"role": "system", "content": "You are a specialized JSON AI assistant for news analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Rendah untuk jawaban analisis deterministik
            response_format={"type": "json_object"},
        )
        
        result_text = completion.choices[0].message.content
        data = json.loads(result_text)
        
        return {
            "summary": data.get("summary", "-"),
            "sentiment": data.get("sentiment", "Netral"),
            "topic": data.get("topic", "-")
        }
    except Exception as e:
        return {"summary": f"[API Error: {str(e)[:50]}]", "sentiment": "Netral", "topic": "-"}


def process_nlp(articles: list[dict], streamlit_progress=None) -> list[dict]:
    """
    Jalankan full NLP pipeline pada list artikel menggunakan API Groq.
    Return: list artikel dengan tambahan fields summary, sentiment, topics.
    """
    total = len(articles)
    processed = []

    for i, article in enumerate(articles):
        content = article.get("content", "")

        # Skip kalau content kosong atau error scraping
        if (not content or 
            content.startswith("[Gagal") or 
            content.startswith("[Error") or
            content.startswith("[newspaper3k") or
            content.startswith("[Konten tidak") or
            content.startswith("[Konten dari") or
            content.startswith("[URL tidak") or
            _is_garbage_content(content) or
            len(content) < 100):
            
            article["summary"] = "-"
            article["sentiment"] = "Netral"
            # Nilai score default agar visualisasi di app.py tetap tidak rusak
            article["sentiment_score"] = 0.0 
            article["topics"] = "-"
            processed.append(article)

        else:
            # Panggil Groq AI untuk melakukan semua task NLP sekaligus
            ai_result = process_single_article(content)
            
            article["summary"] = ai_result["summary"]
            article["sentiment"] = ai_result["sentiment"]
            article["sentiment_score"] = 0.0  # Groq tidak membalas score akurat
            article["topics"] = ai_result["topic"]

            processed.append(article)

        # Update progress bar interface Streamlit
        if streamlit_progress is not None:
            streamlit_progress.progress((i + 1) / total, text=f"Processing AI artikel {i+1}/{total} dengan Groq...")
            
        # Sleep kecil mencegah Rate Limit dari tier API gratisan jika banyak artikel
        time.sleep(1)

    return processed
