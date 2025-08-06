"""
Test suite for RAG (Retrieval-Augmented Generation) functionality.

This module tests the core RAG operations including:
- Document embedding and storage
- Semantic search across knowledge bases
- Document retrieval and reconstruction
- Custom Ollama embedding function
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import List, Dict, Any
import aiohttp

# Import the modules we're testing
from src.backends.rag.db import RAGDB, add_documents_to_kb, get_embeddings_for_kb
from src.backends.rag.service import RAGService
from src.backends.rag.embedding import get_embedding_function, LiteLLMEmbeddingFunction
from src.backends.rag.custom_ollama_embedding import CustomOllamaEmbeddingFunction, get_custom_ollama_embedding_function


class TestCustomOllamaEmbeddingFunction:
    """Test suite for the custom Ollama embedding function."""
    
    @pytest.fixture
    def embedding_function(self):
        """Create a test embedding function."""
        return CustomOllamaEmbeddingFunction(
            model_name="nomic-embed-text:latest",
            primary_base_url="http://test-primary:11434",
            fallback_base_url="http://test-fallback:11434",
            timeout=10
        )
    
    @pytest.mark.asyncio
    async def test_successful_embedding_primary_url(self, embedding_function):
        """Test successful embedding generation from primary URL."""
        mock_response = {
            "embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5]]
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response_obj = Mock()
            mock_response_obj.status = 200
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response_obj)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
            
            embedding = await embedding_function._get_single_embedding("test text")
            
            assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fallback_to_secondary_url(self, embedding_function):
        """Test fallback to secondary URL when primary fails."""
        primary_error = aiohttp.ClientResponseError(
            request_info=Mock(),
            history=(),
            status=502,
            message="Bad Gateway"
        )
        
        fallback_response = {
            "embeddings": [[0.6, 0.7, 0.8, 0.9, 1.0]]
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # First call (primary) fails, second call (fallback) succeeds
            mock_response_success = Mock()
            mock_response_success.status = 200
            mock_response_success.json = AsyncMock(return_value=fallback_response)
            
            mock_post.side_effect = [
                # Primary URL fails
                AsyncMock(side_effect=primary_error),
                # Fallback URL succeeds
                AsyncMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response_success),
                    __aexit__=AsyncMock(return_value=None)
                ))
            ]
            
            embedding = await embedding_function._get_single_embedding("test text")
            
            assert embedding == [0.6, 0.7, 0.8, 0.9, 1.0]
            assert mock_post.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_retry_logic_with_exponential_backoff(self, embedding_function):
        """Test retry logic with exponential backoff."""
        with patch('aiohttp.ClientSession.post') as mock_post, \
             patch('asyncio.sleep') as mock_sleep:
            
            # Fail first attempt, succeed on second
            mock_post.side_effect = [
                AsyncMock(side_effect=aiohttp.ClientError("Connection failed")),
                AsyncMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=Mock(
                        status=200,
                        json=AsyncMock(return_value={"embeddings": [[1, 2, 3]]})
                    )),
                    __aexit__=AsyncMock(return_value=None)
                ))
            ]
            
            embedding = await embedding_function._get_single_embedding("test text")
            
            assert embedding == [1, 2, 3]
            mock_sleep.assert_called_once_with(1)  # 2^0 = 1 second backoff
    
    @pytest.mark.asyncio
    async def test_batch_embedding_processing(self, embedding_function):
        """Test batch processing of multiple texts."""
        texts = ["text1", "text2", "text3"]
        expected_embeddings = [
            [0.1, 0.2],
            [0.3, 0.4], 
            [0.5, 0.6]
        ]
        
        with patch.object(embedding_function, '_get_single_embedding') as mock_single:
            mock_single.side_effect = expected_embeddings
            
            result = await embedding_function._async_get_embeddings(texts)
            
            assert result == expected_embeddings
            assert mock_single.call_count == 3
    
    def test_synchronous_interface(self, embedding_function):
        """Test the synchronous interface for ChromaDB compatibility."""
        with patch.object(embedding_function, '_async_get_embeddings') as mock_async, \
             patch('asyncio.run') as mock_run:
            
            mock_run.return_value = [[1, 2, 3]]
            
            result = embedding_function(["test text"])
            
            assert result == [[1, 2, 3]]
            mock_run.assert_called_once()


class TestRAGDB:
    """Test suite for the RAGDB class."""
    
    @pytest.fixture
    def mock_embeddings(self):
        """Create a mock embedding function."""
        mock = Mock()
        mock.__call__ = Mock(return_value=[[0.1, 0.2, 0.3]])
        return mock
    
    @pytest.fixture
    def ragdb(self, mock_embeddings):
        """Create a RAGDB instance with mocked dependencies."""
        with patch('src.backends.rag.db.client') as mock_client:
            ragdb = RAGDB(embeddings=mock_embeddings)
            ragdb.client = mock_client
            return ragdb

    @pytest.mark.asyncio
    async def test_get_or_create_collection_async(self, ragdb, mock_embeddings):
        """Test asynchronous collection creation/retrieval."""
        mock_collection = Mock()
        ragdb.client.get_or_create_collection.return_value = mock_collection
        
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_executor = Mock()
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_collection)
            
            result = await ragdb.get_or_create_collection("test_collection")
            
            assert result == mock_collection
            mock_loop.return_value.run_in_executor.assert_called_once()
    
    def test_get_unique_sources(self, ragdb, mock_embeddings):
        """Test retrieval of unique sources from a collection."""
        mock_collection = Mock()
        mock_collection.get.return_value = {
            'metadatas': [
                {'source': 'doc1.pdf', 'title': 'Document 1', 'key': 'key1'},
                {'source': 'doc2.pdf', 'title': 'Document 2', 'key': 'key2'},
                {'source': 'doc1.pdf', 'title': 'Document 1', 'key': 'key1'},  # Duplicate
            ]
        }
        ragdb.client.get_collection.return_value = mock_collection
        
        sources = ragdb.get_unique_sources("test_collection")
        
        assert len(sources) == 2
        assert sources[0]['source'] == 'doc1.pdf'
        assert sources[1]['source'] == 'doc2.pdf'
    
    @pytest.mark.asyncio
    async def test_find_document_by_source_or_key(self, ragdb, mock_embeddings):
        """Test document finding by source or key."""
        # Mock uploaded_files collection
        mock_uploaded_collection = Mock()
        mock_uploaded_collection.get.return_value = {
            "documents": ["Full document content"],
            "metadatas": [{"source": "test.pdf", "key": "test_key"}]
        }
        
        # Mock KB collection  
        mock_kb_collection = Mock()
        mock_kb_collection.get.return_value = {
            "documents": ["Chunk 1", "Chunk 2"],
            "metadatas": [{"source": "test.pdf"}, {"source": "test.pdf"}]
        }
        
        def mock_get_collection(name, **kwargs):
            if name == "uploaded_files":
                return mock_uploaded_collection
            else:
                return mock_kb_collection
        
        ragdb.client.get_collection.side_effect = mock_get_collection
        
        # Test finding in uploaded_files
        result = await ragdb.find_document_by_source_or_key("test.pdf", "test_key", ["kb1"])
        
        assert result["type"] == "full_document"
        assert result["content"] == "Full document content"
        assert result["source"] == "uploaded_files"


class TestRAGService:
    """Test suite for the RAGService class."""
    
    @pytest.mark.asyncio
    async def test_get_active_knowledge_bases(self):
        """Test retrieval of active knowledge bases."""
        with patch.object(RAGService, '_initialize_active_knowledge_bases') as mock_init:
            RAGService._active_knowledge_bases = ["kb1", "kb2", "kb3"]
            
            result = await RAGService.get_active_knowledge_bases()
            
            assert result == ["kb1", "kb2", "kb3"]
            assert isinstance(result, list)  # Should be a copy
    
    @pytest.mark.asyncio
    async def test_set_active_knowledge_bases_with_validation(self):
        """Test setting active knowledge bases with validation."""
        mock_db_manager = Mock()
        mock_db_manager.list_knowledge_bases = AsyncMock(return_value=[
            {"id": "kb1"}, {"id": "kb2"}, {"id": "kb3"}
        ])
        
        with patch('src.backends.rag.service.get_database_manager', return_value=mock_db_manager), \
             patch('src.backends.rag.service.ManagerSingleton.update_user_config') as mock_update:
            
            result = await RAGService.set_active_knowledge_bases(["kb1", "kb3", "invalid_kb"])
            
            assert result is True
            assert RAGService._active_knowledge_bases == ["kb1", "kb3"]
            mock_update.assert_called_once_with(active_knowledge_base_ids=["kb1", "kb3"])
    
    @pytest.mark.asyncio
    async def test_query_documents_with_multiple_kbs(self):
        """Test querying documents across multiple knowledge bases."""
        mock_db_manager = Mock()
        mock_db_manager.resolve_knowledge_base_id = AsyncMock(side_effect=lambda x: x)
        mock_db_manager.get_knowledge_base_by_id = AsyncMock(return_value={
            "id": "test_kb",
            "embed_model": "test-embed-model"
        })
        
        mock_embeddings = Mock()
        mock_ragdb = Mock()
        mock_ragdb.query.return_value = {
            "documents": [["Test document content"]],
            "metadatas": [[{"source": "test.pdf", "key": "test_key"}]],
            "distances": [[0.5]]
        }
        
        with patch('src.backends.rag.service.get_database_manager', return_value=mock_db_manager), \
             patch('src.backends.rag.service.get_embedding_function', return_value=mock_embeddings), \
             patch('src.backends.rag.service.RAGDB', return_value=mock_ragdb):
            
            result = await RAGService.query_documents(
                query_text="test query",
                knowledge_base_names=["kb1", "kb2"],
                k=5
            )
            
            assert len(result) > 0
            assert result[0]["content"] == "Test document content"
            assert result[0]["distance"] == 0.5


class TestEmbeddingFunction:
    """Test suite for embedding function selection and fallback logic."""
    
    @pytest.mark.asyncio
    async def test_get_embedding_function_ollama_custom(self):
        """Test that Ollama models use custom embedding function."""
        mock_user_config = Mock()
        mock_user_config.embed_model = "ollama/nomic-embed-text:latest"
        mock_user_config.embed_provider = "ollama"
        mock_user_config.base_url = "http://localhost:11434"
        
        mock_custom_function = Mock(spec=CustomOllamaEmbeddingFunction)
        
        with patch('src.backends.rag.embedding.ManagerSingleton.get_user_config', 
                  return_value=mock_user_config), \
             patch('src.backends.rag.embedding.get_custom_ollama_embedding_function',
                  return_value=mock_custom_function) as mock_get_custom:
            
            result = await get_embedding_function()
            
            assert result == mock_custom_function
            mock_get_custom.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_embedding_function_fallback_to_litellm(self):
        """Test fallback to LiteLLM when custom Ollama fails."""
        mock_user_config = Mock()
        mock_user_config.embed_model = "openai/text-embedding-ada-002"
        mock_user_config.embed_provider = "openai"
        mock_user_config.base_url = None
        
        mock_litellm_function = Mock(spec=LiteLLMEmbeddingFunction)
        
        with patch('src.backends.rag.embedding.ManagerSingleton.get_user_config', 
                  return_value=mock_user_config), \
             patch('src.backends.rag.embedding.LiteLLMEmbeddingFunction',
                  return_value=mock_litellm_function), \
             patch('src.backends.rag.embedding.get_provider_api_key',
                  return_value="test_api_key"):
            
            result = await get_embedding_function()
            
            assert result == mock_litellm_function
    
    @pytest.mark.asyncio
    async def test_get_embedding_function_custom_ollama_as_last_resort(self):
        """Test custom Ollama as last resort when LiteLLM fails."""
        mock_user_config = Mock()
        mock_user_config.embed_model = "ollama/nomic-embed-text:latest"
        mock_user_config.embed_provider = "ollama"
        mock_user_config.base_url = "http://localhost:11434"
        
        mock_custom_function = Mock(spec=CustomOllamaEmbeddingFunction)
        
        with patch('src.backends.rag.embedding.ManagerSingleton.get_user_config', 
                  return_value=mock_user_config), \
             patch('src.backends.rag.embedding.get_custom_ollama_embedding_function') as mock_get_custom:
            
            # First call fails (primary), second call succeeds (fallback)
            mock_get_custom.side_effect = [Exception("Primary failed"), mock_custom_function]
            
            with patch('src.backends.rag.embedding.LiteLLMEmbeddingFunction',
                      side_effect=Exception("LiteLLM failed")):
                
                result = await get_embedding_function()
                
                assert result == mock_custom_function
                assert mock_get_custom.call_count == 2


@pytest.mark.asyncio
async def test_add_documents_to_kb_integration():
    """Integration test for adding documents to knowledge base."""
    test_documents = [
        {
            "content": "This is a test document about machine learning.",
            "source": "ml_doc.pdf",
            "metadata": {"author": "Test Author", "year": 2023}
        },
        {
            "content": "Another document about artificial intelligence.",
            "source": "ai_doc.pdf", 
            "metadata": {"author": "AI Author", "year": 2024}
        }
    ]
    
    mock_db_manager = Mock()
    mock_db_manager.resolve_knowledge_base_id = AsyncMock(return_value="test_kb_id")
    mock_db_manager.get_knowledge_base_by_id = AsyncMock(return_value={
        "embed_model": "test-model"
    })
    
    mock_embeddings = Mock()
    mock_ragdb = Mock()
    mock_ragdb.get_or_create_collection = AsyncMock()
    mock_ragdb.add_chunks_to_collection = AsyncMock()
    
    with patch('src.backends.rag.db.get_database_manager', return_value=mock_db_manager), \
         patch('src.backends.rag.db.get_embeddings_for_kb', return_value=mock_embeddings), \
         patch('src.backends.rag.db.RAGDB', return_value=mock_ragdb):
        
        result = await add_documents_to_kb(test_documents, "test_knowledge_base")
        
        assert result["status"] == "success"
        assert result["chunks_added"] > 0
        mock_ragdb.get_or_create_collection.assert_called_once_with(name="test_kb_id")
        mock_ragdb.add_chunks_to_collection.assert_called_once()


if __name__ == "__main__":
    # Run tests with: python -m pytest src/tests/test_rag.py -v
    pytest.main([__file__, "-v"])
