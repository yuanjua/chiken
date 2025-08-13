import asyncio
import re
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger

from ...llm import create_chatlitellm_from_user_config
from ...sessions.session import Session
from ..base import BaseAgent
from .graph import SearchAgentGraph
from .prompts import get_synthesis_prompt


class SearchGraphAgent(BaseAgent):
    """
    Meta search agent that queries multiple academic web sources and streams relevant rows.

    Streams events:
      - {"type": "progress", "data": {"message": str}}
      - {"type": "row", "data": {"title": str, "abstract": str, "source": str, "url": str, "checked": bool, "score": float}}
      - {"type": "content", "data": str} (final summary)
    """

    def __init__(
        self,
        user_config=None,
        llm=None,
        *,
        prefilter_top_n: int = 20,
        synthesis_top_k: int = 5,
        require_llm: bool = False,
    ):
        self.user_config = user_config
        self.llm = llm
        self.synthesis_top_k = synthesis_top_k
        if self.llm is None:
            msg = (
                "SearchGraphAgent initialized without LLM. Falling back to degraded behavior "
                "for query generation and ranking."
            )
            if require_llm:
                raise ValueError(msg)
            logger.warning(msg)
        # Initialize graph with configurable parameters
        self.graph = SearchAgentGraph(
            llm,
            prefilter_top_n=prefilter_top_n,
        )

    @classmethod
    async def create(cls, user_config=None, _checkpointer=None) -> "SearchGraphAgent":
        llm = None
        try:
            if user_config is not None:
                llm = await create_chatlitellm_from_user_config(user_config)
        except Exception as e:
            logger.warning(f"SearchGraphAgent: failed to create LLM from user config: {e}")
        return cls(user_config=user_config, llm=llm)

    async def stream_response(
        self,
        message: str,
        session: Session,
        context: dict[str, Any] | None = None,
        request: Any | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        # Stream step-by-step progress: generate query → arXiv search → LLM rank
        try:
            from .state import SearchState

            s = SearchState(
                current_user_message_content=(message or ""),
                mention_documents=(context or {}).get("mention_documents", []) if isinstance(context, dict) else [],
            )

            # 1) Generate query
            yield {"type": "progress", "data": {"message": "Generating search query..."}}
            # Attach raw messages for context-aware query generation
            try:
                s._raw_messages = list(session.messages)  # type: ignore[attr-defined]
            except Exception:
                s._raw_messages = []  # type: ignore[attr-defined]
            upd = await self.graph._generate_query(s)
            s.generated_query = upd.get("generated_query")

            # 2) Search
            yield {"type": "progress", "data": {"message": "Searching web sources..."}}
            upd = await self.graph._arxiv_search(s)
            s.search_results = upd.get("search_results", [])

            # 3) Rank
            yield {"type": "progress", "data": {"message": "Ranking results..."}}
            upd = await self.graph._rank_with_llm(s)
            ranked = upd.get("ranked_results", [])

            # Stream a markdown table instead of row events
            def escape_cell(val: str) -> str:
                if not val:
                    return ""
                return str(val).replace("|", "\\|").replace("\n", " ").strip()

            header_lines = [
                "Top results (ranked):\n",
                "| Title | Abstract | Year | Venue | Relevance | Justification | Link |",
                "| --- | --- | --- | --- | --- | --- | :---: |",
            ]
            for ln in header_lines:
                yield {"type": "content", "data": ln + "\n"}
                await asyncio.sleep(0.02)

            # Ensure we have dicts with expected keys
            for item in ranked:
                title = escape_cell(item.get("title", ""))
                abstract = escape_cell((item.get("abstract", "") or "")[:240])
                date = escape_cell(item.get("date", ""))
                venue = escape_cell(item.get("venue", ""))
                score = item.get("relevance_score")
                rel = f"{float(score):.1f}" if isinstance(score, (int, float)) else ""
                just = escape_cell(item.get("justification", ""))
                url = item.get("url", "")
                # Extract year
                year = ""
                if date:
                    m = re.search(r"(20\d{2}|19\d{2})", date)
                    if m:
                        year = m.group(1)
                link_icon = f"[🔗]({url})" if url else ""
                line = f"| {title} | {abstract} | {year} | {venue} | {rel} | {just} | {link_icon} |\n"
                yield {"type": "content", "data": line}
                await asyncio.sleep(0.1)

            yield {"type": "content", "data": "\n"}

            # 4) Short synthesis paragraph
            try:
                if self.llm is not None and ranked:
                    yield {"type": "progress", "data": {"message": "Generating synthesis..."}}
                    topk = ranked[: min(self.synthesis_top_k, len(ranked))]
                    # Build a compact context
                    context_snippets = []
                    for idx, it in enumerate(topk, start=1):
                        context_snippets.append(
                            f"[{idx}] Title: {it.get('title', '')}. Venue: {it.get('venue', '')}. Authors: {', '.join(it.get('authors', [])[:3])}. Abstract: {(it.get('abstract', '') or '')[:600]}"
                        )
                    synth_prompt = get_synthesis_prompt(
                        s.current_user_message_content,
                        context_snippets,
                    )
                    async for chunk in self.llm.astream(synth_prompt):
                        if request and await request.is_disconnected():
                            break
                        if chunk.content:
                            yield {"type": "content", "data": chunk.content}
                    yield {"type": "content", "data": "\n"}
            except Exception as ee:
                logger.warning(f"SearchGraphAgent: synthesis generation failed: {ee}")
        except Exception as e:
            logger.error(f"SearchGraphAgent: pipeline failed: {e}")
            yield {"type": "error", "data": {"message": "Search pipeline failed"}}
