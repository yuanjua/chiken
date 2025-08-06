"""
Base Agent Interface
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any

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
        context: Optional[Dict[str, Any]] = None,
        request: Optional[Any] = None
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