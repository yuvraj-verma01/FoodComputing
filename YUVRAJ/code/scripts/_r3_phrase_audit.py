"""Audit which phrase queries got dropped in Round 3 metadata stage."""
import csv, re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rel_dir = ROOT / "data/runs/edible_oil_adulteration_round_03_2026-06-23/mediacloud/outputs/oil_relevance"

rows = list(csv.DictReader((rel_dir / "metadata_all_articles_review.csv").open(encoding="utf-8-sig")))

phrase_dropped = [r for r in rows if r.get("query_family") == "phrase" and r.get("crawl_priority") == "drop"]
phrase_kept    = [r for r in rows if r.get("query_family") == "phrase" and r.get("crawl_priority") != "drop"]

print(f"Phrase dropped: {len(phrase_dropped)}  Phrase kept (high/medium): {len(phrase_kept)}")

def extract_phrase(q: str) -> str:
    m = re.match(r'\("(.+?)" AND', q)
    return m.group(1) if m else q[:60]

by_phrase = Counter(extract_phrase(r.get("query_used", "")) for r in phrase_dropped)
print("\nDropped phrase queries by search term:")
for ph, cnt in sorted(by_phrase.items(), key=lambda x: -x[1]):
    print(f"  {cnt:4d}  {ph}")
