"""Remove previously-discovered Google News redirect URLs (news.google.com) from
discovered_urls so we can re-run discovery with the URL decoder in place."""
import sqlite3

conn = sqlite3.connect("data/outputs/articles.db")

# Remove google.com redirect URLs from discovered_urls
cur = conn.execute(
    "DELETE FROM discovered_urls WHERE url LIKE '%news.google.com%'"
)
print(f"Removed {cur.rowcount} Google News redirect URLs from discovered_urls")

# Remove any articles that were stored for those redirect URLs
cur2 = conn.execute(
    "DELETE FROM articles WHERE url LIKE '%news.google.com%'"
)
print(f"Removed {cur2.rowcount} Google News articles")

conn.commit()

for row in conn.execute("SELECT status, COUNT(*) FROM discovered_urls GROUP BY status"):
    print(f"  discovered_urls status={row[0]}: {row[1]}")

conn.close()
