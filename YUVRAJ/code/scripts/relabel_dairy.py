import sqlite3, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "outputs" / "articles.db"

OIL_TERMS = {
    'edible oil','mustard oil','cooking oil','vegetable oil','palm oil',
    'soybean oil','groundnut oil','sesame oil','sunflower oil',
    'cottonseed oil','blended oil','rice bran oil','coconut oil',
    'refined oil','loose oil','sarson tel','vanaspati','rapeseed oil',
    'linseed oil'
}

conn = sqlite3.connect(DB)
rows = conn.execute(
    "SELECT article_id, food_terms_found FROM articles WHERE relevance_label = 'relevant'"
).fetchall()

to_relabel = []
for article_id, food_raw in rows:
    try:
        terms = set(t.lower() for t in json.loads(food_raw or '[]'))
    except Exception:
        terms = set()
    if not (terms & OIL_TERMS):
        to_relabel.append(article_id)

conn.executemany(
    "UPDATE articles SET relevance_label = 'dairy_adulteration', "
    "notes = 'Ghee/dairy product - out of scope for edible oil study' "
    "WHERE article_id = ?",
    [(aid,) for aid in to_relabel]
)
conn.commit()
print(f"Re-labeled {len(to_relabel)} ghee/dairy articles -> dairy_adulteration")

counts = dict(conn.execute(
    "SELECT relevance_label, COUNT(*) FROM articles WHERE is_duplicate=0 "
    "GROUP BY relevance_label ORDER BY COUNT(*) DESC"
).fetchall())
print("New breakdown (no dups):", counts)
conn.close()
