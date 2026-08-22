import sqlite3, json

conn = sqlite3.connect("data/outputs/articles.db")
conn.row_factory = sqlite3.Row

print("=" * 70)
print("RELEVANT ARTICLES")
print("=" * 70)
rows = conn.execute("""
    SELECT title, url, domain, publication_date, relevance_score,
           food_terms_found, adulteration_terms_found, location_terms_found
    FROM articles WHERE relevance_label='relevant'
    ORDER BY relevance_score DESC
""").fetchall()
for r in rows:
    food = json.loads(r["food_terms_found"] or "[]")
    adul = json.loads(r["adulteration_terms_found"] or "[]")
    loc  = json.loads(r["location_terms_found"] or "[]")
    print(f"  Score: {r['relevance_score']:.2f}  |  {r['domain']}  |  {r['publication_date']}")
    print(f"  Title: {(r['title'] or '')[:85]}")
    print(f"  Oil  : {food}")
    print(f"  Adul : {adul}")
    print(f"  Loc  : {loc[:4]}")
    print()

print("=" * 70)
print("TOP IRRELEVANT DOMAINS (noise from GDELT)")
print("=" * 70)
rows2 = conn.execute("""
    SELECT domain, COUNT(*) n FROM articles WHERE relevance_label='irrelevant'
    GROUP BY domain ORDER BY n DESC LIMIT 12
""").fetchall()
for r in rows2:
    print(f"  {r['domain']:<42} {r['n']}")
conn.close()
