"""
scrape_fulltext.py

Responsibility: given a list of URLs you've already decided are worth
keeping (i.e. they passed filter_relevance.score_article), fetch and
extract clean full-text using trafilatura.

Deliberately NOT called on every raw API hit — Media Cloud/GDELT results
usually include enough metadata (title, snippet, sometimes full text
already) to run the relevance filter without scraping. Only scrape the
survivors. This keeps the slow, network-heavy, fragile part of the
pipeline as small as possible.
"""

from __future__ import annotations
import time
import requests
import trafilatura
import logging

logger = logging.getLogger("milk_pipeline")

def scrape(urls: list[str], timeout_seconds: int = 15) -> list[dict]:
    """
    Scrape full article text from a list of URLs using trafilatura.
    """
    results = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for url in urls:
        logger.info(f"Scraping: {url}")
        article_data = {
            "url": url,
            "title": "",
            "text": "",
            "scrape_success": False,
            "error": None
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
            
            html = response.text
            extracted = trafilatura.extract(
                html, 
                include_comments=False, 
                include_tables=False, 
                no_fallback=False
            )
            
            if extracted:
                article_data["text"] = extracted
                # Trafilatura can also extract metadata, let's grab title if possible
                metadata = trafilatura.extract_metadata(html)
                if metadata and metadata.title:
                    article_data["title"] = metadata.title
                article_data["scrape_success"] = True
            else:
                article_data["error"] = "Trafilatura returned None (no text extracted)"
                
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            article_data["error"] = str(e)
            
        results.append(article_data)
        time.sleep(1) # Be polite
        
    return results
