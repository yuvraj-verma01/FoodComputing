"""
build_query.py

Responsibility: turn a clean keyword list into ONE bounded Solr query
string for Media Cloud.
"""

from __future__ import annotations
from datetime import date


def build_solr_query(
    keywords: list[str],
    max_terms: int = 6,
    date_from: date | None = None,
    date_to: date | None = None,
) -> str:
    """
    Build a single Solr boolean query string from a keyword list.
    """
    if not keywords:
        raise ValueError("Keywords list cannot be empty.")
        
    if len(keywords) > max_terms:
        raise ValueError(f"Too many keywords: {len(keywords)} > {max_terms}. To prevent API timeouts, keep queries bounded.")

    # Sanitize and format terms: convert spaces to AND so words don't have to be adjacent
    formatted_terms = []
    for kw in keywords:
        # Basic sanitization for solr special characters
        clean_kw = kw.replace('"', '').replace('+', '').replace('-', '').strip()
        if " " in clean_kw:
            # e.g. "adulteration detected milk" -> "(adulteration AND detected AND milk)"
            and_kw = " AND ".join(clean_kw.split())
            formatted_terms.append(f"({and_kw})")
        else:
            formatted_terms.append(clean_kw)

    # Join with OR
    query_string = " OR ".join(formatted_terms)
    
    # If there's more than one term, wrap the whole OR block in parentheses
    if len(formatted_terms) > 1:
        query_string = f"({query_string})"
        
    # Make sure every returned article is at least about milk
    query_string = f"(milk AND {query_string})"
        
    return query_string
