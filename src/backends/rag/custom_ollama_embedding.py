"""
Custom Ollama Embedding Function

LiteLLM fails with Ollama remote endpoints
"""

import aiohttp
import asyncio
import json
from typing import List, Dict, Any, Optional
from loguru import logger
import time
from ..manager_singleton import ManagerSingleton
import os

class CustomOllamaEmbeddingFunction:
    """
    Custom Ollama embedding function that directly calls the Ollama API.
    
    This bypasses LiteLLM issues
    """
    
    def __init__(
        self, 
        model_name: str = "nomic-embed-text:latest",
        primary_base_url: str = "http://localhost:11434",
        fallback_base_url: str = "http://localhost:11434",
        timeout: int = 30
    ):
        self.model_name = model_name.replace("ollama/", "")  # Remove provider prefix if present
        self.primary_base_url = primary_base_url.rstrip('/')
        self.fallback_base_url = fallback_base_url.rstrip('/')
        self.timeout = timeout
        
        # Semaphore to limit concurrent requests
        self._semaphore = asyncio.Semaphore(3)

    def name(self) -> str:
        """
        Returns the name of the embedding function.
        ChromaDB expects this method for validation.
        """
        return f"ollama-{self.model_name}"
    
    async def _get_embedding_from_url(self, text: str, base_url: str) -> List[float]:
        """Get embedding from a specific Ollama instance."""
        url = f"{base_url}/api/embed"
        payload = {
            "model": self.model_name,
            "input": text
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    if "embeddings" in result and result["embeddings"]:
                        return result["embeddings"][0]
                    else:
                        raise ValueError(f"No embeddings in response: {result}")
                else:
                    error_text = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"HTTP {response.status}: {error_text}"
                    )
    
    async def _get_single_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text with minimal retry logic."""
        urls_to_try = [self.primary_base_url, self.fallback_base_url]
        
        for url in urls_to_try:
            try:
                async with self._semaphore:  # Limit concurrent requests
                    start_time = time.time()
                    embedding = await self._get_embedding_from_url(text, url)
                    duration = time.time() - start_time
                    # logger.debug(f"Got embedding from {url} in {duration:.2f}s")
                    return embedding
                    
            except Exception as e:
                logger.warning(f"Failed to get embedding from {url}: {e}")
                continue
        
        raise RuntimeError(f"Failed to get embedding from all URLs: {urls_to_try}")
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """
        Synchronous interface for ChromaDB compatibility.
        
        Always uses a thread executor to avoid event loop conflicts.
        """
        texts = input if isinstance(input, list) else [input]
        
        # Always use thread executor to avoid event loop conflicts
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(self._sync_get_embeddings_fallback, texts)
            return future.result()
    
    def _sync_get_embeddings_fallback(self, texts: List[str]) -> List[List[float]]:
        """Synchronous wrapper that creates a new event loop in a separate thread."""
        # Create a new event loop for this thread
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._async_get_embeddings(texts))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    
    async def _async_get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Asynchronous method to get embeddings for multiple texts."""
        # logger.debug(f"Getting embeddings for {len(texts)} texts")
        
        # Process texts in batches to avoid overwhelming the service
        batch_size = 5
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            tasks = [self._get_single_embedding(text) for text in batch]
            
            try:
                batch_embeddings = await asyncio.gather(*tasks)
                all_embeddings.extend(batch_embeddings)
                # logger.debug(f"Processed batch {i//batch_size + 1}, total embeddings: {len(all_embeddings)}")
            except Exception as e:
                logger.error(f"Failed to process batch {i//batch_size + 1}: {e}")
                raise
        
        logger.info(f"Successfully generated {len(all_embeddings)} embeddings")
        return all_embeddings


async def get_custom_ollama_embedding_function(
    model: Optional[str] = None,
    primary_url: Optional[str] = None,
    fallback_url: Optional[str] = None
) -> CustomOllamaEmbeddingFunction:
    """
    Factory function to create a custom Ollama embedding function with user config.
    """
    
    user_config = await ManagerSingleton.get_user_config()
    
    # Use provided parameters or fall back to keyring/env policy (keyring otherwise default)
    model_name = model or user_config.embed_model or "nomic-embed-text:latest"
    primary_base_url = None
    primary_base_url = os.environ.get("OLLAMA_API_BASE")
    if not primary_base_url:
        primary_base_url = primary_url or "http://localhost:11434"
    fallback_base_url = fallback_url or "http://localhost:11434"
    
    return CustomOllamaEmbeddingFunction(
        model_name=model_name,
        primary_base_url=primary_base_url,
        fallback_base_url=fallback_base_url
    )
