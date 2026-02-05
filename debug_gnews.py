"""
Debug script untuk test GNews.get_full_article()
Jalankan: python debug_gnews.py
"""

from gnews import GNews

# URL dari output kamu
test_url = "https://news.google.com/rss/articles/CBMi5AFBVV95cUxQRHZOaS1kbXp1a2hJRE42M1RnbV9LRzl5ak9wUURFYUhYelIwUi1SSkF3aDNSc1ByTWtZMjNwcmJsMHBIWnd0VHpCSFFqaUJqS0lzSW9HTFRyR2lFemdSeS1ZdWpqRWZqZkduNWlOR19XSzAwRExlN1hYTnZzVFdlc0dtcUNtbHpIUWEydU04TFF5SXhlZ3VQLTltUkRVcWR2S3p5UWUxcWh2eklDbFNOY0x6X3BJSTFUVFNzd3lxWUk1bVRQMEx1N0VYNzBOOWVQZlc4bGhFYjRGUXFxOE00Q25IcEw?oc=5&hl=en-ID&gl=ID&ceid=ID:en"

print("=" * 80)
print("Testing GNews.get_full_article()")
print("=" * 80)
print(f"\nTest URL: {test_url}\n")

try:
    google_news = GNews(language='id', country='ID')
    print("✓ GNews instance created")
    
    print("\nCalling get_full_article()...")
    article = google_news.get_full_article(test_url)
    
    print(f"\n✓ get_full_article() returned: {type(article)}")
    
    if article:
        print(f"\nArticle object attributes:")
        print(f"  - hasattr 'url': {hasattr(article, 'url')}")
        print(f"  - hasattr 'text': {hasattr(article, 'text')}")
        print(f"  - hasattr 'authors': {hasattr(article, 'authors')}")
        
        if hasattr(article, 'url'):
            print(f"\n  URL: {article.url}")
        
        if hasattr(article, 'text'):
            text_preview = article.text[:200] if article.text else "None"
            print(f"\n  Text (first 200 chars): {text_preview}")
        
        if hasattr(article, 'authors'):
            print(f"\n  Authors: {article.authors}")
    else:
        print("\n✗ article is None or False")
    
except Exception as e:
    print(f"\n✗ ERROR: {type(e).__name__}")
    print(f"   Message: {str(e)}")
    import traceback
    print("\n   Full traceback:")
    traceback.print_exc()

print("\n" + "=" * 80)
print("Testing alternative: Search berita + get first article")
print("=" * 80)

try:
    google_news = GNews(language='id', country='ID', max_results=3)
    
    print("\nSearching for 'bps kota surabaya'...")
    news_results = google_news.get_news('bps kota surabaya')
    
    print(f"✓ Found {len(news_results)} results")
    
    if news_results:
        first_item = news_results[0]
        print(f"\nFirst result:")
        print(f"  Title: {first_item.get('title', 'N/A')}")
        print(f"  URL: {first_item.get('url', 'N/A')}")
        
        google_url = first_item.get('url', '')
        
        if google_url:
            print(f"\nTrying get_full_article on first result...")
            article = google_news.get_full_article(google_url)
            
            if article:
                print(f"  ✓ Success!")
                if hasattr(article, 'url'):
                    print(f"  Resolved URL: {article.url}")
                if hasattr(article, 'text'):
                    print(f"  Content length: {len(article.text) if article.text else 0}")
            else:
                print(f"  ✗ article is None")

except Exception as e:
    print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
