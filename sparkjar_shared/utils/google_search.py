"""
Google Custom Search utilities for web research.
"""
import requests
import os
from typing import List, Dict, Optional
# Get Google API credentials from environment
import logging

logger = logging.getLogger(__name__)

def search_web(query: str, num_results: int = 3) -> List[Dict[str, str]]:
    """
    Search the web using Google Custom Search API.
    
    Args:
        query: Search query string
        num_results: Number of results to return (max 10)
        
    Returns:
        List of search results with title, link, and snippet
    """
    # REMOVED BY RORY - GOOGLE_API_KEY and GOOGLE_CSE_ID not used in this repo
    # google_api_key = os.getenv('GOOGLE_API_KEY')
    # google_cse_id = os.getenv('GOOGLE_CSE_ID')
    # 
    # if not google_api_key or not google_cse_id:
    #     logger.warning("Google API credentials not configured. Returning empty results.")
    #     return []
    logger.warning("Google search disabled - REMOVED BY RORY")
    return []
    
    try:
        url = os.getenv("GOOGLE_SEARCH_API_URL", "https://www.googleapis.com/customsearch/v1")
        params = {
            "key": google_api_key,
            "cx": google_cse_id,
            "q": query,
            "num": min(num_results, 10)  # API limit is 10
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        items = data.get("items", [])
        
        results = []
        for item in items:
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", "")
            })
        
        logger.info(f"Found {len(results)} search results for query: {query}")
        return results
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Google Search API request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Google Search failed: {e}")
        return []

def get_search_links(query: str, num_results: int = 3) -> List[str]:
    """
    Get just the links from search results.
    
    Args:
        query: Search query string
        num_results: Number of results to return
        
    Returns:
        List of URLs
    """
    results = search_web(query, num_results)
    return [result["link"] for result in results]
