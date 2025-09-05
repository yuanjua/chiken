"""
Enhanced Environment Variable Parser with Database Sync

Updates the existing parser to load credentials from encrypted database
instead of os.environ to ensure sync with user settings.
"""

import os
from typing import Any, Optional

from loguru import logger

from ..user_config.encryption import decrypt_env_vars, get_cached_encryption_key


class EnvVarParserDB:
    """Enhanced environment variable parser that syncs with encrypted database."""

    @classmethod
    async def get_llm_credentials_from_db(cls, provider: str) -> dict[str, Any]:
        """
        Get LLM credentials from database, synced with user settings.
        This respects what user has set/unset in the settings UI.
        """
        try:
            from ..manager_singleton import ManagerSingleton

            db_manager = await ManagerSingleton.get_database_manager()
            encrypted_data = await db_manager.get_encrypted_env_vars()

            if not encrypted_data:
                logger.debug("No encrypted environment variables found")
                return {}

            encryption_key = get_cached_encryption_key()
            env_vars = decrypt_env_vars(encrypted_data, encryption_key)

            credentials = {}

            if provider == "ollama":
                if "OLLAMA_API_BASE" in env_vars:
                    credentials["api_base"] = env_vars["OLLAMA_API_BASE"]

            elif provider == "openai":
                if "OPENAI_API_KEY" in env_vars:
                    credentials["api_key"] = env_vars["OPENAI_API_KEY"]
                if "OPENAI_BASE_URL" in env_vars:
                    credentials["api_base"] = env_vars["OPENAI_BASE_URL"]

            elif provider == "anthropic":
                if "ANTHROPIC_API_KEY" in env_vars:
                    credentials["api_key"] = env_vars["ANTHROPIC_API_KEY"]

            elif provider == "azure":
                if "AZURE_OPENAI_API_KEY" in env_vars:
                    credentials["api_key"] = env_vars["AZURE_OPENAI_API_KEY"]
                if "AZURE_OPENAI_ENDPOINT" in env_vars:
                    credentials["api_base"] = env_vars["AZURE_OPENAI_ENDPOINT"]

            elif provider == "google":
                if "GOOGLE_API_KEY" in env_vars:
                    credentials["api_key"] = env_vars["GOOGLE_API_KEY"]

            elif provider == "hosted_vllm":
                if "HOSTED_VLLM_API_KEY" in env_vars:
                    credentials["api_key"] = env_vars["HOSTED_VLLM_API_KEY"]
                elif "OPENAI_API_KEY" in env_vars:  # Fallback
                    credentials["api_key"] = env_vars["OPENAI_API_KEY"]
                if "HOSTED_VLLM_API_BASE" in env_vars:
                    credentials["api_base"] = env_vars["HOSTED_VLLM_API_BASE"]

            # Add common settings
            if "REQUEST_TIMEOUT" in env_vars:
                try:
                    credentials["timeout"] = int(env_vars["REQUEST_TIMEOUT"])
                except ValueError:
                    pass
            if "MAX_RETRIES" in env_vars:
                try:
                    credentials["max_retries"] = int(env_vars["MAX_RETRIES"])
                except ValueError:
                    pass

            logger.debug(f"Loaded credentials for {provider}: {list(credentials.keys())}")
            return credentials

        except Exception as e:
            logger.error(f"Failed to load LLM credentials for {provider}: {e}")
            return {}
