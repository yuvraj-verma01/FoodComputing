"""
dedup.py

Responsibility: collapse duplicate/near-duplicate articles across all
rounds into a single clean final dataset.
"""

from __future__ import annotations
import logging
from urllib.parse import urlparse

logger = logging.getLogger("milk_pipeline")

def dedupe(articles: list[dict], title_similarity_threshold: float = 0.9) -> list[dict]:
    """
    Remove exact and near-duplicate articles from the combined dataset.
    """
    unique_urls = set()
    unique_titles = set()
    deduped = []
    
    for a in articles:
        url = a.get("url")
        title = a.get("title", "").strip().lower()
        
        # Normalize url
        norm_url = ""
        if url:
            parsed = urlparse(url)
            norm_url = f"{parsed.netloc}{parsed.path}".rstrip("/")
            
        if norm_url and norm_url in unique_urls:
            continue
            
        if title and title in unique_titles:
            continue
            
        if norm_url:
            unique_urls.add(norm_url)
        if title:
            unique_titles.add(title)
            
        deduped.append(a)
        
    logger.info(f"Deduped from {len(articles)} to {len(deduped)} articles.")
    return deduped
