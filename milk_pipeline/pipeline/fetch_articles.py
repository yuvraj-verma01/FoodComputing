"""
fetch_articles.py

Responsibility: fetch articles from Media Cloud.
"""

from __future__ import annotations
from datetime import date
import logging
import os
import sys
import time
import requests

# Import config for collection IDs — handle running from any working directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as pipeline_config

logger = logging.getLogger("milk_pipeline")

# The correct endpoint is search/story-list, not /api/search/
# Discovered from: https://github.com/mediacloud/api-client/blob/main/mediacloud/api.py
MC_BASE_URL = "https://search.mediacloud.org/api/"

# Media Cloud's platform identifier for online news content
MC_PLATFORM = "onlinenews-mediacloud"


def fetch(
    query: str,
    date_from: date | None,
    date_to: date | None,
    max_results: int,
    timeout_seconds: int,
    max_retries: int,
    retry_backoff_seconds: int,
) -> list[dict]:
    """
    Fetch articles matching a query from Media Cloud's story-list endpoint.
    Requires MC_API_TOKEN environment variable.
    """
    token = os.environ.get("MC_API_TOKEN")
    if not token:
        logger.error("MC_API_TOKEN environment variable not set.")
        raise ValueError("MC_API_TOKEN environment variable is not set. For Command Prompt use: set MC_API_TOKEN=your_token (for PowerShell use $env:MC_API_TOKEN=\"your_token\") before running.")
        
    token = token.strip(' "\'')

    # Correct endpoint discovered from official GitHub source
    url = MC_BASE_URL + "search/story-list"
    
    headers = {
        "Authorization": f"Token {token}",
        "Accept": "application/json",
    }

    # platform and end date are REQUIRED by the Media Cloud API
    effective_end = date_to or date.today()
    effective_start = date_from or date(2021, 1, 1)

    payload = {
        "q": query,
        "platform": MC_PLATFORM,
        "start": effective_start.isoformat(),
        "end": effective_end.isoformat(),
        "page_size": min(max_results, 1000),  # API max is 1000 per page
        # 'cs' (collection IDs) is REQUIRED by the API — comma-separated string
        "cs": ",".join(str(cid) for cid in pipeline_config.MC_COLLECTION_IDS),
    }
        
    logger.info(f"Fetching Media Cloud with query: {query}")
    
    attempt = 0
    while attempt <= max_retries:
        try:
            response = requests.get(url, params=payload, headers=headers, timeout=timeout_seconds)
            
            if response.status_code in (400, 401, 403, 405, 422):
                raise ValueError(f"Media Cloud API Error ({response.status_code}): {response.text}")
                
            response.raise_for_status()
            
            data = response.json()

            # Official response schema: {"stories": [...], "pagination_token": ...}
            stories = data.get("stories", [])
                
            logger.info(f"Retrieved {len(stories)} articles from Media Cloud.")
            
            # Normalize schema from Media Cloud Story type to our internal format
            normalized = []
            for s in stories:
                normalized.append({
                    "url": s.get("url"),
                    "title": s.get("title", ""),
                    "text": s.get("text", s.get("snippet", "")),
                    "publish_date": str(s.get("publish_date", "")),
                })
            return normalized

        except ValueError:
            # Don't retry on auth/bad-request errors — re-raise immediately
            raise
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            if attempt == max_retries:
                logger.error(f"Failed after {max_retries} retries: {e}")
                raise TimeoutError(f"API call failed: {e}")
                
            logger.warning(f"Request failed ({e}). Retrying in {retry_backoff_seconds} seconds...")
            time.sleep(retry_backoff_seconds)
            retry_backoff_seconds *= 2
            attempt += 1

    return []
