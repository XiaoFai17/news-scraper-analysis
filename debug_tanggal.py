"""
Jalankan script ini di lokal:
    python debug_tanggal.py

Tujuan: lihat format tanggal ASLI yang dikembalikan Google News RSS
sebelum kita perbaiki parsing-nya.
"""

import feedparser
from datetime import datetime

# --- Fetch RSS ---
keyword = "beras"
rss_url = f"https://news.google.com/rss/search?q={keyword}&hl=ID:id"

print(f"🔍 Fetching RSS: {rss_url}\n")
feed = feedparser.parse(rss_url)

print(f"Total entry di feed: {len(feed.entries)}\n")
print("=" * 80)

# --- Lihat 5 entry pertama, print semua field mentah ---
for i, entry in enumerate(feed.entries[:5]):
    print(f"\n📌 Artikel #{i+1}")
    print(f"   title     : {entry.get('title', 'N/A')}")
    print(f"   link      : {entry.get('link', 'N/A')}")

    # Ini yang paling penting — lihat format tanggal mentah
    published_raw = entry.get("published", "TIDAK ADA FIELD 'published'")
    print(f"   published (raw) : {published_raw}")
    print(f"   published type  : {type(published_raw)}")

    # feedparser kadang sudah parse tanggal ke struct_time
    published_parsed = entry.get("published_parsed", "TIDAK ADA 'published_parsed'")
    print(f"   published_parsed: {published_parsed}")
    print(f"   published_parsed type: {type(published_parsed)}")

    # Coba juga lihat updated field
    updated_raw = entry.get("updated", "TIDAK ADA FIELD 'updated'")
    print(f"   updated (raw)   : {updated_raw}")

    updated_parsed = entry.get("updated_parsed", "TIDAK ADA 'updated_parsed'")
    print(f"   updated_parsed  : {updated_parsed}")

    # Print semua keys yang ada di entry
    print(f"   [semua keys]    : {list(entry.keys())}")
    print("-" * 80)

# --- Juga lihat summary/description untuk cek URL ---
print("\n\n📌 Contoh summary/description dari entry pertama:")
if feed.entries:
    print(feed.entries[0].get("summary", "N/A"))