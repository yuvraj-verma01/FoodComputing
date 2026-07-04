"""
Audit relevant articles — check whether oil is the adulterated product
or just mentioned incidentally.
"""
import sqlite3, json, re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
conn = sqlite3.connect(ROOT / "data" / "outputs" / "articles.db")

rows = conn.execute("""
    SELECT article_id, title, article_text, food_terms_found, adulteration_terms_found
    FROM articles
    WHERE relevance_label = 'relevant' AND is_duplicate = 0
""").fetchall()

OIL_TERMS = [
    'edible oil','mustard oil','cooking oil','vegetable oil','palm oil',
    'soybean oil','groundnut oil','sesame oil','sunflower oil','cottonseed oil',
    'blended oil','rice bran oil','coconut oil','refined oil','loose oil',
    'sarson tel','vanaspati','rapeseed oil','linseed oil'
]

# Patterns where oil IS the adulterated product
STRONG_OIL_ADULTER = [
    re.compile(r'\b(adulterat\w*|spurious|fake|substandard|misbranded?|contamina\w*|impure|inferior)\s+\w*\s*' + re.escape(oil), re.I)
    for oil in OIL_TERMS
] + [
    re.compile(re.escape(oil) + r'\s+\w*\s*(adulterat\w*|spurious|fake|substandard|failed|unsafe|impure|contamina\w*|mislabel\w*)', re.I)
    for oil in OIL_TERMS
] + [
    re.compile(re.escape(oil) + r'.{0,60}(sample fail|test fail|quality fail|found unsafe|found substandard)', re.I)
    for oil in OIL_TERMS
]

# Patterns where oil is seized for non-adulteration reasons
SEIZURE_ONLY = [
    re.compile(r'\b(hoard|black market|smuggl|illegal storage|without licen|without permit|tax evad|price hike|price control|ration)\b', re.I),
]

categories = Counter()
problem_examples = []

for art_id, title, text, food_raw, adul_raw in rows:
    corpus = f"{title or ''} {text or ''}".lower()

    # Check if any strong oil-adulteration pattern matches
    strong_match = any(p.search(corpus) for p in STRONG_OIL_ADULTER)

    # Check if it's seizure-only (no adulteration language)
    try:
        adul_terms = json.loads(adul_raw or '[]')
    except Exception:
        adul_terms = []

    genuinely_adulterated = (
        'adulterated' in [t.lower() for t in adul_terms] or
        'adulteration' in [t.lower() for t in adul_terms] or
        'spurious' in [t.lower() for t in adul_terms] or
        'substandard' in [t.lower() for t in adul_terms] or
        'fake' in [t.lower() for t in adul_terms] or
        'contaminated' in [t.lower() for t in adul_terms] or
        'sample fail' in corpus or
        'sample failed' in corpus or
        'failed test' in corpus
    )

    if strong_match:
        categories['oil_is_product'] += 1
    elif genuinely_adulterated:
        categories['adulteration_mentioned_but_oil_context_unclear'] += 1
        if len(problem_examples) < 8:
            problem_examples.append(('unclear', title, corpus[:200]))
    else:
        categories['seizure_or_irrelevant'] += 1
        if len(problem_examples) < 8:
            problem_examples.append(('bad', title, corpus[:200]))

print(f"Total relevant (no dups): {len(rows)}\n")
print("=== CATEGORY BREAKDOWN ===")
for cat, cnt in categories.most_common():
    pct = 100 * cnt / len(rows)
    print(f"  {cat}: {cnt} ({pct:.0f}%)")

print("\n=== EXAMPLE PROBLEM ARTICLES ===")
for kind, title, snippet in problem_examples:
    print(f"\n[{kind.upper()}] {title}")
    print(f"  {snippet[:200]}")

conn.close()
