"""
Sessions Management API

This module provides API endpoints for managing chat sessions,
including session creation, deletion, message handling, and session information.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, Field

from .manager import SessionManager
from ..agents.agent_response import AgentResponse
from ..manager_singleton import ManagerSingleton
from .service import SessionsService

# Router setup
router = APIRouter(prefix="/sessions", tags=["Sessions"])


class MessageRequest(BaseModel):
    """Request model for chat messages."""
    message: str = Field(..., description="The message content")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for the message")


class ChatMessage(BaseModel):
    """OpenAI-compatible message format."""
    role: str = Field(..., description="Message role: 'system', 'user', or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp")


class SessionInfoResponse(BaseModel):
    """Response model for session information."""
    session_id: str
    agent_id: str
    agent_type: str
    messages: List[ChatMessage] = Field(default_factory=list, description="Conversation history in OpenAI format")
    statistics: Dict[str, Any]
    memory_context: Dict[str, Any]
    configuration: Dict[str, Any]


class SessionListResponse(BaseModel):
    """Response model for session list."""
    sessions: List[Dict[str, Any]]
    total_count: int
    timestamp: str


@router.get("", response_model=SessionListResponse)
async def list_sessions_by_date_desc(
    session_manager: SessionManager = Depends(ManagerSingleton.get_session_manager)
):
    """List all active sessions sorted by date (newest first)."""
    session_data = await SessionsService.list_sessions_by_date_desc(session_manager)
    return SessionListResponse(**session_data)


@router.get("/{session_id}", response_model=SessionInfoResponse)
async def get_session_info(
    session_id: str,
    session_manager: SessionManager = Depends(ManagerSingleton.get_session_manager)
):
    """Get information about a specific session."""
    session_info = await SessionsService.get_session_info(session_id, session_manager)
    return SessionInfoResponse(**session_info)


@router.post("/{session_id}/title")
async def update_session_title(
    session_id: str,
    title: str,
    session_manager: SessionManager = Depends(ManagerSingleton.get_session_manager)
):
    """Update the title of a specific session."""
    return await SessionsService.update_session_title(session_id, title, session_manager)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    session_manager: SessionManager = Depends(ManagerSingleton.get_session_manager)
):
    """Delete a specific session and its history."""
    return await SessionsService.delete_session(session_id, session_manager)


@router.post("/{session_id}/message", response_model=AgentResponse)
async def message(
    session_id: str,
    request: MessageRequest,
    agent_type: str = Query("chat", description="Type of agent to use"),
    session_manager: SessionManager = Depends(ManagerSingleton.get_session_manager)
):
    """Send a message to a specific session."""
    return await SessionsService.process_message(
        session_id=session_id,
        message=request.message,
        agent_type=agent_type,
        session_manager=session_manager,
        context=request.context
    )


@router.post("/{session_id}/stream")
async def stream_message(
    session_id: str,
    request_data: MessageRequest,
    request: Request,
    agent_type: str = Query("chat", description="Type of agent to use"),
    session_manager: SessionManager = Depends(ManagerSingleton.get_session_manager)
):
    """Stream a message response from a specific session."""
    return await SessionsService.stream_message(
        session_id=session_id,
        message=request_data.message,
        agent_type=agent_type,
        session_manager=session_manager,
        context=request_data.context,
        request=request
    )

# New paginated messages endpoint

@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    before: Optional[float] = Query(None, description="Unix ms timestamp of the oldest already-loaded message"),
    limit: int = Query(200, le=500, description="Number of messages to return (max 500)"),
    session_manager: SessionManager = Depends(ManagerSingleton.get_session_manager)
):
    """Return a window of messages for a session, newest first.

    If `before` is not provided, this returns the latest `limit` messages.
    Otherwise it returns up to `limit` messages strictly older than `before`.
    """
    return await SessionsService.get_session_messages(session_id, before, limit, session_manager)
