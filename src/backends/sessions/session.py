"""
Session Data Class

Encapsulates all state and metadata related to a user session.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage

from ..user_config import UserConfig

@dataclass
class Session:
    """
    A data class representing a single user session.
    """
    session_id: str
    user_config: UserConfig
    
    # Core session state
    messages: List[BaseMessage] = field(default_factory=list)
    title: str = "New Chat"
    
    # Metadata
    created_at: str = ""
    last_activity: str = ""
    message_count: int = 0
    
    # Optional context for more advanced agents
    conversation_summary: str = ""
    key_topics: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: BaseMessage):
        """Adds a message to the session's history."""
        self.messages.append(message)
        self.message_count = len(self.messages)
