"""
User Configuration Module

Simplified user configuration without research agent logic.
"""

from .models import (
    AgentType,
    UserConfig,
    create_chat_config,
    load_config_from_db,
    load_config_from_env,
)

__all__ = [
    "UserConfig",
    "AgentType",
    "create_chat_config",
    "load_config_from_env",
    "load_config_from_db",
]
