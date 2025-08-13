"""
LLM Provider Factory

Simplified factory for creating ChatLiteLLM instances.
"""

import os
from typing import Any, Dict, Optional, TYPE_CHECKING
from loguru import logger
from .chatlitellm import LLM

from ..user_config import UserConfig

class LLMFactory:
    """Simplified factory for creating ChatLiteLLM instances."""
    
    @classmethod
    async def load_provider_credentials(cls, provider: str) -> Dict[str, Any]:
        """Return only base_url for ollama (if set). API keys are read by LiteLLM from env."""
        try:
            if provider == "ollama":
                base = os.environ.get("OLLAMA_API_BASE")
                return {"base_url": base} if base else {}
            return {}
        except Exception as e:
            logger.error(f"⚠️ Failed to load credentials for {provider}: {e}")
            return {}
    
    @classmethod
    async def create_chat_model(cls, config: Dict[str, Any], load_from_db: bool = True, use_custom_endpoints: Optional[bool] = None) -> Optional["LLM"]:
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

            # Load credentials from environment
            env_credentials = await cls.load_provider_credentials(provider)

            # Merge env credentials with config (env takes precedence for base_url and keys)
            final_config = {**config, **env_credentials}

            # Prepare minimal LLM arguments; LiteLLM reads API keys from env
            llm_args = {
                "model_name": final_config["model_name"],
                "temperature": final_config.get("temperature", 0.1),
                "max_tokens": final_config.get("num_tokens", 24 * 1024),
                "num_ctx": final_config.get("num_ctx", 4096),
            }

            # Handle base_url only for ollama
            if provider == "ollama":
                if "base_url" in final_config:
                    llm_args["api_base"] = final_config["base_url"]
                else:
                    env_base = os.environ.get("OLLAMA_API_BASE")
                    if env_base:
                        llm_args["api_base"] = env_base
            logger.debug(f"Creating LLM with args: {llm_args}")
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
