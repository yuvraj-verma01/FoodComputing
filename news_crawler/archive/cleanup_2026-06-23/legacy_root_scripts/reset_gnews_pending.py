"""Reset robots_blocked Google News URLs back to pending for re-crawl."""
import sqlite3

conn = sqlite3.connect("data/outputs/articles.db")

# Only reset the news.google.com blocked URLs
cur = conn.execute(
    "UPDATE discovered_urls SET status='pending' WHERE status='robots_blocked' AND url LIKE '%news.google.com%'"
)
print(f"Reset {cur.rowcount} Google News blocked URLs to pending")
conn.commit()

for row in conn.execute("SELECT status, COUNT(*) FROM discovered_urls GROUP BY status"):
    print(f"  {row[0]}: {row[1]}")

conn.close()
