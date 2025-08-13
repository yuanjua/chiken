"""
Standard response model for all agents.
"""

from typing import Any

from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """Standard response format for all agents."""

    agent_id: str = Field(..., description="ID of the agent that generated the response")
    session_id: str = Field(..., description="Session ID for this interaction")
    message: str = Field(..., description="The response message")
    timestamp: str = Field(..., description="ISO timestamp of the response")
    status: str = Field(default="success", description="Status of the response")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")
