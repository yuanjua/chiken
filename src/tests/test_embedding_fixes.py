#!/usr/bin/env python3
"""
Quick test script to verify the embedding fixes are working.

This script tests:
1. Custom Ollama embedding function
2. Database connectivity
3. ChromaDB integration
4. Concurrency handling
"""

import asyncio
import sys
import os
import time
from pathlib import Path
from loguru import logger

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_custom_embedding():
    """Test the custom Ollama embedding function."""
    logger.info("🧪 Testing custom Ollama embedding function...")
    
    try:
        from backends.rag.custom_ollama_embedding import CustomOllamaEmbeddingFunction
        
        # Create embedding function with test URLs
        embedding_func = CustomOllamaEmbeddingFunction(
            model_name="nomic-embed-text:latest",
            primary_base_url="http://172.22.22.2:11434",
            fallback_base_url="http://localhost:11434",
            timeout=10
        )
        
        # Test single embedding
        start_time = time.time()
        test_texts = ["This is a test document for embedding."]
        
        # Test async method
        embeddings = await embedding_func._async_get_embeddings(test_texts)
        duration = time.time() - start_time
        
        logger.info(f"✅ Custom embedding successful! Got {len(embeddings)} embeddings in {duration:.2f}s")
        logger.info(f"   Embedding dimension: {len(embeddings[0])}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Custom embedding failed: {e}")
        return False

async def test_database_connection():
    """Test database connectivity with improved settings."""
    logger.info("🧪 Testing database connection...")
    
    try:
        from backends.database import get_database_manager
        
        db_manager = await get_database_manager()
        
        # Test basic database operation
        configs = await db_manager.list_user_configs()
        
        logger.info(f"✅ Database connection successful! Found {len(configs)} user configs")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

async def test_chromadb_integration():
    """Test ChromaDB integration."""
    logger.info("🧪 Testing ChromaDB integration...")
    
    try:
        from backends.rag.db import RAGDB
        from backends.rag.custom_ollama_embedding import get_custom_ollama_embedding_function
        
        # Get embedding function
        embeddings = await get_custom_ollama_embedding_function()
        
        # Create RAGDB instance
        ragdb = RAGDB(embeddings=embeddings)
        
        # Test collection listing
        collections = ragdb.list_collections()
        
        logger.info(f"✅ ChromaDB integration successful! Found {len(collections)} collections")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ChromaDB integration failed: {e}")
        return False

async def test_concurrent_embeddings():
    """Test concurrent embedding requests."""
    logger.info("🧪 Testing concurrent embedding handling...")
    
    try:
        from backends.rag.custom_ollama_embedding import CustomOllamaEmbeddingFunction
        
        embedding_func = CustomOllamaEmbeddingFunction(
            model_name="nomic-embed-text:latest",
            primary_base_url="http://172.22.22.2:11434",
            fallback_base_url="http://localhost:11434"
        )
        
        # Test concurrent requests
        texts = [f"Test document {i}" for i in range(5)]
        
        start_time = time.time()
        tasks = [embedding_func._get_single_embedding(text) for text in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        duration = time.time() - start_time
        
        # Check results
        successful = [r for r in results if not isinstance(r, Exception)]
        failed = [r for r in results if isinstance(r, Exception)]
        
        logger.info(f"✅ Concurrent embeddings: {len(successful)}/{len(texts)} successful in {duration:.2f}s")
        
        if failed:
            logger.warning(f"   ⚠️  {len(failed)} requests failed: {[str(f) for f in failed]}")
        
        return len(successful) >= 3  # Allow some failures
        
    except Exception as e:
        logger.error(f"❌ Concurrent embedding test failed: {e}")
        return False

async def test_embedding_function_selection():
    """Test automatic embedding function selection."""
    logger.info("🧪 Testing embedding function selection logic...")
    
    try:
        from backends.rag.embedding import get_embedding_function
        
        # Test getting embedding function (should use custom Ollama)
        embedding_func = await get_embedding_function()
        
        # Check the type
        func_type = type(embedding_func).__name__
        logger.info(f"✅ Embedding function selection successful! Using: {func_type}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Embedding function selection failed: {e}")
        return False

async def main():
    """Run all tests."""
    logger.info("🚀 Starting RAG system verification tests...\n")
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Custom Embedding Function", test_custom_embedding),
        ("Embedding Function Selection", test_embedding_function_selection),
        ("ChromaDB Integration", test_chromadb_integration),
        ("Concurrent Embeddings", test_concurrent_embeddings),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} ---")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("📋 TEST SUMMARY")
    logger.info("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
        if result:
            passed += 1
    
    logger.info(f"\nResults: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        logger.info("\n🎉 All tests passed! The embedding fixes are working correctly.")
        return 0
    else:
        logger.error(f"\n⚠️  {len(results) - passed} tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.error("\n\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n💥 Unexpected error: {e}")
        sys.exit(1)
