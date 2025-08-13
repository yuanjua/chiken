"""
Chat History Manager

A dedicated manager for handling chat history persistence.
This decouples the session manager from the storage implementation.
"""

from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import BaseMessage
from loguru import logger

# logger is imported from loguru


class ChatHistoryManager:
    """Manages the persistence of chat histories."""

    def __init__(self, db_path: str):
        """
        Initialize the ChatHistoryManager.

        Args:
            db_path: The path to the SQLite database file.
        """
        self.db_path = db_path
        self.connection_string = f"sqlite:///{self.db_path}"

    def _get_history_for_session(self, session_id: str) -> SQLChatMessageHistory:
        """Get a SQLChatMessageHistory instance for a given session."""
        return SQLChatMessageHistory(
            session_id=session_id, connection=self.connection_string, table_name="message_store"
        )

    def get_messages(self, session_id: str) -> list[BaseMessage]:
        """
        Retrieve all messages for a given session.

        Args:
            session_id: The ID of the session.

        Returns:
            A list of BaseMessage objects.
        """
        try:
            history = self._get_history_for_session(session_id)
            return history.messages
        except Exception as e:
            logger.error(f"Failed to retrieve messages for session {session_id}: {e}")
            return []

    def add_message(self, session_id: str, message: BaseMessage):
        """
        Add a single message to the history of a session.

        Args:
            session_id: The ID of the session.
            message: The message object to add.
        """
        try:
            history = self._get_history_for_session(session_id)
            history.add_message(message)
        except Exception as e:
            logger.error(f"Failed to add message for session {session_id}: {e}")

    def clear_history(self, session_id: str):
        """
        Clear all messages for a given session.

        Args:
            session_id: The ID of the session.
        """
        try:
            history = self._get_history_for_session(session_id)
            history.clear()
        except Exception as e:
            logger.error(f"Failed to clear history for session {session_id}: {e}")

    def save_messages(self, session_id: str, messages: list[BaseMessage]):
        """
        Save a list of messages, replacing the existing history for a session.

        Args:
            session_id: The ID of the session.
            messages: A list of message objects to save.
        """
        try:
            history = self._get_history_for_session(session_id)
            history.clear()
            for message in messages:
                history.add_message(message)
            logger.debug(f"Saved {len(messages)} messages to database for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to save messages for session {session_id}: {e}")
