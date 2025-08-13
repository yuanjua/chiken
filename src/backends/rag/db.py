import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import chromadb
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from ..constants import get_chroma_db_path
from ..database import get_database_manager
from .embedding import get_embedding_function

chroma_path = get_chroma_db_path()

# Global ChromaDB client with better settings
client = chromadb.PersistentClient(
    path=chroma_path,
    settings=chromadb.Settings(allow_reset=True, anonymized_telemetry=False, is_persistent=True),
)

# Thread pool executor for running synchronous operations with limited concurrency
_executor = ThreadPoolExecutor(max_workers=2)  # Reduced to avoid overwhelming ChromaDB


async def get_embeddings_for_kb(kb_id: str):
    """Return embedding function configured for given KB id."""
    db_manager = await get_database_manager()
    kb_info = await db_manager.get_knowledge_base_by_id(kb_id)
    model = kb_info.get("embed_model")
    return await get_embedding_function(model)


class RAGDB:
    """Database interface for RAG operations using ChromaDB."""

    def __init__(self, embeddings):
        self.embeddings = embeddings
        self.client = client

    async def get_or_create_collection(self, name: str):
        """Get or create a ChromaDB collection with the given name."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            lambda: self.client.get_or_create_collection(name=name, embedding_function=self.embeddings),
        )

    def _sync_add_chunks_to_collection(self, chunks: list[Document], collection_name: str):
        """Synchronous version of add_chunks_to_collection for executor."""
        try:
            logger.info(f"Starting to add {len(chunks)} chunks to collection '{collection_name}'")

            collection = self.client.get_or_create_collection(name=collection_name, embedding_function=self.embeddings)

            # Validate chunks before processing
            valid_chunks = []
            for i, chunk in enumerate(chunks):
                if not chunk.page_content or not chunk.page_content.strip():
                    logger.warning(f"Skipping empty chunk {i}")
                    continue
                if not chunk.metadata:
                    logger.warning(f"Chunk {i} has no metadata, adding minimal metadata")
                    chunk.metadata = {"source": "unknown", "chunk_id": i}
                valid_chunks.append(chunk)

            if not valid_chunks:
                logger.warning("No valid chunks to add after validation")
                return 0

            logger.info(f"Validated {len(valid_chunks)} chunks (filtered from {len(chunks)} original chunks)")

            documents_to_add = [chunk.page_content for chunk in valid_chunks]
            metadatas_to_add = [chunk.metadata for chunk in valid_chunks]

            # Generate unique IDs with timestamp to avoid duplicates
            import time

            timestamp = int(time.time() * 1000)  # millisecond timestamp
            ids_to_add = [
                f"{chunk.metadata.get('source', 'unknown_source')}_{i}_{timestamp}_{hash(chunk.page_content[:100]) % 1000000}"
                for i, chunk in enumerate(valid_chunks)
            ]

            logger.debug(
                f"Prepared {len(documents_to_add)} documents, {len(metadatas_to_add)} metadata objects, {len(ids_to_add)} IDs"
            )

            # Check for any existing IDs in the collection to avoid duplicates
            try:
                existing_ids = set()
                # Get a sample to check if collection has any documents
                sample_result = collection.get(limit=1)
                if sample_result and "ids" in sample_result and sample_result["ids"]:
                    # Collection has documents, check for conflicts
                    for test_id in ids_to_add[:5]:  # Check first 5 IDs as a sample
                        existing_check = collection.get(ids=[test_id])
                        if existing_check and "ids" in existing_check and existing_check["ids"]:
                            existing_ids.add(test_id)

                    if existing_ids:
                        logger.warning(f"Found {len(existing_ids)} existing IDs, regenerating with random suffix")
                        import random

                        random_suffix = random.randint(100000, 999999)
                        ids_to_add = [f"{id_val}_{random_suffix}" for id_val in ids_to_add]

            except Exception as id_check_error:
                logger.debug(f"ID conflict check failed (this is usually normal for new collections): {id_check_error}")

            # Add documents to ChromaDB collection
            logger.debug("Calling collection.add() with prepared data...")
            collection.add(documents=documents_to_add, metadatas=metadatas_to_add, ids=ids_to_add)

            logger.info(f"Successfully added {len(valid_chunks)} chunks to collection '{collection_name}'")
            return len(valid_chunks)

        except Exception as e:
            error_msg = str(e).lower()
            if "already exists" in error_msg or "duplicate" in error_msg:
                logger.error(f"Duplicate ID error when adding chunks to collection '{collection_name}': {str(e)}")
                logger.error("This might indicate a problem with ID generation or a race condition")
            else:
                logger.error(f"Failed to add chunks to collection '{collection_name}': {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise e

    async def add_chunks_to_collection(self, chunks: list[Document], collection_name: str):
        """Adds document chunks to a specified collection."""
        try:
            loop = asyncio.get_event_loop()
            chunks_added = await loop.run_in_executor(
                _executor, self._sync_add_chunks_to_collection, chunks, collection_name
            )
            return chunks_added
        except Exception as e:
            logger.error(f"Async wrapper failed for add_chunks_to_collection: {str(e)}")
            raise e

    def query(
        self,
        query_text: str,
        collection_name: str,
        k: int = 10,
        keys: str | list[str] = None,
        where: dict[str, Any] | None = None,
        where_document: dict[str, str] | None = None,
    ):
        """
        Queries a collection for similar documents with improved error handling.

        Args:
            query_text: The text to search for
            collection_name: Name of the collection to search
            k: Number of results to return
            keys: Single key (str) or list of keys (List[str]) to filter by
            where: Optional metadata filter conditions
            where_document: Optional document content filter
        """
        try:
            collection = self.client.get_collection(name=collection_name, embedding_function=self.embeddings)

            where_clause = where or {}
            if keys:
                if isinstance(keys, str):
                    where_clause["key"] = keys
                elif isinstance(keys, list) and len(keys) > 0:
                    where_clause["key"] = {"$in": keys}

            # Build query parameters
            query_params = {
                "query_texts": [query_text],
                "n_results": k,
                "include": ["metadatas", "documents", "distances"],
            }

            if where_clause:
                query_params["where"] = where_clause

            if where_document:
                query_params["where_document"] = where_document

            result = collection.query(**query_params)
            return result
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            raise e

    def get_documents_by_metadata(
        self, collection_name: str, where: dict[str, Any], include_content: bool = True
    ) -> list[dict[str, Any]]:
        """
        Get documents by metadata filters without requiring embeddings.

        Args:
            collection_name: Name of the collection
            where: Metadata filter conditions
            include_content: Whether to include document content

        Returns:
            List of documents with metadata and optionally content
        """
        try:
            collection = self.client.get_collection(name=collection_name, embedding_function=self.embeddings)

            include_params = ["metadatas"]
            if include_content:
                include_params.append("documents")

            results = collection.get(where=where, include=include_params)

            documents = []
            for i in range(len(results["ids"])):
                doc = {"id": results["ids"][i], "metadata": results["metadatas"][i]}
                if include_content and "documents" in results:
                    doc["content"] = results["documents"][i]
                documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Failed to get documents by metadata from {collection_name}: {e}")
            raise e

    def delete_collection(self, collection_name: str):
        """Delete a collection by name."""
        self.client.delete_collection(name=collection_name)

    def list_collections(self):
        """List all available collections."""
        return self.client.list_collections()

    def get_unique_sources(self, collection_name: str) -> list[dict[str, str]]:
        """Get unique sources (documents) from a collection with their titles."""
        try:
            collection = self.client.get_collection(name=collection_name, embedding_function=self.embeddings)

            # Get all documents with metadata
            results = collection.get(include=["metadatas"])

            # Extract unique sources with titles
            unique_sources = {}
            for metadata in results.get("metadatas", []):
                source = metadata.get("source")
                if source and source not in unique_sources:
                    title = metadata.get("title", source)
                    # Check for key (SHA256 for uploaded PDFs), key (for Zotero), or fallback to source
                    key = metadata.get("key") or source
                    unique_sources[source] = {"source": source, "title": title, "key": key}

            return list(unique_sources.values())
        except Exception as e:
            logger.error(f"Error getting unique sources from collection {collection_name}: {e}")
            return []

    async def find_document_by_source_or_key(
        self, source: str, key: str = None, active_kb_ids: list[str] = None
    ) -> dict[str, Any]:
        """
        Efficiently find a document by source or key across uploaded_files and active knowledge bases.

        Args:
            source: Document source filename
            key: Optional key (SHA256 hash) for uploaded_files collection
            active_kb_ids: List of active knowledge base collection IDs to search

        Returns:
            Dict with document content and metadata, or None if not found
        """
        try:
            # Strategy: Search uploaded_files first (full content), then KB collections (chunks)

            # 1. Try uploaded_files collection first if key provided
            if key:
                try:
                    uploaded_collection = self.client.get_collection(
                        "uploaded_files", embedding_function=self.embeddings
                    )
                    result = uploaded_collection.get(ids=[key], include=["documents", "metadatas"])

                    if result["documents"] and len(result["documents"]) > 0:
                        return {
                            "source": "uploaded_files",
                            "content": result["documents"][0],
                            "metadata": result["metadatas"][0],
                            "type": "full_document",
                        }
                except Exception as e:
                    logger.error(f"Could not search uploaded_files collection: {e}")

            # 2. Search active knowledge base collections by source
            if active_kb_ids:
                for kb_id in active_kb_ids:
                    try:
                        collection = self.client.get_collection(name=kb_id, embedding_function=self.embeddings)

                        # Get all chunks from this source
                        results = collection.get(where={"source": source}, include=["documents", "metadatas"])

                        if results.get("documents") and len(results["documents"]) > 0:
                            # Combine all chunks from this source
                            combined_content = "\n".join(results["documents"])
                            return {
                                "source": kb_id,
                                "content": combined_content,
                                "metadata": results["metadatas"][0],  # Use first chunk's metadata
                                "type": "chunked_document",
                                "chunk_count": len(results["documents"]),
                            }

                    except Exception as e:
                        logger.error(f"Could not search KB collection {kb_id}: {e}")
                        continue

            return None

        except Exception as e:
            logger.error(f"Error in find_document_by_source_or_key: {e}")
            return None


async def add_documents_to_kb(documents: list[dict[str, Any]], knowledge_base_name: str) -> list[str]:
    """
    Processes and adds a list of documents to a specified knowledge base.

    Args:
        documents: A list of dictionaries, where each dict has 'content', 'source',
                   and an optional 'metadata' key.
        knowledge_base_name: The name of the knowledge base (collection) OR the UUID if it's already resolved.

    Returns:
        Dictionary with operation status and details.
    """
    logger.info(f"add_documents_to_kb called with {len(documents)} documents for KB '{knowledge_base_name}'")

    if not documents:
        raise ValueError("The documents list cannot be empty.")
    if not knowledge_base_name:
        raise ValueError("The knowledge_base_name must be provided.")

    # Resolve knowledge base name to collection ID (UUID)
    db_manager = await get_database_manager()

    enable_reference_filtering = True  # Default value
    try:
        kb_id = await db_manager.resolve_knowledge_base_id(knowledge_base_name)
        if kb_id:
            kb_info = await db_manager.get_knowledge_base_by_id(kb_id)
            if kb_info and "enable_reference_filtering" in kb_info:
                enable_reference_filtering = kb_info["enable_reference_filtering"]
                logger.debug(f"Retrieved enable_reference_filtering: {enable_reference_filtering}")
    except Exception as e:
        logger.warning(f"Could not retrieve enable_reference_filtering setting: {e}, using default: True")

    if "-" in knowledge_base_name and len(knowledge_base_name) == 36:
        # Looks like a UUID, use it directly
        kb_id = knowledge_base_name
        logger.info(f"Using provided UUID directly: '{kb_id}'")
    else:
        # It's a name, resolve it to UUID
        kb_id = await db_manager.resolve_knowledge_base_id(knowledge_base_name)
        if not kb_id:
            raise ValueError(f"Knowledge base '{knowledge_base_name}' not found")
        logger.info(f"Resolved KB name '{knowledge_base_name}' to ID '{kb_id}'")

    # Get the actual knowledge base name for metadata (in case we received a UUID)
    if "-" in knowledge_base_name and len(knowledge_base_name) == 36:
        # If we received a UUID, get the actual name for metadata
        kb_info = await db_manager.get_knowledge_base_by_id(kb_id)
        actual_kb_name = kb_info.get("name", knowledge_base_name) if kb_info else knowledge_base_name
    else:
        actual_kb_name = knowledge_base_name

    # Get embedding function for this KB
    embeddings = await get_embeddings_for_kb(kb_id)

    # Get chunk configuration from user config
    try:
        from ..manager_singleton import ManagerSingleton

        user_config = await ManagerSingleton.get_user_config()
        chunk_size = user_config.chunk_size
        chunk_overlap = user_config.chunk_overlap
        logger.debug(f"Using user config chunk settings: size={chunk_size}, overlap={chunk_overlap}")
    except Exception as e:
        logger.warning(f"Could not get user chunk config: {e}, using defaults")
        chunk_size, chunk_overlap = 1600, 300

    # Run text splitting in executor to avoid blocking
    loop = asyncio.get_event_loop()

    def _split_documents():
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap, length_function=len
        )

        all_chunks = []

        for doc_item in documents:
            content = doc_item.get("content")
            source = doc_item.get("source")
            optional_metadata = doc_item.get("metadata", {}) or {}

            # Debug logging
            logger.debug(f"Processing document: source='{source}', content_length={len(content) if content else 0}")

            # Skip if essential information is missing
            if not content or not source:
                logger.warning(
                    f"Skipping document due to missing content or source: source='{source}', has_content={bool(content)}"
                )
                continue

            # Create base metadata and merge optional data from the request
            base_metadata = {"source": source, "knowledge_base": actual_kb_name}
            combined_metadata = {**base_metadata, **optional_metadata}
            # Ensure 'key' is always set in metadata
            if "key" not in combined_metadata or not combined_metadata["key"]:
                combined_metadata["key"] = source

            langchain_doc = Document(page_content=content, metadata=combined_metadata)
            chunks = text_splitter.split_documents([langchain_doc])

            # Filter out chunks of references
            if enable_reference_filtering:
                # TODO:
                logger.debug("Reference filtering is enabled, will do when method updated to ONNX")

            # Add chunk-specific metadata including chunk IDs and page numbers
            for chunk_index, chunk in enumerate(chunks):
                # Create enhanced chunk metadata
                chunk_metadata = chunk.metadata.copy()
                chunk_metadata["chunk_id"] = chunk_index
                chunk_metadata["chunk_index"] = chunk_index  # Alternative name
                chunk_metadata["page"] = chunk_index + 1  # 1-based page numbering
                chunk_metadata["total_chunks"] = len(chunks)
                chunk_metadata["chunk_size"] = len(chunk.page_content)

                # Create new document with enhanced metadata
                enhanced_chunk = Document(page_content=chunk.page_content, metadata=chunk_metadata)
                all_chunks.append(enhanced_chunk)

        logger.info(f"Document processing complete: {len(all_chunks)} total chunks created")
        return all_chunks

    # Run splitting in executor to avoid blocking the event loop
    all_chunks = await loop.run_in_executor(_executor, _split_documents)

    if not all_chunks:
        return {"status": "success", "message": "No new chunks were created.", "chunks_added": 0}

    try:
        rag_db = RAGDB(embeddings=embeddings)
        await rag_db.get_or_create_collection(name=kb_id)  # Use resolved UUID
        chunks_added = await rag_db.add_chunks_to_collection(
            chunks=all_chunks, collection_name=kb_id
        )  # Use resolved UUID

        logger.info(f"Successfully processed and added {chunks_added} chunks to knowledge base '{actual_kb_name}'")

        return {
            "status": "success",
            "message": f"Successfully added {chunks_added} chunks to the '{actual_kb_name}' knowledge base.",
            "chunks_added": chunks_added,
        }
    except Exception as e:
        logger.error(f"Failed to add chunks to knowledge base '{actual_kb_name}': {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to add chunks to the '{actual_kb_name}' knowledge base: {str(e)}",
            "chunks_added": 0,
        }
