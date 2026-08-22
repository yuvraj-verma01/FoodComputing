import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
rel_dir = ROOT / "data/runs/edible_oil_adulteration_round_03_2026-06-23/mediacloud/outputs/oil_relevance"
rows = list(csv.DictReader((rel_dir / "all_articles_review.csv").open(encoding="utf-8-sig")))
print(f"Total in all_articles_review: {len(rows)}\n")
for r in rows:
    print(f"[{r.get('final_label','?'):13s}] rule_cand={r.get('rule_candidate','')} "
          f"llm={r.get('llm_label','')}({r.get('llm_confidence','')})")
    print(f"   title: {r.get('title','')[:95]}")
    print(f"   url:   {r.get('url','')[:100]}")
    print(f"   rule:  {r.get('reason','')[:90]}")
    print(f"   llm:   {r.get('llm_reason','')[:90]}")
    print()
