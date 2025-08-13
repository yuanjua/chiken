"""
LLM Service Module
Provides service-layer functions for LLM operations including model management and configuration.
"""

import os
from datetime import datetime
from typing import Any

import aiohttp
import litellm
from fastapi import HTTPException
from litellm import models_by_provider
from loguru import logger

from ..user_config import UserConfig

# logger is imported from loguru


class LLMService:
    """Service class for LLM operations."""

    @staticmethod
    def get_all_models() -> list[str]:
        """Return a flat list of all models from all providers."""
        return [model for models in models_by_provider.values() for model in models]

    @staticmethod
    def get_available_providers() -> list[dict[str, Any]]:
        """Return provider info with id, name, model count, and type."""
        providers = []
        for provider, models in models_by_provider.items():
            providers.append(
                {
                    "id": provider,
                    "name": provider.replace("_", " ").title(),
                    "model_count": len(models),
                    "type": "cloud"
                    if provider in ["openai", "anthropic", "azure", "google"]
                    else "local"
                    if provider == "ollama"
                    else "service",
                }
            )
        return providers

    @staticmethod
    def get_litellm_model_list() -> list[str]:
        """Return all models, sorted."""
        return sorted(LLMService.get_all_models())

    @staticmethod
    def get_litellm_models_by_provider(provider: str) -> list[str]:
        """Return models for a specific provider."""
        return sorted(models_by_provider.get(provider, []))

    @staticmethod
    async def get_model_cost_info(model_name: str) -> dict[str, Any] | None:
        """Get cost information for a model using LiteLLM."""
        try:
            # Get cost information from LiteLLM
            cost_info = litellm.model_cost.get(model_name)
            if cost_info:
                return {
                    "model": model_name,
                    "input_cost_per_token": cost_info.get("input_cost_per_token"),
                    "output_cost_per_token": cost_info.get("output_cost_per_token"),
                    "max_tokens": cost_info.get("max_tokens"),
                    "currency": "USD",
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get cost info for {model_name}: {e}")
            return None

    @staticmethod
    async def get_llm_config(config: UserConfig) -> dict[str, Any]:
        """Get current LLM configuration with enhanced model information."""
        try:
            available_models = []
            provider_type = config.provider_type

            # Determine display base URL from env rather than stored field
            display_base_url = None

            if provider_type == "ollama":
                try:
                    effective_base = os.environ.get("OLLAMA_API_BASE")
                    display_base_url = effective_base or None
                    available_models = []
                    if effective_base:
                        timeout = aiohttp.ClientTimeout(total=5.0)
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            async with session.get(f"{effective_base}/api/tags") as response:
                                if response.status == 200:
                                    models_data = await response.json()
                                    available_models = [model["name"] for model in models_data.get("models", [])]
                except Exception:
                    available_models = []
                # Also add LiteLLM Ollama models for completion
                litellm_ollama_models = LLMService.get_litellm_models_by_provider("ollama")
                available_models.extend([model.replace("ollama/", "") for model in litellm_ollama_models])
                available_models = list(set(available_models))
            else:
                available_models = LLMService.get_litellm_models_by_provider(provider_type)
            cost_info = await LLMService.get_model_cost_info(config.model_name)
            return {
                "provider": provider_type,
                "model_name": config.model_name,
                "embed_model": config.embed_model,
                "embed_provider": config.embed_provider,
                "temperature": config.temperature,
                "num_ctx": config.num_ctx,
                "base_url": display_base_url if provider_type in ("ollama", "openai") else None,
                "api_key": None,
                "available_models": available_models,
                "suggested_models": LLMService.get_litellm_models_by_provider(provider_type),
                "cost_info": cost_info,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get LLM config: {str(e)}")

    @staticmethod
    async def _enhance_models_with_metadata(models: list[str], provider: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Helper method to enhance model list with cost information and metadata.
        Reused across different model suggestion methods.

        Args:
            models: List of model names
            provider: Provider name
            limit: Maximum number of models to return

        Returns:
            List of enhanced model dictionaries
        """
        enhanced_models = []
        for model in sorted(models)[:limit]:
            cost_info = await LLMService.get_model_cost_info(model)
            enhanced_model = {
                "name": model,
                "display_name": model.replace(f"{provider}/", "") if "/" in model else model,
                "provider": provider,
                "cost_info": cost_info,
            }
            enhanced_models.append(enhanced_model)

        return enhanced_models

    @staticmethod
    async def get_model_completion_suggestions(
        provider: str, partial_model: str = "", base_url: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get model completion suggestions for a provider using models_by_provider.

        Args:
            provider: Provider name (openai, anthropic, ollama, etc.)
            partial_model: Partial model name for filtering suggestions
            base_url: Optional base URL for providers like Ollama

        Returns:
            List of model suggestions with metadata
        """
        try:
            # For Ollama, prefer provided base_url; otherwise fall back to env only
            if provider == "ollama":
                effective_base_url: str | None = base_url
                if not effective_base_url:
                    effective_base_url = os.environ.get("OLLAMA_API_BASE")

            # If we have an effective base URL for Ollama, query the instance
            if provider == "ollama" and (locals().get("effective_base_url") or base_url):
                try:
                    # Get models from the specific Ollama instance
                    chosen_base = locals().get("effective_base_url") or base_url
                    model_data = await LLMService.get_ollama_model_list(chosen_base)  # type: ignore[arg-type]
                    available_models = model_data.get("models", [])

                    # Extract model names from Ollama response
                    model_names = []
                    for model in available_models:
                        if isinstance(model, dict):
                            name = model.get("name", "")
                            if name:
                                model_names.append(name)

                    # Filter by partial model name if provided
                    if partial_model:
                        partial_lower = partial_model.lower()
                        filtered_models = [model for model in model_names if partial_lower in model.lower()]
                    else:
                        filtered_models = model_names

                    # Enhance with metadata
                    suggestions = await LLMService._enhance_models_with_metadata(filtered_models, provider, limit=20)

                    return suggestions

                except Exception as e:
                    logger.warning(f"Failed to get Ollama models from {base_url}: {e}")
                    # Fall back to static list
                    pass

            # Use models_by_provider for direct access to provider models
            if provider in models_by_provider:
                provider_models = models_by_provider[provider]

                # Filter by partial model name if provided
                if partial_model:
                    partial_lower = partial_model.lower()
                    filtered_models = [model for model in provider_models if partial_lower in model.lower()]
                else:
                    filtered_models = provider_models

                # Enhance with cost information and metadata
                suggestions = await LLMService._enhance_models_with_metadata(filtered_models, provider, limit=20)

                return suggestions
            else:
                # Fallback to previous method for providers not in models_by_provider
                provider_models = LLMService.get_litellm_models_by_provider(provider)

                # Filter by partial model name if provided
                if partial_model:
                    partial_lower = partial_model.lower()
                    filtered_models = [model for model in provider_models if partial_lower in model.lower()]
                else:
                    filtered_models = provider_models

                # Enhance with cost information and metadata
                suggestions = await LLMService._enhance_models_with_metadata(filtered_models, provider, limit=20)

                return suggestions
        except Exception as e:
            logger.error(f"Failed to get model suggestions for {provider}: {e}")
            return []

    @staticmethod
    async def get_ollama_model_list() -> dict[str, Any]:
        """Get list of available Ollama models with enhanced suggestions."""
        try:
            base_url = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
            local_models = []
            suggested_models = []
            timeout = aiohttp.ClientTimeout(total=3.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{base_url}/api/tags") as response:
                    if response.status == 200:
                        models_data = await response.json()
                        local_models = models_data.get("models", [])
                    else:
                        logger.error(f"Failed to get models from Ollama: {response.status} - {await response.text()}")
                        raise HTTPException(status_code=502, detail="Failed to get models from Ollama")
            return {
                "models": local_models,
                "suggested_models": suggested_models,
                "provider": "ollama",
                "count": len(local_models),
                "suggestions_count": len(suggested_models),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting Ollama models from {base_url}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get Ollama models: {str(e)}")

    @staticmethod
    async def set_model_params(config: UserConfig, model_params: dict[str, Any]) -> dict[str, Any]:
        """Set model parameters with validation."""
        try:
            # Import here to avoid circular imports
            from ..manager_singleton import ManagerSingleton

            # Update configuration with new parameters
            updated_config = await ManagerSingleton.update_user_config(**model_params)

            logger.info(f"Updated model params: {model_params}")
            return {
                "success": True,
                "message": "Model parameters updated successfully",
                "updated_fields": list(model_params.keys()),
            }

        except Exception as e:
            logger.error(f"Failed to set model params: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid model parameters: {str(e)}")

    @staticmethod
    async def get_provider_model_list(config: UserConfig) -> dict[str, Any]:
        provider_type = config.provider_type
        try:
            if provider_type == "ollama":
                return await LLMService.get_ollama_model_list(config.base_url)
            elif provider_type in ["openai", "azure_openai"]:
                return await LLMService._get_openai_models(config)
            elif provider_type == "anthropic":
                return await LLMService._get_anthropic_models(config)
            else:
                suggested_models = LLMService.get_litellm_models_by_provider(provider_type)
                return {
                    "models": [],
                    "suggested_models": [{"name": model, "full_name": model} for model in suggested_models],
                    "count": 0,
                    "suggestions_count": len(suggested_models),
                    "provider": provider_type,
                    "timestamp": datetime.now().isoformat(),
                }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get models for {provider_type}: {str(e)}")

    @staticmethod
    async def _get_openai_models(config: UserConfig) -> dict[str, Any]:
        suggested_models = LLMService.get_litellm_models_by_provider("openai")
        models_with_cost = await LLMService._enhance_models_with_metadata(suggested_models, "openai")
        return {
            "models": models_with_cost,
            "count": len(models_with_cost),
            "provider": "openai",
            "note": "Models from LiteLLM - requires API key for access",
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    async def _get_anthropic_models(config: UserConfig) -> dict[str, Any]:
        suggested_models = LLMService.get_litellm_models_by_provider("anthropic")
        models_with_cost = await LLMService._enhance_models_with_metadata(suggested_models, "anthropic")
        return {
            "models": models_with_cost,
            "count": len(models_with_cost),
            "provider": "anthropic",
            "note": "Models from LiteLLM - requires API key for access",
            "timestamp": datetime.now().isoformat(),
        }
