"""Apply audited corpus corrections (2026-06-29):
  - Flip 12 relevant articles -> irrelevant (not edible-oil adulteration; reuse
    or oil-absent/incidental). 'Assam fruit ripening' is KEPT relevant.
  - Remove 1 duplicate row (Cyberabad article appears twice; drop the
    ?utm_source=rss copy, keep the clean URL).
Backs up the corpus and writes a change-log before saving.
"""
from __future__ import annotations
import csv, shutil, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
MASTER = ROOT / "reports/master_corpus/master_all_articles.csv"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = MASTER.with_name(f"master_all_articles_backup_{TS}.csv")
LOG = MASTER.with_name(f"corpus_correction_log_{TS}.csv")

FLIP_URLS = [
    "https://timesofindia.indiatimes.com/life-style/food-news/dark-discoloration-high-tpc-levels-found-in-cooking-oil-of-famous-fast-food-chain-what-fssai-says-about-the-health-risks/articleshow/130833701.cms",
    "https://www.siasat.com/hyderabad-food-safety-inspection-flags-unsafe-oil-at-kfc-outlet-in-kondapur-3465689/",
    "https://timesofindia.indiatimes.com/city/bengaluru/think-before-you-snack-namkeens-dairy-products-top-list-of-unsafe-foods-in-karnataka/articleshow/131179662.cms",
    "https://www.livemint.com/news/india/34-people-fall-ill-in-suspected-food-poisoning-case-after-eating-pizza-in-maharashtra-s-bhiwandi-11781889067823.html",
    "https://www.thehindu.com/news/national/telangana/h-fast-raids-unlicensed-food-godown-in-charminar-seizes-adulterated-food/article71121824.ece",
    "https://www.siasat.com/food-raids-in-telangana-snacks-worth-over-rs-60k-seized-license-suspended-3148653/",
    "https://www.thehindu.com/news/national/andhra-pradesh/50-of-food-samples-collected-by-food-safety-department-officials-found-to-be-unsafe/article70252244.ece",
    "https://timesofindia.indiatimes.com/city/hyderabad/tea-to-ice-creams-food-adulteration-on-the-rise-in-hyderabad/articleshow/108746726.cms",
    "https://timesofindia.indiatimes.com/city/ranchi/ahead-of-diwali-crackdown-on-adulterated-food-items-in-city/articleshow/124610900.cms",
    "https://www.thehindu.com/news/national/kerala/food-safety-wing-to-step-up-checks-on-curry-powders-in-kerala/article65700040.ece",
    "https://garhwalpost.in/crackdown-on-adulteration-food-safety-department-conducts-raids-in-mussoorie/",
    "https://www.freepressjournal.in/mumbai/maharashtra-fda-cracks-down-on-banned-gutkha-and-adulterated-food-arrests-102-persons-and-seizes-goods-worth-158-crore-in-one-week",
]
REMOVE_URL = "https://www.indiatoday.in/cities/hyderabad/story/cyberabad-food-adulteration-raids-hyderabad-rs-64-lakh-seizure-28-arrested-2900680-2026-04-23?utm_source=rss"

flip_set = set(FLIP_URLS)

with MASTER.open(encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

shutil.copy2(MASTER, BACKUP)
print(f"Backup: {BACKUP.name}")

log = []
out_rows = []
flipped = removed = 0
for r in rows:
    url = (r.get("url") or "").strip()
    if url == REMOVE_URL:
        removed += 1
        log.append({"url": url, "action": "REMOVED_DUPLICATE",
                    "old_final_keep": r.get("final_keep"), "new_final_keep": "",
                    "title": r.get("title", "")})
        continue
    if url in flip_set:
        old = r.get("final_keep")
        r["final_keep"] = "0"
        if "final_human_label" in r:
            r["final_human_label"] = "irrelevant"
        flipped += 1
        log.append({"url": url, "action": "FLIP_relevant_to_irrelevant",
                    "old_final_keep": old, "new_final_keep": "0",
                    "title": r.get("title", "")})
    out_rows.append(r)

with MASTER.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(out_rows)

with LOG.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["url", "action", "old_final_keep", "new_final_keep", "title"])
    w.writeheader(); w.writerows(log)

def count_rel(rs):
    return sum(1 for r in rs if str(r.get("final_keep", "")).strip() == "1")

print(f"Flipped relevant->irrelevant: {flipped}")
print(f"Removed duplicate rows:        {removed}")
print(f"Rows: {len(rows)} -> {len(out_rows)}")
print(f"Relevant: {count_rel(rows)} -> {count_rel(out_rows)}")
print(f"Change log: {LOG.name}")