"""Build text representations tailored for Milk and Dairy Adulteration articles."""
from __future__ import annotations
import re
import pandas as pd

# ── Milk & Dairy Domain Lexicons ──────────────────────────────────────────────

MILK_TERMS = [
    "milk", "dairy", "paneer", "khoya", "mawa", "curd", "dahi", "ghee",
    "butter", "cheese", "cream", "toned milk", "full cream milk", "raw milk",
    "skimmed milk", "milk powder", "Aavin", "Amul", "KMF", "dairy cooperative"
]

ADULTERATION_TERMS = [
    "adulterated", "adulteration", "fake", "spurious", "misbranded",
    "substandard", "unsafe", "seized", "raid", "raided", "sample failed",
    "failed test", "food safety", "FSSAI", "FDA", "FSDA", "food adulteration",
    "food fraud", "counterfeit", "sub-standard", "unfit", "contaminated",
    "mislabelled", "mislabeled", "synthetic milk", "watered down", "urea",
    "maltodextrin", "detergent", "starch", "solids-not-fat", "SNF", "fat content"
]

KEYWORD_TERMS = MILK_TERMS + ADULTERATION_TERMS

# Regex patterns
_keyword_pattern = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in sorted(KEYWORD_TERMS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

_milk_pattern = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in sorted(MILK_TERMS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

_sentence_split = re.compile(r"(?<=[.!?])\s+(?=[A-Zऀ-ॿ‘“\d\"])")

def split_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation and newline heuristics."""
    sentences = _sentence_split.split(text.strip())
    result = []
    for s in sentences:
        for line in s.splitlines():
            line = line.strip()
            if line:
                result.append(line)
    return result if result else [text]

# ── Representation Builders ────────────────────────────────────────────────---

def title_plus_body_full(title: str, text: str) -> str:
    """Full title + full article body (untruncated)."""
    return f"{title.strip()}\n\n{text.strip()}".strip()

def title_plus_milk_windows(title: str, text: str, window: int = 1) -> str:
    """Title + first paragraph + every milk-related sentence (±1 sentence)."""
    sentences = split_sentences(text)
    if not sentences:
        return f"{title.strip()}\n\n{text.strip()}".strip()
        
    # First paragraph context
    first_block = text.strip().split("\n\n", 1)[0].strip()
    first_para_sents = split_sentences(first_block) if first_block else sentences[:2]
    
    keep_idx: set[int] = set()
    for i, sent in enumerate(sentences):
        if _milk_pattern.search(sent):
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

def title_plus_keyword_windows(title: str, text: str, window: int = 1, max_windows: int = 15) -> str:
    """Title + sentence windows around milk OR adulteration keyword hits."""
    sentences = split_sentences(text)
    if not sentences:
        return title_plus_body_full(title, text)
        
    hit_indices: set[int] = set()
    for i, sent in enumerate(sentences):
        if _keyword_pattern.search(sent):
            for j in range(max(0, i - window), min(len(sentences), i + window + 1)):
                hit_indices.add(j)
                
    if not hit_indices:
        window_text = " ".join(sentences[:30])
    else:
        window_text = " ".join(sentences[i] for i in sorted(hit_indices))
        if len(hit_indices) < max_windows:
            prefix = " ".join(sentences[:2])
            window_text = f"{prefix} {window_text}".strip()
            
    return f"{title.strip()}\n\n{window_text}"

def build_final_representations(df: pd.DataFrame) -> dict[str, list[str]]:
    """Build the three main text representations used across all models."""
    titles = df["title"].fillna("").astype(str).tolist()
    bodies = df["article_text"].fillna("").astype(str).tolist()
    
    builders = {
        "title_plus_body_full": title_plus_body_full,
        "title_plus_milk_windows": title_plus_milk_windows,
        "title_plus_keyword_windows": title_plus_keyword_windows,
    }
    
    result: dict[str, list[str]] = {}
    for name, fn in builders.items():
        result[name] = [fn(t, b) for t, b in zip(titles, bodies)]
        avg_len = sum(len(s) for s in result[name]) / max(len(result[name]), 1)
        print(f" Representation '{name}': {len(result[name])} texts, avg {avg_len:.0f} chars")
    return result

def build_single(title: str, text: str, repr_name: str) -> str:
    """Build one text representation for a single article (Inference time)."""
    _BUILDER_MAP = {
        "title_plus_body_full": title_plus_body_full,
        "title_plus_milk_windows": title_plus_milk_windows,
        "title_plus_keyword_windows": title_plus_keyword_windows,
    }
    if repr_name not in _BUILDER_MAP:
        raise ValueError(f"Unknown representation: {repr_name!r}")
    return _BUILDER_MAP[repr_name](title, text)
