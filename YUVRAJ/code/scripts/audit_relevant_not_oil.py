"""Audit the RELEVANT (final_keep=1) articles: find any that are NOT genuine
edible-oil adulteration incidents — especially oil-reuse cases — by reading the
article TEXT, not the title.

Flags each relevant article on:
  A. REUSE  — text is about reused / recycled / repeatedly-used cooking oil
  B. NO_OIL — no edible-oil product term appears in the text at all
  C. NONOIL_FOOD_DOMINANT — non-oil food terms (milk/paneer/sweets...) dominate
                            and oil appears only incidentally
  D. ADULTERANT — oil used to adulterate another food (oil is the adulterant)
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from crawler.oil_relevance import (
    EDIBLE_OIL_TERMS, NON_OIL_FOOD_TERMS, ADULTERATION_ACTION_TERMS,
)

MASTER = ROOT / "reports/master_corpus/master_all_articles.csv"
OUT = ROOT / "reports/relevant_audit_suspects.csv"

REUSE_RE = re.compile(
    r"\b(re[- ]?used?|re[- ]?using|recycl\w+|repeated(?:ly)?\s+use[d]?|used\s+again|"
    r"multiple\s+times|reheat\w*)\b[^.]{0,40}\boil\b"
    r"|\boil\b[^.]{0,40}\b(re[- ]?used?|re[- ]?using|recycl\w+|repeated(?:ly)?\s+use[d]?|reheat\w*)\b",
    re.I,
)
OIL_WORD_RE = re.compile(r"\boil\b|\boils\b", re.I)


def read_csv(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def terms_in(text, terms):
    low = text.lower()
    return [t for t in terms if re.search(r"\b" + re.escape(t.lower()) + r"\b", low)]


def snippet(text, pat, pad=90):
    m = pat.search(text)
    if not m:
        return ""
    s = max(0, m.start() - pad); e = min(len(text), m.end() + pad)
    return re.sub(r"\s+", " ", text[s:e]).strip()


def main():
    rows = read_csv(MASTER)
    rel = [r for r in rows
           if str(r.get("final_keep", "")).strip() == "1"
           and (r.get("article_text") or "").strip()]
    print(f"Relevant articles with text: {len(rel)}\n")

    suspects = []
    for r in rel:
        text = r.get("article_text", "") or ""
        title = r.get("title", "") or ""
        combined = title + " . " + text

        edible = terms_in(combined, EDIBLE_OIL_TERMS)
        nonoil = terms_in(combined, NON_OIL_FOOD_TERMS)
        reuse_m = REUSE_RE.search(combined)

        flags = []
        if reuse_m:
            flags.append("A_REUSE")
        if not edible and not OIL_WORD_RE.search(combined):
            flags.append("B_NO_OIL")
        elif not edible:
            flags.append("B_NO_EDIBLE_TERM")
        if len(nonoil) >= 3 and len(edible) <= 1:
            flags.append("C_NONOIL_FOOD_DOMINANT")

        if flags:
            suspects.append({
                "flags": "|".join(flags),
                "round": r.get("round_number", ""),
                "title": title[:90],
                "url": r.get("url", ""),
                "edible_terms": "; ".join(edible[:5]),
                "nonoil_terms": "; ".join(nonoil[:6]),
                "reuse_evidence": snippet(combined, REUSE_RE) if reuse_m else "",
            })

    # group + print
    from collections import Counter
    fc = Counter(f for s in suspects for f in s["flags"].split("|"))
    print(f"Suspect relevant articles: {len(suspects)}")
    print("Flag counts:", dict(fc))
    print("=" * 100)

    order = {"A_REUSE": 0, "B_NO_OIL": 1, "B_NO_EDIBLE_TERM": 2, "C_NONOIL_FOOD_DOMINANT": 3}
    suspects.sort(key=lambda s: min(order.get(f, 9) for f in s["flags"].split("|")))
    for s in suspects:
        print(f"\n[{s['flags']}]  (round {s['round']})")
        print(f"  TITLE: {s['title']}")
        print(f"  URL:   {s['url']}")
        print(f"  edible-oil terms found: {s['edible_terms'] or '(none)'}")
        print(f"  non-oil food terms:     {s['nonoil_terms'] or '(none)'}")
        if s["reuse_evidence"]:
            print(f"  REUSE evidence: ...{s['reuse_evidence']}...")

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(suspects[0].keys()) if suspects else ["flags"])
        w.writeheader(); w.writerows(suspects)
    print(f"\nSaved: {OUT}")


if __name__ == "__main__":
    main()