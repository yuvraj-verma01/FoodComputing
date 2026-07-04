import csv, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
MASTER = ROOT / "reports/master_corpus/master_all_articles.csv"
rows = list(csv.DictReader(MASTER.open(encoding="utf-8-sig")))

# title substrings of the 13 to remove (relevant -> not oil adulteration)
REMOVE = [
    ("REUSE", "Dark discoloration"),
    ("REUSE", "unsafe oil at"),
    ("REUSE", "Namkeens & dairy products top"),
    ("REUSE", "34 people fall ill"),
    ("REUSE", "H-FAST raids unlicensed food godown"),
    ("REUSE", "Food raids in Telangana"),
    ("NO-OIL/INCIDENTAL", "50% of food samples"),
    ("NO-OIL/INCIDENTAL", "Tea to ice creams"),
    ("NO-OIL/INCIDENTAL", "Ahead of Diwali, crackdown"),
    ("NO-OIL/INCIDENTAL", "curry powders in Kerala"),
    ("NO-OIL/INCIDENTAL", "raids in Mussoorie"),
    ("NO-OIL/INCIDENTAL", "Banned Gutkha"),
    ("NO-OIL/INCIDENTAL", "illegal fruit ripening"),
]

def find(sub):
    return [r for r in rows if sub.lower() in (r.get("title", "") or "").lower()]

print("=== 13 ARTICLES TO FLIP relevant -> irrelevant ===\n")
n = 0
for cat, sub in REMOVE:
    hits = find(sub)
    for r in hits:
        n += 1
        print(f"[{n:2}] ({cat})  round {r.get('round_number','')}")
        print(f"     {r.get('title','')[:88]}")
        print(f"     {r.get('url','')}")
        print()

print("=== DUPLICATE to remove (same article twice) ===\n")
dup = [r for r in rows if "cyberabad-food-adulteration-raids-hyderabad-rs-64-lakh" in (r.get("url","") or "")]
for r in dup:
    print(f"  round {r.get('round_number','')}  keep={r.get('final_keep','')}")
    print(f"  {r.get('url','')}")