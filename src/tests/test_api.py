"""
Test suite for RAG API endpoints and service integrations.

This module tests the API layer of the RAG system including:
- Knowledge base management endpoints
- Document upload and processing
- Search and query endpoints
- Session and stream handling
- Error handling and validation
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import List, Dict, Any
import json
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Import the modules we're testing
from src.backends.rag.api import router as rag_router
from src.backends.rag.service import RAGService
from src.backends.sessions.service import SessionService
from src.backends.sessions.api import router as sessions_router
from src.main import app


class TestRAGAPIEndpoints:
    """Test suite for RAG API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI application."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_rag_service(self):
        """Mock the RAGService for testing."""
        with patch('src.backends.rag.api.RAGService') as mock:
            yield mock
    
    @pytest.fixture
    def mock_session_service(self):
        """Mock the SessionService for testing.""" 
        with patch('src.backends.sessions.api.SessionService') as mock:
            yield mock
    
    def test_get_knowledge_bases(self, client, mock_rag_service):
        """Test GET /rag/knowledge-bases endpoint."""
        mock_rag_service.get_active_knowledge_bases.return_value = ["kb1", "kb2", "kb3"]
        
        response = client.get("/rag/knowledge-bases")
        
        assert response.status_code == 200
        data = response.json()
        assert data == ["kb1", "kb2", "kb3"]
    
    def test_set_active_knowledge_bases(self, client, mock_rag_service):
        """Test POST /rag/knowledge-bases/active endpoint."""
        mock_rag_service.set_active_knowledge_bases.return_value = True
        
        payload = {"knowledge_base_ids": ["kb1", "kb2"]}
        response = client.post("/rag/knowledge-bases/active", json=payload)
        
        assert response.status_code == 200
        mock_rag_service.set_active_knowledge_bases.assert_called_once_with(["kb1", "kb2"])
    
    def test_search_documents(self, client, mock_rag_service):
        """Test POST /rag/search endpoint."""
        mock_results = [
            {
                "content": "Test document content",
                "metadata": {"source": "test.pdf"},
                "distance": 0.5,
                "knowledge_base_name": "test_kb"
            }
        ]
        mock_rag_service.query_documents.return_value = mock_results
        
        payload = {
            "query": "test query",
            "knowledge_base_names": ["test_kb"],
            "k": 5
        }
        response = client.post("/rag/search", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "Test document content"
    
    def test_upload_documents(self, client, mock_rag_service):
        """Test POST /rag/upload endpoint."""
        mock_rag_service.add_documents_to_kb.return_value = {
            "status": "success",
            "chunks_added": 5,
            "message": "Documents added successfully"
        }
        
        payload = {
            "documents": [
                {
                    "content": "Test document",
                    "source": "test.pdf",
                    "metadata": {"author": "Test Author"}
                }
            ],
            "knowledge_base_name": "test_kb"
        }
        response = client.post("/rag/upload", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["chunks_added"] == 5
    
    def test_get_knowledge_base_documents(self, client, mock_rag_service):
        """Test GET /rag/knowledge-bases/{kb_name}/documents endpoint."""
        mock_documents = [
            {"source": "doc1.pdf", "title": "Document 1", "key": "key1"},
            {"source": "doc2.pdf", "title": "Document 2", "key": "key2"}
        ]
        mock_rag_service.get_documents_in_kb.return_value = mock_documents
        
        response = client.get("/rag/knowledge-bases/test_kb/documents")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["source"] == "doc1.pdf"
    
    def test_delete_knowledge_base(self, client, mock_rag_service):
        """Test DELETE /rag/knowledge-bases/{kb_name} endpoint."""
        mock_rag_service.delete_knowledge_base.return_value = True
        
        response = client.delete("/rag/knowledge-bases/test_kb")
        
        assert response.status_code == 200
        mock_rag_service.delete_knowledge_base.assert_called_once_with("test_kb")
    
    def test_search_documents_invalid_payload(self, client):
        """Test search endpoint with invalid payload."""
        payload = {"invalid_field": "test"}
        response = client.post("/rag/search", json=payload)
        
        assert response.status_code == 422  # Validation error
    
    def test_search_documents_empty_knowledge_bases(self, client, mock_rag_service):
        """Test search endpoint when no knowledge bases are active."""
        mock_rag_service.query_documents.side_effect = HTTPException(
            status_code=400, 
            detail="No knowledge bases available for querying"
        )
        
        payload = {"query": "test query", "knowledge_base_names": [], "k": 5}
        response = client.post("/rag/search", json=payload)
        
        assert response.status_code == 400


class TestSessionAPIEndpoints:
    """Test suite for Session API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI application."""
        return TestClient(app)
    
    @pytest.fixture  
    def mock_session_service(self):
        """Mock the SessionService for testing."""
        with patch('src.backends.sessions.api.SessionService') as mock:
            yield mock
    
    def test_create_session(self, client, mock_session_service):
        """Test session creation endpoint."""
        mock_session_id = "test_session_123"
        mock_session_service.create_session.return_value = {
            "session_id": mock_session_id,
            "agent_type": "chat",
            "created_at": "2025-07-28T04:00:00Z"
        }
        
        payload = {"agent_type": "chat"}
        response = client.post("/sessions", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == mock_session_id
        assert data["agent_type"] == "chat"
    
    def test_get_session_history(self, client, mock_session_service):
        """Test getting session history."""
        mock_history = [
            {
                "id": "msg1",
                "role": "user", 
                "content": "Hello",
                "timestamp": "2025-07-28T04:00:00Z"
            },
            {
                "id": "msg2",
                "role": "assistant",
                "content": "Hi there!",
                "timestamp": "2025-07-28T04:00:01Z"
            }
        ]
        mock_session_service.get_session_history.return_value = mock_history
        
        response = client.get("/sessions/test_session_123/history")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[1]["role"] == "assistant"
    
    def test_delete_session(self, client, mock_session_service):
        """Test session deletion."""
        mock_session_service.delete_session.return_value = True
        
        response = client.delete("/sessions/test_session_123")
        
        assert response.status_code == 200
        mock_session_service.delete_session.assert_called_once_with("test_session_123")
    
    def test_list_sessions(self, client, mock_session_service):
        """Test listing all sessions."""
        mock_sessions = [
            {
                "session_id": "session1",
                "agent_type": "chat",
                "created_at": "2025-07-28T03:00:00Z"
            },
            {
                "session_id": "session2", 
                "agent_type": "chat",
                "created_at": "2025-07-28T04:00:00Z"
            }
        ]
        mock_session_service.list_sessions.return_value = mock_sessions
        
        response = client.get("/sessions")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["session_id"] == "session1"


class TestStreamingEndpoints:
    """Test suite for streaming endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI application."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_session_service(self):
        """Mock the SessionService for streaming tests."""
        with patch('src.backends.sessions.api.SessionService') as mock:
            yield mock
    
    def test_stream_chat_response(self, client, mock_session_service):
        """Test streaming chat response endpoint."""
        # Mock an async generator for streaming
        async def mock_stream():
            yield b'data: {"type": "message", "content": "Hello"}\n\n'
            yield b'data: {"type": "message", "content": " World"}\n\n'
            yield b'data: {"type": "done"}\n\n'
        
        mock_session_service.stream_response.return_value = mock_stream()
        
        payload = {
            "message": "Hello, how are you?",
            "session_id": "test_session_123"
        }
        
        # Note: Testing streaming endpoints requires special handling
        # This is a simplified test - in practice you might need to test
        # the actual streaming behavior differently
        with patch('src.backends.sessions.api.StreamingResponse') as mock_streaming:
            response = client.post("/sessions/test_session_123/stream", json=payload)
            
            # Verify that streaming response was attempted
            mock_session_service.stream_response.assert_called_once()
    
    def test_stream_with_invalid_session(self, client, mock_session_service):
        """Test streaming with invalid session ID."""
        mock_session_service.stream_response.side_effect = HTTPException(
            status_code=404, 
            detail="Session not found"
        )
        
        payload = {"message": "Test message"}
        response = client.post("/sessions/invalid_session/stream", json=payload)
        
        assert response.status_code == 404


class TestErrorHandling:
    """Test suite for API error handling."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI application."""
        return TestClient(app)
    
    def test_validation_error_handling(self, client):
        """Test that validation errors return proper HTTP status codes."""
        # Missing required fields
        response = client.post("/rag/search", json={})
        assert response.status_code == 422
        
        # Invalid data types
        response = client.post("/rag/search", json={"query": 123, "k": "invalid"})
        assert response.status_code == 422
    
    def test_404_error_handling(self, client):
        """Test 404 error handling for non-existent endpoints."""
        response = client.get("/non-existent-endpoint")
        assert response.status_code == 404
    
    def test_internal_server_error_handling(self, client):
        """Test internal server error handling."""
        with patch('src.backends.rag.api.RAGService.query_documents') as mock_query:
            mock_query.side_effect = Exception("Database connection failed")
            
            payload = {"query": "test", "knowledge_base_names": ["kb1"], "k": 5}
            response = client.post("/rag/search", json=payload)
            
            # Should return 500 for unhandled exceptions
            assert response.status_code == 500


class TestConcurrencyAndPerformance:
    """Test suite for concurrency and performance aspects."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI application."""
        return TestClient(app)
    
    @pytest.mark.asyncio
    async def test_concurrent_embedding_requests(self):
        """Test handling of concurrent embedding requests."""
        from src.backends.rag.custom_ollama_embedding import CustomOllamaEmbeddingFunction
        
        embedding_function = CustomOllamaEmbeddingFunction(
            model_name="test-model",
            primary_base_url="http://test:11434",
            fallback_base_url="http://test2:11434"
        )
        
        # Mock successful responses
        mock_response = {"embeddings": [[0.1, 0.2, 0.3]]}
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response_obj = Mock()
            mock_response_obj.status = 200
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response_obj)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Run multiple concurrent requests
            tasks = [
                embedding_function._get_single_embedding(f"text {i}")
                for i in range(10)
            ]
            
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 10
            assert all(result == [0.1, 0.2, 0.3] for result in results)
    
    def test_rate_limiting_behavior(self, client):
        """Test API rate limiting behavior (if implemented)."""
        # This would test rate limiting if implemented
        # For now, just ensure multiple requests don't break the API
        
        with patch('src.backends.rag.api.RAGService.query_documents') as mock_query:
            mock_query.return_value = [{"content": "test", "distance": 0.5}]
            
            payload = {"query": "test", "knowledge_base_names": ["kb1"], "k": 5}
            
            # Make multiple rapid requests
            responses = []
            for _ in range(5):
                response = client.post("/rag/search", json=payload)
                responses.append(response)
            
            # All should succeed (no rate limiting implemented yet)
            assert all(r.status_code == 200 for r in responses)
    
    def test_large_document_upload(self, client):
        """Test uploading large documents."""
        with patch('src.backends.rag.api.RAGService.add_documents_to_kb') as mock_add:
            mock_add.return_value = {
                "status": "success",
                "chunks_added": 100,
                "message": "Large document processed"
            }
            
            # Simulate a large document
            large_content = "This is a test document. " * 1000  # ~25KB
            
            payload = {
                "documents": [{
                    "content": large_content,
                    "source": "large_doc.pdf",
                    "metadata": {"size": "large"}
                }],
                "knowledge_base_name": "test_kb"
            }
            
            response = client.post("/rag/upload", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data["chunks_added"] == 100


class TestDatabaseIntegration:
    """Test suite for database integration aspects."""
    
    @pytest.mark.asyncio
    async def test_database_connection_failure_handling(self):
        """Test handling of database connection failures."""
        from src.backends.rag.service import RAGService
        
        with patch('src.backends.rag.service.get_database_manager') as mock_get_db:
            mock_get_db.side_effect = Exception("Database connection failed")
            
            with pytest.raises(Exception, match="Database connection failed"):
                await RAGService.query_documents("test query", ["kb1"])
    
    @pytest.mark.asyncio
    async def test_chromadb_connection_failure_handling(self):
        """Test handling of ChromaDB connection failures."""
        from src.backends.rag.db import RAGDB
        
        mock_embeddings = Mock()
        ragdb = RAGDB(embeddings=mock_embeddings)
        
        with patch.object(ragdb, 'client') as mock_client:
            mock_client.get_collection.side_effect = Exception("ChromaDB connection failed")
            
            with pytest.raises(Exception, match="ChromaDB connection failed"):
                ragdb.query("test query", "test_collection")
    
    @pytest.mark.asyncio
    async def test_sqlite_lock_handling(self):
        """Test handling of SQLite database locks."""
        from src.backends.database import DatabaseManager
        
        # Mock SQLite lock error
        import sqlite3
        lock_error = sqlite3.OperationalError("database is locked")
        
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = Mock()
            mock_db.execute.side_effect = lock_error
            mock_connect.return_value.__aenter__.return_value = mock_db
            
            db_manager = DatabaseManager("/tmp/test.db")
            
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                await db_manager.initialize()


if __name__ == "__main__":
    # Run tests with: python -m pytest src/tests/test_api.py -v
    pytest.main([__file__, "-v"])
