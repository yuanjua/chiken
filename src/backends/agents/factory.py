"""
Agent Factory

Creates agents based on type. Simplified to remove research agent logic.
"""

from typing import Any, List, Optional
from loguru import logger

from ..user_config import UserConfig, AgentType

# logger is imported from loguru


async def create_agent(agent_type: str, user_config: UserConfig, checkpointer: Optional[Any] = None) -> Any:
    """
    Create an agent instance based on type.
    
    Args:
        agent_type: Type of agent to create (currently only "chat")
        user_config: User configuration
        checkpointer: Optional checkpointer for stateful agents
        
    Returns:
        Agent instance
    """
    agent_type_lower = agent_type.lower()
    
    try:
        if agent_type_lower == "chat" or agent_type_lower == AgentType.CHAT.value:
            # Import chat agent here to avoid circular imports
            from .chat_graph.agent import ChatAgent
            return await ChatAgent.create(user_config, checkpointer)
        elif agent_type_lower == "search_graph":
            from .search_graph.agent import SearchGraphAgent
            return await SearchGraphAgent.create(user_config, checkpointer)
        
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
            
    except ImportError as e:
        logger.error(f"Failed to import {agent_type} agent: {e}")
        raise ValueError(f"Agent type '{agent_type}' not available: {e}")


class AgentFactory:
    """Factory class for creating agents (class-based interface)."""
    
    @staticmethod
    async def create_agent(agent_type: str, user_config: UserConfig, checkpointer: Optional[Any] = None) -> Any:
        """Create agent using the factory function."""
        return await create_agent(agent_type, user_config, checkpointer)
    
    @staticmethod
    def is_agent_type_supported(agent_type: str) -> bool:
        """Check if an agent type is supported."""
        supported_types = get_supported_agent_types()
        return agent_type.lower() in [t.lower() for t in supported_types]
    
    @staticmethod
    def get_supported_agent_types() -> List[str]:
        """Get list of supported agent types."""
        return get_supported_agent_types()


def get_supported_agent_types() -> List[str]:
    """Get list of all supported agent types."""
    return ["chat", "search_graph"]