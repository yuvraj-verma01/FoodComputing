import sqlite3, time
conn = sqlite3.connect("data/outputs/articles.db")
for row in conn.execute("SELECT status, COUNT(*) FROM discovered_urls GROUP BY status"):
    print(f"  discovered: {row[0]}: {row[1]}")
n_art = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
n_success = conn.execute("SELECT COUNT(*) FROM articles WHERE extraction_status='pending' AND raw_html_path IS NOT NULL").fetchone()[0]
print(f"\n  articles total: {n_art}")
print(f"  articles with HTML downloaded: {n_success}")
# Show some sample article URLs
rows = conn.execute("SELECT url, domain FROM articles WHERE raw_html_path IS NOT NULL LIMIT 5").fetchall()
for r in rows:
    print(f"  {r[1]}: {r[0][:80]}")
conn.close()
