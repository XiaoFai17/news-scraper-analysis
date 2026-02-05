from gnews import GNews
from newspaper import Article
from datetime import datetime
import time
import re
from bs4 import BeautifulSoup

# Selenium untuk resolve Google News URL
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ============================================================
# Global Selenium Driver (reuse untuk efficiency)
# ============================================================

_driver = None


def get_selenium_driver():
    """
    Get or create Selenium WebDriver instance.
    Driver di-reuse untuk semua requests agar lebih efisien.
    """
    global _driver
    
    if _driver is None:
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Tanpa GUI
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36')
        
        # Disable images untuk speed
        prefs = {'profile.managed_default_content_settings.images': 2}
        chrome_options.add_experimental_option('prefs', prefs)
        
        _driver = webdriver.Chrome(options=chrome_options)
    
    return _driver


def close_selenium_driver():
    """Close Selenium driver saat selesai."""
    global _driver
    if _driver is not None:
        _driver.quit()
        _driver = None


# ============================================================
# BAGIAN 1: Fetch dari Google News menggunakan GNews
# ============================================================

def fetch_rss(keyword: str, max_results: int = 100) -> dict:
    """Fetch berita dari Google News menggunakan GNews."""
    try:
        google_news = GNews(
            language='id',
            country='ID',
            max_results=max_results
        )
        
        news_results = google_news.get_news(keyword)
        articles = []
        
        for item in news_results:
            date_str = item.get('published date', '')
            try:
                tanggal = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z')
            except:
                tanggal = None
            
            judul = item.get('title', '').strip()
            
            publisher_info = item.get('publisher', {})
            if isinstance(publisher_info, dict):
                nama_media = publisher_info.get('title', 'Unknown')
            else:
                nama_media = str(publisher_info) if publisher_info else 'Unknown'
            
            articles.append({
                'title': judul,
                'date': tanggal,
                'url': item.get('url', ''),
                'source': nama_media,
                'content': '',
                'journalist': ''
            })
        
        return {'error': None, 'articles': articles}
    
    except Exception as e:
        return {'error': f'Gagal fetch: {str(e)}', 'articles': []}


# ============================================================
# BAGIAN 2: Resolve Google News URL dengan Selenium
# ============================================================

def resolve_google_news_url_selenium(google_url: str, timeout: int = 10) -> str:
    """
    Resolve Google News URL menggunakan Selenium.
    
    Strategi:
    1. Load halaman Google News dengan Selenium (render JavaScript)
    2. Tunggu redirect otomatis atau cari link di halaman
    3. Return URL final
    """
    if not google_url or 'news.google.com' not in google_url:
        return google_url
    
    try:
        driver = get_selenium_driver()
        
        # Load halaman
        driver.get(google_url)
        
        # Tunggu sebentar untuk redirect otomatis
        time.sleep(2)
        
        # Cek URL setelah redirect
        current_url = driver.current_url
        
        # Kalau sudah redirect ke artikel asli
        google_domains = ['google.com', 'gstatic.com', 'googleusercontent.com']
        if not any(domain in current_url for domain in google_domains):
            return current_url
        
        # Kalau masih di Google, cari link di halaman
        try:
            # Tunggu ada link yang bukan Google
            WebDriverWait(driver, timeout).until(
                lambda d: any(
                    elem.get_attribute('href') and 
                    elem.get_attribute('href').startswith('http') and
                    not any(gd in elem.get_attribute('href') for gd in google_domains)
                    for elem in d.find_elements(By.TAG_NAME, 'a')
                )
            )
            
            # Ambil semua link
            links = driver.find_elements(By.TAG_NAME, 'a')
            candidate_urls = []
            
            for link in links:
                href = link.get_attribute('href')
                if href and href.startswith('http'):
                    if not any(d in href for d in google_domains + ['youtube.com']):
                        if len(href) > 30:
                            candidate_urls.append(href)
            
            if candidate_urls:
                # Ambil URL terpanjang
                return max(candidate_urls, key=len)
        
        except Exception:
            pass
        
        # Gagal, return URL asli
        return google_url
    
    except Exception:
        return google_url


# ============================================================
# BAGIAN 3: Filter Tanggal
# ============================================================

def filter_by_date(articles: list[dict], from_date: datetime, to_date: datetime) -> list[dict]:
    """Filter artikel berdasarkan rentang tanggal."""
    filtered = []
    
    if hasattr(from_date, 'hour'):
        fd = from_date.replace(tzinfo=None, hour=0, minute=0, second=0)
    else:
        fd = datetime.combine(from_date, datetime.min.time())
    
    if hasattr(to_date, 'hour'):
        td = to_date.replace(tzinfo=None, hour=23, minute=59, second=59)
    else:
        td = datetime.combine(to_date, datetime.max.time())
    
    for article in articles:
        tanggal = article.get('date')
        if tanggal is None:
            continue
        if hasattr(tanggal, 'tzinfo') and tanggal.tzinfo is not None:
            tanggal = tanggal.replace(tzinfo=None)
        if fd <= tanggal <= td:
            filtered.append(article)
    
    return filtered


# ============================================================
# BAGIAN 4: Scraping Full Text
# ============================================================

def scrape_with_newspaper(url: str) -> dict:
    """Scrape artikel pakai newspaper3k."""
    result = {'content': '', 'journalist': ''}
    
    try:
        article = Article(url, language='id')
        article.download()
        article.parse()
        
        if article.text and len(article.text.strip()) > 50:
            result['content'] = article.text.strip()
        
        if article.authors:
            result['journalist'] = ', '.join(article.authors)
    
    except Exception as e:
        result['content'] = f'[newspaper3k: {str(e)}]'
    
    return result


def scrape_with_selenium_direct(url: str) -> dict:
    """Scrape menggunakan Selenium + BeautifulSoup."""
    result = {'content': '', 'journalist': ''}
    
    try:
        driver = get_selenium_driver()
        driver.get(url)
        
        # Tunggu halaman load
        time.sleep(3)
        
        # Parse HTML dari Selenium
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Hapus noise
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()
        
        content = ''
        
        # Cari <article>
        article_tag = soup.find('article')
        if article_tag:
            content = article_tag.get_text(separator=' ', strip=True)
        
        # Fallback
        if len(content) < 100:
            for cls in ['article-content', 'article-body', 'post-content']:
                elem = soup.find(class_=cls)
                if elem:
                    content = elem.get_text(separator=' ', strip=True)
                    if len(content) > 100:
                        break
        
        if len(content) < 100:
            texts = [p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 50]
            content = ' '.join(texts)
        
        content = re.sub(r'\s+', ' ', content).strip()
        result['content'] = content if content else ''
        
        # Author
        meta_author = soup.find('meta', attrs={'name': re.compile(r'author', re.I)})
        if meta_author and meta_author.get('content'):
            result['journalist'] = meta_author['content'].strip()
    
    except Exception:
        pass
    
    return result


def scrape_full_text(google_news_url: str) -> dict:
    """Main scraping function."""
    result = {'resolved_url': google_news_url, 'content': '', 'journalist': ''}
    
    # Resolve URL pakai Selenium
    real_url = resolve_google_news_url_selenium(google_news_url)
    result['resolved_url'] = real_url
    
    # Kalau masih Google URL
    if 'google.com' in real_url or 'gstatic.com' in real_url:
        result['content'] = '[URL tidak berhasil di-resolve]'
        return result
    
    # Coba newspaper3k dulu
    newspaper_result = scrape_with_newspaper(real_url)
    if newspaper_result['content'] and len(newspaper_result['content']) > 100 and not newspaper_result['content'].startswith('['):
        result['content'] = newspaper_result['content']
        result['journalist'] = newspaper_result['journalist']
        return result
    
    # Fallback: Selenium scraping
    selenium_result = scrape_with_selenium_direct(real_url)
    if selenium_result['content'] and len(selenium_result['content']) > 100:
        result['content'] = selenium_result['content']
        result['journalist'] = selenium_result['journalist'] or newspaper_result['journalist']
        return result
    
    # Semua gagal
    if newspaper_result['content']:
        result['content'] = newspaper_result['content']
        result['journalist'] = newspaper_result['journalist']
    else:
        result['content'] = '[Konten tidak berhasil di-extract]'
    
    return result


def scrape_all_articles(articles: list[dict], delay: float = 1.0) -> list[dict]:
    """
    Scrape semua artikel dengan delay.
    Selenium driver akan di-reuse untuk semua artikel.
    """
    scraped = []
    
    try:
        for i, article in enumerate(articles):
            result = scrape_full_text(article['url'])
            
            article['content'] = result['content']
            article['journalist'] = result['journalist']
            article['url'] = result['resolved_url']
            
            scraped.append(article)
            
            if i < len(articles) - 1:
                time.sleep(delay)
    
    finally:
        # Close driver setelah semua selesai
        close_selenium_driver()
    
    return scraped