"""
FastAPI endpoints for the LangGraph Chat Agent.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agent_response import AgentResponse


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    context: dict[str, Any] | None = None


# Create router for chat graph endpoints
router = APIRouter(prefix="/chat-graph", tags=["LangGraph Chat"])


# Dependency to get session manager
async def get_session_manager():
    """Get the session manager instance."""
    from ...sessions.manager import get_session_manager

    return await get_session_manager()


@router.post("/message", response_model=AgentResponse)
async def process_chat_message(request: ChatRequest, session_manager=Depends(get_session_manager)):
    """
    Send a message to the LangGraph chat agent and get a response.
    """
    try:
        response = await session_manager.process_message(
            message=request.message, session_id=request.session_id, context=request.context
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process message with LangGraph: {str(e)}")


@router.post("/stream")
async def stream_chat_message(request: ChatRequest, session_manager=Depends(get_session_manager)):
    """
    Stream a response from the LangGraph chat agent.
    """
    try:

        async def generate_chunks():
            async for chunk in session_manager.stream_response(
                message=request.message, session_id=request.session_id, context=request.context
            ):
                yield chunk

        return StreamingResponse(generate_chunks(), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stream message with LangGraph: {str(e)}")


@router.get("/agent-info")
async def get_agent_info(session_manager=Depends(get_session_manager)):
    """
    Get information about the chat agent.
    """
    try:
        return session_manager.get_agent_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent info: {str(e)}")


@router.get("/session/{session_id}")
async def get_session_info(session_id: str, session_manager=Depends(get_session_manager)):
    """
    Get information about a specific session.
    """
    try:
        return session_manager.get_session_info(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session info: {str(e)}")


@router.delete("/session/{session_id}")
async def clear_session(session_id: str, session_manager=Depends(get_session_manager)):
    """
    Clear conversation history for a specific session.
    """
    try:
        session_manager.clear_session_history(session_id)
        return {"message": f"Session {session_id} cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}")


@router.get("/session/{session_id}/summary")
async def get_conversation_summary(session_id: str, session_manager=Depends(get_session_manager)):
    """
    Get conversation summary for a specific session.
    """
    try:
        return session_manager.get_conversation_summary(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversation summary: {str(e)}")
