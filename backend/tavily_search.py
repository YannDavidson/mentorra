"""Small Tavily search adapter used by Mentorra mentor tools.

The adapter deliberately keeps the web-search dependency behind one function so
mentor orchestration does not depend on Tavily-specific response details.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_TIMEOUT_SECONDS = 20
_ALLOWED_TOPICS = {"general", "news", "finance"}


def run_tavily_deep_search(
    query: str,
    context: Optional[str] = None,
    topic: str = "general",
) -> Dict[str, Any]:
    """Run an advanced Tavily search and return a JSON-serializable result.

    Missing credentials and upstream errors are returned as structured tool
    results instead of crashing the mentor conversation.
    """

    clean_query = (query or "").strip()
    if not clean_query:
        return {"ok": False, "error": "A non-empty search query is required."}

    api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not api_key:
        return {"ok": False, "error": "TAVILY_API_KEY is not configured."}

    clean_topic = (topic or "general").strip().lower()
    if clean_topic not in _ALLOWED_TOPICS:
        clean_topic = "general"

    search_query = clean_query[:400]
    clean_context = (context or "").strip()
    if clean_context:
        search_query = f"{search_query}\nContext: {clean_context[:1200]}"

    payload = {
        "api_key": api_key,
        "query": search_query,
        "topic": clean_topic,
        "search_depth": "advanced",
        "include_answer": True,
        "include_raw_content": False,
        "max_results": 5,
    }

    request = Request(
        TAVILY_SEARCH_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=TAVILY_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return {"ok": False, "error": f"Tavily returned HTTP {exc.code}."}
    except URLError as exc:
        return {"ok": False, "error": f"Tavily request failed: {exc.reason}."}
    except (TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"Tavily response could not be processed: {exc}."}

    results = []
    for item in data.get("results", []) or []:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
                "score": item.get("score"),
            }
        )

    return {
        "ok": True,
        "answer": data.get("answer"),
        "results": results,
        "response_time": data.get("response_time"),
    }
