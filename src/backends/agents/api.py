"""
Main Agents API Router

Provides endpoints for agent discovery and management.
"""

from fastapi import APIRouter
from .factory import get_supported_agent_types

router = APIRouter(prefix="/agents", tags=["agents"])

@router.get("")
async def get_available_agents():
    """Get list of available agent types."""
    agent_types = get_supported_agent_types()
    return {
        "agent_types": agent_types,
        "count": len(agent_types)
    }

@router.get("/health")
async def agents_health_check():
    """Health check for agents service."""
    return {"status": "healthy", "service": "agents"} 