"""Debug: test URL decoder and storage for Google News results."""
import sys
sys.path.insert(0, ".")

import feedparser
from crawler.config import Config
from crawler.discovery.google_news import GoogleNewsDiscovery, _decode_google_news_url
from crawler.relevance import url_looks_relevant
from crawler.storage import Storage

cfg = Config("config/config_gdelt10.yaml")
gnews = GoogleNewsDiscovery(cfg)
storage = Storage(cfg)

query = "edible oil adulteration India"
url = (
    f"https://news.google.com/rss/search"
    f"?q=edible+oil+adulteration+India"
    f"&hl=en-IN&gl=IN&ceid=IN%3Aen"
)

feed = feedparser.parse(url)
entries = feed.get("entries", [])
print(f"Feed returned {len(entries)} entries")

if entries:
    entry = entries[0]
    raw_url = entry.get("link", "")
    print(f"\nRaw URL: {raw_url[:100]}")
    decoded = _decode_google_news_url(raw_url)
    print(f"Decoded URL: {decoded}")
    print(f"url_looks_relevant: {url_looks_relevant(decoded, entry.get('title',''))}")

    # Try saving
    rec = {
        "url": decoded,
        "discovery_method": "google_news_rss",
        "query_used": query,
        "discovered_at": "2026-06-17T00:00:00Z",
        "title_snippet": entry.get("title", "")[:500],
        "source": "test",
        "domain": "",
        "published_date": None,
        "status": "pending",
    }
    saved = storage.save_discovered(rec)
    print(f"save_discovered returned: {saved}")

# Count how many entries decode successfully
n_decoded = 0
n_gnews_still = 0
for e in entries[:10]:
    raw = e.get("link", "")
    decoded = _decode_google_news_url(raw)
    if "news.google.com" in decoded:
        n_gnews_still += 1
        print(f"FAILED to decode: {raw[:80]}")
    else:
        n_decoded += 1
        print(f"OK: {decoded[:80]}")

print(f"\nDecoded {n_decoded}/10 entries. {n_gnews_still} still point to news.google.com")

storage.close()
