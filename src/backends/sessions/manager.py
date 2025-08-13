"""
Lightweight Session Manager

Simple session management that lets agents decide what they need.
Removed research agent logic and heavy initialization.
"""

from loguru import logger
import os
from datetime import datetime
from typing import Dict, Any, Optional, AsyncGenerator, List
from langchain_core.messages import HumanMessage, AIMessage

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ..user_config import UserConfig
from ..agents.factory import AgentFactory
from ..agents.agent_response import AgentResponse
from .history import ChatHistoryManager
from .session import Session
from ..agents.base import BaseAgent


# Set up logging
# logger is imported from loguru

class SessionManager:
    """Lightweight session manager - agents decide what they need."""

    def __init__(self, user_config: UserConfig, db_path: str):
        """Initialize the SessionManager."""
        self.user_config = user_config
        self.db_path = db_path
        if not self.db_path:
            raise ValueError("Database path cannot be empty.")
        self.history_manager = ChatHistoryManager(self.db_path)
        self.checkpointer_context = None
        self.checkpointer = None
        self.sessions: Dict[str, Session] = {}  # Cache for active sessions
        self.agents: Dict[str, Any] = {}  # Agent cache
        logger.debug(f"SessionManager initialized")

    async def get_or_create_agent(self, agent_type: str, agent_config: Optional[UserConfig] = None) -> BaseAgent:
        """
        Get or create an agent instance.
        A unique agent is created for each model configuration.
        """
        if agent_config is None:
            agent_config = self.user_config

        # Create a unique key based on agent type and model name
        agent_key = f"{agent_type}_{agent_config.model_name}"

        if agent_key not in self.agents:
            logger.debug(f"Creating agent for key: {agent_key}")
            
            checkpointer = None
            if self._agent_needs_checkpointer(agent_type):
                checkpointer = await self._get_checkpointer()
            
            # Pass the specific config to the factory
            agent = await AgentFactory.create_agent(agent_type, agent_config, checkpointer)
            
            if not isinstance(agent, BaseAgent):
                raise TypeError(f"Agent of type {agent_type} does not implement the BaseAgent interface.")

            self.agents[agent_key] = agent
            logger.info(f"✅ Agent '{agent_key}' created.")
        
        return self.agents[agent_key]

    def _agent_needs_checkpointer(self, agent_type: str) -> bool:
        """Check if an agent type needs persistent langgraph storage."""
        stateful_agents = {'chat'}  # Only 'chat' agent uses langgraph checkpointer for now
        return agent_type.lower() in stateful_agents

    async def _get_checkpointer(self):
        """Lazy initialization of checkpointer."""
        if self.checkpointer_context is None:
            logger.debug("Initializing checkpointer for LangGraph.")
            self.checkpointer_context = AsyncSqliteSaver.from_conn_string(self.db_path)
            self.checkpointer = await self.checkpointer_context.__aenter__()
        return self.checkpointer

    async def stream_response(
        self,
        message: str,
        session_id: str,
        agent_type: str = "chat",
        context: Optional[Dict[str, Any]] = None,
        request: Optional[Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream a response from the appropriate agent.
        This is the primary entry point for user messages.
        Yields structured dictionary events.
        """
        try:
            if not AgentFactory.is_agent_type_supported(agent_type):
                yield {"type": "error", "data": {"message": f"Unsupported agent type: {agent_type}"}}
                return

            # --- Dynamic Configuration Handling ---
            agent_config = self.user_config
            if context and "model" in context:
                # Create a temporary config for this request with the specified model
                overrides = {"model_name": context["model"]}
                agent_config = self.user_config.model_copy(update=overrides)
                logger.debug(f"Request-specific model override: {context['model']}")
            # --- End Dynamic Configuration ---

            # Pass the potentially overridden config to the agent
            agent = await self.get_or_create_agent(agent_type, agent_config)
            session = await self.get_session(session_id)

            # The agent's stream_response should return an async generator
            response_chunks_for_saving = []
            async for chunk in agent.stream(message, session, context, request):
                if request and await request.is_disconnected():
                    logger.warning(f"Client disconnected during streaming for session {session_id}.")
                    break
                
                # Ensure chunk is a dictionary before yielding
                if isinstance(chunk, dict):
                    yield chunk
                    if chunk.get("type") == "content":
                        response_chunks_for_saving.append(str(chunk.get("data", "")))
                elif isinstance(chunk, str):
                    # Wrap string chunks for backward compatibility
                    event = {"type": "content", "data": chunk}
                    yield event
                    response_chunks_for_saving.append(chunk)

            # Persist history for agents
            try:
                was_empty = session.message_count == 0
                # Append user and assistant messages to session history for all agents
                session.add_message(HumanMessage(content=message))
                full_response = "".join(response_chunks_for_saving)
                if full_response:
                    session.add_message(AIMessage(content=full_response))

                # Set session title from first turn if it was empty
                if was_empty and len(response_chunks_for_saving) > 0:
                    session.title = message[:50] + "..." if len(message) > 50 else message

                # Update last_activity timestamp when messages are processed
                session.last_activity = datetime.now().isoformat()

                # After streaming, update the session state
                await self.update_session(session)
            except Exception as persist_err:
                logger.error(f"Failed to persist session {session_id} history: {persist_err}")

        except Exception as e:
            logger.error(f"Error streaming with {agent_type} agent for session {session_id}: {e}", exc_info=True)
            yield {"type": "error", "data": {"message": f"An error occurred during streaming: {str(e)}"}}

    async def process_message(
        self,
        message: str,
        session_id: str,
        agent_type: str = "chat",
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process a message and return a complete response (non-streaming).
        This uses the stream_response method internally to avoid duplication.
        """
        try:
            if not AgentFactory.is_agent_type_supported(agent_type):
                return AgentResponse(
                    agent_id=f"{agent_type}_agent",
                    session_id=session_id,
                    message=f"Unsupported agent type: {agent_type}",
                    timestamp=datetime.now().isoformat(),
                    status="error",
                    metadata={"error": "unsupported_agent_type"}
                )

            # Use stream_response internally and collect chunks
            response_chunks = []
            async for chunk in self.stream_response(message, session_id, agent_type, context):
                response_chunks.append(chunk)
            
            full_response = "".join(response_chunks)
            
            # Get session for metadata
            session = await self.get_session(session_id)

            return AgentResponse(
                agent_id=f"{agent_type}_agent",
                session_id=session_id,
                message=full_response,
                timestamp=datetime.now().isoformat(),
                status="success",
                metadata={
                    "agent_type": agent_type,
                    "message_count": session.message_count,
                    "session_title": session.title
                }
            )

        except Exception as e:
            logger.error(f"Error processing message with {agent_type} agent for session {session_id}: {e}")
            return AgentResponse(
                agent_id=f"{agent_type}_agent",
                session_id=session_id,
                message=f"An error occurred while processing your message: {str(e)}",
                timestamp=datetime.now().isoformat(),
                status="error",
                metadata={"error": str(e), "agent_type": agent_type}
            )

    async def get_session(self, session_id: str) -> Session:
        """Get or create a session object."""
        if session_id not in self.sessions:
            db_manager = await self._get_db_manager()
            session_metadata = await db_manager.get_session_metadata(session_id)
            
            if session_metadata:
                # Load existing session from database
                session = Session(
                    session_id=session_id,
                    user_config=self.user_config,
                    title=session_metadata["title"],
                    message_count=session_metadata["message_count"],
                    created_at=session_metadata["created_at"],
                    last_activity=session_metadata["updated_at"],
                    messages=self.history_manager.get_messages(session_id)
                )
                logger.debug(f"Loaded session {session_id} from database with {len(session.messages)} messages.")
            else:
                # Create a new session
                session = Session(session_id=session_id, user_config=self.user_config)
                await db_manager.save_session_metadata(session_id, session.title, 0)
                logger.debug(f"Created new session: {session_id}")
            
            self.sessions[session_id] = session
        
        # Don't update last_activity here - only update it when messages are actually processed
        return self.sessions[session_id]

    async def get_session_info_cached(self, session_id: str) -> Dict[str, Any]:
        """Get session information with caching."""
        session = await self.get_session(session_id)
        
        # Convert messages to OpenAI format
        openai_messages = []
        for msg in session.messages:
            if hasattr(msg, 'type') and hasattr(msg, 'content'):
                role = {"system": "system", "human": "user", "ai": "assistant"}.get(msg.type, "user")
                timestamp = getattr(msg, 'timestamp', None)
                openai_messages.append({
                    "role": role,
                    "content": str(msg.content),
                    "timestamp": timestamp
                })
        
        return {
            "session_id": session_id,
            "messages": openai_messages,
            "statistics": {
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "message_count": session.message_count,
                "status": "active"
            },
            "memory_context": {
                "summary": session.conversation_summary,
                "key_topics": session.key_topics,
                "user_preferences": session.user_preferences,
            },
            "configuration": {
                "agent_type": (
                    self.user_config.agent_type.value 
                    if hasattr(self.user_config.agent_type, 'value') 
                    else str(self.user_config.agent_type)
                ),
                "model_name": self.user_config.model_name,
                "provider": self.user_config.provider,
                "temperature": self.user_config.temperature,
                "max_tokens": self.user_config.max_tokens,
                "agent_name": getattr(self.user_config, 'agent_name', 'Assistant')
            }
        }

    async def update_session_state(self, session_id: str, key: str, value: str):
        """Update a specific field in the session state."""
        session = await self.get_session(session_id)
        
        if key == "title":
            session.title = value
        elif key == "conversation_summary":
            session.conversation_summary = value
        else:
            # For other keys, you might want to add them to user_preferences
            session.user_preferences[key] = value
        
        await self.update_session(session)

    async def _get_db_manager(self):
        """Get database manager for accessing session data."""
        from ..database import get_database_manager
        return await get_database_manager()

    async def update_session(self, session: Session):
        """Update a session in the cache and save its state to the database."""
        self.sessions[session.session_id] = session
        
        try:
            db_manager = await self._get_db_manager()
            
            # Update metadata
            await db_manager.save_session_metadata(
                session_id=session.session_id,
                title=session.title,
                message_count=len(session.messages)
            )
            
            # Save message history
            self.history_manager.save_messages(session.session_id, session.messages)
            
        except Exception as e:
            logger.error(f"Failed to update session {session.session_id} in database: {e}")

    async def get_all_session_metadata(self) -> List[Dict[str, Any]]:
        """Get metadata for all sessions from the database."""
        try:
            db_manager = await self._get_db_manager()
            return await db_manager.list_sessions_metadata()
        except Exception as e:
            logger.error(f"Failed to load sessions from database: {e}")
            return []

    async def clear_session_history(self, session_id: str):
        """Clear a session's history from the cache and database."""
        if session_id in self.sessions:
            del self.sessions[session_id]
        
        try:
            db_manager = await self._get_db_manager()
            await db_manager.delete_session_metadata(session_id)
            self.history_manager.clear_history(session_id)
            logger.debug(f"Cleared session {session_id} from database.")
        except Exception as e:
            logger.error(f"Failed to clear session {session_id} from database: {e}")
        
        if self.checkpointer:
            try:
                # This is for LangGraph workflows
                await self.checkpointer.adelete_thread(session_id)
            except Exception as e:
                logger.error(f"Failed to delete session {session_id} from checkpointer: {e}")

    async def aclose(self):
        """Close resources, like the checkpointer connection."""
        if self.checkpointer_context:
            try:
                await self.checkpointer_context.__aexit__(None, None, None)
                self.checkpointer_context = None
                self.checkpointer = None
                logger.debug("✅ Checkpointer closed")
            except Exception as e:
                logger.error(f"Error closing checkpointer: {e}")


async def get_session_manager() -> "SessionManager":
    """Get the singleton session manager instance."""
    from ..manager_singleton import ManagerSingleton
    return await ManagerSingleton.get_session_manager()

async def close_session_manager():
    """Close the singleton session manager instance."""
    from ..manager_singleton import ManagerSingleton
    await ManagerSingleton.close_all()
 