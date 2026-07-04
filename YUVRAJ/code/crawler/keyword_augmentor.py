"""Iterative keyword augmentation for Media Cloud discovery.

Algorithm (as described by the professor):

  Round 0 — Seed keywords
    seed_keywords → Media Cloud search → article URLs
    crawl URLs → extract text → keyword_set_0

  Round 1
    keyword_set_0 → Media Cloud search → more article URLs
    crawl new URLs → extract text → keyword_set_1

  Round N — repeat until convergence:
    Jaccard(keyword_set_N, keyword_set_{N-1}) >= convergence_threshold
    OR max_rounds reached
    OR no new keywords added

Keyword extraction uses TF-IDF across all article texts collected so far,
post-filtered to terms that:
  (a) appear in at least min_df articles
  (b) co-occur with at least one oil or adulteration domain term

State is persisted to a JSON file so runs can be resumed.

Usage (via CLI):
  python -m crawler --config config/config_mediacloud.yaml mc-augment
  python -m crawler --config config/config_mediacloud.yaml mc-augment --round 2
"""

from __future__ import annotations

import json
import logging
import re
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .config import Config

logger = logging.getLogger(__name__)

# ── Domain-specific stopwords (terms too generic to be useful keywords) ───────
_DOMAIN_STOPWORDS = {
    "india", "indian", "news", "article", "report", "said", "also", "new",
    "year", "time", "state", "government", "government's", "official",
    "officials", "police", "court", "district", "city", "people", "home",
    "public", "data", "per", "cent", "lakh", "crore", "rupees", "rs",
    "kg", "litre", "litres", "ton", "tonnes", "department", "minister",
    "national", "local", "high", "low", "large", "small", "good", "bad",
    "days", "months", "years", "week", "january", "february", "march",
    "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
}

# Terms that anchor a keyword to the food-safety domain
_OIL_TERMS = {
    "oil", "edible", "mustard", "palm", "groundnut", "soybean", "sunflower",
    "sesame", "coconut", "cottonseed", "vegetable",
    "cooking", "refined", "blended", "rice bran", "rapeseed", "linseed",
    "sarson", "tel",
}
_ADULTERATION_TERMS = {
    "adulter", "spurious", "substandard", "fake", "contaminat", "impure",
    "unsafe", "unhygienic", "mislabel", "misbranding", "seized", "seize",
    "raid", "fssai", "fda", "food safety", "food inspector", "crackdown",
    "arrested", "confiscated", "sample fail", "lab test", "quality test",
    "penalty", "fine", "notice", "warning", "banned", "violation",
}

# English stopword list (minimal, no nltk dependency)
_ENGLISH_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "during",
    "before", "after", "above", "below", "between", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "could", "should", "may", "might", "shall",
    "can", "need", "dare", "ought", "used", "that", "which", "who", "whom",
    "this", "these", "those", "it", "its", "he", "she", "they", "we",
    "you", "i", "me", "him", "her", "us", "them", "my", "your", "his",
    "our", "their", "what", "when", "where", "how", "why", "if", "then",
    "so", "as", "more", "most", "such", "than", "not", "no", "nor",
    "very", "just", "over", "under", "also", "even", "still",
}


class KeywordAugmentor:
    """Manages iterative keyword expansion.

    Parameters
    ----------
    cfg : Config
        Loaded config object. Reads augmentation settings from
        ``augmentation`` section of the YAML.
    storage_path : Path
        Where to persist augmentation state (JSON file).
    """

    def __init__(self, cfg: Config, storage_path: Optional[Path] = None) -> None:
        self.cfg = cfg
        self.max_rounds: int = int(cfg.get("augmentation", "max_rounds") or 5)
        self.convergence_threshold: float = float(
            cfg.get("augmentation", "convergence_threshold") or 0.85
        )
        self.min_df: int = int(cfg.get("augmentation", "min_df") or 2)
        self.max_new_keywords: int = int(cfg.get("augmentation", "max_new_keywords") or 30)
        self.top_n_per_round: int = int(cfg.get("augmentation", "top_n_per_round") or 20)

        if storage_path is None:
            storage_path = Path(cfg.get("paths", "outputs") or "data/outputs") / "augmentation_state.json"
        self.state_path = Path(storage_path)
        self._state: dict = self._load_state()

    # ── State persistence ─────────────────────────────────────────────────────

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "current_round": 0,
            "keyword_rounds": [],     # list of lists, one per round
            "all_keywords": [],       # flat deduplicated list across all rounds
            "article_counts": [],     # articles found per round
            "converged": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Augmentation state saved to %s", self.state_path)

    @property
    def current_round(self) -> int:
        return self._state["current_round"]

    @property
    def all_keywords(self) -> list[str]:
        return self._state["all_keywords"]

    @property
    def converged(self) -> bool:
        return self._state["converged"]

    # ── Keyword sets ──────────────────────────────────────────────────────────

    # Oil-specific anchors included in every round to prevent topic drift.
    # Without these, extracted keywords drift toward generic food safety terms
    # and Media Cloud returns restaurant/hygiene articles unrelated to edible oil.
    _ANCHOR_QUERIES = [
        "edible oil adulteration India",
        "mustard oil adulteration India",
        "FSSAI edible oil raid",
        "adulterated oil seized India",
    ]

    def get_queries_for_round(self, round_num: int) -> list[str]:
        """Return the query list to use for a given round.

        Round 0 uses seed keywords from config.
        Later rounds combine a fixed set of oil-specific anchors with the
        keywords extracted from the previous round's articles.
        """
        if round_num == 0:
            return list(self._load_seed_keywords())

        # Rounds 1+: anchors + previous round's extracted keywords (deduplicated).
        anchor_set = set(q.lower() for q in self._ANCHOR_QUERIES)
        rounds = self._state["keyword_rounds"]
        extracted = []
        if rounds:
            prev_kws = rounds[-1]
            if prev_kws:
                extracted = [k for k in prev_kws if k.lower() not in anchor_set]

        queries = list(self._ANCHOR_QUERIES) + extracted
        return queries[:self.max_new_keywords] if queries else list(self._load_seed_keywords())

    def _load_seed_keywords(self) -> list[str]:
        """Load seed keywords.

        Priority:
          1. augmentation.seed_keywords (inline list in config YAML)
          2. augmentation.seed_keywords_file (path to a YAML file)
          3. Auto-generated food × adulteration combinations
        """
        seeds: list[str] = cfg_list(self.cfg, "augmentation", "seed_keywords")
        if seeds:
            return seeds

        # Try loading from external seed keywords file
        seed_file = self.cfg.get("augmentation", "seed_keywords_file")
        if seed_file:
            from .config import BASE_DIR
            import yaml as _yaml
            seed_path = BASE_DIR / seed_file
            if seed_path.exists():
                try:
                    data = _yaml.safe_load(seed_path.read_text(encoding="utf-8")) or {}
                    seeds = data.get("seed_keywords") or []
                    if seeds:
                        return [str(s) for s in seeds]
                except Exception as exc:
                    logger.warning("Could not load seed keywords file %s: %s", seed_path, exc)

        # Final fallback: auto-generate from config term lists
        seeds = [
            f"{ft} {at} India"
            for ft in (self.cfg.food_terms or [])[:5]
            for at in (self.cfg.adulteration_terms or [])[:3]
        ]
        return seeds

    # ── Keyword extraction ────────────────────────────────────────────────────

    def extract_keywords_from_texts(
        self, texts: list[str], prev_keywords: Optional[set[str]] = None
    ) -> list[str]:
        """Extract candidate keywords from a list of article texts.

        Tries three methods in order:
          1. YAKE (if installed) — unsupervised, no training data needed
          2. scikit-learn TF-IDF — classic statistical approach
          3. Frequency-based fallback — simple word frequency

        Returns a deduplicated, domain-filtered, ranked list of new keywords.
        """
        if not texts:
            return []

        prev_set = set(k.lower() for k in (prev_keywords or []))

        # Try YAKE first
        candidates = self._extract_yake(texts)

        # Fall back to TF-IDF
        if not candidates:
            candidates = self._extract_tfidf(texts)

        # Last resort: word frequency
        if not candidates:
            candidates = self._extract_frequency(texts)

        # Post-filter: domain relevance + novelty
        new_keywords = []
        seen: set[str] = set()
        for kw in candidates:
            kw_lower = kw.lower().strip()
            if kw_lower in seen or kw_lower in prev_set:
                continue
            if not self._is_domain_relevant(kw_lower, texts):
                continue
            if len(kw_lower) < 4:
                continue
            # Require at least 2 words — single terms are too generic as search queries
            if len(kw_lower.split()) < 2:
                continue
            seen.add(kw_lower)
            new_keywords.append(kw)
            if len(new_keywords) >= self.top_n_per_round:
                break

        return new_keywords

    def _extract_yake(self, texts: list[str]) -> list[str]:
        try:
            import yake  # type: ignore
            kw_extractor = yake.KeywordExtractor(
                lan="en", n=3, dedupLim=0.7, top=50, features=None
            )
            # Concatenate all texts with some separation
            combined = " ".join(t[:2000] for t in texts[:50])
            raw = kw_extractor.extract_keywords(combined)
            # YAKE returns (keyword, score) sorted by score ascending (lower = better)
            keywords = [kw for kw, _ in raw]
            return self._filter_stopwords(keywords)
        except ImportError:
            return []
        except Exception as exc:
            logger.debug("YAKE extraction failed: %s", exc)
            return []

    def _extract_tfidf(self, texts: list[str]) -> list[str]:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
            import numpy as np  # type: ignore
        except ImportError:
            return []

        if len(texts) < 2:
            # TF-IDF needs at least 2 docs; use the same text twice
            texts = texts * 2

        try:
            vec = TfidfVectorizer(
                ngram_range=(1, 3),
                min_df=min(self.min_df, len(texts)),
                max_df=0.85,
                stop_words=list(_ENGLISH_STOPWORDS | _DOMAIN_STOPWORDS),
                sublinear_tf=True,
                max_features=500,
            )
            X = vec.fit_transform(texts)
            feature_names = vec.get_feature_names_out()
            # Sum TF-IDF scores across all documents for ranking
            scores = np.asarray(X.sum(axis=0)).flatten()
            top_idx = scores.argsort()[::-1][:100]
            keywords = [feature_names[i] for i in top_idx]
            return self._filter_stopwords(keywords)
        except Exception as exc:
            logger.debug("TF-IDF extraction failed: %s", exc)
            return []

    def _extract_frequency(self, texts: list[str]) -> list[str]:
        """Simple bigram/trigram frequency fallback."""
        from collections import Counter
        combined = " ".join(texts).lower()
        # Remove punctuation
        combined = re.sub(r"[^\w\s]", " ", combined)
        tokens = [t for t in combined.split() if t not in _ENGLISH_STOPWORDS | _DOMAIN_STOPWORDS and len(t) > 3]
        bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens)-1)]
        trigrams = [f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}" for i in range(len(tokens)-2)]
        counts = Counter(bigrams + trigrams)
        return [kw for kw, _ in counts.most_common(100)]

    def _filter_stopwords(self, keywords: list[str]) -> list[str]:
        result = []
        for kw in keywords:
            tokens = kw.lower().split()
            if all(t in _ENGLISH_STOPWORDS | _DOMAIN_STOPWORDS for t in tokens):
                continue
            if all(t in string.punctuation for t in tokens):
                continue
            result.append(kw)
        return result

    def _is_domain_relevant(self, kw: str, texts: list[str]) -> bool:
        """Return True if kw co-occurs with oil/adulteration terms in ≥ min_df texts."""
        # Quick check: does the keyword itself contain a domain term?
        for term in _OIL_TERMS | _ADULTERATION_TERMS:
            if term in kw:
                return True
        # Slower check: count documents where kw appears near a domain term
        hits = 0
        kw_re = re.compile(re.escape(kw), re.I)
        for text in texts:
            if not kw_re.search(text):
                continue
            tl = text.lower()
            if any(term in tl for term in _OIL_TERMS | _ADULTERATION_TERMS):
                hits += 1
            if hits >= self.min_df:
                return True
        return False

    # ── Round management ──────────────────────────────────────────────────────

    def record_round(self, round_num: int, new_keywords: list[str], article_count: int) -> None:
        """Record the result of a completed augmentation round."""
        # Extend round history
        while len(self._state["keyword_rounds"]) <= round_num:
            self._state["keyword_rounds"].append([])
        while len(self._state["article_counts"]) <= round_num:
            self._state["article_counts"].append(0)

        self._state["keyword_rounds"][round_num] = new_keywords
        self._state["article_counts"][round_num] = article_count

        # Update global keyword set (deduplicated)
        existing = set(k.lower() for k in self._state["all_keywords"])
        for kw in new_keywords:
            if kw.lower() not in existing:
                self._state["all_keywords"].append(kw)
                existing.add(kw.lower())

        self._state["current_round"] = round_num + 1

    def check_convergence(self, round_num: int) -> tuple[bool, float]:
        """Return (converged, jaccard_similarity) for the most recent round pair.

        Convergence means the keyword sets from successive rounds are
        highly similar — we are no longer discovering substantially new
        vocabulary.
        """
        rounds = self._state["keyword_rounds"]
        if round_num < 1 or len(rounds) < 2:
            return False, 0.0

        prev_set = set(k.lower() for k in rounds[round_num - 1])
        curr_set = set(k.lower() for k in rounds[round_num])
        if not prev_set and not curr_set:
            return True, 1.0
        union = prev_set | curr_set
        inter = prev_set & curr_set
        jaccard = len(inter) / len(union) if union else 1.0

        converged = jaccard >= self.convergence_threshold
        if converged:
            self._state["converged"] = True

        return converged, jaccard

    def summary(self) -> str:
        """Return a human-readable summary of augmentation progress."""
        rounds = self._state["keyword_rounds"]
        lines = [
            "── Keyword Augmentation State ──",
            f"  Rounds completed : {self._state['current_round']}",
            f"  Total keywords   : {len(self._state['all_keywords'])}",
            f"  Converged        : {self._state['converged']}",
            "",
        ]
        for i, (kws, count) in enumerate(
            zip(rounds, self._state.get("article_counts", []))
        ):
            lines.append(f"  Round {i}: {count} articles, {len(kws)} new keywords")
            for kw in kws[:5]:
                lines.append(f"    - {kw}")
            if len(kws) > 5:
                lines.append(f"    ... ({len(kws) - 5} more)")
        return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

def cfg_list(cfg: Config, *keys: str) -> list[str]:
    """Extract a list value from config, handling None and scalars."""
    val = cfg.get(*keys)
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v) for v in val]
    return [str(val)]
