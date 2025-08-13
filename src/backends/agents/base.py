"""
Base Agent Interface
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

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

    async def stream(
        self,
        message: str,
        session: Session,
        context: dict[str, Any] | None = None,
        request: Any | None = None,
    ) -> AsyncGenerator[Any, None]:
        """
        Unified wrapper that runs `stream_response` and cooperatively cancels
        when the client disconnects.
        """
        queue: asyncio.Queue = asyncio.Queue()
        finished = asyncio.Event()

        async def producer():
            try:
                async for event in self.stream_response(message, session, context, request):
                    await queue.put(event)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                await queue.put({"type": "error", "data": {"message": str(e)}})
            finally:
                finished.set()

        producer_task = asyncio.create_task(producer())
        try:
            while not finished.is_set() or not queue.empty():
                if await self.is_disconnected(request):
                    producer_task.cancel()
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)
                except TimeoutError:
                    continue
                yield event
                queue.task_done()
        finally:
            if not producer_task.done():
                producer_task.cancel()
                try:
                    await producer_task
                except Exception:
                    pass
