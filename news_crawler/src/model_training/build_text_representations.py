"""Build the four text representations used by all classifiers.

Representations
---------------
title_only              : headline only (metadata-stage baseline)
body_only               : full article text only
title_plus_body         : title + body, truncated to max_chars
title_plus_keyword_windows : title + sentence windows that contain any
                             oil/adulteration keyword (most information-dense)
"""

from __future__ import annotations

import re
from typing import Sequence

import pandas as pd

# ── Keyword list ──────────────────────────────────────────────────────────────

OIL_TERMS = [
    "edible oil", "cooking oil", "mustard oil", "refined oil", "palm oil",
    "soybean oil", "soya oil", "groundnut oil", "sesame oil", "sunflower oil",
    "rice bran oil", "cottonseed oil", "argemone oil",
    "vegetable oil", "canola oil", "olive oil",
]
# NOTE: "ghee" and "vanaspati" are deliberately EXCLUDED — they were hard
# exclusions at discovery and must not act as positive oil keywords here.

ADULTERATION_TERMS = [
    "adulterated", "adulteration", "fake", "spurious", "misbranded",
    "substandard", "unsafe", "seized", "raid", "raided", "sample failed",
    "failed test", "food safety", "FSSAI", "FDA", "FSDA", "food adulteration",
    "food fraud", "counterfeit", "sub-standard", "unfit", "contaminated",
    "mislabelled", "mislabeled",
]

KEYWORD_TERMS = OIL_TERMS + ADULTERATION_TERMS

# Build a single compiled regex for fast sentence matching
_keyword_pattern = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in sorted(KEYWORD_TERMS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# ── Sentence splitter ─────────────────────────────────────────────────────────

_sentence_split = re.compile(r"(?<=[.!?])\s+(?=[A-Zऀ-ॿ‘“\d\"])")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation heuristics."""
    sentences = _sentence_split.split(text.strip())
    # Further split on newlines (paragraph breaks in crawled text)
    result = []
    for s in sentences:
        for line in s.splitlines():
            line = line.strip()
            if line:
                result.append(line)
    return result if result else [text]


# ── Individual representation builders ───────────────────────────────────────

def title_only(title: str, _text: str = "") -> str:
    return title.strip()


def body_only(_title: str, text: str) -> str:
    return text.strip()


def title_plus_body(title: str, text: str, max_chars: int = 15_000) -> str:
    combined = f"{title.strip()}\n\n{text.strip()}"
    return combined[:max_chars]


def title_plus_keyword_windows(
    title: str,
    text: str,
    window: int = 1,
    max_windows: int = 20,
) -> str:
    """Title + sentence windows around keyword hits (±window sentences)."""
    sentences = split_sentences(text)
    if not sentences:
        return title_plus_body(title, text)

    hit_indices: set[int] = set()
    for i, sent in enumerate(sentences):
        if _keyword_pattern.search(sent):
            for j in range(max(0, i - window), min(len(sentences), i + window + 1)):
                hit_indices.add(j)

    if not hit_indices:
        # No keyword hits — fall back to first 30 sentences + title
        window_text = " ".join(sentences[:30])
    else:
        window_text = " ".join(sentences[i] for i in sorted(hit_indices))
        if len(hit_indices) < max_windows:
            # Prepend first 2 sentences as context
            prefix = " ".join(sentences[:2])
            window_text = f"{prefix} {window_text}".strip()

    return f"{title.strip()}\n\n{window_text}"


# ── Oil-only pattern (for title_plus_oil_windows) ─────────────────────────────

_oil_pattern = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in sorted(OIL_TERMS, key=len, reverse=True)) + r"|\boil\b)\b",
    re.IGNORECASE,
)


def title_plus_body_full(title: str, text: str) -> str:
    """Full title + full article body — NO truncation."""
    return f"{title.strip()}\n\n{text.strip()}".strip()


def title_plus_oil_windows(title: str, text: str, window: int = 1) -> str:
    """Title + first paragraph + every oil-related sentence (±1 sentence)."""
    sentences = split_sentences(text)
    if not sentences:
        return f"{title.strip()}\n\n{text.strip()}".strip()

    # First paragraph = text before the first blank line, else first 2 sentences.
    first_block = text.strip().split("\n\n", 1)[0].strip()
    first_para_sents = split_sentences(first_block) if first_block else sentences[:2]

    keep_idx: set[int] = set()
    for i, sent in enumerate(sentences):
        if _oil_pattern.search(sent):
            for j in range(max(0, i - window), min(len(sentences), i + window + 1)):
                keep_idx.add(j)

    window_text = " ".join(sentences[i] for i in sorted(keep_idx))
    parts = [title.strip(), " ".join(first_para_sents).strip(), window_text.strip()]
    seen, out = set(), []
    for part in parts:
        if part and part not in seen:
            seen.add(part)
            out.append(part)
    return "\n\n".join(out)


def build_final_representations(df: pd.DataFrame) -> dict[str, list[str]]:
    """The three representations used by the final model run."""
    titles = df["title"].fillna("").astype(str).tolist()
    bodies = df["article_text"].fillna("").astype(str).tolist()
    builders = {
        "title_plus_body_full":       title_plus_body_full,
        "title_plus_oil_windows":     title_plus_oil_windows,
        "title_plus_keyword_windows": title_plus_keyword_windows,
    }
    result: dict[str, list[str]] = {}
    for name, fn in builders.items():
        result[name] = [fn(t, b) for t, b in zip(titles, bodies)]
        avg_len = sum(len(s) for s in result[name]) / max(len(result[name]), 1)
        print(f"  Representation '{name}': {len(result[name])} texts, avg {avg_len:.0f} chars")
    return result


# ── Main builder ──────────────────────────────────────────────────────────────

REPR_NAMES = ["title_only", "body_only", "title_plus_body", "title_plus_keyword_windows"]

_BUILDER_MAP = {
    "title_only": title_only,
    "body_only": body_only,
    "title_plus_body": title_plus_body,
    "title_plus_keyword_windows": title_plus_keyword_windows,
    "title_plus_body_full": title_plus_body_full,
    "title_plus_oil_windows": title_plus_oil_windows,
}


def build_representations(df: pd.DataFrame) -> dict[str, list[str]]:
    """Return a dict mapping each representation name to a list of text strings."""
    titles = df["title"].fillna("").astype(str).tolist()
    bodies = df["article_text"].fillna("").astype(str).tolist()

    result: dict[str, list[str]] = {}
    for name, fn in _BUILDER_MAP.items():
        result[name] = [fn(t, b) for t, b in zip(titles, bodies)]
        avg_len = sum(len(s) for s in result[name]) / max(len(result[name]), 1)
        print(f"  Representation '{name}': {len(result[name])} texts, "
              f"avg {avg_len:.0f} chars")
    return result


def build_single(title: str, text: str, repr_name: str) -> str:
    """Build one text representation for a single article (inference time)."""
    if repr_name not in _BUILDER_MAP:
        raise ValueError(f"Unknown representation: {repr_name!r}. "
                         f"Choose from {list(_BUILDER_MAP)}")
    return _BUILDER_MAP[repr_name](title, text)
