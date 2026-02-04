import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime
import time
import re
from urllib.parse import unquote

# newspaper3k untuk extract artikel dari URL
from newspaper import Article


# ============================================================
# USER AGENTS
# ============================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]


def get_headers(index: int = 0) -> dict:
    return {
        "User-Agent": USER_AGENTS[index % len(USER_AGENTS)],
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    }


# ============================================================
# BAGIAN 1: Resolve Google News URL -> URL Asli
# ============================================================

def resolve_google_news_url(google_url: str) -> str:
    """
    Resolve Google News redirect URL ke URL artikel asli.
    Fetch HTML dari Google News dan extract link yang bukan google.com.
    """
    if not google_url:
        return ""

    try:
        response = requests.get(google_url, headers=get_headers(), allow_redirects=True, timeout=15)

        # Kalau sudah redirect ke non-google, langsung return
        if "google.com" not in response.url and "news.google.com" not in response.url:
            return response.url

        # Parse HTML dan cari link asli
        soup = BeautifulSoup(response.text, "html.parser")

        # Strategi 1: Cari <a> tag dengan href non-google
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("http") and "google.com" not in href:
                return href

        # Strategi 2: Cari URL di dalam script tags
        for script in soup.find_all("script"):
            if script.string:
                urls_found = re.findall(r'https?://[^"\s<>]+', script.string)
                for url in urls_found:
                    if "google.com" not in url and len(url) > 30:
                        return unquote(url)

        # Strategi 3: og:url meta tag
        og_url = soup.find("meta", attrs={"property": "og:url"})
        if og_url and og_url.get("content") and "google.com" not in og_url["content"]:
            return og_url["content"]

        # Semua gagal, return URL google
        return google_url

    except Exception:
        return google_url


# ============================================================
# BAGIAN 2: Fetch dari Google News RSS
# ============================================================

def build_rss_url(keyword: str, region: str = "ID:id") -> str:
    keyword_encoded = keyword.replace(" ", "+")
    return f"https://news.google.com/rss/search?q={keyword_encoded}&hl={region}"


def fetch_rss(keyword: str) -> dict:
    """
    Fetch Google News RSS dan parse hasilnya.
    Return: dict berisi 'error' dan 'articles'
    """
    rss_url = build_rss_url(keyword)

    try:
        feed = feedparser.parse(rss_url)
    except Exception as e:
        return {"error": f"Gagal fetch RSS: {str(e)}", "articles": []}

    articles = []

    for entry in feed.entries:

        # --- Tanggal: pakai published_parsed (struct_time) dari feedparser ---
        struct_time = entry.get("published_parsed", None)
        tanggal = datetime(*struct_time[:6]) if struct_time else None

        # --- Judul dan Nama Media ---
        judul_raw = entry.get("title", "").strip()
        nama_media = ""
        judul = judul_raw

        # Format: "Judul Berita - Nama Media"
        if " - " in judul_raw:
            bagian = judul_raw.rsplit(" - ", 1)
            judul = bagian[0].strip()
            nama_media = bagian[1].strip()

        # Backup dari summary HTML: <font color="#6f6f6f">Nama Media</font>
        if not nama_media:
            summary_html = entry.get("summary", "")
            soup_summary = BeautifulSoup(summary_html, "html.parser")
            font_tag = soup_summary.find("font", attrs={"color": "#6f6f6f"})
            if font_tag:
                nama_media = font_tag.get_text(strip=True)

        if not nama_media:
            nama_media = "Unknown"

        articles.append({
            "title": judul,
            "date": tanggal,
            "url": entry.get("link", ""),   # masih Google News URL
            "source": nama_media,
            "content": "",
            "journalist": ""
        })

    return {"error": None, "articles": articles}


# ============================================================
# BAGIAN 3: Filter Tanggal
# ============================================================

def filter_by_date(articles: list[dict], from_date: datetime, to_date: datetime) -> list[dict]:
    """Filter artikel berdasarkan rentang tanggal (naive datetime)."""
    filtered = []

    if hasattr(from_date, "hour"):
        fd = from_date.replace(tzinfo=None, hour=0, minute=0, second=0)
    else:
        fd = datetime.combine(from_date, datetime.min.time())

    if hasattr(to_date, "hour"):
        td = to_date.replace(tzinfo=None, hour=23, minute=59, second=59)
    else:
        td = datetime.combine(to_date, datetime.max.time())

    for article in articles:
        tanggal = article.get("date")
        if tanggal is None:
            continue
        if hasattr(tanggal, "tzinfo") and tanggal.tzinfo is not None:
            tanggal = tanggal.replace(tzinfo=None)
        if fd <= tanggal <= td:
            filtered.append(article)

    return filtered


# ============================================================
# BAGIAN 4: Scraping Full Text
# ============================================================

def scrape_with_newspaper(url: str) -> dict:
    """
    Extract artikel pakai newspaper3k.
    newspaper3k dirancang khusus untuk extract main content dari halaman berita.
    """
    result = {"content": "", "journalist": ""}

    try:
        article = Article(url, language="id")
        article.download()
        article.parse()

        if article.text and len(article.text.strip()) > 50:
            result["content"] = article.text.strip()

        if article.authors:
            result["journalist"] = ", ".join(article.authors)

    except Exception as e:
        result["content"] = f"[newspaper3k: {str(e)}]"

    return result


def scrape_with_beautifulsoup(url: str) -> dict:
    """Fallback scraping pakai BeautifulSoup."""
    result = {"content": "", "journalist": ""}

    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "header", "footer",
                         "aside", "iframe", "noscript", "svg", "button"]):
            tag.decompose()

        content = ""

        # <article> tag
        article_tag = soup.find("article")
        if article_tag:
            content = article_tag.get_text(separator=" ", strip=True)

        # Class umum
        if len(content) < 100:
            for cls in ["article-content", "article-body", "post-content",
                        "entry-content", "content-article", "article__body",
                        "DetailArticle_content", "article_content",
                        "text-article", "body-article", "konten-artikel"]:
                elem = soup.find(class_=cls)
                if elem:
                    content = elem.get_text(separator=" ", strip=True)
                    if len(content) > 100:
                        break

        # Kumpul <p> panjang
        if len(content) < 100:
            texts = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 50]
            content = " ".join(texts)

        content = re.sub(r"\s+", " ", content).strip()
        result["content"] = content if content else ""

        # Meta author
        meta_author = soup.find("meta", attrs={"name": re.compile(r"author", re.I)})
        if meta_author and meta_author.get("content"):
            journalist = meta_author["content"].strip()
            if len(journalist) < 60:
                result["journalist"] = journalist

    except Exception:
        pass

    return result


def scrape_full_text(google_news_url: str) -> dict:
    """
    Main scrape per artikel:
    1. Resolve Google News URL -> URL asli
    2. Coba newspaper3k dulu
    3. Kalau gagal / konten pendek, fallback ke BeautifulSoup
    """
    result = {"resolved_url": google_news_url, "content": "", "journalist": ""}

    # Step 1: Resolve URL
    real_url = resolve_google_news_url(google_news_url)
    result["resolved_url"] = real_url

    # Step 2: newspaper3k
    newspaper_result = scrape_with_newspaper(real_url)
    if newspaper_result["content"] and len(newspaper_result["content"]) > 100:
        result["content"] = newspaper_result["content"]
        result["journalist"] = newspaper_result["journalist"]
        return result

    # Step 3: Fallback BeautifulSoup
    bs_result = scrape_with_beautifulsoup(real_url)
    if bs_result["content"] and len(bs_result["content"]) > 100:
        result["content"] = bs_result["content"]
        result["journalist"] = bs_result["journalist"] or newspaper_result["journalist"]
        return result

    # Kedua gagal
    if newspaper_result["content"] and not newspaper_result["content"].startswith("["):
        result["content"] = newspaper_result["content"]
        result["journalist"] = newspaper_result["journalist"]
    else:
        result["content"] = "[Konten tidak berhasil di-extract]"

    return result


def scrape_all_articles(articles: list[dict], delay: float = 1.5) -> list[dict]:
    """Scrape semua artikel dengan delay antar request."""
    scraped = []

    for i, article in enumerate(articles):
        result = scrape_full_text(article["url"])

        article["content"] = result["content"]
        article["journalist"] = result["journalist"]
        article["url"] = result["resolved_url"]

        scraped.append(article)

        if i < len(articles) - 1:
            time.sleep(delay)

    return scraped