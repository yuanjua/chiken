import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import quote_plus
import aiohttp
from ....tools.web import arxiv_search as web_arxiv_search, DEFAULT_HEADERS as WEB_DEFAULT_HEADERS, DEFAULT_TIMEOUT as WEB_DEFAULT_TIMEOUT
import feedparser
from loguru import logger

DEFAULT_HEADERS = {
    "User-Agent": "ChiKen-SearchAgent/1.0 (+https://github.com/your-org/chiken)"
}
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=20)


@dataclass
class ArxivPaper:
    title: str
    url: str
    summary: str
    published: Optional[str] = None
    authors: Optional[List[str]] = None
    primary_category: Optional[str] = None


def build_candidate_queries(user_query: str, mentioned_titles: Sequence[str]) -> List[str]:
    """Build candidate queries. Keep main query; optionally include at most one explicitly referenced title."""
    queries: List[str] = []
    uq = (user_query or "").strip()
    if uq:
        queries.append(uq)
    lowered = uq.lower()
    picked: Optional[str] = None
    for t in mentioned_titles:
        tt = (t or "").strip()
        if tt and tt.lower() in lowered:
            picked = tt
            break
    if picked and picked.lower() not in {q.lower() for q in queries}:
        queries.append(picked)
    logger.debug(f"Arxiv: candidate queries: {queries}")
    return queries


async def _search_single_arxiv(query: str, session: aiohttp.ClientSession, max_results: int = 10) -> List[ArxivPaper]:
    # Reuse the existing web.py arxiv_search for consistency
    try:
        res = await web_arxiv_search(query, session)
        out: List[ArxivPaper] = []
        for item in res.get("results", [])[:max_results]:
            out.append(
                ArxivPaper(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    summary=(item.get("content") or "").replace("\n", " ").strip(),
                )
            )
        return out
    except Exception as e:
        logger.error(f"Arxiv: exception for '{query}': {e}")
        return []


async def search_arxiv_multi(
    queries: Sequence[str],
    max_results_per_query: int = 10,
    concurrency: int = 3,
) -> List[ArxivPaper]:
    """Search arXiv for multiple queries concurrently with basic throttling."""
    sem = asyncio.Semaphore(concurrency)
    out: List[ArxivPaper] = []

    async with aiohttp.ClientSession() as session:
        async def run_one(q: str):
            async with sem:
                papers = await _search_single_arxiv(q, session, max_results=max_results_per_query)
                logger.info(f"Arxiv: got {len(papers)} results for '{q}'")
                return papers

        tasks = [run_one(q) for q in queries if q.strip()]
        groups = await asyncio.gather(*tasks, return_exceptions=True)
        for grp in groups:
            if isinstance(grp, Exception):
                logger.error(f"Arxiv: task exception: {grp}")
                continue
            out.extend(grp)

    # Deduplicate by URL
    seen: set[str] = set()
    deduped: List[ArxivPaper] = []
    for p in out:
        key = p.url or p.title
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)

    logger.info(f"Arxiv: total deduped results: {len(deduped)}")
    return deduped


