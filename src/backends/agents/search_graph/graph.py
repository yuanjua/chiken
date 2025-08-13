from typing import Any, Dict, List, Optional
import re
import json
from loguru import logger
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel

from .state import SearchState
from ...tools.web import meta_search_tool
from .nlp import tokenize, compute_tfidf_scores
from .prompts import paper_comment_prompt, get_search_query_prompt, get_rank_prompt
from ...tools.read_tools import search_documents
from ...tools.web import meta_search_tool
from ...tools.utils import get_abstract_by_keys
from ..utils import truncate_think_tag


class SearchAgentGraph:
    def __init__(
        self,
        llm: BaseChatModel,
        *,
        prefilter_top_n: int = 20,
    ):
        self.llm = llm
        self.prefilter_top_n = prefilter_top_n
        self.app = self._build_graph()

    async def _generate_query(self, state: SearchState) -> Dict[str, Any]:
        user_q = state.current_user_message_content
        # Leverage mentioned documents to guide query
        mentioned_titles = [md.get("title", "") for md in state.mention_documents]
        context_hint = "\n\nMentioned documents related to the user research topics and questions:\n" + "\n".join(f"- {t}" for t in mentioned_titles) if mentioned_titles else ""
        # Combine Zotero abstracts and KB fallback snippets
        try:
            abs_lines: List[str] = []
            keys = [md.get("key") for md in state.mention_documents if md.get("key")]
            abs_map: Dict[str, str] = {}
            if keys:
                try:
                    abs_map = await get_abstract_by_keys(keys)
                except Exception:
                    abs_map = {}
            for md in state.mention_documents:
                k = md.get("key")
                if not k:
                    continue
                abstract = (abs_map.get(k) or "").strip()
                if abstract:
                    abs_lines.append(f"- {abstract}")
                else:
                    # Fallback: only when abstract missing
                    try:
                        results = await search_documents(
                            query="abstract introduction conclusion",
                            n_results=2,
                            where={"key": k},
                        )
                        if results:
                            snippet = str(results[0].get("content", ""))
                            if snippet:
                                abs_lines.append(f"- {snippet}")
                    except Exception:
                        continue
            if abs_lines:
                context_hint += "\n\nAbstracts:\n" + "\n".join(abs_lines)
        except Exception:
            pass
        # Build history context: always include recent turns, model will use only if relevant
        history_context = ""
        try:
            raw_history: List[BaseMessage] = getattr(state, "_raw_messages", [])
            if raw_history:
                def clean(text: str) -> str:
                    return "\n".join([ln for ln in (text or "").splitlines() if not (ln.strip().startswith("|") and "|" in ln)])
                recent = raw_history[-6:]
                lines: List[str] = []
                for m in recent:
                    if isinstance(m, HumanMessage):
                        lines.append(f"User: {clean(m.content)}")
                    elif isinstance(m, AIMessage):
                        lines.append(f"Assistant: {clean(m.content)}")
                if lines:
                    history_context = "\n\n(Conversation history; use only if relevant):\n" + "\n".join(lines)
        except Exception:
            pass

        if self.llm is None:
            # Fallback: use raw user text
            query = user_q.strip()
        else:
            prompt = get_search_query_prompt(user_q, history_context, context_hint)
            resp = await self.llm.ainvoke(prompt)
            query = truncate_think_tag((resp.content or "")).strip().strip('"')
        logger.info(f"SearchGraph.generate_query → {query}")
        return {"generated_query": query}

    async def _arxiv_search(self, state: SearchState) -> Dict[str, Any]:
        """Run meta-search over academic sources using the generated query."""
        query = state.generated_query or state.current_user_message_content
        try:
            results = await meta_search_tool(query)
        except Exception as e:
            logger.warning(f"Meta search failed: {e}")
            results = []
        logger.info(f"SearchGraph.arxiv_search → {len(results)} results")
        return {"search_results": results}

    async def _prefilter(self, state: SearchState) -> Dict[str, Any]:
        """Fast heuristic prefilter using lightweight TF-IDF against title+abstract."""
        if not state.search_results:
            return {"search_results": []}
        docs = [f"{r.get('title','')}\n{r.get('abstract','')}" for r in state.search_results]
        # Use user question + mentioned titles as query terms
        q_terms = tokenize(state.current_user_message_content + " " + " ".join([md.get("title","") for md in state.mention_documents]))
        scores = compute_tfidf_scores(q_terms, docs)
        ranked = sorted(zip(scores, state.search_results), key=lambda x: x[0], reverse=True)
        # keep top-N for LLM rerank
        filtered = [r for _, r in ranked[: min(self.prefilter_top_n, len(ranked))]]
        logger.info(f"SearchGraph.prefilter → kept {len(filtered)} of {len(state.search_results)}")
        return {"search_results": filtered}

    async def _rank_with_llm(self, state: SearchState) -> Dict[str, Any]:
        if self.llm is None:
            return {"ranked_results": state.search_results}
        # Feed all results to LLM to rank; include venue/year/authors to disambiguate
        def _yr(date_str: str) -> str:
            m = re.search(r"(20\d{2}|19\d{2})", date_str or "")
            return m.group(1) if m else ""
        serialized = "\n".join([
            (
                f"[{i}] Title: {r.get('title','')}\n"
                f"Venue: {r.get('venue','')} | Year: {_yr(r.get('date',''))} | Authors: {', '.join(r.get('authors', [])[:3])}\n"
                f"Abstract: {r.get('abstract','')}"
            )
            for i, r in enumerate(state.search_results)
        ])
        prompt = get_rank_prompt(state.current_user_message_content, serialized)
        resp = await self.llm.ainvoke(prompt)
        text = truncate_think_tag((resp.content or "")).strip()
        try:
            ranked = json.loads(text)
            if isinstance(ranked, list):
                logger.info(f"SearchGraph.rank_with_llm → ranked {len(ranked)} items with scores")
                # Map ids back to full rows
                by_id = {i: r for i, r in enumerate(state.search_results)}
                # sort by score desc
                def score_of(x):
                    try:
                        return float(x.get("relevance_score", 0))
                    except Exception:
                        return 0.0
                sorted_items = sorted(ranked, key=lambda x: score_of(x), reverse=True)
                sorted_rows = []
                for item in sorted_items:
                    rid = item.get("id")
                    row = by_id.get(int(rid)) if rid is not None else None
                    if row:
                        row = {**row, "relevance_score": item.get("relevance_score"), "justification": item.get("justification", "")}
                        sorted_rows.append(row)
                return {"ranked_results": sorted_rows}
        except Exception as e:
            logger.warning(f"SearchGraph.rank_with_llm: JSON parse failed: {e}")
            # Try extract JSON array from within text
            try:
                m = re.search(r"\[.*\]", text, re.DOTALL)
                if m:
                    ranked = json.loads(m.group(0))
                    if isinstance(ranked, list):
                        logger.info(f"SearchGraph.rank_with_llm → recovered {len(ranked)} items with scores (embedded JSON)")
                        by_id = {i: r for i, r in enumerate(state.search_results)}
                        def score_of(x):
                            try:
                                return float(x.get("relevance_score", 0))
                            except Exception:
                                return 0.0
                        sorted_items = sorted(ranked, key=lambda x: score_of(x), reverse=True)
                        sorted_rows = []
                        for item in sorted_items:
                            rid = item.get("id")
                            row = by_id.get(int(rid)) if rid is not None else None
                            if row:
                                row = {**row, "relevance_score": item.get("relevance_score"), "justification": item.get("justification", "")}
                                sorted_rows.append(row)
                        return {"ranked_results": sorted_rows}
            except Exception as ee:
                logger.warning(f"SearchGraph.rank_with_llm: embedded JSON extract failed: {ee}")
        return {"ranked_results": state.search_results}

    def _build_graph(self):
        g = StateGraph(SearchState)
        g.add_node("generate_query", self._generate_query)
        g.add_node("arxiv_search", self._arxiv_search)
        g.add_node("prefilter", self._prefilter)
        g.add_node("rank_with_llm", self._rank_with_llm)

        g.set_entry_point("generate_query")
        g.add_edge("generate_query", "arxiv_search")
        g.add_edge("arxiv_search", "prefilter")
        g.add_edge("prefilter", "rank_with_llm")
        g.add_edge("rank_with_llm", END)
        return g.compile()


