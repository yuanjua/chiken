"""
ChromaDB Write Operations for RAG Systems

Based on chroma-mcp server patterns: https://github.com/chroma-core/chroma-mcp
"""

from typing import Any

from loguru import logger

from ..rag.db import add_documents_to_kb
from .utils import get_active_knowledge_bases

# ==============================================================================
# Plan for Search Agent
# ==============================================================================


async def add_document(
    collection_name: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    """
    Add a new document to a collection with proper chunk metadata.

    Args:
        collection_name: Target collection name or ID
        content: Document text content
        metadata: Optional metadata dictionary
        document_id: Optional custom document ID (defaults to auto-generated)

    Returns:
        Dict[str, Any]: Operation result with status and document information

    Example:
        >>> result = await add_document(
        ...     collection_name="research-papers",
        ...     content="Recent advances in transformer architectures...",
        ...     metadata={"title": "Transformer Study", "author": "Smith", "year": 2024},
        ...     document_id="smith_2024_transformers"
        ... )
    """
    try:
        # Verify collection exists and is active
        active_collections = await get_active_knowledge_bases()
        target_collection = None

        for kb in active_collections:
            if kb["id"] == collection_name or kb.get("display_name") == collection_name:
                target_collection = kb
                break

        if not target_collection:
            return {
                "status": "error",
                "message": f"Collection '{collection_name}' not found in active knowledge bases",
            }

        # Prepare document
        doc_metadata = metadata or {}
        source_id = document_id or f"doc_{len(content) // 100}_{hash(content[:100])}"

        # Ensure metadata has required fields
        if "source" not in doc_metadata:
            doc_metadata["source"] = source_id
        if "key" not in doc_metadata:
            doc_metadata["key"] = source_id

        # Add document-level metadata for chunk tracking
        doc_metadata["document_id"] = source_id
        doc_metadata["total_length"] = len(content)

        document = {"content": content, "source": source_id, "metadata": doc_metadata}

        # Add to knowledge base
        result = await add_documents_to_kb(documents=[document], knowledge_base_name=target_collection["id"])

        logger.info(f"Added document '{source_id}' to collection '{collection_name}'")
        return {
            "status": "success",
            "document_id": source_id,
            "collection": collection_name,
            "chunks_added": result.get("chunks_added", 0),
            "message": f"Successfully added document to '{collection_name}'",
        }

    except Exception as e:
        logger.error(f"Error adding document to collection '{collection_name}': {e}")
        return {"status": "error", "message": str(e)}


async def add_documents_batch(collection_name: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Add multiple documents to a collection in a batch operation.

    Args:
        collection_name: Target collection name or ID
        documents: List of document dictionaries with 'content', 'metadata', and optional 'document_id'

    Returns:
        Dict[str, Any]: Batch operation result with status and statistics

    Example:
        >>> docs = [
        ...     {
        ...         "content": "First document content...",
        ...         "metadata": {"title": "Doc 1", "author": "Smith"},
        ...         "document_id": "doc_1"
        ...     },
        ...     {
        ...         "content": "Second document content...",
        ...         "metadata": {"title": "Doc 2", "author": "Jones"}
        ...     }
        ... ]
        >>> result = await add_documents_batch("research-papers", docs)
    """
    try:
        # Verify collection exists and is active
        active_collections = await get_active_knowledge_bases()
        target_collection = None

        for kb in active_collections:
            if kb["id"] == collection_name or kb.get("display_name") == collection_name:
                target_collection = kb
                break

        if not target_collection:
            return {
                "status": "error",
                "message": f"Collection '{collection_name}' not found in active knowledge bases",
            }

        if not documents:
            return {"status": "error", "message": "No documents provided for batch addition"}

        # Prepare documents for batch processing
        processed_documents = []
        document_ids = []

        for i, doc_data in enumerate(documents):
            content = doc_data.get("content", "")
            metadata = doc_data.get("metadata", {})
            doc_id = doc_data.get("document_id") or f"batch_doc_{i}_{hash(content[:100])}"

            if not content:
                logger.warning(f"Skipping document {i} due to empty content")
                continue

            # Ensure metadata has required fields
            if "source" not in metadata:
                metadata["source"] = doc_id
            if "key" not in metadata:
                metadata["key"] = doc_id

            # Add document-level metadata for chunk tracking
            metadata["document_id"] = doc_id
            metadata["total_length"] = len(content)
            metadata["batch_index"] = i

            processed_documents.append({"content": content, "source": doc_id, "metadata": metadata})
            document_ids.append(doc_id)

        if not processed_documents:
            return {"status": "error", "message": "No valid documents found for processing"}

        # Add batch to knowledge base
        result = await add_documents_to_kb(documents=processed_documents, knowledge_base_name=target_collection["id"])

        logger.info(f"Added {len(processed_documents)} documents to collection '{collection_name}'")
        return {
            "status": "success",
            "collection": collection_name,
            "documents_added": len(processed_documents),
            "document_ids": document_ids,
            "chunks_added": result.get("chunks_added", 0),
            "message": f"Successfully added {len(processed_documents)} documents to '{collection_name}'",
        }

    except Exception as e:
        logger.error(f"Error adding batch documents to collection '{collection_name}': {e}")
        return {"status": "error", "message": str(e)}
