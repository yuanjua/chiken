import asyncio
import random
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from loguru import logger

from ...user_config import UserConfig, create_chat_config
from ..base import BaseAgent
from .graph import AgentGraphs
from .state import SessionState

if TYPE_CHECKING:
    from ...llm.chatlitellm import LLM
from ...sessions.session import Session

# logger is imported from loguru


class ChatAgent(BaseAgent):
    """
    Chat Agent that works with the new decoupled session management.
    """

    def __init__(self, user_config: UserConfig, llm: "LLM", checkpointer: AsyncSqliteSaver | None = None):
        """Initialize the Chat Agent with pre-created LLM."""
        self.user_config = user_config
        self.checkpointer = checkpointer
        self.graphs = AgentGraphs(user_config, llm, checkpointer)
        logger.debug("✅ ChatAgent initialized")

    @classmethod
    async def create(cls, user_config: UserConfig, checkpointer: AsyncSqliteSaver | None = None) -> "ChatAgent":
        from ...llm import create_chatlitellm_from_user_config

        llm = await create_chatlitellm_from_user_config(user_config)
        return cls(user_config, llm, checkpointer)

    async def stream_response(
        self,
        message: str,
        session: Session,
        context: dict[str, Any] | None = None,
        request: Any | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Orchestrates the RAG, generation, and memory graphs for a streaming response.
        """
        logger.info(f"ChatAgent: Starting stream_response for session {session.session_id}")

        full_response_chunks = []
        try:
            # Step 1: Prepare the initial state
            session_state = SessionState.from_session(session)
            session_state.current_user_message_content = message
            if context:
                session_state.document_keys = [doc["key"] for doc in context["mention_documents"]]
            ## TODO: add mention_documents info to query generation

            initial_state_dict = session_state.model_dump()

            # Step 2: Run the RAG graph to get context
            logger.info("ChatAgent: Running RAG workflow...")
            if hasattr(context, "mention_documents") and context["mention_documents"]:
                yield {"type": "progress", "data": {"message": "Reading documents..."}}
            else:
                yield {"type": "progress", "data": {"message": "Reading knowledge bases..."}}
            rag_result = await self.graphs.rag_app.ainvoke(initial_state_dict)

            # Merge the RAG results back into the state for the next graph
            current_state_dict = {**initial_state_dict, **rag_result}

            # Step 3: Run the Generation graph with the (potentially updated) state
            logger.info("ChatAgent: Running Generation workflow...")
            yield {"type": "progress", "data": {"message": "Preparing response..."}}
            gen_result = await self.graphs.generation_app.ainvoke(current_state_dict)

            prepared_messages = gen_result.get("prepared_messages")

            # Step 4: Stream the final response from the LLM
            if prepared_messages:
                logger.info("ChatAgent: Starting LLM streaming...")
                yield {"type": "progress", "data": {"message": random.choice(self.COZY_MESSAGES)}}
                async for chunk in self.graphs.llm.astream(prepared_messages):
                    if request and await request.is_disconnected():
                        logger.warning("Client disconnected during generation.")
                        break

                    if chunk.content:
                        full_response_chunks.append(chunk.content)
                        yield chunk.content
            else:
                error_msg = "Critical error: Generation graph failed to prepare messages."
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.info("ChatAgent: LLM stream finished.")

            # Step 5: Run the Memory graph in the background
            full_response = "".join(full_response_chunks)

            # Create the final state object to pass to the memory update task
            final_session_state = SessionState.model_validate(gen_result)
            final_session_state.current_ai_response_content = full_response
            yield {"type": "progress", "data": {"message": "Summarizing conversation..."}}

            asyncio.create_task(self._run_memory_update(final_session_state, session))

        except Exception as e:
            logger.error(f"Error in ChatAgent streaming orchestration: {e}", exc_info=True)
            yield f"I encountered an error: {str(e)}"

    async def _run_memory_update(self, final_state: SessionState, session: Session):
        """Runs the memory graph in the background and updates the original session object."""
        logger.info(f"ChatAgent: Running Memory Graph in background for session {session.session_id}...")
        try:
            config = {"configurable": {"thread_id": session.session_id}}

            # Invoke the memory graph to update history, LTM, and title
            final_state_from_memory = await self.graphs.memory_app.ainvoke(final_state.model_dump(), config=config)

            # Create a fully updated SessionState object and use it to update the live session
            if final_state_from_memory:
                updated_session_state = SessionState.model_validate(final_state_from_memory)
                updated_session_state.update_session(session)

            logger.info(f"ChatAgent: Memory Graph finished for session {session.session_id}.")
        except Exception as e:
            logger.error(f"Error in background memory update: {e}", exc_info=True)

    def get_agent_info(self) -> dict[str, Any]:
        """Get agent information."""
        return {
            "agent_id": self.user_config.agent_id,
            "agent_name": getattr(self.user_config, "agent_name", "Chat Agent"),
        }


async def create_chat_agent_with_langgraph(config: UserConfig | None = None) -> ChatAgent:
    """
    Create a new LangGraph-based chat agent instance.
    """
    if config is None:
        config = create_chat_config(
            agent_id="chat_agent",
            agent_name="LangGraph Chat Assistant (Optimized)",
            agent_description="An enhanced conversational AI agent with optimized LangGraph workflow, memory, and true async streaming",
        )

    return await ChatAgent.create(config)
