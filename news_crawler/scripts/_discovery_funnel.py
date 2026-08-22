"""Print full URL discovery funnel per round."""
import csv
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "runs"


def jsonl_count(p):
    if not p.exists():
        return 0
    return sum(1 for ln in p.open(encoding="utf-8") if ln.strip())


def csv_rows(p):
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def first_glob(parent, pattern):
    hits = list(parent.glob(pattern))
    return hits[0] if hits else None


# ── Round 1 ───────────────────────────────────────────────────────────────────
r1 = RUNS / "edible_oils_boolean_title_proximity_2026-06-22" / "mediacloud" / "outputs"
r1_meta_p = first_glob(r1 / "oil_relevance", "metadata_all*")
r1_rel_p  = first_glob(r1 / "oil_relevance", "relevant_oil*")
r1_meta   = csv_rows(r1_meta_p) if r1_meta_p else []
r1_prio   = Counter(r.get("crawl_priority", "?") for r in r1_meta)
r1_all_p  = first_glob(r1 / "oil_relevance", "all_articles*")
r1_all    = csv_rows(r1_all_p) if r1_all_p else []
r1_labels = Counter(r.get("final_label", "?") for r in r1_all)

print("ROUND 1  (edible_oils_boolean_title_proximity_2026-06-22)")
print(f"  Raw MC discovery (jsonl)     : {jsonl_count(r1 / 'discovered_urls.jsonl'):>5}")
print(f"  After dedup (url_review.csv) : {len(csv_rows(r1 / 'discovery_url_review.csv')):>5}")
print(f"  Metadata filter input        : {len(r1_meta):>5}  priority: {dict(r1_prio)}")
print(f"  Crawled (articles.jsonl)     : {jsonl_count(r1 / 'articles.jsonl'):>5}")
print(f"  Classified                   : {len(r1_all):>5}  labels: {dict(r1_labels)}")
r1_rel = csv_rows(r1_rel_p) if r1_rel_p else []
print(f"  Model-relevant (pre-human)   : {len(r1_rel):>5}")

# ── Round 2 ───────────────────────────────────────────────────────────────────
r2 = RUNS / "edible_oil_adulteration_round_02_2026-06-23" / "mediacloud" / "outputs"
r2_meta   = csv_rows(r2 / "oil_relevance" / "metadata_all_articles_review.csv")
r2_prio   = Counter(r.get("crawl_priority", "?") for r in r2_meta)
r2_all    = csv_rows(r2 / "oil_relevance" / "all_articles_review.csv")
r2_labels = Counter(r.get("final_label", "?") for r in r2_all)
r2_final  = csv_rows(r2 / "oil_relevance" / "final_relevant_articles.csv")

print()
print("ROUND 2  (edible_oil_adulteration_round_02_2026-06-23)")
print(f"  Raw MC discovery (jsonl)     : {jsonl_count(r2 / 'discovered_urls.jsonl'):>5}")
print(f"  After dedup (url_review.csv) : {len(csv_rows(r2 / 'discovery_url_review.csv')):>5}  (no prior-round dedup this round)")
print(f"  Metadata filter input        : {len(r2_meta):>5}  priority: {dict(r2_prio)}")
print(f"  Crawled (articles.jsonl)     : {jsonl_count(r2 / 'articles.jsonl'):>5}")
print(f"  Classified                   : {len(r2_all):>5}  labels: {dict(r2_labels)}")
print(f"  Final relevant (post-human)  : {len(r2_final):>5}")

# ── Round 3 ───────────────────────────────────────────────────────────────────
r3 = RUNS / "edible_oil_adulteration_round_03_2026-06-23" / "mediacloud" / "outputs"
r3_prev   = csv_rows(r3 / "discovery_previously_reviewed_urls.csv")
r3_meta   = csv_rows(r3 / "oil_relevance" / "metadata_all_articles_review.csv")
r3_prio   = Counter(r.get("crawl_priority", "?") for r in r3_meta)
r3_all    = csv_rows(r3 / "oil_relevance" / "all_articles_review.csv")
r3_labels = Counter(r.get("final_label", "?") for r in r3_all)

print()
print("ROUND 3  (edible_oil_adulteration_round_03_2026-06-23)")
print(f"  Raw MC discovery (jsonl)     : {jsonl_count(r3 / 'discovered_urls.jsonl'):>5}")
print(f"  Prev-reviewed excluded       : {len(r3_prev):>5}")
print(f"  After dedup (url_review.csv) : {len(csv_rows(r3 / 'discovery_url_review.csv')):>5}")
print(f"  Metadata filter input        : {len(r3_meta):>5}  priority: {dict(r3_prio)}")
print(f"  Crawled (articles.jsonl)     : {jsonl_count(r3 / 'articles.jsonl'):>5}")
print(f"  Classified                   : {len(r3_all):>5}  labels: {dict(r3_labels)}")
rel3 = [r for r in r3_all if r.get("final_label") == "relevant"]
print(f"  Model-relevant (pre-human)   : {len(rel3):>5}")

# ── Totals ────────────────────────────────────────────────────────────────────
r1_raw = jsonl_count(r1 / "discovered_urls.jsonl")
r2_raw = jsonl_count(r2 / "discovered_urls.jsonl")
r3_raw = jsonl_count(r3 / "discovered_urls.jsonl")

print()
print("=" * 55)
print("TOTALS")
print(f"  Raw URLs from MediaCloud (R1+R2+R3) : {r1_raw + r2_raw + r3_raw:>5}")
print(f"    Round 1                            : {r1_raw:>5}")
print(f"    Round 2                            : {r2_raw:>5}")
print(f"    Round 3                            : {r3_raw:>5}")
print(f"  After round-to-round dedup (R3 only) : {r3_raw - len(r3_prev):>5}  new in R3")
print(f"  Total unique new URLs seen R1-R3     : {r1_raw + r2_raw + (r3_raw - len(r3_prev)):>5}")
