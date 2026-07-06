"""
extract_keywords.py

Responsibility: turn a list of articles into ranked candidate keywords using KeyBERT.
"""

from __future__ import annotations
import logging
from typing import List, Tuple

try:
    from keybert import KeyBERT
except ImportError:
    KeyBERT = None

logger = logging.getLogger("milk_pipeline")

# Initialize model once to avoid reloading for every batch
_kw_model = None

def _get_model():
    global _kw_model
    if _kw_model is None:
        if KeyBERT is None:
            raise ImportError("KeyBERT is not installed. Please install it with 'pip install keybert'")
        logger.info("Loading KeyBERT model...")
        _kw_model = KeyBERT()
    return _kw_model

def extract_keywords(
    articles: list[dict],
    max_ngram_size: int = 3,
    dedup_threshold: float = 0.9, # Note: Not used directly by basic KeyBERT, can use MMR or MaxSum
    top_n: int | None = None,
) -> list[tuple[str, float]]:
    """
    Extract ranked keyword candidates from a batch of articles using KeyBERT.
    KeyBERT score convention: HIGHER = more relevant.
    """
    if not articles:
        raise ValueError("Articles list is empty")

    kw_model = _get_model()

    # Concatenate title and text for each article
    corpus_docs = []
    for art in articles:
        text = art.get("text", "")
        title = art.get("title", "")
        full_text = f"{title} {text}".strip()
        if full_text:
            corpus_docs.append(full_text)
            
    if not corpus_docs:
        raise ValueError("No usable text found in articles")

    logger.info(f"Extracting keywords from {len(corpus_docs)} documents using KeyBERT...")
    
    # We can either extract per-document and aggregate, or join the entire corpus.
    # Joining corpus usually extracts the most globally common themes.
    # We'll do a combined approach: extract per document, average scores.
    
    keyword_scores = {}
    keyword_counts = {}
    
    for doc in corpus_docs:
        # Extract keywords with unigram to trigram
        keywords = kw_model.extract_keywords(
            doc, 
            keyphrase_ngram_range=(1, max_ngram_size), 
            stop_words='english',
            use_mmr=True, # MMR for diversity
            diversity=0.7,
            top_n=20
        )
        for kw, score in keywords:
            kw_lower = kw.lower()
            keyword_scores[kw_lower] = keyword_scores.get(kw_lower, 0) + score
            keyword_counts[kw_lower] = keyword_counts.get(kw_lower, 0) + 1
            
    # Average the scores
    avg_scores = [(kw, score / keyword_counts[kw]) for kw, score in keyword_scores.items()]
    
    # Sort best-first (descending order for KeyBERT)
    sorted_keywords = sorted(avg_scores, key=lambda x: x[1], reverse=True)
    
    if top_n is not None:
        sorted_keywords = sorted_keywords[:top_n]
        
    return sorted_keywords


def merge_keyword_rounds(
    previous_keywords: list[str],
    new_candidates: list[tuple[str, float]],
    top_n: int,
) -> list[str]:
    """
    Combine keywords carried over from a previous round with newly
    extracted candidates, for use in round 2+ of the pipeline.
    """
    # Keep the top 3 previous keywords as anchor
    anchor_count = min(3, len(previous_keywords))
    anchors = previous_keywords[:anchor_count]
    
    # Fill the rest with new candidates
    merged = list(anchors)
    for kw, score in new_candidates:
        if kw not in merged:
            merged.append(kw)
        if len(merged) >= top_n:
            break
            
    return merged
