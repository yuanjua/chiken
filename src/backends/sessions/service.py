"""
Sessions Service Layer

This module contains the business logic for session management operations,
separated from the API layer for better maintainability.
"""

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from ..agents.agent_response import AgentResponse
from .manager import SessionManager


class SessionsService:
    """Service class for session management operations."""

    @staticmethod
    async def update_session_state(
        session_id: str, key: str, value: str, session_manager: SessionManager
    ) -> dict[str, Any]:
        """Update the state of a specific session."""
        try:
            await session_manager.update_session_state(session_id, key, value)
            return {
                "message": f"Session '{session_id}' {key} updated successfully",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update session {key}: {str(e)}")

    @staticmethod
    async def update_session_title(session_id: str, title: str, session_manager: SessionManager) -> dict[str, Any]:
        """Update the title of a specific session."""
        return await SessionsService.update_session_state(session_id, "title", title, session_manager)

    @staticmethod
    async def delete_session(session_id: str, session_manager: SessionManager) -> dict[str, Any]:
        """Delete a specific session and its history."""
        try:
            await session_manager.clear_session_history(session_id)
            return {
                "message": f"Session '{session_id}' deleted successfully",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

    @staticmethod
    async def process_message(
        session_id: str,
        message: str,
        agent_type: str,
        session_manager: SessionManager,
        context: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Send a message to a specific session."""
        try:
            response = await session_manager.process_message(
                message=message, session_id=session_id, agent_type=agent_type, context=context
            )
            return response
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")

    @staticmethod
    async def stream_message(
        session_id: str,
        message: str,
        agent_type: str,
        session_manager: SessionManager,
        context: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> StreamingResponse:
        """Stream a message response from a specific session using SSE."""

        async def sse_generator():
            """Generator that yields SSE-formatted messages."""
            queue = asyncio.Queue()
            finished = asyncio.Event()

            async def stream_producer():
                """Puts events from the session manager into the queue."""
                try:
                    async for event in session_manager.stream_response(
                        message=message,
                        session_id=session_id,
                        agent_type=agent_type,
                        context=context,
                        request=request,
                    ):
                        if request and await request.is_disconnected():
                            break
                        await queue.put(event)
                except Exception as e:
                    error_event = {"type": "error", "data": {"message": str(e)}}
                    await queue.put(error_event)
                finally:
                    await asyncio.sleep(0.1)
                    finished.set()

            async def keep_alive_sender():
                """Sends a keep-alive comment every 15 seconds."""
                while not finished.is_set():
                    try:
                        await asyncio.wait_for(finished.wait(), timeout=15)
                    except TimeoutError:
                        if not finished.is_set():
                            await queue.put({"type": "keep-alive"})

            producer_task = asyncio.create_task(stream_producer())
            keep_alive_task = asyncio.create_task(keep_alive_sender())

            while not finished.is_set() or not queue.empty():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)

                    if isinstance(event, dict):
                        if event.get("type") == "keep-alive":
                            yield ": keep-alive\n\n"
                        else:
                            yield f"data: {json.dumps(event)}\n\n"
                    elif isinstance(event, str):
                        # For backward compatibility with agents yielding strings
                        payload = {"type": "content", "data": event}
                        yield f"data: {json.dumps(payload)}\n\n"

                    queue.task_done()
                except TimeoutError:
                    continue

            producer_task.cancel()
            keep_alive_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                pass

        headers = {
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
        return StreamingResponse(sse_generator(), media_type="text/event-stream", headers=headers)

    @staticmethod
    async def get_session_info(session_id: str, session_manager: SessionManager) -> dict[str, Any]:
        """Get information about a specific session."""
        try:
            session_info = await session_manager.get_session_info_cached(session_id)

            # Add agent_type field that's required by the response model if it's missing
            if "agent_type" not in session_info:
                session_info["agent_type"] = (
                    session_manager.user_config.agent_type.value
                    if hasattr(session_manager.user_config.agent_type, "value")
                    else str(session_manager.user_config.agent_type)
                )

            return session_info
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get session info: {str(e)}")

    @staticmethod
    async def list_sessions_by_date_desc(session_manager: SessionManager) -> dict[str, Any]:
        """List all active sessions sorted by date (newest first)."""
        try:
            # Use the new method that loads sessions from persistent storage
            sessions = await session_manager.get_all_session_metadata()

            # Sort by updated_at (newest first) - this is what the database actually returns
            sessions.sort(key=lambda x: x["updated_at"], reverse=True)

            # Add agent_type field that's expected by the frontend
            for session in sessions:
                if "agent_type" not in session:
                    session["agent_type"] = "chat"  # Default agent type
                # Map updated_at to last_activity for frontend compatibility
                session["last_activity"] = session["updated_at"]

            return {
                "sessions": sessions,
                "total_count": len(sessions),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")

    @staticmethod
    async def get_session_messages(
        session_id: str, before: float | None, limit: int, session_manager: SessionManager
    ) -> dict[str, Any]:
        """Retrieve a window of messages for the given session.

        Args:
            session_id: ID of the chat session.
            before: Only return messages with timestamp < before (unix-ms). If None, take newest messages.
            limit: Max number of messages to return.
            session_manager: DI-provided SessionManager.

        Returns:
            dict with keys: messages (list), has_more (bool), oldest (timestamp|None)
        """
        try:
            session = await session_manager.get_session(session_id)

            all_messages = session.messages  # list[BaseMessage] in chronological order (newest last)

            # Filter older than `before` if provided
            if before is not None:
                filtered = [m for m in all_messages if getattr(m, "timestamp", 0) < before]
            else:
                filtered = all_messages

            # Take the newest `limit` of the filtered list
            window = filtered[-limit:]

            # Determine if there are more older messages beyond this window
            has_more = len(filtered) > len(window)

            # Convert to OpenAI-style dicts
            role_map = {"system": "system", "human": "user", "ai": "assistant"}
            converted = [
                {
                    "role": role_map.get(getattr(msg, "type", "human"), "user"),
                    "content": str(getattr(msg, "content", "")),
                    "timestamp": getattr(msg, "timestamp", None),
                }
                for msg in window
            ]

            oldest_ts = converted[0]["timestamp"] if converted else None

            return {
                "messages": converted,
                "has_more": has_more,
                "oldest": oldest_ts,
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get session messages: {str(e)}")
