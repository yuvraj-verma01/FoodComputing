import sys, openpyxl
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
wb = openpyxl.load_workbook(ROOT / "reports/rescreen/round4_keyword_candidates.xlsx", data_only=True)
ws = wb["Keyword Candidates"]
hdrs = [c.value for c in ws[1]]
approved = []
for row in ws.iter_rows(min_row=2, values_only=True):
    d = dict(zip(hdrs, row))
    v = d.get("add_to_queries")
    if v in (1, "1", 1.0, "yes", "Yes", "YES", True):
        approved.append(d)
print("Approved: %d" % len(approved))
for k in approved:
    print("  [df=%s] %s  (anchored=%s already_used=%s)" % (
        k["doc_freq_new"], k["term"], k["anchored"], k["already_used"]))
