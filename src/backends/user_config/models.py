"""
User Configuration Models

Simplified user configuration without research agent logic.
"""

import os
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentType(str, Enum):
    """Available agent types."""

    CHAT = "chat"


class UserConfig(BaseModel):
    """
    Simplified user configuration for chat and proofreading agents.
    Uses LiteLLM model naming convention where provider is included in model_name.
    """

    # === LLM Configuration ===
    provider: str = Field(
        default="ollama",
        title="LLM Provider",
        description="The provider for the LLM (e.g., 'ollama', 'openai', 'anthropic')",
    )
    model_name: str = Field(
        default="gemma3:latest",
        title="LiteLLM Model Name",
        description="The model string for LiteLLM (e.g., 'llama3', 'gpt-4o', 'claude-3-opus')",
    )
    base_url: str | None = Field(
        default="http://localhost:11434",
        title="LLM Provider Base URL",
        description="[LEGACY/COMPAT] Optional base URL for local providers. This field is maintained for UI compatibility and migration, but is ignored in backend logic. All provider URLs are now managed via environment variables/keyring.",
    )

    # === Generation Parameters ===
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, title="Temperature")
    max_tokens: int | None = Field(default=32 * 1024, title="Max Tokens")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, title="Top P")
    top_k: int = Field(default=40, ge=1, le=100, title="Top K")
    num_ctx: int = Field(default=4096, title="Context Window Size")

    # === Embedding Configuration ===
    embed_model: str = Field(default="nomic-embed-text", title="Embedding Model")
    embed_provider: str = Field(
        default="ollama",
        title="Embedding Provider",
        description="Provider for embedding model (e.g., 'ollama', 'openai', 'anthropic')",
    )

    # === Agent Behavior ===
    system_prompt: str | None = Field(default=None, title="System Prompt")

    # === User Context ===
    user_id: str | None = Field(default=None, title="User ID")
    config_id: str | None = Field(default=None, title="Configuration ID")

    # === Advanced Settings ===
    memory_enabled: bool = Field(default=True, title="Memory Enabled")
    max_history_length: int = Field(default=50, title="Max History Length")
    memory_update_frequency: int = Field(default=5, title="Memory Update Frequency")
    use_custom_endpoints: bool = Field(
        default=False,
        title="Use Custom Endpoints",
        description="Use custom endpoints stored in database instead of config",
    )

    # === PDF Parser Configuration ===
    pdf_parser_type: str = Field(default="local", title="PDF Parser Type")
    pdf_parser_url: str | None = Field(default=None, title="PDF Parser URL")

    # === Web Search Configuration ===
    search_engine: str = Field(default="searxng", title="Search Engine")
    search_endpoint: str | None = Field(default="http://localhost:8888", title="Search Endpoint")
    search_api_key: str | None = Field(default=None, title="Search API Key")

    # === MCP Configuration ===
    mcp_transport: str = Field(default="stdio", title="MCP Transport Type")
    mcp_port: int | None = Field(default=8000, title="MCP Port")

    # === Knowledge Base Configuration ===
    active_knowledge_base_ids: list[str] | None = Field(
        default_factory=list,
        title="Active Knowledge Base IDs",
        description="List of active knowledge base IDs that should be queried by default",
    )

    # === Document Processing Configuration ===
    chunk_size: int = Field(
        default=1600,
        title="Document Chunk Size",
        description="Size of text chunks for document processing and storage",
    )

    chunk_overlap: int = Field(
        default=200,
        title="Document Chunk Overlap",
        description="Number of characters that overlap between adjacent chunks",
    )

    enable_reference_filtering: bool = Field(
        default=True,
        title="Enable Reference Filtering",
        description="Filter out references and citations from document content during processing",
    )

    # === Timestamps ===
    created_at: str | None = Field(default=None, title="Created At")
    updated_at: str | None = Field(default=None, title="Updated At")

    # === Environment Variables Key Tracking ===
    env_keys: list[str] = Field(
        default_factory=list,
        title="Environment Variable Keys",
        description="List of environment variable names that should be active in os.environ. Used for reconciliation with keychain.",
    )

    model_config = ConfigDict(use_enum_values=False)

    @property
    def provider_type(self) -> str:
        """
        Extract provider type from model_name.
        Returns the provider prefix (e.g., 'ollama', 'openai', 'anthropic') or 'unknown'.
        """
        return self.provider

    def get_llm_config(self) -> dict[str, Any]:
        """Get LLM-specific configuration for ChatLiteLLM."""
        provider_type = self.provider_type

        config = {
            "provider": self.provider,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "num_ctx": self.num_ctx,
        }

        # LiteLLM handles base URLs automatically via environment variables
        # No need to manually pass base_url - LiteLLM will use env vars like:
        # OLLAMA_API_BASE, OPENAI_BASE_URL, HOSTED_VLLM_API_BASE, etc.

        return config


def create_chat_config(user_id: str | None = None, config_id: str | None = None, **overrides) -> UserConfig:
    """Create a configuration optimized for chat agents."""
    return UserConfig(user_id=user_id, config_id=config_id, **overrides)


def load_config_from_env() -> UserConfig:
    """Load configuration from environment variables (fallback to defaults)."""
    return create_chat_config()


async def load_config_from_db(config_id: str = "default") -> UserConfig:
    """Load configuration from database."""
    from ..manager_singleton import ManagerSingleton

    try:
        await ManagerSingleton.initialize()
        return await ManagerSingleton.get_user_config()
    except Exception:
        return create_chat_config(config_id=config_id)
