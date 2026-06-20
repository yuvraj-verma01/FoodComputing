import sqlite3, json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
conn = sqlite3.connect(ROOT / "data" / "outputs" / "articles.db")

print("=== ARTICLE COUNTS ===")
for label, cnt in conn.execute("SELECT relevance_label, COUNT(*) FROM articles GROUP BY relevance_label ORDER BY COUNT(*) DESC"):
    print(f"  {label}: {cnt}")
total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
dups  = conn.execute("SELECT COUNT(*) FROM articles WHERE is_duplicate=1").fetchone()[0]
print(f"  TOTAL: {total}  |  Duplicates: {dups}")

print("\n=== DISCOVERY METHOD (relevant, no dups) ===")
for method, cnt in conn.execute("SELECT discovery_method, COUNT(*) FROM articles WHERE relevance_label='relevant' AND is_duplicate=0 GROUP BY discovery_method ORDER BY COUNT(*) DESC"):
    print(f"  {method}: {cnt}")

print("\n=== TOP 15 DOMAINS (relevant, no dups) ===")
for domain, cnt in conn.execute("SELECT domain, COUNT(*) FROM articles WHERE relevance_label='relevant' AND is_duplicate=0 GROUP BY domain ORDER BY COUNT(*) DESC LIMIT 15"):
    print(f"  {domain}: {cnt}")

print("\n=== BY YEAR (relevant, no dups) ===")
rows = conn.execute("SELECT publication_date, COUNT(*) FROM articles WHERE relevance_label='relevant' AND is_duplicate=0 GROUP BY publication_date").fetchall()
year_counts = Counter()
for pub_date, cnt in rows:
    if pub_date and len(pub_date) >= 4:
        year_counts[pub_date[:4]] += cnt
for yr, cnt in sorted(year_counts.items()):
    print(f"  {yr}: {cnt}")

print("\n=== OIL TYPES FOUND (relevant, no dups) ===")
OIL_TERMS = ['mustard oil','edible oil','palm oil','cooking oil','soybean oil',
             'groundnut oil','coconut oil','sesame oil','vanaspati','sunflower oil',
             'rice bran oil','cottonseed oil','refined oil','loose oil','blended oil']
food_rows = conn.execute("SELECT food_terms_found FROM articles WHERE relevance_label='relevant' AND is_duplicate=0").fetchall()
oil_counts = Counter()
for (raw,) in food_rows:
    try:
        for t in json.loads(raw or '[]'):
            if t.lower() in OIL_TERMS:
                oil_counts[t.lower()] += 1
    except Exception:
        pass
for oil, cnt in oil_counts.most_common():
    print(f"  {oil}: {cnt}")

print("\n=== TOP STATES (relevant, no dups) ===")
STATES = ['Uttar Pradesh','Gujarat','Maharashtra','Rajasthan','Punjab','Haryana',
          'Delhi','West Bengal','Madhya Pradesh','Karnataka','Tamil Nadu','Kerala',
          'Andhra Pradesh','Telangana','Bihar','Odisha','Assam','Uttarakhand',
          'Himachal Pradesh','Chhattisgarh','Jharkhand','Goa']
loc_rows = conn.execute("SELECT location_terms_found FROM articles WHERE relevance_label='relevant' AND is_duplicate=0").fetchall()
state_counts = Counter()
for (raw,) in loc_rows:
    try:
        terms = [t.lower() for t in json.loads(raw or '[]')]
        for s in STATES:
            if s.lower() in terms:
                state_counts[s] += 1
    except Exception:
        pass
for s, cnt in state_counts.most_common():
    print(f"  {s}: {cnt}")

print("\n=== ADULTERATION TYPES (relevant, no dups) ===")
adult_rows = conn.execute("SELECT adulteration_terms_found FROM articles WHERE relevance_label='relevant' AND is_duplicate=0").fetchall()
adult_counts = Counter()
for (raw,) in adult_rows:
    try:
        for t in json.loads(raw or '[]'):
            adult_counts[t.lower()] += 1
    except Exception:
        pass
for term, cnt in adult_counts.most_common(15):
    print(f"  {term}: {cnt}")

conn.close()
