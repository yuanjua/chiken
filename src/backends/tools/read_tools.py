"""
ChromaDB Read Operations for RAG Systems

Based on chroma-mcp server patterns: https://github.com/chroma-core/chroma-mcp
"""

from typing import Any

from loguru import logger

from ..rag.db import get_database_manager
from ..rag.service import RAGService
from .utils import get_active_knowledge_bases

# ==============================================================================
# Collection Information Tools
# ==============================================================================


async def list_collections() -> list[dict[str, Any]]:
    """
    List all available collections (knowledge bases) with metadata.

    Only returns collections that are configured as active in the user's settings,
    maintaining user control over which knowledge bases the LLM should consider.

    Returns:
        List[Dict[str, Any]]: List of collection metadata dictionaries containing:
            - id: Collection UUID
            - display_name: Human-readable name
            - description: Collection description
            - chunk_size: Text chunking size
            - chunk_overlap: Text chunk overlap
            - embed_model: Embedding model used
            - document_count: Number of documents (if available)
            - created_at: Creation timestamp (if available)

    Example:
        >>> collections = await list_collections()
        >>> print(f"Found {len(collections)} active collections")
        >>> for col in collections:
        ...     print(f"- {col['display_name']}: {col.get('description', 'No description')}")
    """
    try:
        # Get only active collections as configured by user
        active_collections = await get_active_knowledge_bases()

        if not active_collections:
            logger.info("No active knowledge bases configured")
            return []

        # Enhance with additional metadata if available
        db_manager = await get_database_manager()
        enhanced_collections = []

        for collection in active_collections:
            try:
                # Try to get additional metadata
                kb_info = await db_manager.get_knowledge_base_by_id(collection["id"])
                if kb_info:
                    # Merge the information
                    enhanced_collection = {**collection, **kb_info}
                    enhanced_collections.append(enhanced_collection)
                else:
                    enhanced_collections.append(collection)
            except Exception as e:
                logger.warning(f"Could not enhance metadata for collection {collection['id']}: {e}")
                enhanced_collections.append(collection)

        logger.info(f"Listed {len(enhanced_collections)} active collections")
        return enhanced_collections

    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        return []


async def get_collection_info(collection_name: str) -> dict[str, Any]:
    """
    Get detailed information about a specific collection.

    Args:
        collection_name: The name or ID of the collection to inspect

    Returns:
        Dict[str, Any]: Collection metadata and statistics including:
            - basic_info: Collection metadata
            - document_count: Number of documents
            - sample_metadata: Sample of metadata fields used
            - embedding_model: Embedding model information
            - storage_info: Storage-related information

    Example:
        >>> info = await get_collection_info("research-papers")
        >>> print(f"Collection: {info['basic_info']['display_name']}")
        >>> print(f"Documents: {info['document_count']}")
    """
    try:
        # Check if collection is in active knowledge bases
        active_collections = await get_active_knowledge_bases()
        collection = None

        # Find the collection by name or ID
        for kb in active_collections:
            if kb["id"] == collection_name or kb.get("display_name") == collection_name:
                collection = kb
                break

        if not collection:
            logger.error(f"Collection '{collection_name}' not found in active knowledge bases")
            return {"error": f"Collection '{collection_name}' not found or not active"}

        # Get detailed information
        db_manager = await get_database_manager()
        detailed_info = await db_manager.get_knowledge_base_by_id(collection["id"])

        # Get document count and sample metadata
        try:
            # Try to get some sample documents to understand structure
            sample_docs = await RAGService.query_documents(
                query_text="sample", knowledge_base_names=[collection["id"]], k=5
            )

            document_count = len(sample_docs)
            sample_metadata = {}

            if sample_docs:
                # Extract unique metadata keys
                all_metadata_keys = set()
                for doc in sample_docs:
                    if "metadata" in doc:
                        all_metadata_keys.update(doc["metadata"].keys())

                sample_metadata = {
                    "metadata_fields": list(all_metadata_keys),
                    "sample_doc_metadata": sample_docs[0].get("metadata", {}) if sample_docs else {},
                }

        except Exception as e:
            logger.warning(f"Could not get document statistics for {collection_name}: {e}")
            document_count = "unknown"
            sample_metadata = {}

        result = {
            "basic_info": {**collection, **(detailed_info or {})},
            "document_count": document_count,
            "sample_metadata": sample_metadata,
            "embedding_model": detailed_info.get("embed_model") if detailed_info else "unknown",
            "collection_id": collection["id"],
        }

        logger.info(f"Retrieved information for collection '{collection_name}'")
        return result

    except Exception as e:
        logger.error(f"Error getting collection info for '{collection_name}': {e}")
        return {"error": str(e)}


async def peek_collection(collection_name: str, n_samples: int = 3) -> dict[str, Any]:
    """
    Preview documents in a collection to understand its structure and content.

    Args:
        collection_name: The name or ID of the collection to peek into
        n_samples: Number of sample documents to return (default: 3)

    Returns:
        Dict[str, Any]: Collection preview containing:
            - collection_info: Basic collection metadata
            - sample_documents: List of sample documents with content and metadata
            - metadata_summary: Summary of common metadata fields
            - content_sample: Preview of document content types

    Example:
        >>> preview = await peek_collection("research-papers", 2)
        >>> for doc in preview['sample_documents']:
        ...     print(f"- {doc['metadata'].get('title', 'Untitled')}")
    """
    try:
        # Verify collection is active
        active_collections = await get_active_knowledge_bases()
        collection = None

        for kb in active_collections:
            if kb["id"] == collection_name or kb.get("display_name") == collection_name:
                collection = kb
                break

        if not collection:
            return {"error": f"Collection '{collection_name}' not found in active knowledge bases"}

        # Get sample documents using a broad query
        sample_docs = await RAGService.query_documents(
            query_text="document sample content",  # Generic query to get diverse results
            knowledge_base_names=[collection["id"]],
            k=n_samples,
        )

        if not sample_docs:
            return {
                "collection_info": collection,
                "sample_documents": [],
                "metadata_summary": {"message": "No documents found in collection"},
                "content_sample": {"message": "Collection appears to be empty"},
            }

        # Analyze metadata patterns
        metadata_fields = set()
        metadata_values = {}

        for doc in sample_docs:
            metadata = doc.get("metadata", {})
            metadata_fields.update(metadata.keys())

            for key, value in metadata.items():
                if key not in metadata_values:
                    metadata_values[key] = []
                if len(metadata_values[key]) < 3:  # Keep only first 3 examples
                    metadata_values[key].append(value)

        # Create content sample
        content_preview = []
        for i, doc in enumerate(sample_docs[:n_samples]):
            content = doc.get("content", "")
            preview_text = content[:200] + "..." if len(content) > 200 else content

            content_preview.append(
                {
                    "index": i + 1,
                    "content_preview": preview_text,
                    "content_length": len(content),
                    "metadata": doc.get("metadata", {}),
                    "similarity_score": 1.0 - doc.get("distance", 0.0),  # Convert distance to similarity
                }
            )

        result = {
            "collection_info": collection,
            "sample_documents": content_preview,
            "metadata_summary": {
                "total_metadata_fields": len(metadata_fields),
                "field_names": list(metadata_fields),
                "field_examples": metadata_values,
            },
            "content_sample": {
                "total_samples": len(sample_docs),
                "avg_content_length": sum(len(doc.get("content", "")) for doc in sample_docs) // len(sample_docs)
                if sample_docs
                else 0,
            },
        }

        logger.info(f"Peeked into collection '{collection_name}' with {len(sample_docs)} samples")
        return result

    except Exception as e:
        logger.error(f"Error peeking collection '{collection_name}': {e}")
        return {"error": str(e)}


# ==============================================================================
# Document Search and Retrieval Tools
# ==============================================================================


async def search_documents(
    query: str,
    collection_name: str | None = None,
    n_results: int = 10,
    where: dict[str, Any] | None = None,
    where_document: dict[str, str] | None = None,
    include_similarity_scores: bool = True,
) -> list[dict[str, Any]]:
    """
    Perform semantic search across documents with advanced filtering capabilities.

    Args:
        query: Natural language search query
        collection_name: Specific collection to search (None = search all active collections)
        n_results: Maximum number of results to return
        where: Metadata filter conditions (e.g., {"author": "Smith", "year": {"$gte": 2020}})
        where_document: Document content filter (e.g., {"$contains": "machine learning"})
        include_similarity_scores: Whether to include similarity scores in results

    Returns:
        List[Dict[str, Any]]: Search results with content, metadata, and optional similarity scores

    Example:
        >>> # Search specific collection with metadata filter
        >>> results = await search_documents(
        ...     query="transformer architectures",
        ...     collection_name="ai-papers",
        ...     where={"year": {"$gte": 2020}},
        ...     n_results=10
        ... )

        >>> # Search all active collections
        >>> results = await search_documents(
        ...     query="natural language processing",
        ...     n_results=10
        ... )
    """
    try:
        # Determine which collections to search
        if collection_name:
            # Search specific collection
            active_collections = await get_active_knowledge_bases()
            target_collection = None

            for kb in active_collections:
                if kb["id"] == collection_name or kb.get("display_name") == collection_name:
                    target_collection = kb
                    break

            if not target_collection:
                logger.error(f"Collection '{collection_name}' not found in active knowledge bases")
                return []

            kb_names = [target_collection["id"]]
            search_context = f"collection '{collection_name}'"
        else:
            # Search all active collections
            active_collections = await get_active_knowledge_bases()
            if not active_collections:
                logger.info("No active knowledge bases found")
                return []

            kb_names = [kb["id"] for kb in active_collections]
            search_context = f"{len(kb_names)} active collections"

        logger.info(f"Searching {search_context} for: '{query}' (limit: {n_results})")

        # Perform the search with where clauses
        results = await RAGService.query_documents(
            query_text=query,
            knowledge_base_names=kb_names,
            k=n_results,
            where=where,
            where_document=where_document,
        )

        # Format results with enhanced metadata
        formatted_results = []
        for i, item in enumerate(results):
            result_item = {
                "rank": i + 1,
                "content": item.get("content", ""),
                "metadata": item.get("metadata", {}),
                "source": item.get("metadata", {}).get("source", "unknown"),
                "key": item.get("metadata", {}).get("key", ""),
            }

            if include_similarity_scores:
                # Convert distance to similarity percentage (0-100%)
                distance = item.get("distance", 0.0)
                similarity_percent = max(0, min(100, (1.0 - distance) * 100))
                result_item["similarity_score"] = round(similarity_percent, 2)
                result_item["distance"] = distance

            formatted_results.append(result_item)

        logger.info(f"Found {len(formatted_results)} results")
        return formatted_results

    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return []


async def get_document_by_id(document_id: str, collection_name: str | None = None) -> dict[str, Any]:
    """
    Retrieve a specific document by its ID or key.

    Args:
        document_id: The document ID, key, or source identifier
        collection_name: Optional collection name to limit search scope

    Returns:
        Dict[str, Any]: Document with full content and metadata, or empty dict if not found

    Example:
        >>> doc = await get_document_by_id("paper_123", "research-papers")
        >>> if doc:
        ...     print(f"Title: {doc['metadata'].get('title', 'Unknown')}")
    """
    try:
        # First try to get full text using existing utility
        document = await RAGService.get_uploaded_file_by_key(document_id)
        if document:
            return {
                "content": document["content"],
                "metadata": document["metadata"],
                "source": "uploaded_files",
                "document_id": document_id,
            }

        # Try alternative methods
        document = await RAGService.get_document_by_zotero_key(document_id)
        if document:
            return {
                "content": document["content"],
                "metadata": document["metadata"],
                "source": "zotero",
                "document_id": document_id,
            }

        # add reconstructed document from chunks
        logger.info(f"Attempting to reconstruct document '{document_id}' from chunks")

        # Determine which knowledge bases to search
        search_kb_names = None
        if collection_name:
            active_collections = await get_active_knowledge_bases()
            for kb in active_collections:
                if kb["id"] == collection_name or kb.get("display_name") == collection_name:
                    search_kb_names = [kb["id"]]
                    break

        # Try to reconstruct document from chunks
        reconstructed_doc = await RAGService.reconstruct_document_from_chunks(
            document_id=document_id, knowledge_base_names=search_kb_names
        )

        if reconstructed_doc:
            return reconstructed_doc

        logger.info(f"Document '{document_id}' could not be found or reconstructed")
        return {}

    except Exception as e:
        logger.error(f"Error retrieving document '{document_id}': {e}")
        return {}


async def query_documents_with_context(
    query: str,
    collection_name: str | None = None,
    n_results: int = 10,
    context_window: int = 2,  # TODO: implement context window
    include_metadata_filter: list[str] | None = None,
    where: dict[str, Any] | None = None,
    where_document: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Advanced document query with contextual information and enhanced filtering.

    Args:
        query: Search query
        collection_name: Optional specific collection
        n_results: Number of results
        context_window: Number of additional context chunks around each result
        include_metadata_filter: List of metadata fields to include in results
        where: Metadata filter conditions
        where_document: Document content filter

    Returns:
        Dict[str, Any]: Enhanced search results with context and filtered metadata

    Example:
        >>> results = await query_documents_with_context(
        ...     query="machine learning algorithms",
        ...     n_results=5,
        ...     where={"year": {"$gte": 2020}},
        ...     include_metadata_filter=["title", "author", "year"]
        ... )
    """
    try:
        # Get base search results
        base_results = await search_documents(
            query=query,
            collection_name=collection_name,
            n_results=n_results,
            where=where,
            where_document=where_document,
            include_similarity_scores=True,
        )

        if not base_results:
            return {
                "status": "success",
                "query": query,
                "results": [],
                "context_info": {"message": "No results found"},
            }

        # Enhance results with context and filtered metadata
        enhanced_results = []

        for result in base_results:
            enhanced_result = {
                "rank": result["rank"],
                "content": result["content"],
                "similarity_score": result.get("similarity_score", 0),
                "source": result["source"],
                "key": result["key"],
            }

            # Filter metadata if requested
            if include_metadata_filter and result.get("metadata"):
                filtered_metadata = {
                    key: value for key, value in result["metadata"].items() if key in include_metadata_filter
                }
                enhanced_result["metadata"] = filtered_metadata
            else:
                enhanced_result["metadata"] = result.get("metadata", {})

            # Add content length and preview
            content = result["content"]
            enhanced_result["content_length"] = len(content)
            enhanced_result["content_preview"] = content[:150] + "..." if len(content) > 150 else content

            enhanced_results.append(enhanced_result)

        # Calculate result statistics
        similarity_scores = [r.get("similarity_score", 0) for r in enhanced_results]

        result_summary = {
            "query": query,
            "total_results": len(enhanced_results),
            "collection_searched": collection_name or "all active collections",
            "avg_similarity": round(sum(similarity_scores) / len(similarity_scores), 2) if similarity_scores else 0,
            "highest_similarity": max(similarity_scores) if similarity_scores else 0,
            "results": enhanced_results,
        }

        logger.info(
            f"Enhanced query completed: {len(enhanced_results)} results with avg similarity {result_summary['avg_similarity']}%"
        )
        return {"status": "success", **result_summary}

    except Exception as e:
        logger.error(f"Error in enhanced document query: {e}")
        return {"status": "error", "message": str(e), "query": query}
