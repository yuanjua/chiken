"""
LLM Provider Factory

Simplified factory for creating ChatLiteLLM instances.
"""

import os
from typing import Any, Dict, Optional, TYPE_CHECKING
from loguru import logger
from .chatlitellm import LLM

from ..user_config import UserConfig
from ..user_config.provider_keys import get_provider_config, get_provider_api_key, get_provider_base_url

class LLMFactory:
    """Simplified factory for creating ChatLiteLLM instances."""
    
    @classmethod
    async def load_provider_credentials(cls, provider: str) -> Dict[str, Any]:
        """Load API key and base URL from database for a provider."""
        try:
            # Get all provider configs from database
            all_configs = {}
            provider_names = ["openai", "anthropic", "azure", "replicate", "cohere", "openrouter", "together", "huggingface"]
            
            for p in provider_names:
                config = await get_provider_config(p)
                if config:
                    all_configs[p] = config
            
            credentials = {}
            
            # Set environment variables for all providers with API keys
            env_key_map = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY", 
                "azure": "AZURE_API_KEY",
                "replicate": "REPLICATE_API_KEY",
                "cohere": "COHERE_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "together": "TOGETHERAI_API_KEY",
                "huggingface": "HF_TOKEN",
            }
            
            for p, config in all_configs.items():
                api_key = config.get("api_key")
                if api_key and p in env_key_map:
                    os.environ[env_key_map[p]] = api_key
            
            # Get specific provider config for base_url and fallback api_key
            provider_config = await get_provider_config(provider)
            if provider_config:
                # Add base URL if available and use_custom_endpoint is enabled for this provider
                base_url = provider_config.get("base_url")
                use_custom_endpoint = provider_config.get("use_custom_endpoint", False)
                
                if base_url and use_custom_endpoint:
                    credentials["base_url"] = base_url  # Use base_url, not api_base, for config
                    logger.info(f"🌐 Using base_url from database: {base_url}")

                # If provider not in named fields, use generic api_key
                api_key = provider_config.get("api_key")
                if api_key and provider not in ["openai", "anthropic", "azure", "replicate", "cohere", "openrouter"]:
                    credentials["api_key"] = api_key
                    logger.info(f"🔑 Using generic api_key for {provider}")
            
            return credentials
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

            # Load credentials from database if requested
            db_credentials = {}
            if load_from_db:
                db_credentials = await cls.load_provider_credentials(provider)

            # Merge database credentials with config (config takes precedence)
            final_config = {**db_credentials, **config}

            # Ensure use_custom_endpoints is always set and defaults to False
            if "use_custom_endpoints" not in final_config or final_config["use_custom_endpoints"] is None:
                final_config["use_custom_endpoints"] = False
            if use_custom_endpoints is None:
                use_custom_endpoints = final_config["use_custom_endpoints"]

            # Prepare LLM arguments with all possible named API key fields
            llm_args = {
                "model_name": final_config["model_name"],
                "temperature": final_config.get("temperature", 0.1),
                "max_tokens": final_config.get("num_tokens", 24 * 1024),
                "num_ctx": final_config.get("num_ctx", 4096),
            }

            # Add named API key fields if present
            named_key_fields = [
                "openai_api_key", "anthropic_api_key", "azure_api_key", 
                "replicate_api_key", "cohere_api_key", "openrouter_api_key"
            ]
            for field in named_key_fields:
                if field in final_config:
                    llm_args[field] = final_config[field]

            # Add generic api_key
            if "api_key" in final_config:
                llm_args["api_key"] = final_config["api_key"]

            # Handle base_url for providers that need it (especially Ollama)
            # For Ollama, we always need the base_url regardless of use_custom_endpoints setting
            if provider == "ollama" or use_custom_endpoints:
                if "api_base" in final_config:
                    llm_args["api_base"] = final_config["api_base"]
                elif "base_url" in final_config:
                    llm_args["api_base"] = final_config["base_url"]

            return LLM(**llm_args)
        except Exception as e:
            raise e
    
    @classmethod
    async def create_chat_model_from_user_config(cls, user_config) -> Optional["LLM"]:
        """Create ChatLiteLLM from UserConfig object."""
        if not UserConfig or not isinstance(user_config, UserConfig):
            return None

        config = user_config.get_llm_config()

        # Get use_custom_endpoints from user_config directly
        use_custom_endpoints = getattr(user_config, 'use_custom_endpoints', False)
        config["use_custom_endpoints"] = use_custom_endpoints
        
        return await cls.create_chat_model(config, load_from_db=use_custom_endpoints, use_custom_endpoints=use_custom_endpoints)

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
