import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from loguru import logger

from ...sessions.session import Session
from ...user_config import UserConfig
from ..base import BaseAgent
from .graph import enhanced_deep_research_graph

if TYPE_CHECKING:
    from ...llm.chatlitellm import LLM

import os
langfuse_handler = None

if os.environ.get("LANGFUSE_SECRET_KEY"):
    try:
        from langfuse.langchain import CallbackHandler
        langfuse_handler = CallbackHandler()
    except:
        logger.warning("Langfuse is not installed, skipping langfuse handler")

class DeepResearchAgent(BaseAgent):
    """
    Simplified Deep Research Agent focused on your 3 tools:
    - web_meta_search_tool (web search)  
    - search_documents (knowledge base search)
    - get_document_by_id (document retrieval)
    
    Features enhanced duplicate prevention and sophisticated multi-stage research workflow.
    """

    def __init__(self, user_config: UserConfig, llm: "LLM"):
        self.user_config = user_config
        self.llm = llm
        self.graph = enhanced_deep_research_graph
        logger.debug("✅ DeepResearchAgent initialized for your 3 tools")

    @classmethod
    async def create(cls, user_config: UserConfig, checkpointer=None) -> "DeepResearchAgent":
        from ...llm import create_chatlitellm_from_user_config

        llm = await create_chatlitellm_from_user_config(user_config)
        return cls(user_config, llm)

    async def stream_response(
        self,
        message: str,
        session: Session,
        context: dict[str, Any] | None = None,
        request: Any | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            yield {"type": "progress", "data": {"message": "🔬 Initializing focused deep research..."}}

            runnable_config: RunnableConfig = {
                "configurable": {
                    "llm_instance": self.llm,
                },
                "metadata": {
                    "owner": self.user_config.user_id or "anonymous",
                },
                "tags": ["langsmith:nostream"],
                "callbacks": [langfuse_handler] if langfuse_handler else None,
            }

            # Include conversation history for better clarification context
            all_messages = []
            
            # Add session history if available
            if session and hasattr(session, 'messages') and session.messages:
                all_messages.extend(session.messages)
            
            # Add the current user message
            all_messages.append(HumanMessage(content=message))
            
            graph_input = {"messages": all_messages}

            yield {"type": "progress", "data": {"message": "🚀 Running focused deep research workflow..."}}

            start_time = asyncio.get_event_loop().time()
            final_state = None
            clarification_emitted = False
            async for event in self.graph.astream(graph_input, runnable_config):
                final_state = event
                if isinstance(event, dict):
                    if "clarify_with_user" in event:
                        # Stream the AI clarification message(s) directly to the client
                        try:
                            node_out = event.get("clarify_with_user", {})
                            messages = node_out.get("messages") or []
                            for msg in messages:
                                content = getattr(msg, "content", None)
                                if content:
                                    yield {"type": "content", "data": str(content)}
                                    clarification_emitted = True
                        except Exception:
                            pass
                        yield {"type": "progress", "data": {"message": "Clarification stage complete"}}
                    if "write_research_brief" in event:
                        yield {"type": "progress", "data": {"message": "Research brief prepared"}}
                    if "research_supervisor" in event:
                        yield {"type": "progress", "data": {"message": "Research supervision and delegation running"}}
                    if "final_report_generation" in event:
                        yield {"type": "progress", "data": {"message": "Final report generation in progress"}}

            # If we asked for clarification and streamed it, stop here (no final report yet)
            if clarification_emitted:
                return

            execution_time = asyncio.get_event_loop().time() - start_time
            yield {"type": "progress", "data": {"message": f"✅ Research completed in {execution_time:.1f}s"}}

            final_report = None
            if isinstance(final_state, dict):
                final_report = (
                    final_state.get("final_report")
                    or final_state.get("finalize", {}).get("final_report")
                    or final_state.get("compressed_research")
                )
            if final_report:
                yield {"type": "content", "data": final_report}

        except Exception as e:
            logger.error(f"Error in DeepResearchAgent (v2): {e}", exc_info=True)
            yield {"type": "content", "data": f"An error occurred during research: {e}"}


