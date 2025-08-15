"""
Base Agent Interface
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger
from ..sessions.session import Session


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    """

    @abstractmethod
    async def stream_response(
        self,
        message: str,
        session: Session,
        context: dict[str, Any] | None = None,
        request: Any | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Process a message within a session and stream the response.
        Use:
        ```
        yield {"type": "progress", "data": {"message": "Processing context..."}}
        ```
        in the function to indicate progress.

        Mentioned documents can be passed in the context under the key 'mention_documents'.
        ```
        context['mention_documents']
        >>> [{'title': 'Document Title', 'source': 'doc.pdf', 'key': 'sha256...', 'content': '...'}, ...]
        ```

        Args:
            message: The user's message.
            session: The session object containing history and metadata.
            context: Additional context for the request.
                - Mentioned documents (e.g. @doc references) should be passed in context under the key 'mention_documents'.
                - Each entry in 'mention_documents' should be a dict with at least 'title', and optionally 'content', 'source', or 'key'.
                - If 'content' is not provided, agents may fetch it using 'source' or 'key' from the knowledge base or uploaded files.
                - Example:
                    context = {
                        'mention_documents': [
                            {'title': 'Document Title', 'source': 'doc.pdf', 'key': 'sha256...', 'content': '...'},
                            ...
                        ],
                        ...other context...
                    }
            request: The raw request object (e.g., from FastAPI).

        Note: chat interfaces support displaying progress messages.
        Agents can yield progress messages during streaming.
        Example:
            yield {"type": "progress", "data": {"message": "Your progress message here"}}
        """
        pass

    # can generate more during streaming 🤗
    COZY_MESSAGES = [
        "Brewing some thoughts... ☕️",
        "Sketching out an answer... ✍️",
        "Composing a reply... 🎵",
        "Just a moment, finding the right words... ⏳",
        "Composing a reply... 🎼",
        "Gathering my thoughts... 💡",
        "Flipping the record... 🎶",
        "Stargazing for a sec... ✨",
        "Listening to the lofi beats... 🎧",
        "Watering my digital plants... 🪴",
        "Cozying up with some data... 🌱",
        "Let me check my notes... 📓",
        "Diving deeper into the data... 🔍",
        "Crafting the perfect response... 🎨",
        "Exploring new ideas... 🌌",
        "Finding the right angle... 📐",
        "Channeling some late-night cafe vibes... ✨",
        "Taking a moment to reflect... 🤔",
        "Just a sec, tuning my thoughts... 🎶",
        "Building a mental model... 🏗️",
        "Mapping out the conversation... 🗺️",
        "Sifting through the details... 🧪",
        "Polishing the final draft... ✨",
        "Gathering my thoughts... ☁️",
        "Skimming the table of contents... 📋",
        "Channeling some late-night study session vibes... 🦉",
        "Lost in the footnotes for a moment... 🧐",
        "Cross-referencing a few sources... 📚",
        "Just turning the page... 📖",
        "Highlighting a key passage... 🖍️",
        "Finding the right chapter... 🔖",
    ]

    async def is_disconnected(self, request: Any | None) -> bool:
        """Return True if the client has disconnected, else False."""
        if request is None:
            return False
        try:
            checker = getattr(request, "is_disconnected", None)
            if checker is None:
                return False
            return bool(await checker())
        except Exception:
            return True

    def create_cancellation_monitor(self, request: Any | None = None, external_event: asyncio.Event | None = None) -> tuple[asyncio.Event, asyncio.Task | None]:
        """
        Create a cancellation event and monitoring task for request disconnection.
        
        Returns:
            tuple: (cancellation_event, monitor_task or None)
            
        Usage in agent implementations:
            cancellation_event, monitor_task = self.create_cancellation_monitor(request)
            try:
                # Use cancellation_event with LLM streaming
                async for chunk in llm.astream(..., cancellation_event=cancellation_event):
                    if cancellation_event.is_set():
                        break
                    yield chunk
            finally:
                await self.cleanup_cancellation_monitor(cancellation_event, monitor_task)
        """
        cancellation_event = asyncio.Event()
        
        if request is None and external_event is None:
            return cancellation_event, None
            
        async def monitor_cancellation():
            """Monitor request disconnection and external cancellation events."""
            try:
                while not cancellation_event.is_set():
                    # Check request disconnection
                    if request and await self.is_disconnected(request):
                        logger.info("Client disconnected - setting cancellation event")
                        cancellation_event.set()
                        break
                    
                    # Check external cancellation event
                    if external_event and external_event.is_set():
                        logger.info("External cancellation - setting cancellation event")
                        cancellation_event.set()
                        break
                        
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning(f"Error in cancellation monitor: {e}")
        
        monitor_task = asyncio.create_task(monitor_cancellation())
        return cancellation_event, monitor_task

    async def cleanup_cancellation_monitor(self, cancellation_event: asyncio.Event, monitor_task: asyncio.Task | None):
        """
        Clean up the cancellation monitor task.
        
        Args:
            cancellation_event: The cancellation event to set (stops monitoring)
            monitor_task: The monitoring task to cancel
        """
        cancellation_event.set()  # Stop monitoring
        if monitor_task and not monitor_task.done():
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    async def stream(
        self,
        message: str,
        session: Session,
        context: dict[str, Any] | None = None,
        request: Any | None = None,
    ) -> AsyncGenerator[Any, None]:
        """
        Stream response from the agent.
        The agent implementation should handle request disconnection directly.
        """
        async for event in self.stream_response(message, session, context, request):
            yield event
