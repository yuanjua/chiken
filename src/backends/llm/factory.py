"""
LLM Provider Factory

Simplified factory for creating ChatLiteLLM instances.
"""

import os
from typing import Any, Optional

from loguru import logger

from ..user_config import UserConfig
from .chatlitellm import LLM
from .env_parser import EnvVarParser
from .env_parser_db import EnvVarParserDB


class LLMFactory:
    """Simplified factory for creating ChatLiteLLM instances."""

    @classmethod
    async def load_provider_credentials(cls, provider: str, from_db: bool = True) -> dict[str, Any]:
        """Load and validate provider credentials using database-synced parsing."""
        try:
            if from_db:
                # Use database-synced parser that respects UI settings
                return await EnvVarParserDB.get_llm_credentials_from_db(provider)
            else:
                # Fallback to regular env parser
                return EnvVarParser.get_provider_credentials(provider)
        except Exception as e:
            logger.error(f"⚠️ Failed to load credentials for {provider}: {e}")
            return {}

    @classmethod
    async def create_chat_model(
        cls,
        config: dict[str, Any],
        load_from_db: bool = True,
        use_custom_endpoints: bool | None = None,
    ) -> Optional["LLM"]:
        """
        Creates a ChatLiteLLM (LangChain wrapper) instance.

        Args:
            config: Configuration dictionary for the provider.
            load_from_db: Whether to load credentials from database

        Returns:
            ChatLiteLLM instance or None if creation fails
        """
        try:
            from .chatlitellm import LLM

            # Determine provider from model_name or config
            provider = config.get("provider", "openai")
            if "/" in config.get("model_name", ""):
                provider = config["model_name"].split("/")[0]

            # Load credentials from database with UI sync (default)
            env_credentials = await cls.load_provider_credentials(provider, from_db=load_from_db)

            # Merge env credentials with config (env takes precedence for base_url and keys)
            final_config = {**config, **env_credentials}

            # Prepare LLM arguments with explicit API keys and base URLs
            llm_args = {
                "model_name": final_config["model_name"],
                "temperature": final_config.get("temperature", 0.1),
                "max_tokens": final_config.get("max_tokens", 24 * 1024),
                "num_ctx": final_config.get("num_ctx", 4096),
            }

            # Explicitly pass API keys and base URLs as arguments
            if "api_key" in env_credentials:
                llm_args["api_key"] = env_credentials["api_key"]

            if "api_base" in env_credentials:
                llm_args["api_base"] = env_credentials["api_base"]

            # Add timeout and retry settings if available
            if "timeout" in env_credentials:
                llm_args["request_timeout"] = env_credentials["timeout"]

            if "max_retries" in env_credentials:
                llm_args["max_retries"] = env_credentials["max_retries"]

            logger.debug(f"Creating LLM with args: {list(llm_args.keys())}")
            return LLM(**llm_args)
        except Exception as e:
            raise e

    @classmethod
    async def create_chat_model_from_user_config(cls, user_config) -> Optional["LLM"]:
        """Create ChatLiteLLM from UserConfig object."""
        if not UserConfig or not isinstance(user_config, UserConfig):
            return None

        config = user_config.get_llm_config()

        # Merge in-memory env variables into process env so loaders can pick them up
        try:
            env_map = getattr(getattr(user_config, "env", None), "as_dict", lambda: {})()
            for k, v in env_map.items():
                if v is not None:
                    os.environ[k] = v
        except Exception:
            pass

        # Load from env only
        return await cls.create_chat_model(config, load_from_db=True, use_custom_endpoints=False)


async def create_chatlitellm_from_user_config(user_config) -> Optional["LLM"]:
    """
    Factory function to create ChatLiteLLM from UserConfig.
    Delegates to LLMFactory to avoid duplication.

    Args:
        user_config: UserConfig instance

    Returns:
        ChatLiteLLM instance or None
    """
    return await LLMFactory.create_chat_model_from_user_config(user_config)
