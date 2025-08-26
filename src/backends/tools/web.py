import asyncio
import json
import os
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote_plus

import aiohttp
import feedparser
from loguru import logger


def _reconstruct_abstract(inverted_index: dict[str, list[int]]) -> str:
    """Reconstructs a readable abstract from OpenAlex's inverted index."""
    if not isinstance(inverted_index, dict):
        return ""
    try:
        max_pos = max(max(positions) for positions in inverted_index.values() if positions)
        abstract_list = [""] * (max_pos + 1)
        for word, positions in inverted_index.items():
            for pos in positions:
                abstract_list[pos] = word
        return " ".join(abstract_list).strip()
    except (ValueError, TypeError):
        return ""


DEFAULT_HEADERS = {
    "User-Agent": "ChiKen/1.0 (+https://github.com/yuanjua/chiken; contact: devnull@example.com)",
}
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15)


def _get_academic_mailto() -> str:
    """Resolve an academic contact email for courteous API usage."""
    mailto_secret = os.getenv("ACADEMIC_MAILTO") or os.getenv("MAILTO")
    if mailto_secret:
        return mailto_secret
    return os.getenv("ACADEMIC_MAILTO") or os.getenv("MAILTO") or "devnull@example.com"


def _secret_or_env(name: str) -> str | None:
    """Return from environment variable only."""
    return os.getenv(name)


def _build_headers_with_mailto(mailto: str | None) -> dict[str, str]:
    """Return headers with a polite User-Agent including mailto when provided."""
    ua_base = "ChiKen/1.0 (+https://github.com/yuanjua/chiken"
    if mailto:
        ua = f"{ua_base}; mailto:{mailto})"
    else:
        ua = f"{ua_base}; contact: devnull@example.com)"
    headers = dict(DEFAULT_HEADERS)
    headers["User-Agent"] = ua
    return headers


async def arxiv_search(query: str, session: aiohttp.ClientSession, limit: int = 3) -> dict:
    # No changes needed here, it's working well.
    url = f"http://export.arxiv.org/api/query?search_query=all:{quote_plus(query)}&start=0&max_results={int(limit)}"
    try:
        async with session.get(url, timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS) as resp:
            if resp.status != 200:
                logger.error(f"ArXiv Error: Status {resp.status}")
                return {"results": []}
            text = await resp.text()
            feed = feedparser.parse(text)
            results = []
            for entry in feed.entries:
                authors = [a.get("name", "") for a in getattr(entry, "authors", [])][:5]
                venue = (
                    getattr(entry, "arxiv_primary_category", {}).get("term", "")
                    if hasattr(entry, "arxiv_primary_category")
                    else ""
                )
                results.append(
                    {
                        "title": entry.title,
                        "url": entry.link,
                        "abstract": entry.summary.replace("\n", " "),
                        "content": entry.summary.replace("\n", " "),
                        "raw_content": entry.summary,
                        "authors": authors,
                        "date": getattr(entry, "published", ""),
                        "venue": venue,
                    }
                )
            return {"results": results}
    except Exception as e:
        logger.error(f"An error occurred in arxiv_search: {e}")
        return {"results": []}


async def crossref_search(query: str, session: aiohttp.ClientSession, limit: int = 3) -> dict:
    # No changes needed here, it's working well.
    mailto = _get_academic_mailto()
    url = f"https://api.crossref.org/works?query={quote_plus(query)}&rows={int(limit)}&mailto={quote_plus(mailto)}"
    headers = _build_headers_with_mailto(mailto)
    try:
        async with session.get(url, timeout=DEFAULT_TIMEOUT, headers=headers) as resp:
            if resp.status != 200:
                logger.error(f"Crossref Error: Status {resp.status}")
                return {"results": []}
            data = await resp.json()
            items = data.get("message", {}).get("items", [])
            results = []
            for item in items:
                # Title
                title_list = item.get("title") or []
                title = title_list[0] if title_list else ""
                title = " ".join(title.split())

                # Abstract
                abstract = (item.get("abstract") or "").strip()
                # strip common JATS tags
                abstract = (
                    abstract.replace("<jats:p>", "")
                    .replace("</jats:p>", "")
                    .replace("<jats:bold>", "")
                    .replace("</jats:bold>", "")
                )
                if not abstract:
                    # Fallback to subtitle if available
                    subs = item.get("subtitle") or []
                    if subs:
                        abstract = " ".join((subs[0] or "").split())
                abstract = abstract or ""

                # Authors
                authors: list[str] = []
                for au in item.get("author", [])[:5]:
                    given = au.get("given", "")
                    family = au.get("family", "")
                    full = " ".join((given + " " + family).split()).strip()
                    if full:
                        authors.append(full)

                # Year
                year = ""
                for key in ("published-print", "published-online", "issued", "published"):
                    dp = (item.get(key) or {}).get("date-parts") or []
                    if dp and dp[0]:
                        try:
                            year = str(dp[0][0])
                            break
                        except Exception:
                            pass

                # Venue
                venue_list = item.get("container-title") or []
                venue = venue_list[0] if venue_list else ""

                # URL: prefer primary resource URL if present
                url = ((item.get("resource") or {}).get("primary") or {}).get("URL") or item.get("URL", "")

                results.append(
                    {
                        "title": title,
                        "url": url,
                        "abstract": abstract,
                        "content": abstract,
                        "raw_content": abstract,
                        "authors": authors,
                        "date": year,
                        "venue": venue,
                    }
                )
            return {"results": results}
    except Exception as e:
        logger.error(f"An error occurred in crossref_search: {e}")
        return {"results": []}


async def pubmed_search(query: str, session: aiohttp.ClientSession, limit: int = 3) -> dict:
    # No changes needed here, it's working well.
    # Note: PubMed can return empty abstracts for some articles, which is expected.
    # (Your output showed one "N/A", which this code handles).
    try:
        api_key = _secret_or_env("NCBI_API_KEY") or _secret_or_env("PUBMED_API_KEY")
        search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmax={int(limit)}&term={quote_plus(query)}&retmode=json"
        if api_key:
            search_url += f"&api_key={quote_plus(api_key)}"
        async with session.get(search_url, timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS) as resp:
            if resp.status != 200:
                logger.error(f"PubMed Search Error: Status {resp.status}")
                return {"results": []}
            search_data = await resp.json()
            ids = search_data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return {"results": []}
        fetch_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={','.join(ids)}&retmode=xml"
        )
        if api_key:
            fetch_url += f"&api_key={quote_plus(api_key)}"
        async with session.get(fetch_url, timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS) as detail_resp:
            if detail_resp.status != 200:
                logger.error(f"PubMed Fetch Error: Status {detail_resp.status}")
                return {"results": []}
            xml = await detail_resp.text()
            root = ET.fromstring(xml)
            results = []
            for article in root.findall(".//PubmedArticle"):
                title = article.findtext(".//ArticleTitle", default="")
                abstract_elements = article.findall(".//Abstract/AbstractText")
                abstract = " ".join([elem.text for elem in abstract_elements if elem.text])
                pmid = article.findtext(".//PMID", default="")
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
                # Authors
                authors = []
                for au in article.findall(".//AuthorList/Author")[:5]:
                    last = au.findtext("LastName", default="")
                    initials = au.findtext("Initials", default="")
                    full = (last + " " + initials).strip()
                    if full:
                        authors.append(full)
                # Venue and year
                venue = article.findtext(".//Journal/Title", default="")
                year = article.findtext(".//JournalIssue/PubDate/Year", default="")
                if not year:
                    year = article.findtext(".//ArticleDate/Year", default="")
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "abstract": abstract,
                        "content": abstract,
                        "raw_content": abstract,
                        "authors": authors,
                        "date": year,
                        "venue": venue,
                    }
                )
            return {"results": results}
    except Exception as e:
        logger.error(f"An error occurred in pubmed_search: {e}")
        return {"results": []}


async def semantic_scholar_search(query: str, session: aiohttp.ClientSession, limit: int = 3) -> dict:
    """Semantic Scholar Graph API search with optional API key."""
    api_key = _secret_or_env("SEMANTIC_SCHOLAR_API_KEY")
    headers = dict(DEFAULT_HEADERS)
    if api_key:
        headers["x-api-key"] = api_key
    fields = "title,url,abstract,authors,year,venue"
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote_plus(query)}&limit={int(limit)}&fields={fields}"
    try:
        async with session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT) as resp:
            if resp.status != 200:
                logger.error(f"Semantic Scholar Error: Status {resp.status}, Body: {await resp.text()}")
                return {"results": []}
            data = await resp.json()
            results = []
            for paper in data.get("data", []):
                authors = [a.get("name", "") for a in paper.get("authors", [])][:5]
                year = str(paper.get("year") or "")
                venue = paper.get("venue", "") or ""
                abstract = paper.get("abstract", "") or ""
                abstract = " ".join(abstract.split())
                results.append(
                    {
                        "title": paper.get("title", "") or "",
                        "url": paper.get("url", "") or "",
                        "abstract": abstract,
                        "content": abstract,
                        "raw_content": abstract,
                        "authors": authors,
                        "date": year,
                        "venue": venue,
                    }
                )
            return {"results": results}
    except Exception as e:
        logger.error(f"An error occurred in semantic_scholar_search: {e}")
        return {"results": []}


async def openalex_search(query: str, session: aiohttp.ClientSession, limit: int = 3) -> dict:
    """
    Search OpenAlex for works matching the query.

    Args:
        query (str): The search term.
        session (aiohttp.ClientSession): The aiohttp session for making HTTP requests.

    Returns:
        Dict: A dictionary with a "results" key containing a list of works.
    """
    mailto = _get_academic_mailto()

    # Use correct OpenAlex parameters and put mailto in header (query mailto currently returns 400)
    url = f"https://api.openalex.org/works?search={quote_plus(query)}&per_page={int(limit)}"
    headers = _build_headers_with_mailto(mailto)

    try:
        async with session.get(url, timeout=DEFAULT_TIMEOUT, headers=headers) as resp:
            if resp.status != 200:
                # This detailed print statement is excellent for debugging, let's keep it.
                logger.error(f"OpenAlex Error: Status {resp.status}, Body: {await resp.text()}")
                return {"results": []}

            data = await resp.json()
            results = []
            for work in data.get("results", []):
                abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
                doi = work.get("doi")
                work_url = doi if doi else work.get("id", "")
                authors = []
                for au in work.get("authorships", [])[:5]:
                    name = (au.get("author") or {}).get("display_name")
                    if name:
                        authors.append(name)
                venue = (work.get("host_venue") or {}).get("display_name", "")
                year = str(work.get("publication_year") or "")
                results.append(
                    {
                        "title": work.get("display_name", ""),
                        "url": work_url,
                        "abstract": abstract,
                        "content": abstract,
                        "raw_content": abstract,
                        "authors": authors,
                        "date": year,
                        "venue": venue,
                    }
                )
            return {"results": results}
    except Exception as e:
        logger.error(f"An error occurred in openalex_search: {e}")
        return {"results": []}


# --- Meta search utility ---
def _extract_year(value: str) -> int | None:
    if not value:
        return None
    import re

    m = re.search(r"(19\d{2}|20\d{2})", str(value))
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def _normalize_whitespace(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _normalize_title(text: str) -> str:
    t = _normalize_whitespace(text)
    # Remove trailing punctuation artifacts and collapse spaces
    return t.strip().lower()


async def meta_search_papers(
    query: str,
    session: aiohttp.ClientSession,
    *,
    sources: list[str] | None = None,
    year_range: tuple[int | None, int | None] | None = None,
    per_source_limit: int = 3,
) -> list[dict[str, Any]]:
    """
    Run all academic web searches concurrently and return a unified list of paper dictionaries.

    Returns list of dicts with keys:
      - title: str
      - abstract: str
      - url: str
      - source: str  # one of arxiv|crossref|pubmed|semantic_scholar|openalex
    """
    try:
        provider_funcs: dict[str, Callable[[str, aiohttp.ClientSession, int], Awaitable[dict]]]
        provider_funcs = {
            "arxiv": arxiv_search,
            "crossref": crossref_search,
            "pubmed": pubmed_search,
            "semantic_scholar": semantic_scholar_search,
            "openalex": openalex_search,
        }

        if not sources or "all" in sources :
            use_sources = list(provider_funcs.keys())
        else:
            use_sources = sources

        task_pairs = [
            (name, provider_funcs[name](query, session, per_source_limit))
            for name in use_sources
            if name in provider_funcs
        ]
        results = await asyncio.gather(*(t for _, t in task_pairs), return_exceptions=True)

        unified: list[dict[str, Any]] = []
        for (source, _), res in zip(task_pairs, results):
            if isinstance(res, Exception):
                # Skip failed source
                logger.warning(f"Skipping failed source: {source}")
                continue
            for item in (res or {}).get("results", []):
                unified.append(
                    {
                        "title": item.get("title", ""),
                        "abstract": item.get("abstract") or item.get("content") or item.get("raw_content") or "",
                        "url": item.get("url", ""),
                        "source": source,
                        "authors": item.get("authors", []) or [],
                        "date": item.get("date", ""),
                        "venue": item.get("venue", ""),
                    }
                )

        # Optional year filtering
        if year_range is not None:
            start, end = year_range
            unified = [
                it
                for it in unified
                if (lambda y: y is not None and (start is None or y >= start) and (end is None or y <= end))(
                    _extract_year(it.get("date", ""))
                )
            ]

        # Deduplicate: prefer normalized title + sorted normalized authors; fallback to URL when title missing
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for paper in unified:
            title_key = _normalize_title(paper.get("title", ""))
            authors_norm = sorted(
                {_normalize_whitespace(str(a)) for a in (paper.get("authors", []) or []) if a},
                key=lambda s: s.casefold(),
            )
            key = f"{title_key}|{','.join(authors_norm)}" if title_key else (paper.get("url") or "")
            if not key:
                deduped.append(paper)
                continue
            if key in seen:
                continue
            seen.add(key)
            deduped.append(paper)

        return deduped
    except Exception as e:
        logger.error(f"An error occurred in meta_search_papers: {e}")
        return []


async def web_meta_search_tool(
    query: str,
    *,
    sources: list[str] | None = None,
    year_range: tuple[int | None, int | None] | None = None,
    per_source_limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Meta-search academic papers across multiple sources.
    Agents can make subsequent web search tool calls utilizing retrieved urls.

    Args:
      query: str, Natural-language or keyword query describing the topic/papers.
      sources: list[str] | None, Optional, subset of providers to query. Supported values:
        ["all", "arxiv", "crossref", "pubmed", "semantic_scholar", "openalex"].
        Defaults to all when not provided.
      year_range: tuple[int | None, int | None] | None, Optional, (start_year, end_year). Use None to leave side open,
        e.g., (2020, None) → from 2020 onward; (None, 2022) → up to 2022.
      per_source_limit: int, Max results to request from each provider. Defaults to 10.

    Returns:
      List of normalized result dicts (title, abstract, url, source, authors, date, venue).
      - title: str
      - abstract: str
      - url: str  # url of the paper
      - source: str  # one of arxiv|crossref|pubmed|semantic_scholar|openalex
      - authors: list[str]  # list of authors
      - date: str  # year of publication
      - venue: str  # venue of publication
    """
    async with aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS) as session:
        return await meta_search_papers(
            query,
            session,
            sources=sources,
            year_range=year_range,
            per_source_limit=per_source_limit,
        )


# --- Main Execution ---
async def main():
    query = "large language models"
    results = await web_meta_search_tool(
        query,
        sources=["arxiv", "semantic_scholar", "openalex", "pubmed", "crossref"],
        year_range=(2020, None),
        per_source_limit=4,
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
