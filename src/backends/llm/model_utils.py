"""
Model utilities for the entire backend system.
Provides functions to normalize and validate model names in LiteLLM format for both chat and embedding models.
"""

from loguru import logger

# logger is imported from loguru


def normalize_model_name(model_name: str | None, provider: str | None = None, model_type: str = "chat") -> str | None:
    """
    Normalize model name to LiteLLM provider/model format.

    Args:
        model_name: The model name to normalize
        provider: The provider (e.g., "ollama", "openai", "anthropic")
        model_type: The type of model ("chat" or "embedding")

    Returns:
        Normalized model name in LiteLLM format (e.g., "ollama/llama3", "gpt-4o")
        Returns None if model_name is None or empty
    """
    if not model_name or not model_name.strip():
        return None

    model_name = model_name.strip()

    # If model already has provider prefix, validate and return as-is
    if "/" in model_name:
        parts = model_name.split("/")
        if len(parts) >= 2:
            existing_provider = parts[0]
            model_part = "/".join(parts[1:])

            # Clean up common version suffixes
            if model_part.endswith(":latest"):
                model_part = model_part.replace(":latest", "")
                model_name = f"{existing_provider}/{model_part}"

            logger.debug(f"Model already has provider prefix: {model_name}")
            return model_name

    # Infer provider if not provided
    if not provider:
        provider = infer_provider_from_model(model_name, model_type)
        logger.debug(f"No provider specified, inferred '{provider}' for model: {model_name}")

    # Clean up version suffixes
    if model_name.endswith(":latest"):
        model_name = model_name.replace(":latest", "")

    # Format according to LiteLLM conventions
    normalized_name = format_model_for_litellm(provider, model_name)

    logger.debug(f"Normalized {model_type} model from '{model_name}' to '{normalized_name}'")
    return normalized_name


def infer_provider_from_model(model_name: str, model_type: str = "chat") -> str:
    """
    Infer provider from model name characteristics.

    Args:
        model_name: The model name
        model_type: The type of model ("chat" or "embedding")

    Returns:
        Inferred provider name
    """
    model_lower = model_name.lower()

    # OpenAI patterns
    if any(pattern in model_lower for pattern in ["gpt-", "text-embedding-", "text-davinci", "code-", "ada-"]):
        return "openai"

    # Anthropic patterns
    if model_lower.startswith("claude"):
        return "anthropic"

    # Embedding-specific patterns
    if model_type == "embedding":
        if any(name in model_lower for name in ["nomic", "all-minilm", "bge", "e5", "sentence-transformers"]):
            return "ollama"  # Common local embedding models
        elif "embed" in model_lower and any(provider in model_lower for provider in ["openai", "cohere", "voyage"]):
            # Try to extract provider from model name
            for provider in ["openai", "cohere", "voyage"]:
                if provider in model_lower:
                    return provider

    # Chat model patterns
    if model_type == "chat":
        if any(name in model_lower for name in ["llama", "mistral", "gemma", "qwen", "codellama", "phi"]):
            return "ollama"  # Common local chat models

    # Default fallback
    return "ollama"


def format_model_for_litellm(provider: str, model: str) -> str:
    """
    Format model name for LiteLLM based on provider.

    Args:
        provider: The provider name (e.g., "ollama", "openai", "anthropic")
        model: The model name

    Returns:
        Formatted model name for LiteLLM
    """
    if not model:
        return model

    # If model already has provider prefix, return as-is if it matches
    if "/" in model:
        model_provider = model.split("/")[0]
        if model_provider == provider:
            return model
        # If providers don't match, clean and re-format
        model = "/".join(model.split("/")[1:])

    # Format according to provider
    if provider == "ollama":
        return f"ollama/{model}"
    elif provider == "anthropic":
        # Claude models can be used with or without prefix
        if model.startswith("claude"):
            return model
        return f"anthropic/{model}"
    elif provider == "openai":
        # Most OpenAI models don't need prefix
        return model
    elif provider == "azure":
        return f"azure/{model}"
    elif provider == "google":
        return f"gemini/{model}"
    elif provider == "groq":
        return f"groq/{model}"
    elif provider == "together_ai":
        return f"together_ai/{model}"
    elif provider == "replicate":
        return f"replicate/{model}"
    elif provider == "huggingface":
        return f"huggingface/{model}"
    elif provider == "cohere":
        return f"cohere/{model}"
    elif provider == "voyage":
        return f"voyage/{model}"
    else:
        # For custom providers, add provider prefix
        return f"{provider}/{model}"


def extract_provider_from_model(model_name: str) -> str | None:
    """
    Extract provider from a LiteLLM model name.

    Args:
        model_name: The model name (e.g., "ollama/llama3", "gpt-4o")

    Returns:
        The provider name or None if no provider prefix found
    """
    if not model_name or "/" not in model_name:
        return None

    return model_name.split("/")[0]


def extract_model_from_litellm_name(model_name: str) -> str:
    """
    Extract the actual model name from a LiteLLM format string.

    Args:
        model_name: The LiteLLM model name (e.g., "ollama/llama3", "gpt-4o")

    Returns:
        The model name without provider prefix
    """
    if not model_name:
        return model_name

    if "/" in model_name:
        return "/".join(model_name.split("/")[1:])

    return model_name


def is_litellm_format(model_name: str) -> bool:
    """
    Check if a model name is in LiteLLM format (has provider prefix).

    Args:
        model_name: The model name to check

    Returns:
        True if the model name has a provider prefix, False otherwise
    """
    return bool(model_name and "/" in model_name)


# Convenience functions for specific model types
def normalize_chat_model_name(model_name: str | None, provider: str | None = None) -> str | None:
    """Normalize chat model name to LiteLLM format."""
    return normalize_model_name(model_name, provider, "chat")


def normalize_embedding_model_name(model_name: str | None, provider: str | None = None) -> str | None:
    """Normalize embedding model name to LiteLLM format."""
    return normalize_model_name(model_name, provider, "embedding")
