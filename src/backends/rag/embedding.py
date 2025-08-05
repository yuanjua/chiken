import litellm
from loguru import logger
from typing import List, Optional
from ..manager_singleton import ManagerSingleton
from ..model_utils import extract_provider_from_model, is_litellm_format


class LiteLLMEmbeddingFunction:
    """
    LiteLLM embedding function that supports multiple providers.
    
    This is the primary embedding function for the system, supporting:
    - Multiple providers (OpenAI, Anthropic, Ollama, etc.)
    - Consistent API through LiteLLM
    - Proper error handling and logging
    """
    
    def __init__(self, model_name: str, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        
        # Note: We don't set global LiteLLM configs here to avoid conflicts
        # Instead, we pass them per-request to maintain thread safety
            
    def __call__(self, input: List[str]) -> List[List[float]]:
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
                
                # Add optional parameters if provided
                if self.api_key:
                    params["api_key"] = self.api_key
                if self.base_url:
                    params["api_base"] = self.base_url
                
                # Use LiteLLM embedding function
                response = litellm.embedding(**params)
                
                # Extract embedding from response
                if response and hasattr(response, 'data') and response.data:
                    embedding = response.data[0]['embedding']
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
        logger.error(f"No embedding model configured")

    # Fetch the API key for the embedding provider (if any)
    from ..user_config.provider_keys import get_provider_api_key
    provider = extract_provider_from_model(embed_model) if is_litellm_format(embed_model) else user_config.embed_provider
    api_key = None
    if provider:
        api_key = await get_provider_api_key(provider)

    # For Ollama models, try custom implementation first to avoid LiteLLM issues
    if provider == "ollama" or "ollama/" in embed_model or not provider:
        try:
            from .custom_ollama_embedding import get_custom_ollama_embedding_function
            logger.info(f"Using custom Ollama embedding function for model: {embed_model}")
            return await get_custom_ollama_embedding_function(model=embed_model)
        except Exception as e:
            logger.warning(f"Custom Ollama embedding failed, falling back to LiteLLM: {e}")

    # Fallback to LiteLLM for non-Ollama providers or if custom Ollama fails
    try:
        return LiteLLMEmbeddingFunction(
            model_name=embed_model,  # Use model name as-is (LiteLLM handles provider prefixes)
            api_key=api_key,
            base_url=user_config.base_url if (provider == "ollama" or not provider) else None
        )
    except Exception as e:
        logger.error(f"Error creating embedding function for model {embed_model}: {e}")
        
        # If LiteLLM also fails and it's an Ollama model, try custom implementation as last resort
        if provider == "ollama" or "ollama/" in embed_model or not provider:
            try:
                from .custom_ollama_embedding import get_custom_ollama_embedding_function
                logger.info(f"LiteLLM failed, using custom Ollama embedding function as last resort for model: {embed_model}")
                return await get_custom_ollama_embedding_function(model=embed_model)
            except Exception as e2:
                logger.error(f"Both LiteLLM and custom Ollama embedding failed: {e2}")
                raise e2
        else:
            raise e