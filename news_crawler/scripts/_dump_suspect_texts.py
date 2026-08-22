import csv, sys, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
MASTER = ROOT / "reports/master_corpus/master_all_articles.csv"
SUSP = ROOT / "reports/relevant_audit_suspects.csv"

want_flag = sys.argv[1] if len(sys.argv) > 1 else "A_REUSE"

susp = list(csv.DictReader(SUSP.open(encoding="utf-8-sig")))
if want_flag == "REMAINING":   # all suspects NOT already covered by A_REUSE
    urls = [s["url"] for s in susp if "A_REUSE" not in s["flags"]]
else:
    urls = [s["url"] for s in susp if want_flag in s["flags"]]
rows = {r["url"]: r for r in csv.DictReader(MASTER.open(encoding="utf-8-sig"))}

print(f"=== Full texts of {len(urls)} '{want_flag}' suspects ===\n")
for i, u in enumerate(urls, 1):
    r = rows.get(u, {})
    text = re.sub(r"\s+", " ", (r.get("article_text") or "")).strip()
    print(f"\n{'#'*95}")
    print(f"[{i}] {r.get('title','')}")
    print(f"    round={r.get('round_number','')}  url={u}")
    print(f"    {'-'*80}")
    print("   ", text)