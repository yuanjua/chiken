from __future__ import annotations
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field, field_validator, model_validator
from ...user_config.models import UserConfig, create_chat_config
from ...sessions.session import Session

class SessionState(BaseModel):
    """Represents the state of a single conversation session for LangGraph."""
    session_id: str
    
    # User configuration embedded in session state (supports both old and new config types)
    user_config: Union[UserConfig] = Field(default_factory=create_chat_config)

    # Session data
    system_prompt_content: str = ""
    title: str = "New Chat"  # Session title
    messages: List[BaseMessage] = Field(default_factory=list)
    message_count: int = 0
    conversation_summary: str = ""
    key_topics: List[str] = Field(default_factory=list)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    new_messages_to_save: List[BaseMessage] = Field(default_factory=list)

    # RAG
    run_rag: bool = False  # Flag to control RAG execution
    rag_query: str = ""
    rag_results: List[Dict[str, Any]] = Field(default_factory=list)
    rag_context: str = ""  # Pre-formatted context for RAG
    document_keys: List[str] = Field(default_factory=list)  # Document keys for RAG

    # Configuration for this session's memory (derived from user_config)
    @property
    def max_history_length(self) -> int:
        return self.user_config.max_history_length
    
    @property
    def memory_update_frequency(self) -> int:
        return self.user_config.memory_update_frequency

    # Transient fields for a single graph run
    current_user_message_content: Optional[str] = None
    current_ai_response_content: Optional[str] = None
    error_message: Optional[str] = None
    prepared_messages: Optional[List[BaseMessage]] = None  # Messages prepared for LLM

    # Timestamps (can be managed by the agent wrapper if preferred)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_activity: str = Field(default_factory=lambda: datetime.now().isoformat())

    # To ensure Pydantic models can be used as TypedDicts in LangGraph if needed
    class Config:
        arbitrary_types_allowed = True

    @field_validator("messages", mode='before')
    @classmethod
    def serialize_messages(cls, v: Any) -> List[Dict[str, Any]]:
        if not v:
            return []
        if isinstance(v[0], BaseMessage):
             # If messages are already BaseMessage objects, serialize them to dicts
            return [msg.model_dump() for msg in v]
        # Otherwise, assume they are already dicts and return as is
        return v

    @classmethod
    def from_session(cls, session: Session) -> "SessionState":
        """Create a SessionState object from a Session object."""
        return cls(
            session_id=session.session_id,
            user_config=session.user_config,
            messages=session.messages,
            title=session.title,
            created_at=session.created_at,
            last_activity=session.last_activity,
            message_count=session.message_count,
            conversation_summary=session.conversation_summary,
            key_topics=session.key_topics,
            user_preferences=session.user_preferences
        )

    def update_session(self, session: Session) -> None:
        """Update non-history fields on the Session object.
        Chat history is persisted exclusively by SessionManager to avoid duplication.
        """
        session.title = self.title
        session.conversation_summary = self.conversation_summary
        session.key_topics = self.key_topics
        session.user_preferences = self.user_preferences
