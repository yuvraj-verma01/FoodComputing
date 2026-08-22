"""Audit which master corpus rows have no article_text."""
import csv, sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent

rows = list(csv.DictReader(
    (ROOT / "reports/master_corpus/master_all_articles.csv").open(encoding="utf-8-sig")
))

empty = [r for r in rows if not (r.get("article_text") or "").strip()]
print(f"Total rows : {len(rows)}")
print(f"Empty text : {len(empty)}")
print(f"Has text   : {len(rows) - len(empty)}")
print()
print(f"By round   : {dict(Counter(r.get('round_number','?') for r in empty))}")
print(f"By keep    : {dict(Counter(str(r.get('final_keep','?')) for r in empty))}")
print()
for r in empty:
    rnd   = r.get("round_number", "?")
    keep  = r.get("final_keep", "?")
    src   = (r.get("source") or "")[:28]
    tag   = r.get("human_review_status", "")[:30]
    title = (r.get("title") or "")[:70]
    url   = (r.get("url") or "")[:80]
    print(f"  r{rnd} keep={keep}  [{tag}]  {title}")
    print(f"          {url}")
