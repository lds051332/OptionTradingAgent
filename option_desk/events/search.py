from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    query: str

    def as_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "query": self.query,
        }


def _tavily_search(query: str, api_key: str, limit: int) -> list[SearchHit]:
    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)
    payload = client.search(query, max_results=limit)
    hits: list[SearchHit] = []
    for item in payload.get("results", []):
        hits.append(
            SearchHit(
                title=item.get("title") or "",
                url=item.get("url") or "",
                snippet=(item.get("content") or "")[:500],
                query=query,
            )
        )
    return hits


def _ddgs_search(query: str, limit: int) -> list[SearchHit]:
    from ddgs import DDGS

    hits: list[SearchHit] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=limit):
            hits.append(
                SearchHit(
                    title=item.get("title") or "",
                    url=item.get("href") or item.get("url") or "",
                    snippet=(item.get("body") or item.get("snippet") or "")[:500],
                    query=query,
                )
            )
    return hits


def search_web(query: str, tavily_api_key: str | None, limit: int = 5) -> list[SearchHit]:
    if tavily_api_key:
        try:
            return _tavily_search(query, tavily_api_key, limit)
        except Exception:
            pass
    try:
        return _ddgs_search(query, limit)
    except Exception:
        return []
