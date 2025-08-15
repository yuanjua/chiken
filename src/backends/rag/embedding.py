import os

import litellm
from fastapi import HTTPException
from loguru import logger

from ..llm.model_utils import extract_provider_from_model, is_litellm_format
from ..manager_singleton import ManagerSingleton
from .custom_ollama_embedding import get_custom_ollama_embedding_function


class LiteLLMEmbeddingFunction:
    """
    LiteLLM embedding function that supports multiple providers.

    This is the primary embedding function for the system, supporting:
    - Multiple providers (OpenAI, Anthropic, Ollama, etc.)
    - Consistent API through LiteLLM
    - Proper error handling and logging
    """

    def __init__(self, model_name: str, api_key: str | None = None, base_url: str | None = None):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url

        # Note: We don't set global LiteLLM configs here to avoid conflicts
        # Instead, we pass them per-request to maintain thread safety

    def name(self) -> str:
        """Return the name of the embedding function for ChromaDB compatibility."""
        return f"litellm_{self.model_name.replace('/', '_').replace('-', '_')}"

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts using LiteLLM."""
        texts = input if isinstance(input, list) else [input]
        embeddings = []

        for text in texts:
            try:
                # Prepare LiteLLM parameters
                params = {
                    "model": self.model_name,
                    "input": text,
                }

                # Add optional API key if provided
                # LiteLLM will automatically handle base URLs via environment variables
                if self.api_key:
                    params["api_key"] = self.api_key

                # Use LiteLLM embedding function
                response = litellm.embedding(**params)

                # Extract embedding from response
                if response and hasattr(response, "data") and response.data:
                    embedding = response.data[0]["embedding"]
                    embeddings.append(embedding)
                else:
                    raise ValueError(f"Empty or invalid embedding response for model {self.model_name}")

            except Exception as e:
                logger.error(f"Error getting LiteLLM embedding for text with model {self.model_name}: {e}")
                raise e

        return embeddings


async def get_embedding_function(model=None):
    """Get a working embedding function for our setup."""
    user_config = await ManagerSingleton.get_user_config()
    embed_model = model if model else user_config.embed_model

    # Use configured embedding model or fallback to a sensible default
    if not embed_model or embed_model.strip() == "":
        logger.error("No embedding model configured")

    # Determine provider
    provider = (
        extract_provider_from_model(embed_model)
        if is_litellm_format(embed_model)
        else (user_config.embed_provider or "ollama")
    )

    # Resolve API key from runtime env only (set via /llm/credentials)
    api_key: str | None = None
    provider_env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "azure": "AZURE_API_KEY",
        "replicate": "REPLICATE_API_KEY",
        "cohere": "COHERE_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "together": "TOGETHERAI_API_KEY",
        "huggingface": "HF_TOKEN",
        "hosted_vllm": "HOSTED_VLLM_API_KEY",
    }
    if provider in provider_env_map:
        api_key = os.environ.get(provider_env_map[provider])
    if not api_key:
        api_key = os.environ.get("API_KEY")

    # Validate presence for cloud providers that require keys
    PROVIDERS_REQUIRING_API_KEYS = (
        "openai",
        "anthropic",
        "cohere",
        "azure",
        "openrouter",
        "replicate",
    )
    if provider in PROVIDERS_REQUIRING_API_KEYS and not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"Missing API key for embedding provider '{provider}'. Please set it in Environment Variables.",
        )

    # Use LiteLLM for all providers - it handles base URLs automatically via environment variables
    # LiteLLM will use env vars like OLLAMA_API_BASE, HOSTED_VLLM_API_BASE, OPENAI_BASE_URL, etc.
    return LiteLLMEmbeddingFunction(
        model_name=embed_model,
        api_key=api_key,
        base_url=None,  # Let LiteLLM handle URLs via env vars
    )


async def get_provider_api_key(provider: str) -> str | None:
    """Resolve provider API key from runtime environment variables only."""
    provider_env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "azure": "AZURE_API_KEY",
        "replicate": "REPLICATE_API_KEY",
        "cohere": "COHERE_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "together": "TOGETHERAI_API_KEY",
        "huggingface": "HF_TOKEN",
        "hosted_vllm": "HOSTED_VLLM_API_KEY",
    }
    env_name = provider_env_map.get(provider)
    if env_name:
        return os.environ.get(env_name)
    return os.environ.get("API_KEY")
