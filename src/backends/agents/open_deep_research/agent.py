import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from loguru import logger

from ...sessions.session import Session
from ...user_config import UserConfig
from ..base import BaseAgent
from .deep_researcher import deep_researcher
from .configuration import Configuration

if TYPE_CHECKING:
    from ...llm.chatlitellm import LLM


class OpenDeepResearchAgent(BaseAgent):
    """
    Open Deep Research Agent that implements comprehensive research workflows
    using the production-ready deep research system with tool wrapper.
    """

    def __init__(self, user_config: UserConfig, llm: "LLM"):
        """Initialize the Open Deep Research Agent."""
        self.user_config = user_config
        self.research_agent = None
        self.llm = llm
        self.llm_with_tools = None
        logger.debug("✅ OpenDeepResearchAgent initialized")

    @classmethod
    async def create(cls, user_config: UserConfig, checkpointer=None) -> "OpenDeepResearchAgent":
        """Create an instance of the OpenDeepResearchAgent."""
        from ...llm import create_chatlitellm_from_user_config
        
        llm = await create_chatlitellm_from_user_config(user_config)
        return cls(user_config, llm)
    
    async def _initialize_research_agent(self):
        """Prepare the deep_researcher graph and a shared LLM-with-tools instance."""
        if self.research_agent is not None and self.llm_with_tools is not None:
            return self.research_agent
            
        try:
            # The graph is compiled at import time; we reuse it
            self.research_agent = deep_researcher
            # Pass the project's ChatLiteLLM instance directly; nodes will handle binding/structured output
            self.llm_with_tools = self.llm
            logger.info("✅ Deep Researcher graph initialized; using ChatLiteLLM from user config")
            return self.research_agent
            
        except Exception as e:
            logger.error(f"Failed to initialize research agent: {e}", exc_info=True)
            raise

    async def stream_response(
        self,
        message: str,
        session: Session,
        context: dict[str, Any] | None = None,
        request: Any | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process a research request using the deep_researcher LangGraph.
        
        Args:
            message: The user's research question/request
            session: The session object containing history and metadata
            context: Additional context for the request
            request: The raw request object
            
        Yields:
            Progress updates and final research report
        """
        try:
            yield {"type": "progress", "data": {"message": "🔬 Initializing deep research graph..."}}

            # Ensure graph and shared LLM are ready
            await self._initialize_research_agent()

            # Create RunnableConfig to pass the LLM instance into the graph
            max_tokens = self.user_config.max_tokens or 8192
            runnable_config: RunnableConfig = {
                "configurable": {
                    "llm_instance": self.llm_with_tools,
                    "allow_clarification": True,
                },
                "metadata": {
                    "owner": self.user_config.user_id or "anonymous",
                },
                "tags": ["langsmith:nostream"],
            }

            # Prepare input for the graph
            graph_input = {"messages": [HumanMessage(content=message)]}

            yield {"type": "progress", "data": {"message": "🚀 Running deep_researcher workflow..."}}

            start_time = asyncio.get_event_loop().time()
            # Stream progress by stepping through the graph
            final_state = None
            async for event in self.research_agent.astream(graph_input, runnable_config):
                final_state = event
                if isinstance(event, dict):
                    if "clarify_with_user" in event:
                        yield {"type": "progress", "data": {"message": "Clarification stage complete"}}
                    if "write_research_brief" in event:
                        yield {"type": "progress", "data": {"message": "Research brief prepared"}}
                    if "research_supervisor" in event:
                        yield {"type": "progress", "data": {"message": "Research supervision and delegation running"}}
                    if "researcher" in event:
                        yield {"type": "progress", "data": {"message": "Researcher analyzing and planning tool usage"}}
                    if "researcher_tools" in event:
                        yield {"type": "progress", "data": {"message": "Tools executed, processing results"}}
                    if "compress_research" in event:
                        yield {"type": "progress", "data": {"message": "Compressing and synthesizing research findings"}}
                    if "final_report_generation" in event:
                        yield {"type": "progress", "data": {"message": "Final report generation in progress"}}
            end_time = asyncio.get_event_loop().time()

            execution_time = end_time - start_time
            yield {"type": "progress", "data": {"message": f"✅ Research completed in {execution_time:.1f}s"}}

            final_report = None
            if isinstance(final_state, dict):
                final_report = (
                    final_state.get("final_report")
                    or final_state.get("final_report_generation", {}).get("final_report")
                    or final_state.get("compressed_research")
                )
            if not final_report:
                final_report = str(final_state) if final_state is not None else "Research complete."

            if final_report and len(final_report.split()) < 100:
                yield {"type": "progress", "data": {"message": "⚠️  Output looks brief; verify model/tool configuration if needed."}}

            yield {"type": "content", "data": final_report}
            
        except Exception as e:
            logger.error(f"Error in OpenDeepResearchAgent: {e}", exc_info=True)
            error_message = f"An error occurred during research: {str(e)}"
            yield {"type": "content", "data": error_message}

