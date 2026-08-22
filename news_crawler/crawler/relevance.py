"""Relevance scoring for edible oil adulteration articles.

Layer 1: Rule-based weighted scoring (always runs).
Layer 2: Zero-shot classification hook (stub — wire in an LLM/model later).

Score is in [0.0, 1.0]. Labels:
  relevant       ≥ min_score_relevant (default 0.55)
  maybe_relevant ≥ min_score_maybe    (default 0.25)
  irrelevant     < min_score_maybe
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from .config import Config

logger = logging.getLogger(__name__)

# ── Patterns that indicate NON-relevant articles ──────────────────────────────
_REJECT_PATTERNS = [
    re.compile(r"\b(recipe|how to cook|cooking tips|nutritional value|calorie|calories)\b", re.I),
    re.compile(r"\b(stock market|commodity price|futures|MCX|NCDEX|global market)\b", re.I),
    re.compile(r"\bhow to (check|test|identify) (pure|purity|quality)\b", re.I),
    re.compile(r"\b(buy online|add to cart|buy now|shop|price per litre|per kg)\b", re.I),
    re.compile(r"\bbenefits of (eating|consuming|using)\b", re.I),
]

# Patterns that indicate location is India
_INDIA_PATTERNS = [
    re.compile(r"\b(india|indian|fssai|food safety and standards|up|uttar pradesh|"
               r"maharashtra|delhi|rajasthan|punjab|haryana|gujarat|bihar|west bengal|"
               r"madhya pradesh|karnataka|tamil nadu|kerala|andhra pradesh|telangana|"
               r"odisha|jharkhand|assam|chhattisgarh|himachal|uttarakhand|"
               r"hyderabad|mumbai|kolkata|chennai|bengaluru|bangalore|jaipur|lucknow|"
               r"kanpur|varanasi|patna|noida|ahmedabad)\b", re.I),
]


@dataclass
class RelevanceResult:
    score: float
    label: str
    food_terms_found: list[str] = field(default_factory=list)
    adulteration_terms_found: list[str] = field(default_factory=list)
    action_terms_found: list[str] = field(default_factory=list)
    location_terms_found: list[str] = field(default_factory=list)
    incident_terms_found: list[str] = field(default_factory=list)
    reject_reason: Optional[str] = None


class RelevanceScorer:
    """Rule-based relevance scorer."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

        thresh_cfg = cfg.get("relevance") or {}
        self.threshold_relevant = float(thresh_cfg.get("min_score_relevant", 0.55))
        self.threshold_maybe = float(thresh_cfg.get("min_score_maybe", 0.25))
        self.require_india = bool(thresh_cfg.get("require_india_term", True))
        self.require_oil = bool(thresh_cfg.get("require_oil_term", True))
        self.require_adulteration = bool(thresh_cfg.get("require_adulteration_or_action_term", True))

        w = (thresh_cfg.get("weights") or {})
        self.w_oil_hit = float(w.get("oil_term_hit", 0.25))
        self.w_oil_cap = float(w.get("oil_term_cap", 0.30))
        self.w_adul_hit = float(w.get("adulteration_term_hit", 0.20))
        self.w_adul_cap = float(w.get("adulteration_term_cap", 0.25))
        self.w_act_hit = float(w.get("action_term_hit", 0.15))
        self.w_act_cap = float(w.get("action_term_cap", 0.20))
        self.w_india = float(w.get("location_india_hit", 0.10))
        self.w_state = float(w.get("location_state_hit", 0.05))
        self.w_loc_cap = float(w.get("location_cap", 0.15))
        self.w_date = float(w.get("date_in_range", 0.10))

        # Compile term patterns
        self._oil_pats = _compile(cfg.food_terms)
        self._adul_pats = _compile(cfg.adulteration_terms)
        self._act_pats = _compile(cfg.action_terms)
        self._loc_pats = _compile(cfg.location_terms)
        # Broad India terms for the hard filter
        self._india_pats = _INDIA_PATTERNS

    def score(
        self,
        text: str,
        title: str = "",
        url: str = "",
        publication_date: Optional[str] = None,
    ) -> RelevanceResult:
        """Score a single article.  *text* should be the cleaned article body."""
        corpus = f"{title} {text}".lower()
        corpus_url = f"{corpus} {url}".lower()

        # ── Hard rejection ────────────────────────────────────────────
        for pat in _REJECT_PATTERNS:
            if pat.search(corpus):
                return RelevanceResult(
                    score=0.0,
                    label="irrelevant",
                    reject_reason=f"reject pattern: {pat.pattern[:60]}",
                )

        # ── Term matching ─────────────────────────────────────────────
        oil_found = _find_terms(self._oil_pats, corpus_url, cfg_terms=self.cfg.food_terms)
        adul_found = _find_terms(self._adul_pats, corpus_url, cfg_terms=self.cfg.adulteration_terms)
        act_found = _find_terms(self._act_pats, corpus_url, cfg_terms=self.cfg.action_terms)
        loc_found = _find_terms(self._loc_pats, corpus_url, cfg_terms=self.cfg.location_terms)

        # ── Hard filter (require conditions) ─────────────────────────
        has_india = any(p.search(corpus_url) for p in self._india_pats)
        if self.require_india and not has_india:
            return RelevanceResult(
                score=0.0,
                label="irrelevant",
                food_terms_found=oil_found,
                reject_reason="no India/location term found",
            )

        if self.require_oil and not oil_found:
            return RelevanceResult(
                score=0.0,
                label="irrelevant",
                reject_reason="no oil/food term found",
            )

        if self.require_adulteration and not (adul_found or act_found):
            return RelevanceResult(
                score=0.05,
                label="irrelevant",
                food_terms_found=oil_found,
                location_terms_found=loc_found,
                reject_reason="no adulteration or action term found",
            )

        # ── Weighted scoring ──────────────────────────────────────────
        score = 0.0

        # Oil terms (each unique term adds weight, capped)
        score += min(len(oil_found) * self.w_oil_hit, self.w_oil_cap)

        # Adulteration terms
        score += min(len(adul_found) * self.w_adul_hit, self.w_adul_cap)

        # Action terms (enforcement signals)
        score += min(len(act_found) * self.w_act_hit, self.w_act_cap)

        # Location bonus
        loc_score = 0.0
        if has_india:
            loc_score += self.w_india
        # State/city mentions beyond bare "India"
        non_india = [t for t in loc_found if t.lower() not in ("india", "indian")]
        if non_india:
            loc_score += self.w_state
        score += min(loc_score, self.w_loc_cap)

        # Date bonus
        if publication_date and _date_in_range(
            publication_date, self.cfg.date_start, self.cfg.date_end
        ):
            score += self.w_date

        score = round(min(score, 1.0), 4)

        # ── Label ─────────────────────────────────────────────────────
        if score >= self.threshold_relevant:
            label = "relevant"
        elif score >= self.threshold_maybe:
            label = "maybe_relevant"
        else:
            label = "irrelevant"

        return RelevanceResult(
            score=score,
            label=label,
            food_terms_found=oil_found,
            adulteration_terms_found=adul_found,
            action_terms_found=act_found,
            location_terms_found=loc_found,
        )

    # ── Layer 2 stub ──────────────────────────────────────────────────

    def classify_zero_shot(self, text: str) -> Optional[str]:
        """Stub for future zero-shot LLM/model classification.

        Returns one of:
          'relevant_edible_oil_adulteration_incident'
          'general_food_safety'
          'recipe_consumer_advice'
          'commodity_price'
          'unrelated'
        """
        raise NotImplementedError(
            "Zero-shot classification not yet implemented. "
            "Integrate a HuggingFace pipeline or LLM call here."
        )


# ── URL-level pre-filter (fast, no HTML download needed) ─────────────────────

_TITLE_SIGNAL_PATS = [
    re.compile(r"\b(adulter|spurious|substandard|seized|seize|fake|contaminat|"
               r"fssai|fda|food safety|food inspector|crackdown|arrested|confiscated|"
               r"unsafe|unhygienic|misbranding|mislabel|regulatory warning|"
               r"food authority|food standard|quality test|lab test|sample fail|"
               r"busted|raid|raided|penalty|violation|food law|license cancel)\b", re.I),
    re.compile(r"\b(oil|mustard|edible|cooking oil|vegetable oil)\b"
               r".*?"
               r"\b(ban|quality|test|sample|standard|violation|penalty|fine|"
               r"notice|warning|seized|raid|adulterat|fake|spurious|unsafe)\b", re.I),
    re.compile(r"\b(ban|quality test|seized|raid|fine|warning|violation|penalty)\b"
               r".*?"
               r"\b(oil|mustard|edible|cooking oil)\b", re.I),
]

_LIFESTYLE_URL_PATS = [
    re.compile(r"/(lifestyle|health-tips|wellness|beauty|fitness|weight-loss|"
               r"diet-tips|home-remedies|natural-remedies)/", re.I),
    re.compile(r"/(top-\d+|10-best|10-uses|best-\d+|tips-for|how-to-use|"
               r"benefits-of|uses-of)-", re.I),
]


def url_looks_relevant(url: str, title_snippet: str = "") -> bool:
    """Quick pre-filter: return False for obvious non-articles.

    Two checks:
    1. Block URLs with explicit lifestyle/recipe/e-commerce path segments.
    2. If a non-empty title snippet is provided, require at least one
       adulteration/enforcement signal word so Yahoo lifestyle & health
       articles don't slip through.
    """
    combined = f"{url} {title_snippet}".lower()
    # Block obvious non-article URL patterns
    block_url_pats = [
        r"/recipe", r"/cooking-tips", r"/how-to-cook", r"/buy-", r"/shop/",
        r"/product/", r"/category/oil-", r"amazon\.", r"flipkart\.",
        r"bigbasket\.", r"swiggy\.", r"zomato\.", r"/stock-", r"/market-price",
        r"wikipedia\.org", r"youtube\.com", r"/video/",
        r"msn\.com",
    ]
    for pat in block_url_pats:
        if re.search(pat, combined):
            return False

    # Block lifestyle section URLs (Yahoo, Healthline, WebMD etc.)
    for pat in _LIFESTYLE_URL_PATS:
        if pat.search(url):
            return False

    # If we have a title snippet, require at least one enforcement/adulteration signal
    if title_snippet and len(title_snippet) > 15:
        if not any(p.search(title_snippet) for p in _TITLE_SIGNAL_PATS):
            return False

    return True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compile(terms: list[str]) -> list[tuple[re.Pattern, str]]:
    """Return list of (pattern, original_term)."""
    patterns = []
    for t in terms:
        try:
            pat = re.compile(r"\b" + re.escape(t.lower()) + r"\b")
            patterns.append((pat, t))
        except re.error:
            pass
    return patterns


def _find_terms(
    patterns: list[tuple[re.Pattern, str]], text: str, cfg_terms: list[str]
) -> list[str]:
    found = []
    for pat, term in patterns:
        if pat.search(text):
            found.append(term)
    return found


def _date_in_range(date_str: str, start: str, end: str) -> bool:
    try:
        return start <= date_str[:10] <= end
    except Exception:
        return False
