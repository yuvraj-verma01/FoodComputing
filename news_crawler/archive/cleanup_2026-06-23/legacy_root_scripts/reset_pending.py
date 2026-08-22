import sqlite3
conn = sqlite3.connect("data/outputs/articles.db")
cur = conn.execute("UPDATE discovered_urls SET status='pending' WHERE status='failed'")
print(f"Reset {cur.rowcount} failed URLs to pending")
conn.commit()
for row in conn.execute("SELECT status, COUNT(*) FROM discovered_urls GROUP BY status"):
    print(f"  {row[0]}: {row[1]}")
conn.close()
