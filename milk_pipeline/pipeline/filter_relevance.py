"""
filter_relevance.py

Responsibility: filter keywords and score articles.
"""

from __future__ import annotations
import logging

logger = logging.getLogger("milk_pipeline")

def filter_keywords(
    candidates: list[tuple[str, float]],
    blocklist: set[str],
    top_n: int,
) -> list[str]:
    """
    Filter KeyBERT's raw candidate keywords down to a clean, bounded list.
    """
    clean = []
    
    for kw, score in candidates:
        kw_lower = kw.lower()
        
        # Check against blocklist
        blocked = False
        for bad_term in blocklist:
            if bad_term in kw_lower:
                blocked = True
                break
                
        if not blocked:
            # Maybe also skip pure numbers or very short keywords
            if not kw_lower.isnumeric() and len(kw_lower) > 2:
                clean.append(kw_lower)
                
        if len(clean) >= top_n:
            break
            
    return clean


def score_article(
    article: dict,
    seed_keywords: list[str],
    min_matches: int,
    blocklist: set[str] | None = None,
) -> float:
    """
    Score a single fetched article for topical relevance.

    Matches against title + text + URL (URL is always populated from Media Cloud
    even when full text is absent). Keywords are decomposed into individual tokens
    so "milk adulteration detected" → ["milk", "adulteration", "detected"], meaning
    any token found anywhere in the article counts as a partial match.
    
    If the article's text, title, or URL contains any keyword from the blocklist,
    it automatically scores 0.0.
    """
    # URL contains keywords even when text is empty (e.g. /milk-adulteration-case/)
    corpus = " ".join([
        article.get("title", ""),
        article.get("text", ""),
        article.get("url", ""),
    ]).lower()

    if blocklist:
        for bad_term in blocklist:
            if bad_term.lower() in corpus:
                return 0.0

    matches = 0
    for kw in seed_keywords:
        # Decompose multi-word phrases / boolean-AND terms into tokens
        tokens = kw.lower().replace(" and ", " ").split()
        # Count this keyword as matched if ANY of its tokens appear in the corpus
        if any(tok in corpus for tok in tokens if len(tok) > 2):
            matches += 1

    return float(matches)
