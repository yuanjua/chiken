"""
RAG Service Layer

This module contains the business logic for RAG (Retrieval-Augmented Generation) operations,
separated from the API layer for better maintainability.
"""

import asyncio
import hashlib
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from loguru import logger

from ..constants import CHUNK_OVERLAP, CHUNK_SIZE
from ..database import get_database_manager
from ..manager_singleton import ManagerSingleton
from .db import RAGDB, add_documents_to_kb
from .embedding import get_embedding_function


class RAGService:
    """Service class for RAG operations."""

    _active_knowledge_bases = None

    @staticmethod
    async def get_active_knowledge_bases() -> list[str]:
        """Get list of active knowledge base IDs."""
        if RAGService._active_knowledge_bases is None:
            await RAGService._initialize_active_knowledge_bases()
        return RAGService._active_knowledge_bases.copy()

    @staticmethod
    async def get_active_knowledge_bases_validated() -> list[str]:
        """Get list of active knowledge base IDs, validated against current database state."""
        try:
            # Get current active list
            current_active = await RAGService.get_active_knowledge_bases()

            # Validate against current database
            db_manager = await get_database_manager()
            all_kb_ids = {kb["id"] for kb in await db_manager.list_knowledge_bases()}

            # Filter to only existing KBs
            valid_active = [kb_id for kb_id in current_active if kb_id in all_kb_ids]

            # If the list changed, update it
            if len(valid_active) != len(current_active):
                invalid_ids = [kb_id for kb_id in current_active if kb_id not in all_kb_ids]
                logger.warning(f"Removing non-existent knowledge bases from active list: {invalid_ids}")
                await RAGService.set_active_knowledge_bases(valid_active)

            return valid_active
        except Exception as e:
            logger.error(f"Error validating active knowledge bases: {e}")
            return []

    @staticmethod
    async def set_active_knowledge_bases(kb_ids: list[str]) -> bool:
        """Set the list of active knowledge base IDs and persist to user config."""
        try:
            # Validate that all provided KB IDs exist
            db_manager = await get_database_manager()
            all_kbs = await db_manager.list_knowledge_bases()
            existing_ids = {kb["id"] for kb in all_kbs}

            # Filter to only valid IDs
            valid_ids = [kb_id for kb_id in kb_ids if kb_id in existing_ids]
            invalid_ids = [kb_id for kb_id in kb_ids if kb_id not in existing_ids]

            if invalid_ids:
                logger.warning(f"Ignoring non-existent knowledge base IDs: {invalid_ids}")

            # Update the in-memory cache
            RAGService._active_knowledge_bases = valid_ids
            logger.info(f"Active knowledge bases set to: {valid_ids}")

            # Persist to user config
            await ManagerSingleton.update_user_config(active_knowledge_base_ids=valid_ids)
            logger.info(f"Active knowledge bases persisted to user config: {valid_ids}")

            return True
        except Exception as e:
            logger.error(f"Error setting active knowledge bases: {e}")
            return False

    @staticmethod
    async def refresh_active_knowledge_bases():
        """Refresh active knowledge bases from user config (useful after config changes)."""
        try:
            RAGService._active_knowledge_bases = None
            await RAGService._initialize_active_knowledge_bases()
            logger.info("Active knowledge bases refreshed from user config")
        except Exception as e:
            logger.error(f"Error refreshing active knowledge bases: {e}")

    @staticmethod
    async def add_to_active_knowledge_bases(kb_id: str) -> bool:
        """Add a knowledge base to the active list."""
        try:
            current_active = await RAGService.get_active_knowledge_bases()
            if kb_id not in current_active:
                current_active.append(kb_id)
                return await RAGService.set_active_knowledge_bases(current_active)
            return True
        except Exception as e:
            logger.error(f"Error adding knowledge base {kb_id} to active list: {e}")
            return False

    @staticmethod
    async def remove_from_active_knowledge_bases(kb_id: str) -> bool:
        """Remove a knowledge base from the active list."""
        try:
            current_active = await RAGService.get_active_knowledge_bases()
            if kb_id in current_active:
                current_active.remove(kb_id)
                return await RAGService.set_active_knowledge_bases(current_active)
            return True
        except Exception as e:
            logger.error(f"Error removing knowledge base {kb_id} from active list: {e}")
            return False

    @staticmethod
    async def _initialize_active_knowledge_bases():
        """Initialize active knowledge bases from user config, fallback to all available KBs."""
        try:
            user_config = await ManagerSingleton.get_user_config()

            # Check if user config has active knowledge base IDs set
            if (
                user_config
                and hasattr(user_config, "active_knowledge_base_ids")
                and user_config.active_knowledge_base_ids
            ):
                # Validate that the configured knowledge bases still exist
                db_manager = await get_database_manager()
                all_kb_ids = {kb["id"] for kb in await db_manager.list_knowledge_bases()}
                valid_ids = [kb_id for kb_id in user_config.active_knowledge_base_ids if kb_id in all_kb_ids]

                RAGService._active_knowledge_bases = valid_ids
                logger.info(f"Loaded active knowledge bases from user config: {valid_ids}")

                # If some configured KBs no longer exist, update the config to remove them
                if len(valid_ids) != len(user_config.active_knowledge_base_ids):
                    invalid_ids = [kb_id for kb_id in user_config.active_knowledge_base_ids if kb_id not in all_kb_ids]
                    logger.warning(f"Removing non-existent knowledge bases from config: {invalid_ids}")
                    await ManagerSingleton.update_user_config(active_knowledge_base_ids=valid_ids)

                return

            # Fallback: activate all available knowledge bases
            db_manager = await get_database_manager()
            all_kbs = await db_manager.list_knowledge_bases()
            all_kb_ids = [kb["id"] for kb in all_kbs]

            RAGService._active_knowledge_bases = all_kb_ids
            logger.info(f"No active knowledge bases configured, activating all available: {all_kb_ids}")

            # Save this default to user config
            if all_kb_ids:
                await ManagerSingleton.update_user_config(active_knowledge_base_ids=all_kb_ids)

        except Exception as e:
            logger.error(f"Error initializing active knowledge bases: {e}")
            RAGService._active_knowledge_bases = []

    @staticmethod
    async def get_active_knowledge_bases_info() -> list[dict[str, Any]]:
        """Get detailed information about active knowledge bases from database"""
        try:
            # Get active knowledge base IDs from the RAGService cache/user config
            active_ids = await RAGService.get_active_knowledge_bases()
            if not active_ids:
                return []

            # Get detailed info for each active knowledge base
            active_kbs_info = []
            for kb_id in active_ids:
                try:
                    kb_info = await RAGService.get_knowledge_base_info(kb_id)
                    if kb_info:
                        active_kbs_info.append(
                            {
                                "id": kb_info["id"],
                                "name": kb_info.get("name", ""),
                                "description": kb_info.get("description", ""),
                                "isActive": True,
                                "createdAt": kb_info.get("created_at"),
                                "type": "knowledge_base",
                            }
                        )
                except Exception as e:
                    logger.warning(f"Could not get info for knowledge base {kb_id}: {e}")
                    continue

            return active_kbs_info
        except Exception as e:
            logger.error(f"Error getting active knowledge bases info: {e}")
            return []

    @staticmethod
    async def list_knowledge_bases() -> dict[str, Any]:
        """
        Lists all available knowledge bases from the database.

        Returns:
            Dictionary with list of knowledge bases and their metadata
        """
        try:
            db_manager = await get_database_manager()
            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)

            # Get knowledge bases from database
            kb_list = await db_manager.list_knowledge_bases()

            # Get active knowledge base IDs
            active_kb_ids = await RAGService.get_active_knowledge_bases()

            knowledge_bases = []
            for kb_info in kb_list:
                doc_count = 0
                try:
                    # Get unique sources to count documents accurately, not chunks
                    unique_sources = rag_db.get_unique_sources(kb_info["id"])
                    doc_count = len(unique_sources)
                except Exception as e:
                    logger.warning(f"Could not get document count for KB {kb_info['id']}: {e}")

                knowledge_bases.append(
                    {
                        "id": kb_info["id"],
                        "name": kb_info["display_name"],  # Use display name for frontend
                        "description": kb_info["description"],
                        "chunk_size": kb_info.get("chunk_size", CHUNK_SIZE),
                        "chunk_overlap": kb_info.get("chunk_overlap", CHUNK_OVERLAP),
                        "documentCount": doc_count,
                        "isActive": kb_info["id"] in active_kb_ids,
                        "createdAt": kb_info["created_at"],
                        "type": "knowledge_base",
                    }
                )

            return {
                "knowledgeBases": knowledge_bases,
                "total": len(knowledge_bases),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list knowledge bases: {str(e)}")

    @staticmethod
    async def create_knowledge_base(
        name: str,
        description: str = None,
        chunk_size: int = None,
        chunk_overlap: int = None,
        embed_model: str | None = None,
        enable_reference_filtering: bool = True,
    ) -> dict[str, Any]:
        """
        Creates a new empty knowledge base with database entry and ChromaDB collection.

        Args:
            name: Display name of the knowledge base
            description: Optional description
            chunk_size: Size of text chunks for processing
            chunk_overlap: Overlap between chunks

        Returns:
            Dictionary with created knowledge base info
        """
        if not name or not name.strip():
            raise HTTPException(status_code=400, detail="Knowledge base name is required")

        from ..constants import CHUNK_OVERLAP, CHUNK_SIZE

        try:
            # Use defaults if not provided
            chunk_size = chunk_size if chunk_size is not None else CHUNK_SIZE
            chunk_overlap = chunk_overlap if chunk_overlap is not None else CHUNK_OVERLAP
            # Create database entry and get generated ID
            db_manager = await get_database_manager()
            kb_id = await db_manager.create_knowledge_base(
                display_name=name.strip(),
                description=description,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                embed_model=embed_model,
                enable_reference_filtering=enable_reference_filtering,
            )

            # Create ChromaDB collection using the generated ID with proper embedding model
            embeddings = await get_embedding_function(embed_model)
            rag_db = RAGDB(embeddings=embeddings)
            collection = await rag_db.get_or_create_collection(name=kb_id)

            # Add the new KB to the active list
            await RAGService.add_to_active_knowledge_bases(kb_id)

            knowledge_base = {
                "id": kb_id,
                "name": name.strip(),  # Display name for frontend
                "description": description or f"Knowledge base: {name.strip()}",
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "documentCount": 0,
                "isActive": True,  # New KBs should be active by default
                "createdAt": datetime.now().isoformat(),
                "type": "knowledge_base",
            }

            return {
                "knowledgeBase": knowledge_base,
                "message": f"Knowledge base '{name}' created successfully",
            }

        except ValueError as e:
            # Database manager raises ValueError for conflicts
            raise HTTPException(status_code=409, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create knowledge base: {str(e)}")

    @staticmethod
    async def delete_knowledge_base(kb_id: str) -> dict[str, Any]:
        """
        Deletes a knowledge base (database entry and ChromaDB collection).
        Also cleans up uploaded_files collection references.

        Args:
            kb_id: ID of the knowledge base to delete

        Returns:
            Dictionary confirming deletion
        """
        if not kb_id or not kb_id.strip():
            raise HTTPException(status_code=400, detail="Knowledge base ID is required")

        try:
            # Get knowledge base info before deletion
            db_manager = await get_database_manager()
            kb_info = await db_manager.get_knowledge_base_by_id(kb_id)
            if not kb_info:
                raise HTTPException(status_code=404, detail=f"Knowledge base with ID '{kb_id}' not found")

            # Clean up uploaded_files collection first
            cleanup_result = await RAGService.cleanup_uploaded_files_for_kb(kb_id)

            # Delete ChromaDB collection
            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)

            try:
                rag_db.delete_collection(kb_id)
            except Exception as e:
                logger.warning(f"Could not delete ChromaDB collection {kb_id}: {e}")

            # Delete database entry
            deleted = await db_manager.delete_knowledge_base(kb_id)
            if not deleted:
                raise HTTPException(
                    status_code=404,
                    detail=f"Knowledge base with ID '{kb_id}' not found in database",
                )

            # Remove from active knowledge bases list
            await RAGService.remove_from_active_knowledge_bases(kb_id)

            message = f"Knowledge base '{kb_info['display_name']}' deleted successfully"
            if cleanup_result.get("success"):
                message += f" (cleaned {cleanup_result['cleaned_count']} uploaded file refs, deleted {cleanup_result['deleted_count']} orphaned files)"

            return {"success": True, "message": message, "cleanup_stats": cleanup_result}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete knowledge base: {str(e)}")

    @staticmethod
    async def get_knowledge_base_info(name: str) -> dict[str, Any]:
        """
        Gets detailed information about a specific knowledge base.

        Args:
            name: Display name or ID of the knowledge base

        Returns:
            Dictionary with knowledge base details
        """
        if not name or not name.strip():
            raise HTTPException(status_code=400, detail="Knowledge base name is required")

        try:
            # Resolve knowledge base name to get info from database
            db_manager = await get_database_manager()

            # Try to get by display name first, then by ID
            kb_info = await db_manager.get_knowledge_base_by_display_name(name)
            if not kb_info:
                kb_info = await db_manager.get_knowledge_base_by_id(name)

            if not kb_info:
                raise HTTPException(status_code=404, detail=f"Knowledge base '{name}' not found")

            # Get document count from ChromaDB
            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)

            doc_count = 0
            try:
                collection = rag_db.client.get_collection(name=kb_info["id"], embedding_function=rag_db.embeddings)
                doc_count = collection.count()
            except Exception as e:
                logger.warning(f"Could not get document count for KB {kb_info['id']}: {e}")

            return {
                "id": kb_info["id"],
                "name": kb_info["display_name"],
                "description": kb_info["description"],
                "documentCount": doc_count,
                "isActive": False,
                "createdAt": kb_info["created_at"],
                "type": "knowledge_base",
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get knowledge base info: {str(e)}")

    @staticmethod
    async def add_documents_to_knowledge_base(
        documents: list[dict[str, Any]], knowledge_base_name: str
    ) -> dict[str, Any]:
        """
        Processes, chunks, and adds a list of documents to a specified knowledge base.
        Also stores full text in uploaded_files collection for all documents.

        Args:
            documents: List of document dictionaries with content, source, and optional metadata
            knowledge_base_name: Target knowledge base name or ID

        Returns:
            A dictionary confirming the status of the operation.
        """
        if not documents:
            raise HTTPException(status_code=400, detail="The documents list cannot be empty.")

        # Resolve knowledge base name/ID to ChromaDB collection ID
        db_manager = await get_database_manager()
        kb_id = await db_manager.resolve_knowledge_base_id(knowledge_base_name)
        if not kb_id:
            raise HTTPException(status_code=404, detail=f"Knowledge base '{knowledge_base_name}' not found")

        # Retrieve enable_reference_filtering parameter from knowledge base configuration
        # This will be used later for content filtering
        enable_reference_filtering = True  # Default value
        try:
            kb_info = await db_manager.get_knowledge_base_by_id(kb_id)
            if kb_info and "enable_reference_filtering" in kb_info:
                enable_reference_filtering = kb_info["enable_reference_filtering"]
                logger.debug(f"Retrieved enable_reference_filtering: {enable_reference_filtering}")
        except Exception as e:
            logger.warning(f"Could not retrieve enable_reference_filtering setting: {e}, using default: True")

        try:
            # Process documents and add content hashes
            processed_documents = []
            for doc in documents:
                # Generate content hash from file bytes if available, otherwise from text content
                doc_metadata = doc.get("metadata", {}).copy()

                # Check if we have file bytes in metadata for hash calculation
                if "file_bytes" in doc_metadata:
                    content_hash = hashlib.sha256(doc_metadata["file_bytes"]).hexdigest()
                    doc_metadata.pop("file_bytes")  # Remove bytes from metadata to avoid storage issues
                else:
                    # Fallback to content-based hash for text-only documents
                    content_hash = hashlib.sha256(doc["content"].encode("utf-8")).hexdigest()

                # Add content hash to metadata
                doc_metadata["content_hash"] = content_hash
                doc_metadata["key"] = content_hash
                doc_metadata["file_hash"] = content_hash

                processed_doc = {
                    "content": doc["content"],
                    "source": doc["source"],
                    "metadata": doc_metadata,
                }
                processed_documents.append(processed_doc)

                # Store full text in uploaded_files collection
                try:
                    title = doc_metadata.get("title", doc["source"])
                    filename = doc_metadata.get("filename", doc["source"])
                    file_type = doc_metadata.get("file_type", "unknown")

                    await RAGService._add_to_uploaded_files_collection(
                        content=doc["content"],
                        title=title,
                        key=content_hash,
                        filename=filename,
                        knowledge_base_id=kb_id,
                        file_type=file_type,
                        source=doc["source"],
                        additional_metadata=doc_metadata,
                    )
                    logger.info(f"Added document {doc['source']} to uploaded_files with key {content_hash}")
                except Exception as e:
                    logger.warning(f"Failed to add document {doc['source']} to uploaded_files: {e}")

            # Add documents to knowledge base
            result = await add_documents_to_kb(documents=processed_documents, knowledge_base_name=kb_id)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            raise HTTPException(status_code=500, detail="An internal server error occurred.")

    @staticmethod
    async def query_documents(
        query_text: str,
        knowledge_base_names: list[str] = None,
        keys: str | list[str] = None,
        k: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Queries multiple knowledge bases for document chunks similar to the query text.
        Results are ranked by similarity score across all knowledge bases.

        Args:
            query_text: The text to search for
            knowledge_base_names: List of knowledge base names or IDs to search (defaults to active KBs)
            keys: Single key (str) or list of keys (List[str]) to filter by document keys
            k: Total number of results to return (distributed across all KBs)
            where: Optional metadata filter conditions (e.g., {"author": "Smith", "year": {"$gte": 2020}})
            where_document: Optional document content filter (e.g., {"$contains": "machine learning"})

        Returns:
            Dictionary with query results ranked by similarity
        """
        # Use active knowledge bases if none specified
        if not knowledge_base_names:
            knowledge_base_names = await RAGService.get_active_knowledge_bases_validated()

        if not knowledge_base_names:
            raise HTTPException(status_code=400, detail="No knowledge bases available for querying")

        try:
            db_manager = await get_database_manager()

            # Map KB names/IDs to actual KB info by embed_model
            kb_info_list = []
            for kb_name_or_id in knowledge_base_names:
                # Try to resolve as name first, then as ID
                kb_id = await db_manager.resolve_knowledge_base_id(kb_name_or_id)
                if kb_id:
                    info = await db_manager.get_knowledge_base_by_id(kb_id)
                    if info:
                        kb_info_list.append(info)

            if not kb_info_list:
                raise HTTPException(status_code=404, detail="No valid knowledge bases found")

            from collections import defaultdict

            grouped: defaultdict[str, list] = defaultdict(list)
            for info in kb_info_list:
                # Use the embedding model from KB config, fallback to user config default
                embed_model = info.get("embed_model")
                if not embed_model:
                    # Get default from user config
                    from ..manager_singleton import ManagerSingleton

                    user_config = await ManagerSingleton.get_user_config()
                    embed_model = user_config.embed_model or "nomic-embed-text"
                grouped[embed_model].append(info["id"])

            all_results = []
            for model_name, kb_ids in grouped.items():
                embeddings = await get_embedding_function(model_name)
                rag_db = RAGDB(embeddings=embeddings)
                for kb_id in kb_ids:
                    query_result = rag_db.query(
                        query_text=query_text,
                        collection_name=kb_id,
                        k=k,
                        keys=keys,
                        where=where,
                        where_document=where_document,
                    )
                    for i in range(len(query_result["documents"][0])):
                        all_results.append(
                            {
                                "content": query_result["documents"][0][i],
                                "metadata": query_result["metadatas"][0][i],
                                "distance": query_result["distances"][0][i],
                                "knowledge_base_name": kb_id,
                            }
                        )

            all_results.sort(key=lambda x: x["distance"])
            return all_results[:k]
        except HTTPException:
            raise

    @staticmethod
    def _clean_metadata_for_chromadb(metadata: dict[str, Any]) -> dict[str, Any]:
        """Convert list values to strings for ChromaDB compatibility."""
        cleaned = {}
        for key, value in metadata.items():
            if isinstance(value, list):
                if all(isinstance(item, dict) for item in value):
                    # Handle list of dicts (like creators)
                    cleaned[key] = ", ".join(
                        [f"{item.get('firstName', '')} {item.get('lastName', '')}".strip() for item in value]
                    )
                else:
                    # Handle simple lists (like tags, collections)
                    cleaned[key] = ", ".join([str(item) for item in value])
            else:
                cleaned[key] = value
        return cleaned

    @staticmethod
    def _sanitize_metadata(metadata: dict) -> dict:
        """Ensure all metadata values are str/int/float/bool, replace None with ''."""
        return {k: (v if v is not None else "") for k, v in metadata.items()}

    @staticmethod
    async def get_documents_by_metadata(
        knowledge_base_names: list[str], where: dict[str, Any], include_content: bool = True
    ) -> list[dict[str, Any]]:
        """
        Get documents by metadata filters without requiring embeddings.
        This is useful for reconstruction and other non-semantic operations.

        Args:
            knowledge_base_names: List of knowledge base names or IDs to search
            where: Metadata filter conditions
            include_content: Whether to include document content

        Returns:
            List of documents with metadata and optionally content
        """
        try:
            db_manager = await get_database_manager()
            all_documents = []

            for kb_name in knowledge_base_names:
                try:
                    # Resolve KB name/ID
                    kb_id = await db_manager.resolve_knowledge_base_id(kb_name)
                    if not kb_id:
                        logger.warning(f"Knowledge base {kb_name} not found")
                        continue

                    # Get KB info for embedding model
                    kb_info = await db_manager.get_knowledge_base_by_id(kb_id)
                    embed_model = kb_info.get("embed_model") if kb_info else None

                    # Get embeddings (needed for collection access but not for metadata queries)
                    embeddings = await get_embedding_function(embed_model)
                    rag_db = RAGDB(embeddings=embeddings)

                    # Get documents by metadata without embeddings
                    documents = rag_db.get_documents_by_metadata(
                        collection_name=kb_id, where=where, include_content=include_content
                    )

                    # Add knowledge base info to each document
                    for doc in documents:
                        doc["knowledge_base_name"] = kb_id
                        doc["knowledge_base_display_name"] = kb_info.get("display_name", kb_id) if kb_info else kb_id

                    all_documents.extend(documents)

                except Exception as e:
                    logger.debug(f"Error getting documents from KB {kb_name}: {e}")
                    continue

            return all_documents

        except Exception as e:
            logger.error(f"Error getting documents by metadata: {e}")
            return []

    @staticmethod
    async def _parse_pdf_bytes(pdf_bytes: bytes, filename: str) -> str:
        """Parse PDF bytes and extract text using config-based parser."""
        from .parser import extract_full_text_from_bytes_with_config

        try:
            return await extract_full_text_from_bytes_with_config(pdf_bytes, filename)
        except Exception as e:
            error_msg = str(e)
            if "Parser Server" in error_msg.lower():
                raise ValueError(f"Parser Server failed: {error_msg}. Try switching to Kreuzberg parser in settings.")
            raise ValueError(f"PDF parsing failed: {error_msg}")

    @staticmethod
    async def _process_single_zotero_item(
        item_key: str, kb_id: str, completed_count: int, total_count: int, progress_callback=None
    ) -> dict[str, Any]:
        """Process a single Zotero item using unified pipeline."""
        from ..zotero.service import zotero_service

        try:
            logger.info(f"[{completed_count}/{total_count}] Processing: {item_key}")

            # Get PDF bytes and metadata from Zotero
            pdf_bytes_list = await zotero_service.get_pdf_bytes_by_keys([item_key])
            meta_data_list = await zotero_service.extract_items_meta([item_key])

            if not pdf_bytes_list or not pdf_bytes_list[0]:
                error_result = {"key": item_key, "status": "failed", "error": "No PDF found"}
                if progress_callback:
                    await progress_callback(item_key, "failed", error_result)
                return error_result

            # Prepare metadata for unified processing
            meta_data = meta_data_list[0] if meta_data_list else {}
            cleaned_metadata = RAGService._clean_metadata_for_chromadb(meta_data)
            sanitized_metadata = RAGService._sanitize_metadata(cleaned_metadata)
            sanitized_metadata["zotero_key"] = item_key

            # Use unified processing pipeline
            result = await RAGService._process_and_add_document(
                file_bytes=pdf_bytes_list[0],
                filename=f"{item_key}.pdf",
                kb_id=kb_id,
                source=item_key,
                additional_metadata=sanitized_metadata,
                progress_callback=progress_callback,
                progress_data={"key": item_key, "status": "processing"},
            )

            # Format result for Zotero-specific response
            if result["status"] == "completed":
                logger.info(
                    f"[{completed_count}/{total_count}] ✓ Added to DB {item_key}: {result.get('title', 'Unknown')} ({result.get('chunks_added', 0)} chunks)"
                )
                if progress_callback:
                    await progress_callback(item_key, "completed", result)
            elif result["status"] == "already_exists":
                if progress_callback:
                    await progress_callback(item_key, "skipped", result)
            else:
                if progress_callback:
                    await progress_callback(item_key, "failed", result)

            return result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{completed_count}/{total_count}] ✗ Failed {item_key}: {error_msg}")
            error_result = {"key": item_key, "status": "failed", "error": error_msg}

            if progress_callback:
                await progress_callback(item_key, "failed", error_result)

            return error_result

    @staticmethod
    async def zotero_bulk_add_to_knowledge_base(zotero_keys: list[str], knowledge_base_name: str) -> dict[str, Any]:
        """
        Non-streaming version that delegates to streaming version without callback.
        """
        return await RAGService.zotero_bulk_add_to_knowledge_base_with_streaming(
            zotero_keys=zotero_keys, knowledge_base_name=knowledge_base_name, progress_callback=None
        )

    @staticmethod
    async def zotero_bulk_add_to_knowledge_base_with_streaming(
        zotero_keys: list[str], knowledge_base_name: str, progress_callback=None
    ) -> dict[str, Any]:
        """
        Optimized bulk import with concurrent PDF processing and sequential ChromaDB operations.

        Args:
            zotero_keys: List of Zotero item keys
            knowledge_base_name: Target knowledge base name or ID
            progress_callback: Callback function for progress updates

        Returns:
            Dictionary confirming the operation status
        """
        logger.info(f"Starting optimized bulk import for {len(zotero_keys)} items into '{knowledge_base_name}'...")

        # Resolve knowledge base name/ID to ChromaDB collection ID
        db_manager = await get_database_manager()
        kb_id = await db_manager.resolve_knowledge_base_id(knowledge_base_name)
        if not kb_id:
            raise HTTPException(status_code=404, detail=f"Knowledge base '{knowledge_base_name}' not found")

        # Results tracking
        successful_items = []
        failed_items = []
        total_chunks = 0

        # Process items in small batches for better concurrency
        batch_size = 4
        completed_count = 0

        for i in range(0, len(zotero_keys), batch_size):
            batch_keys = zotero_keys[i : i + batch_size]
            batch_tasks = []

            # Process batch concurrently
            for key in batch_keys:
                completed_count += 1
                task = RAGService._process_single_zotero_item(
                    key, kb_id, completed_count, len(zotero_keys), progress_callback
                )
                batch_tasks.append(task)

            # Wait for batch to complete
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Process results
            for result in results:
                if isinstance(result, dict):
                    if result.get("status") in ["completed", "already_exists"]:
                        successful_items.append(result)
                        total_chunks += result.get("chunks_added", 0)
                    else:
                        failed_items.append(result)

            # Small delay between batches
            if i + batch_size < len(zotero_keys):
                await asyncio.sleep(0.1)

        # Final summary
        logger.info("\n=== BULK IMPORT SUMMARY ===")
        logger.info(f"Total items: {len(zotero_keys)}")
        logger.info(f"Successful: {len(successful_items)}")
        logger.info(f"Failed: {len(failed_items)}")
        logger.info(f"Total chunks added: {total_chunks}")

        if len(successful_items) == 0:
            raise HTTPException(
                status_code=400,
                detail="No documents were successfully processed and added to the knowledge base.",
            )

        return {
            "status": "success",
            "message": f"Successfully added {total_chunks} chunks from {len(successful_items)} documents to the '{knowledge_base_name}' knowledge base.",
            "total_items": len(zotero_keys),
            "successful_items": len(successful_items),
            "failed_items": len(failed_items),
            "chunks_added": total_chunks,
            "details": {"successful": successful_items, "failed": failed_items},
        }

    @staticmethod
    async def process_uploaded_pdf(pdf_bytes: bytes, filename: str, knowledge_base_name: str) -> dict[str, Any]:
        """
        Processes an uploaded PDF file and adds it to a knowledge base using unified pipeline.

        Args:
            pdf_bytes: Raw PDF file bytes
            filename: Original filename of the uploaded PDF
            knowledge_base_name: Target knowledge base name or ID

        Returns:
            Dictionary confirming the operation status
        """
        try:
            # Resolve knowledge base name/ID to ChromaDB collection ID
            db_manager = await get_database_manager()
            kb_id = await db_manager.resolve_knowledge_base_id(knowledge_base_name)
            if not kb_id:
                raise HTTPException(status_code=404, detail=f"Knowledge base '{knowledge_base_name}' not found")

            # Use unified processing pipeline
            result = await RAGService._process_and_add_document(
                file_bytes=pdf_bytes,
                filename=filename,
                kb_id=kb_id,
                source=filename,
                additional_metadata={"upload_method": "direct", "uploaded_filename": filename},
            )

            # Format response for API consistency
            if result["status"] == "completed":
                response = {
                    "status": "completed",
                    "message": f"Successfully processed {filename}",
                    "filename": filename,
                    "content_hash": result.get("content_hash"),
                    "chunks_added": result.get("chunks_added", 0),
                    "fulltext_stored": True,
                    "fulltext_key": result.get("content_hash"),
                }
            elif result["status"] == "already_exists":
                response = {
                    "status": "already_exists",
                    "message": f"Document with hash {result.get('content_hash')} already exists in knowledge base '{knowledge_base_name}'",
                    "filename": filename,
                    "content_hash": result.get("content_hash"),
                    "existing_source": result.get("existing_source", "unknown"),
                    "chunks_added": 0,
                    "fulltext_stored": True,
                }
            else:
                raise HTTPException(status_code=500, detail=result.get("error", f"Failed to process {filename}"))

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to process uploaded PDF {filename}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def _add_to_uploaded_files_collection(
        content: str,
        title: str,
        key: str,
        filename: str,
        knowledge_base_id: str,
        file_type: str = "pdf",
        source: str = None,
        additional_metadata: dict[str, Any] = None,
    ):
        """Add full document text to uploaded_files collection with SHA256 key."""
        collection = await RAGService._get_uploaded_files_collection()

        # Check if document exists
        try:
            existing = collection.get(ids=[key], include=["metadatas"])
            if existing["ids"]:
                # Update KB references using centralized method
                return await RAGService._centralized_kb_reference_update(key, knowledge_base_id, "add")
        except Exception:
            pass

        # Create new document
        metadata = {
            "key": key,
            "title": title,
            "filename": filename,
            "knowledge_base_refs": knowledge_base_id,
            "file_type": file_type,
            "source": source or filename,
        }

        if additional_metadata:
            metadata.update({k: v for k, v in additional_metadata.items() if k != "knowledge_base_refs"})

        collection.add(ids=[key], documents=[content], metadatas=[metadata])
        logger.info(f"Added document to uploaded_files: {key}, KB: {knowledge_base_id}")
        return True

    @staticmethod
    async def get_uploaded_file_by_key(key: str) -> dict[str, Any] | None:
        """Retrieve a document from uploaded_files collection by key (Zotero Key or SHA256 hash)."""
        try:
            from .db import RAGDB

            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)

            # Try to get the collection (it might not exist)
            try:
                collection = rag_db.client.get_collection("uploaded_files", embedding_function=embeddings)
            except Exception:
                return None

            # Get document by key
            results = collection.get(ids=[key], include=["documents", "metadatas"])

            if results["documents"] and len(results["documents"]) > 0:
                return {
                    "key": key,
                    "content": results["documents"][0],
                    "metadata": results["metadatas"][0],
                }

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve document {key}: {e}")
            return None

    @staticmethod
    async def get_uploaded_files_by_keys(keys: list[str]) -> dict[str, dict[str, Any]]:
        """
        Efficiently retrieve multiple documents from uploaded_files collection by keys using bulk query.

        Args:
            keys: List of keys (SHA256 hashes) to retrieve

        Returns:
            Dictionary mapping key -> document data, only includes found documents
        """
        try:
            from .db import RAGDB

            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)

            # Try to get the collection (it might not exist)
            try:
                collection = rag_db.client.get_collection("uploaded_files", embedding_function=embeddings)
            except Exception:
                return {}

            # Bulk get documents by keys - much more efficient than individual calls
            results = collection.get(ids=keys, include=["documents", "metadatas"])

            # Build result dictionary
            documents = {}
            for i, doc_id in enumerate(results["ids"]):
                documents[doc_id] = {
                    "key": doc_id,
                    "content": results["documents"][i],
                    "metadata": results["metadatas"][i],
                }

            return documents

        except Exception as e:
            logger.error(f"Failed to retrieve documents {keys}: {e}")
            return {}

    @staticmethod
    async def search_uploaded_files(
        query: str = None, knowledge_base_id: str = None, file_type: str = None
    ) -> list[dict[str, Any]]:
        """Search uploaded_files collection by various criteria."""
        try:
            from .db import RAGDB

            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)

            try:
                collection = rag_db.client.get_collection("uploaded_files", embedding_function=embeddings)
            except Exception:
                return []

            where_clause = {"file_type": file_type} if file_type else {}

            if query:
                results = collection.query(
                    query_texts=[query],
                    where=where_clause if where_clause else None,
                    n_results=10,
                    include=["documents", "metadatas", "distances"],
                )
                documents = [
                    {
                        "key": results["metadatas"][0][i].get("key"),
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i],
                    }
                    for i in range(len(results["documents"][0]))
                    if not knowledge_base_id
                    or knowledge_base_id
                    in RAGService._parse_kb_refs(results["metadatas"][0][i].get("knowledge_base_refs", ""))
                ]
            else:
                results = collection.get(
                    where=where_clause if where_clause else None, include=["documents", "metadatas"]
                )
                documents = [
                    {
                        "key": results["metadatas"][i].get("key"),
                        "content": results["documents"][i],
                        "metadata": results["metadatas"][i],
                    }
                    for i in range(len(results["documents"]))
                    if not knowledge_base_id
                    or knowledge_base_id
                    in RAGService._parse_kb_refs(results["metadatas"][i].get("knowledge_base_refs", ""))
                ]

            return documents

        except Exception as e:
            logger.error(f"Failed to search uploaded_files: {e}")
            return []

    @staticmethod
    async def get_document_by_zotero_key(zotero_key: str) -> dict[str, Any] | None:
        """
        Get document from uploaded_files collection by Zotero key.

        Args:
            zotero_key: Original Zotero item key

        Returns:
            Document dictionary with content and metadata, or None if not found
        """
        try:
            from .db import RAGDB

            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)

            # Try to get the collection
            try:
                collection = rag_db.client.get_collection("uploaded_files", embedding_function=embeddings)
            except Exception:
                return None

            # Get document by zotero_key
            results = collection.get(where={"zotero_key": zotero_key}, include=["documents", "metadatas"])

            if results["documents"] and len(results["documents"]) > 0:
                return {
                    "key": results["metadatas"][0].get("key"),
                    "content": results["documents"][0],
                    "metadata": results["metadatas"][0],
                }

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve document by zotero_key {zotero_key}: {e}")
            return None

    @staticmethod
    async def get_documents_by_zotero_keys(zotero_keys: list[str]) -> dict[str, dict[str, Any]]:
        """
        Efficiently get multiple documents from uploaded_files collection by Zotero keys using $in operator.

        Args:
            zotero_keys: List of Zotero item keys

        Returns:
            Dictionary mapping zotero_key -> document data, only includes found documents
        """
        try:
            from .db import RAGDB

            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)

            # Try to get the collection
            try:
                collection = rag_db.client.get_collection("uploaded_files", embedding_function=embeddings)
            except Exception:
                return {}

            # Bulk get documents by zotero_keys using $in operator - much more efficient!
            results = collection.get(where={"zotero_key": {"$in": zotero_keys}}, include=["documents", "metadatas"])

            # Build result dictionary keyed by zotero_key
            documents = {}
            for i, (doc, metadata) in enumerate(zip(results["documents"], results["metadatas"])):
                zotero_key = metadata.get("zotero_key")
                if zotero_key:
                    documents[zotero_key] = {
                        "key": metadata.get("key"),
                        "content": doc,
                        "metadata": metadata,
                    }

            return documents

        except Exception as e:
            logger.error(f"Failed to retrieve documents by zotero_keys {zotero_keys}: {e}")
            return {}

    @staticmethod
    async def remove_kb_reference_from_uploaded_files(content_hash: str, knowledge_base_id: str) -> bool:
        """Remove KB reference from uploaded file, delete if no refs remain."""
        return await RAGService._update_uploaded_file_kb_refs(content_hash, knowledge_base_id, add=False)

    @staticmethod
    async def cleanup_uploaded_files_for_kb(knowledge_base_id: str) -> dict[str, Any]:
        """Clean up uploaded_files when a knowledge base is deleted."""
        try:
            from .db import RAGDB

            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)

            try:
                collection = rag_db.client.get_collection("uploaded_files", embedding_function=embeddings)
            except Exception:
                return {
                    "cleaned_count": 0,
                    "deleted_count": 0,
                    "error": "uploaded_files collection not found",
                }

            results = collection.get(include=["metadatas"])
            cleaned_count = deleted_count = 0

            for i, doc_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i]
                kb_refs = RAGService._parse_kb_refs(metadata.get("knowledge_base_refs", ""))

                if knowledge_base_id in kb_refs:
                    kb_refs.remove(knowledge_base_id)
                    cleaned_count += 1

                    if not kb_refs:
                        collection.delete(ids=[doc_id])
                        deleted_count += 1
                    else:
                        metadata["knowledge_base_refs"] = RAGService._format_kb_refs(kb_refs)
                        collection.update(ids=[doc_id], metadatas=[metadata])

            logger.info(
                f"Cleaned up uploaded_files for KB {knowledge_base_id}: {cleaned_count} cleaned, {deleted_count} deleted"
            )
            return {"cleaned_count": cleaned_count, "deleted_count": deleted_count, "success": True}

        except Exception as e:
            logger.error(f"Failed to cleanup uploaded_files for KB {knowledge_base_id}: {e}")
            return {"cleaned_count": 0, "deleted_count": 0, "error": str(e), "success": False}

    @staticmethod
    async def migrate_uploaded_files_to_kb_refs() -> dict[str, Any]:
        """
        Migration utility to convert existing uploaded_files documents from knowledge_base_id
        to knowledge_base_refs comma-separated string format.

        Returns:
            Migration status and statistics
        """
        try:
            from .db import RAGDB

            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)

            # Try to get the collection
            try:
                collection = rag_db.client.get_collection("uploaded_files", embedding_function=embeddings)
            except Exception:
                return {
                    "migrated_count": 0,
                    "error": "uploaded_files collection not found",
                    "success": False,
                }

            # Get all documents
            results = collection.get(include=["metadatas"])

            migrated_count = 0
            updated_documents = []

            for i, doc_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i]

                # Check if document uses old format (knowledge_base_id) instead of new format (knowledge_base_refs)
                if "knowledge_base_id" in metadata and "knowledge_base_refs" not in metadata:
                    old_kb_id = metadata["knowledge_base_id"]

                    # Create new metadata with knowledge_base_refs as comma-separated string
                    new_metadata = metadata.copy()
                    new_metadata["knowledge_base_refs"] = old_kb_id  # Single KB ID becomes the string
                    del new_metadata["knowledge_base_id"]  # Remove old field

                    updated_documents.append((doc_id, new_metadata))
                    migrated_count += 1

            # Perform batch updates
            for doc_id, metadata in updated_documents:
                collection.update(ids=[doc_id], metadatas=[metadata])

            logger.info(f"Migrated {migrated_count} uploaded_files documents to use knowledge_base_refs")

            return {
                "migrated_count": migrated_count,
                "total_documents": len(results["ids"]),
                "success": True,
                "message": f"Successfully migrated {migrated_count} documents to new KB reference format",
            }

        except Exception as e:
            logger.error(f"Failed to migrate uploaded_files KB refs: {e}")
            return {"migrated_count": 0, "error": str(e), "success": False}

    @staticmethod
    async def clear_uploaded_files_collection() -> dict[str, Any]:
        """Clear all documents from uploaded_files collection."""
        try:
            from .db import RAGDB

            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)

            try:
                rag_db.delete_collection("uploaded_files")
                logger.info("Cleared uploaded_files collection")
                return {"success": True, "message": "uploaded_files collection cleared"}
            except Exception:
                return {
                    "success": True,
                    "message": "uploaded_files collection was already empty or didn't exist",
                }

        except Exception as e:
            logger.error(f"Failed to clear uploaded_files: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _parse_kb_refs(kb_refs_str: str) -> list[str]:
        """Parse comma-separated KB references string into list."""
        return [kb.strip() for kb in kb_refs_str.split(",") if kb.strip()] if kb_refs_str else []

    @staticmethod
    def _format_kb_refs(kb_refs: list[str]) -> str:
        """Format list of KB references into comma-separated string."""
        return ",".join(kb_refs)

    # =====================================================
    # CENTRALIZED HELPER METHODS FOR DATABASE ACCESS
    # =====================================================

    @staticmethod
    async def _get_rag_db_for_kb(kb_id: str):
        """Get RAGDB instance configured for a specific knowledge base."""
        db_manager = await get_database_manager()
        try:
            kb_info = await db_manager.get_knowledge_base_by_id(kb_id)
            embed_model = kb_info.get("embed_model") if kb_info else None
        except Exception:
            embed_model = None

        embeddings = await get_embedding_function(embed_model)
        return RAGDB(embeddings=embeddings)

    @staticmethod
    async def _get_uploaded_files_collection():
        """Get uploaded_files ChromaDB collection with error handling."""
        embeddings = await get_embedding_function()
        rag_db = RAGDB(embeddings=embeddings)
        try:
            return rag_db.client.get_collection("uploaded_files", embedding_function=embeddings)
        except Exception:
            return None

    @staticmethod
    async def _document_exists_in_kb(content_hash: str, kb_id: str) -> bool:
        """Check if document with content_hash already exists in knowledge base."""
        existing_metadata = await RAGService._centralized_document_exists_check(content_hash, kb_id)
        return existing_metadata is not None

    @staticmethod
    async def _centralized_document_exists_check(content_hash: str, kb_id: str) -> dict[str, Any] | None:
        """
        Centralized method to check if a document already exists in a knowledge base.

        Args:
            content_hash: SHA256 hash of document content
            kb_id: Knowledge base ID to check

        Returns:
            Document metadata if exists, None otherwise
        """
        try:
            rag_db = await RAGService._get_rag_db_for_kb(kb_id)
            collection = rag_db.client.get_collection(kb_id, embedding_function=rag_db.embeddings)

            existing = collection.get(where={"content_hash": content_hash}, include=["metadatas"])

            if existing["ids"]:
                return existing["metadatas"][0]

            return None

        except Exception as e:
            logger.debug(f"Error checking document existence in KB {kb_id}: {e}")
            return None

    # =====================================================
    # UNIFIED DOCUMENT PROCESSING PIPELINE
    # =====================================================

    @staticmethod
    async def _process_and_add_document(
        file_bytes: bytes,
        filename: str,
        kb_id: str,
        source: str = None,
        additional_metadata: dict[str, Any] = None,
        progress_callback=None,
        progress_data: dict[str, Any] = None,
    ) -> dict[str, Any]:
        """
        Unified document processing pipeline.
        Handles: hash calculation, duplicate check, text extraction, KB addition, uploaded_files storage.
        """
        try:
            # Calculate content hash from file bytes
            content_hash = hashlib.sha256(file_bytes).hexdigest()
            source = source or filename

            # Check for duplicates first (before expensive text extraction) using centralized method
            existing_metadata = await RAGService._centralized_document_exists_check(content_hash, kb_id)
            if existing_metadata:
                # Update uploaded_files KB reference if needed
                await RAGService._centralized_kb_reference_update(content_hash, kb_id, "add")
                return {
                    "key": source,
                    "status": "already_exists",
                    "content_hash": content_hash,
                    "title": existing_metadata.get("title", filename),
                    "existing_source": existing_metadata.get("source", "unknown"),
                    "message": "Document already exists in knowledge base",
                }

            # Extract text from file bytes
            if progress_callback and progress_data:
                await progress_callback(source, "processing", {**progress_data, "title": "Extracting text..."})

            full_text = await RAGService._parse_pdf_bytes(file_bytes, filename)
            if not full_text:
                return {"key": source, "status": "failed", "error": "No text extracted"}

            # Extract title from parser metadata if available
            title = filename
            if isinstance(full_text, list) and len(full_text) > 0 and isinstance(full_text[0], dict):
                parser_metadata = full_text[0].get("metadata", {})
                title = parser_metadata.get("title", filename)
                full_text = full_text[0].get("text", str(full_text))

            # Prepare metadata
            metadata = {
                "filename": filename,
                "title": title,
                "file_type": "pdf",
                "content_hash": content_hash,
                "file_hash": content_hash,
                "key": content_hash,
            }
            if additional_metadata:
                metadata.update(additional_metadata)

            # Create document for KB addition
            document = {"content": full_text, "source": source, "metadata": metadata}

            # Add to knowledge base
            result = await add_documents_to_kb(documents=[document], knowledge_base_name=kb_id)

            # Check if KB addition was successful
            if result.get("status") != "success":
                error_msg = result.get("message", "Unknown error adding to knowledge base")
                logger.error(f"KB addition failed for {source}: {error_msg}")
                return {"key": source, "status": "failed", "error": error_msg}

            chunks_added = result.get("chunks_added", 0)
            if chunks_added == 0:
                logger.error(f"KB addition returned 0 chunks for {source}: {result}")
                return {
                    "key": source,
                    "status": "failed",
                    "error": "No chunks were added to knowledge base",
                }

            logger.info(f"Successfully added {chunks_added} chunks to KB for {source}")

            # Add to uploaded_files collection
            try:
                await RAGService._add_to_uploaded_files_collection(
                    content=full_text,
                    title=title,
                    key=content_hash,
                    filename=filename,
                    knowledge_base_id=kb_id,
                    file_type="pdf",
                    source=source,
                    additional_metadata=metadata,
                )
                logger.info(f"Successfully added to uploaded_files collection for {source}")
            except Exception as uploaded_files_error:
                logger.error(f"Failed to add to uploaded_files collection for {source}: {str(uploaded_files_error)}")
                # Don't fail the entire operation for uploaded_files errors - KB addition succeeded
                logger.warning("Continuing despite uploaded_files error - KB addition was successful")

            logger.info(f"Document processing completed successfully for {source}: {chunks_added} chunks")

            return {
                "key": source,
                "status": "completed",
                "title": title,
                "content_hash": content_hash,
                "chunks_added": chunks_added,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Exception in _process_and_add_document for {source}: {error_msg}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback

            logger.error(f"Exception traceback: {traceback.format_exc()}")
            return {"key": source, "status": "failed", "error": error_msg}

    @staticmethod
    async def _update_uploaded_file_kb_refs(key: str, kb_id: str, add: bool = True) -> bool:
        """
        Add or remove a KB reference from an uploaded file.

        Args:
            key: Document key (SHA256 hash)
            kb_id: Knowledge base ID
            add: True to add reference, False to remove

        Returns:
            True if successful, False otherwise
        """
        action = "add" if add else "remove"
        return await RAGService._centralized_kb_reference_update(key, kb_id, action)

    @staticmethod
    async def _centralized_kb_reference_update(key: str, kb_id: str, action: str = "add") -> bool:
        """
        Centralized method to manage KB references in uploaded_files collection.

        Args:
            key: Document key (content hash)
            kb_id: Knowledge base ID to add/remove
            action: "add" or "remove"

        Returns:
            True if successful, False otherwise
        """
        try:
            collection = await RAGService._get_uploaded_files_collection()

            # Handle case where uploaded_files collection doesn't exist
            if collection is None:
                logger.warning(f"uploaded_files collection not found - skipping KB reference update for {key}")
                return True  # Return True as this is not a critical failure

            # Get current document
            results = collection.get(ids=[key], include=["metadatas"])
            if not results["ids"]:
                if action == "add":
                    logger.warning(f"Document {key} not found in uploaded_files, cannot update KB references")
                return False

            current_metadata = results["metadatas"][0].copy()
            kb_refs = RAGService._parse_kb_refs(current_metadata.get("knowledge_base_refs", ""))

            # Update references based on action
            if action == "add" and kb_id not in kb_refs:
                kb_refs.append(kb_id)
            elif action == "remove" and kb_id in kb_refs:
                kb_refs.remove(kb_id)
            else:
                # No change needed
                return True

            if not kb_refs:
                # No more references, delete document
                collection.delete(ids=[key])
                logger.info(f"Deleted document {key} from uploaded_files - no KB references remain")
            else:
                # Update references
                current_metadata["knowledge_base_refs"] = RAGService._format_kb_refs(kb_refs)
                collection.update(ids=[key], metadatas=[current_metadata])
                logger.info(f"Updated document {key} KB refs: {kb_refs}")

            return True

        except Exception as e:
            logger.error(f"Failed to update KB references for {key}: {e}")
            return False

    @staticmethod
    async def get_knowledge_base_documents(knowledge_base_name: str) -> list[dict[str, Any]]:
        """
        Get document titles from a knowledge base for @ mentions.
        Only returns documents that actually exist in this specific knowledge base.

        Args:
            knowledge_base_name: Name or ID of the knowledge base

        Returns:
            List of document dictionaries with keys:
            'source': source,
            'title': title,
            'key': key (content hash for full text access if available)
        """
        # Resolve knowledge base name/ID to ChromaDB collection ID
        db_manager = await get_database_manager()
        kb_id = await db_manager.resolve_knowledge_base_id(knowledge_base_name)
        if not kb_id:
            raise HTTPException(status_code=404, detail=f"Knowledge base '{knowledge_base_name}' not found")

        try:
            # Get knowledge base info to use proper embedding model
            embed_model = None
            try:
                kb_info = await db_manager.get_knowledge_base_by_id(kb_id)
                embed_model = kb_info.get("embed_model") if kb_info else None
            except Exception:
                pass

            embeddings = await get_embedding_function(embed_model)
            rag_db = RAGDB(embeddings=embeddings)

            # Get unique sources/documents from the ChromaDB collection (actual KB documents)
            unique_sources = rag_db.get_unique_sources(kb_id)

            # Build documents list from KB data
            documents_list = []
            for source_info in unique_sources:
                source = source_info.get("source", "unknown")
                title = source_info.get("title", source)

                # Try to find content hash for full text access
                content_hash = source_info.get("content_hash") or source_info.get("key")

                documents_list.append(
                    {
                        "source": source,
                        "title": title,
                        "key": content_hash
                        if content_hash
                        else source,  # Use content hash if available, fallback to source
                    }
                )

            return documents_list

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get documents from knowledge base: {str(e)}")

    @staticmethod
    async def reconstruct_document_from_chunks(
        document_id: str, knowledge_base_names: list[str] | None = None
    ) -> dict[str, Any] | None:
        """
        Reconstruct a full document by gathering and assembling all chunks with the same source/zotero_key.

        Args:
            document_id: The document ID, zotero_key, or source identifier
            knowledge_base_names: Optional list of knowledge base names to search in

        Returns:
            Dict with reconstructed content and metadata, or None if not found
        """
        try:
            # Use active knowledge bases if none specified
            if not knowledge_base_names:
                knowledge_base_names = await RAGService.get_active_knowledge_bases_validated()

            if not knowledge_base_names:
                logger.warning("No active knowledge bases available for reconstruction")
                return None

            # Search for chunks with matching source or zotero_key
            all_chunks = []

            # Search by source field
            chunks_by_source = await RAGService.get_documents_by_metadata(
                knowledge_base_names=knowledge_base_names,
                where={"source": document_id},
                include_content=True,
            )

            # Convert to the expected format for compatibility
            for doc in chunks_by_source:
                chunk = {
                    "content": doc.get("content", ""),
                    "metadata": doc.get("metadata", {}),
                    "knowledge_base_name": doc.get("knowledge_base_name", ""),
                }
                all_chunks.append(chunk)

            # Also search by zotero_key if different from source
            chunks_by_zotero = await RAGService.get_documents_by_metadata(
                knowledge_base_names=knowledge_base_names,
                where={"zotero_key": document_id},
                include_content=True,
            )

            # Convert and add zotero key results
            for doc in chunks_by_zotero:
                chunk = {
                    "content": doc.get("content", ""),
                    "metadata": doc.get("metadata", {}),
                    "knowledge_base_name": doc.get("knowledge_base_name", ""),
                }
                all_chunks.append(chunk)

            if not all_chunks:
                logger.info(f"No chunks found for document '{document_id}'")
                return None

            # Remove duplicates based on chunk_id
            seen_chunk_ids = set()
            unique_chunks = []
            for chunk in all_chunks:
                chunk_id = chunk.get("metadata", {}).get("chunk_id")
                if chunk_id and chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    unique_chunks.append(chunk)
                elif not chunk_id:
                    # If no chunk_id, use a combination of other fields to dedupe
                    chunk_key = (
                        chunk.get("metadata", {}).get("source", ""),
                        chunk.get("metadata", {}).get("chunk_index", -1),
                        chunk.get("content", "")[:100],  # First 100 chars as identifier
                    )
                    if chunk_key not in seen_chunk_ids:
                        seen_chunk_ids.add(chunk_key)
                        unique_chunks.append(chunk)

            if not unique_chunks:
                logger.info(f"No valid chunks found for document '{document_id}' after deduplication")
                return None

            # Sort chunks by chunk_index
            unique_chunks.sort(key=lambda x: x.get("metadata", {}).get("chunk_index", 0))

            # Reconstruct the document
            reconstructed_content = ""
            base_metadata = {}
            total_chunks = len(unique_chunks)

            for i, chunk in enumerate(unique_chunks):
                content = chunk.get("content", "")
                metadata = chunk.get("metadata", {})

                # Add content
                reconstructed_content += content

                # Use metadata from first chunk as base, excluding chunk-specific fields
                if i == 0:
                    base_metadata = {
                        k: v for k, v in metadata.items() if k not in ["chunk_id", "chunk_index", "chunk_size"]
                    }

            # Add reconstruction info to metadata
            base_metadata.update(
                {
                    "reconstructed_from_chunks": True,
                    "chunks_count": total_chunks,
                    "total_chunks": total_chunks,
                    "source": document_id,
                    "collection": "knowledge_base_chunks",
                }
            )

            logger.info(f"Reconstructed document '{document_id}' from {total_chunks} chunks")

            return {
                "content": reconstructed_content,
                "metadata": base_metadata,
                "source": "knowledge_base_chunks",
                "document_id": document_id,
                "chunks_count": total_chunks,
            }

        except Exception as e:
            logger.error(f"Error reconstructing document '{document_id}': {e}")
            return None
