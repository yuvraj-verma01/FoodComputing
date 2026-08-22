"""Remove Google News JS-redirect pages from the articles and discovered_urls tables.

These are articles where domain='news.google.com' — they're all the same
JavaScript reader page, not actual articles. The downloader saved them because
Google returns HTTP 200 (not a redirect) for the RSS article URLs.
"""
import sqlite3

conn = sqlite3.connect("data/outputs/articles.db")

# Count before
n_articles = conn.execute("SELECT COUNT(*) FROM articles WHERE domain LIKE '%google%'").fetchone()[0]
n_discovered = conn.execute(
    "SELECT COUNT(*) FROM discovered_urls WHERE url LIKE '%news.google.com%'"
).fetchone()[0]
print(f"Articles with Google domain: {n_articles}")
print(f"Discovered URLs with news.google.com: {n_discovered}")

# Delete article records for news.google.com domain (JS pages, not real articles)
conn.execute("DELETE FROM articles WHERE domain LIKE '%google%'")

# Delete the corresponding discovered_urls entries so they can be rediscovered
# as real article URLs via DuckDuckGo
conn.execute(
    "DELETE FROM discovered_urls WHERE url LIKE '%news.google.com%'"
)

conn.commit()

# Show counts after
n_art_after = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
n_disc_after = conn.execute("SELECT COUNT(*) FROM discovered_urls").fetchone()[0]
print(f"\nAfter cleanup:")
print(f"  articles: {n_art_after}")
print(f"  discovered_urls: {n_disc_after}")

for row in conn.execute("SELECT status, COUNT(*) FROM discovered_urls GROUP BY status"):
    print(f"  {row[0]}: {row[1]}")

conn.close()
print("\nDone. Run: python -m crawler --config config/config_gdelt10.yaml discover --sources ddgs")
