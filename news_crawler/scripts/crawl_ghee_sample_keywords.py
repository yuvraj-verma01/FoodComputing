"""Crawl ghee sample URLs from DOCX and extract ghee-specific keyword candidates.

This is a thin ghee adapter around ``crawl_sample_keywords.py``. It keeps the
same output schema and scoring method used for the edible-oil sample workflow,
but swaps the domain lexicon and review-label heuristics so ghee terms are
treated as the target product instead of out-of-scope dairy noise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import crawl_sample_keywords as base  # noqa: E402


DEFAULT_DOCX = ROOT.parent / "Ghee sample articles.docx"
DEFAULT_RUN_DIR = ROOT / "data" / "runs" / "ghee_from_sample_2026-06-30"
DEFAULT_CONFIG = ROOT / "config" / "config.yaml"

GHEE_PRODUCT_TERMS = [
    "ghee",
    "desi ghee",
    "pure ghee",
    "cow ghee",
    "buffalo ghee",
    "loose ghee",
    "clarified butter",
    "milk fat",
    "butter fat",
]

GHEE_ADULTERANT_TERMS = [
    "vanaspati",
    "vanaspati ghee",
    "dalda",
    "vegetable fat",
    "vegetable oil",
    "palm oil",
    "palmolein",
    "hydrogenated oil",
    "hydrogenated vegetable oil",
    "animal fat",
    "body fat",
    "tallow",
    "lard",
    "starch",
    "synthetic colour",
    "essence",
]

GHEE_ADULTERATION_TERMS = [
    "adulterated",
    "adulteration",
    "substandard",
    "spurious",
    "fake",
    "counterfeit",
    "misbranded",
    "misbranding",
    "mislabelled",
    "mislabeled",
    "contaminated",
    "unsafe",
    "fraud",
    "synthetic",
    "impure",
    "not conforming",
    "sample failed",
    "failed test",
    "quality failed",
    "mixed with",
]

GHEE_ENFORCEMENT_TERMS = [
    "fssai",
    "fda",
    "fsda",
    "food safety",
    "food safety department",
    "food safety officer",
    "raid",
    "raids",
    "raided",
    "seized",
    "seizure",
    "samples collected",
    "sample collected",
    "samples sent",
    "lab test",
    "laboratory test",
    "quality test",
    "prosecution",
    "licence suspended",
    "license suspended",
    "shop sealed",
    "warehouse",
    "godown",
    "arrested",
    "crackdown",
    "inspection",
    "ban",
    "banned",
    "fine",
    "penalty",
]

NON_TARGET_FOOD_TERMS = {
    "paneer",
    "mawa",
    "khoya",
    "tea",
    "ice cream",
    "ice creams",
    "milk",
    "curd",
    "cheese",
    "dates",
    "wheat",
    "namkeen",
    "sweets",
    "bakery",
    "meat",
    "sauce",
    "sauces",
    "oil",
    "oils",
}


def configure_ghee_keyword_extractor() -> None:
    base.PRODUCT_TERMS[:] = GHEE_PRODUCT_TERMS
    base.ADULTERATION_TERMS[:] = GHEE_ADULTERATION_TERMS
    base.ENFORCEMENT_TERMS[:] = GHEE_ENFORCEMENT_TERMS
    base.NON_OIL_FOOD_TERMS = NON_TARGET_FOOD_TERMS
    base.CATEGORY_TERMS.clear()
    base.CATEGORY_TERMS.update(
        {
            "ghee/product": GHEE_PRODUCT_TERMS,
            "adulterant/mixing": GHEE_ADULTERANT_TERMS,
            "adulteration/fraud": GHEE_ADULTERATION_TERMS,
            "enforcement/evidence": GHEE_ENFORCEMENT_TERMS,
            "location": base.LOCATION_TERMS,
        }
    )
    base.has_oil_signal = has_ghee_signal
    base.is_ghee_only = lambda _phrase: False
    base.contains_non_oil_food_context = contains_non_target_food_context
    base.is_domainish = is_ghee_domainish
    base.quality_drop_reason = ghee_quality_drop_reason
    base.assign_review_label = assign_ghee_review_label


def has_ghee_signal(phrase: str) -> bool:
    p = phrase.lower()
    return any(term in p for term in GHEE_PRODUCT_TERMS)


def has_adulterant_signal(phrase: str) -> bool:
    p = phrase.lower()
    return any(term in p for term in GHEE_ADULTERANT_TERMS)


def contains_non_target_food_context(phrase: str) -> bool:
    p = phrase.lower()
    return any(term in p for term in NON_TARGET_FOOD_TERMS)


def is_ghee_domainish(phrase: str) -> bool:
    p = phrase.lower()
    return any(
        term in p
        for term in (
            "ghee",
            "desi",
            "clarified butter",
            "milk fat",
            "butter fat",
            "vanaspati",
            "dalda",
            "vegetable fat",
            "animal fat",
            "adulter",
            "fake",
            "spurious",
            "substandard",
            "misbrand",
            "mislabel",
            "contamin",
            "unsafe",
            "fssai",
            "fda",
            "fsda",
            "raid",
            "seiz",
            "food safety",
            "sample",
            "lab",
            "quality",
            "fraud",
            "ban",
            "crackdown",
        )
    )


def ghee_quality_drop_reason(phrase: str, category: str) -> str:
    p = phrase.lower()
    tokens = p.split()
    if len(tokens) > 6:
        return "too long for a seed keyword"
    if tokens and tokens[0] in {"time", "credits", "source", "sources"}:
        return "boilerplate or incomplete phrase"
    if re.search(r"\b(canva|etimes|copyright|advertisement|newsletter)\b", p):
        return "page boilerplate"
    if re.search(r"\bghee\s+(worth|supplied|sold|production|under|as per)\b", p):
        return "context fragment around ghee, not a reusable discovery keyword"
    if re.search(r"\b(worth|supplied|sold|production|under|as per)\s+ghee\b", p):
        return "context fragment around ghee, not a reusable discovery keyword"
    if contains_non_target_food_context(p) and not (has_ghee_signal(p) or has_adulterant_signal(p)):
        return "non-ghee food context without ghee/adulterant signal"
    if category == "other_candidate" and not is_ghee_domainish(p):
        return "outside ghee/adulteration domain"
    return ""


def assign_ghee_review_label(
    phrase: str,
    category: str,
    composite_score: float,
    method_count: int,
    document_frequency: int,
    total_frequency: int,
) -> tuple[str, str]:
    drop_reason = ghee_quality_drop_reason(phrase, category)
    if drop_reason:
        return "drop", drop_reason

    if category == "location":
        return "manual_review", "location term; useful only if we decide to add geography-specific queries"

    if category == "ghee/product":
        if " ".join(phrase.lower().split()) in {"ghee", "desi ghee", "pure ghee", "cow ghee", "buffalo ghee", "loose ghee", "clarified butter", "milk fat", "butter fat"}:
            return "keep_core", "clear ghee product term found in sample text"
        if composite_score >= 0.30 and method_count >= 2:
            return "manual_review", "ghee product phrase; verify it adds a new query concept"
        return "manual_review", "ghee product term, but weakly represented in this sample"

    if category == "adulterant/mixing":
        if composite_score >= 0.35 and (method_count >= 2 or total_frequency >= 2):
            return "keep_core", "strong candidate adulterant/mixing term for ghee queries"
        return "manual_review", "possible ghee adulterant/mixing term; verify before using"

    if category == "incident/action phrase":
        if composite_score >= 0.35 and (has_ghee_signal(phrase) or has_adulterant_signal(phrase) or method_count >= 2):
            return "keep_core", "combined ghee/adulteration/enforcement phrase"
        return "manual_review", "incident/action phrase needs human pruning"

    if category in {"adulteration/fraud", "enforcement/evidence"}:
        if composite_score >= 0.45 and (method_count >= 2 or document_frequency >= 2 or total_frequency >= 3):
            return "keep_core", "strong domain term for combining with ghee-product terms"
        if composite_score >= 0.20 or method_count >= 2:
            return "manual_review", "domain term is plausible but weaker or too broad"
        return "drop", "weak domain term below threshold"

    if method_count >= 2 and composite_score >= 0.45:
        return "manual_review", "statistically strong phrase but not in ghee/adulteration categories"

    return "drop", "low score or outside ghee/adulteration scope"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx", default=str(DEFAULT_DOCX))
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--playwright-fallback", action="store_true")
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Disable robots.txt checks for this academic sample crawl.",
    )
    parser.add_argument("--keywords-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_ghee_keyword_extractor()
    if args.ignore_robots:
        original_override_paths = base._override_paths

        def override_paths_ignore_robots(cfg, run_dir, use_playwright):
            original_override_paths(cfg, run_dir, use_playwright)
            crawl = cfg.raw.setdefault("crawl", {})
            crawl["respect_robots_txt"] = False

        base._override_paths = override_paths_ignore_robots

    sys.argv = [
        "crawl_sample_keywords.py",
        "--docx",
        str(args.docx),
        "--run-dir",
        str(args.run_dir),
        "--config",
        str(args.config),
    ]
    if args.limit:
        sys.argv.extend(["--limit", str(args.limit)])
    if args.playwright_fallback:
        sys.argv.append("--playwright-fallback")
    if args.ignore_robots:
        # Stored in the ghee wrapper command line; actual config override happens above.
        pass
    if args.keywords_only:
        sys.argv.append("--keywords-only")
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
