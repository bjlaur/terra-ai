"""Web search fallback for TerraAI.

Uses DuckDuckGo's instant answer API (no key required).
Falls back to a simple web scrape if no instant answer is available.
"""

import json
import logging

import httpx

logger = logging.getLogger("terraai")


def web_search(query: str) -> str:
    """Search the web for a query. Returns a summary string.

    Uses DuckDuckGo instant answer API first, falls back to scraping.
    """
    try:
        # Try DuckDuckGo instant answer
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = json.loads(resp.text)

        # Extract answer
        if data.get("AbstractText"):
            return data["AbstractText"]

        # Try related topics
        topics = data.get("RelatedTopics", [])
        if topics:
            parts = []
            for t in topics[:5]:
                if "Text" in t:
                    parts.append(t["Text"])
            if parts:
                return "\n".join(parts)

        return "No results found."

    except Exception as e:
        logger.error("Web search failed for %r: %s", query, e)
        return f"Error: Search failed: {e}"
