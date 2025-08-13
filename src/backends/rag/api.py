"""
RAG API

This module provides API endpoints for RAG (Retrieval-Augmented Generation) operations,
including document management and knowledge base queries.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import asyncio
import uuid
from datetime import datetime
from loguru import logger

from .service import RAGService
from ..database import get_database_manager
from .db import get_embedding_function
from ..llm.model_utils import normalize_embedding_model_name
from ..manager_singleton import ManagerSingleton

# Router setup
router = APIRouter(prefix="/rag", tags=["RAG"])

class DocumentModel(BaseModel):
    content: str = Field(..., description="The full text content of the document or page.")
    source: str = Field(..., description="A unique identifier for the document source, e.g., a file name, Zotero key, or URL.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata like page number, author, etc.")

class AddDocumentsRequest(BaseModel):
    documents: List[DocumentModel]
    knowledge_base_name: str

class QueryRequest(BaseModel):
    query_text: str = Field(..., json_schema_extra={"example": "What are the key features of the new product?"})
    knowledge_base_names: List[str] = Field(..., json_schema_extra={"example": ["product_docs_v2"]}, description="List of knowledge base names to search")
    k: int = Field(10, gt=0, le=50, description="Number of results to return")

class QueryResultItem(BaseModel):
    content: str
    metadata: Dict[str, Any]
    distance: float
    knowledge_base_name: Optional[str] = Field(None, description="Source knowledge base")

class QueryResponse(BaseModel):
    results: List[QueryResultItem]

class ZoteroBulkAddRequest(BaseModel):
    zotero_keys: List[str]
    knowledge_base_name: str

class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(..., description="Name of the knowledge base")
    description: Optional[str] = Field(None, description="Optional description")
    chunk_size: Optional[int] = Field(1000, description="Chunk size for text splitting")
    chunk_overlap: Optional[int] = Field(200, description="Overlap between chunks")
    embed_model: Optional[str] = Field(None, description="Embedding model to use for this KB")
    enable_reference_filtering: Optional[bool] = Field(True, description="Enable filtering of references and citations")

class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    description: str
    documentCount: int
    isActive: bool
    createdAt: Optional[str]
    type: str

class KnowledgeBasesListResponse(BaseModel):
    knowledgeBases: List[KnowledgeBaseResponse]
    total: int
    timestamp: Optional[str]

class ActiveKnowledgeBasesRequest(BaseModel):
    knowledge_base_ids: List[str]

class ActiveKnowledgeBasesResponse(BaseModel):
    active_knowledge_bases: List[str]
    message: str

@router.post("/documents")
async def add_documents(request: AddDocumentsRequest):
    """
    Add documents to a knowledge base.
    """
    try:
        result = await RAGService.add_documents_to_knowledge_base(
            documents=request.documents,
            knowledge_base_name=request.knowledge_base_name
        )
        return result
    except Exception as e:
        logger.error(f"Failed to add documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add documents: {str(e)}")


@router.post("/documents/add")
async def add_documents_alias(request: AddDocumentsRequest):
    """
    Add documents to a knowledge base (alias endpoint for backward compatibility).
    """
    return await add_documents(request)


@router.post("/documents/query", response_model=QueryResponse)
async def query_documents_endpoint(request: QueryRequest):
    """
    Queries specified knowledge bases for document chunks similar to the query text.
    Results are ranked by similarity score across all knowledge bases.
    """
    result = await RAGService.query_documents(
        query_text=request.query_text,
        knowledge_base_names=request.knowledge_base_names,
        k=request.k
    )
    
    # Format results for response model
    formatted_results = [
        QueryResultItem(**item) for item in result
    ]
    
    return QueryResponse(results=formatted_results)


@router.post("/zotero/bulk-add")
async def zotero_bulk_add_endpoint(request: ZoteroBulkAddRequest):
    """
    Fetches multiple Zotero PDFs concurrently, processes their pages,
    and adds them to a knowledge base.
    """
    return await RAGService.zotero_bulk_add_to_knowledge_base(
        zotero_keys=request.zotero_keys,
        knowledge_base_name=request.knowledge_base_name
    )

@router.post("/zotero/bulk-add-stream")
async def zotero_bulk_add_stream_endpoint(request: ZoteroBulkAddRequest):
    """
    Fetches multiple Zotero PDFs with streaming progress updates.
    """
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    async def generate_progress():
        try:
            # Send initial progress
            yield f"data: {json.dumps({'task_id': task_id, 'status': 'starting', 'total_items': len(request.zotero_keys), 'completed_items': 0, 'current_item': None})}\n\n"
            
            # Use asyncio queue for real-time progress updates
            progress_queue = asyncio.Queue()
            completed_count = 0
            
            async def progress_callback(key: str, status: str, result: Dict[str, Any]):
                nonlocal completed_count
                
                # Count completed items
                if status == "completed" or status == "failed":
                    completed_count += 1
                
                # Send progress update immediately
                progress_data = {
                    'task_id': task_id,
                    'status': 'processing' if completed_count < len(request.zotero_keys) else status,
                    'total_items': len(request.zotero_keys),
                    'completed_items': completed_count,
                    'current_item': result,
                }
                await progress_queue.put(progress_data)
            
            # Start the bulk add process in a background task
            async def run_bulk_add():
                try:
                    result = await RAGService.zotero_bulk_add_to_knowledge_base_with_streaming(
                        zotero_keys=request.zotero_keys,
                        knowledge_base_name=request.knowledge_base_name,
                        progress_callback=progress_callback
                    )
                    # Signal completion
                    await progress_queue.put({
                        'task_id': task_id,
                        'status': 'completed',
                        'total_items': len(request.zotero_keys),
                        'completed_items': len(result.get('details', {}).get('successful', [])),
                        'failed_items': len(result.get('details', {}).get('failed', [])),
                        'chunks_added': result.get('chunks_added', 0),
                        'current_item': None,
                        'result': result
                    })
                except Exception as e:
                    await progress_queue.put({
                        'task_id': task_id,
                        'status': 'error',
                        'total_items': len(request.zotero_keys),
                        'completed_items': 0,
                        'current_item': None,
                        'error': str(e)
                    })
                finally:
                    await progress_queue.put(None)  # Signal end
            
            # Start the bulk add task
            bulk_add_task = asyncio.create_task(run_bulk_add())
            
            # Stream progress updates as they come
            while True:
                try:
                    # Wait for progress update with timeout
                    progress_data = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    if progress_data is None:  # End signal
                        break
                    yield f"data: {json.dumps(progress_data)}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"
            
            # Wait for the bulk add task to complete
            await bulk_add_task
            
        except Exception as e:
            # Send error
            error_data = {
                'task_id': task_id,
                'status': 'error',
                'total_items': len(request.zotero_keys) if 'request' in locals() else 0,
                'completed_items': 0,
                'current_item': None,
                'error': str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/knowledge-bases", response_model=KnowledgeBasesListResponse)
async def list_knowledge_bases_endpoint():
    """
    Lists all available knowledge bases (ChromaDB collections).
    """
    return await RAGService.list_knowledge_bases()


@router.post("/knowledge-bases")
async def create_knowledge_base_endpoint(request: CreateKnowledgeBaseRequest):
    """
    Creates a new empty knowledge base (ChromaDB collection).
    """
    # Normalize embedding model name to LiteLLM format
    normalized_embed_model = normalize_embedding_model_name(
        request.embed_model, 
        provider=None  # Let the function infer the provider
    )
    
    return await RAGService.create_knowledge_base(
        name=request.name,
        description=request.description,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
        embed_model=normalized_embed_model,
        enable_reference_filtering=request.enable_reference_filtering,
    )


@router.get("/active-knowledge-bases")
async def get_active_knowledge_bases():
    """Get the list of active knowledge base IDs."""
    active_ids = await RAGService.get_active_knowledge_bases()
    return ActiveKnowledgeBasesResponse(
        active_knowledge_bases=active_ids,
        message=f"Current active knowledge bases: {active_ids}"
    )

@router.post("/active-knowledge-bases")
async def set_active_knowledge_bases(request: ActiveKnowledgeBasesRequest):
    """Set the list of active knowledge base IDs."""
    success = await RAGService.set_active_knowledge_bases(request.knowledge_base_ids)
    
    if success:
        active_ids = await RAGService.get_active_knowledge_bases()
        return ActiveKnowledgeBasesResponse(
            active_knowledge_bases=active_ids,
            message=f"Set {len(active_ids)} active knowledge bases"
        )
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to set active knowledge bases"
        )


@router.get("/knowledge-bases/{kb_name}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base_endpoint(kb_name: str):
    """
    Gets detailed information about a specific knowledge base.
    """
    return await RAGService.get_knowledge_base_info(name=kb_name)


@router.delete("/knowledge-bases/{kb_id}")
async def delete_knowledge_base_endpoint(kb_id: str):
    """
    Deletes a knowledge base and all its documents.
    """
    return await RAGService.delete_knowledge_base(kb_id=kb_id)


@router.post("/documents/pdf")
async def upload_pdf_to_knowledge_base(
    file: UploadFile = File(...),
    knowledge_base_name: str = Form(...)
):
    """
    Upload a PDF file to a specific knowledge base.
    Returns the content hash (SHA256) as key for fulltext retrieval.
    """
    try:
        # Read PDF content
        pdf_bytes = await file.read()
        
        # Process the PDF and add to knowledge base
        result = await RAGService.process_uploaded_pdf(
            pdf_bytes=pdf_bytes,
            filename=file.filename,
            knowledge_base_name=knowledge_base_name
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to upload PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload PDF: {str(e)}")

@router.post("/documents/extract-text")
async def extract_text_from_pdf(file: UploadFile = File(...)):
    """
    Extract text from a PDF file without adding it to any knowledge base.
    Returns just the extracted text content.
    """
    # Read file content
    pdf_bytes = await file.read()
    
    # Get the filename for cleaner display
    filename = file.filename or "uploaded_document.pdf"
    
    # Extract text using config-based parser
    from .service import RAGService
    from .parser import extract_full_text_from_bytes_with_config
    
    try:
        # Extract full text using config-based parser selection
        full_text = await extract_full_text_from_bytes_with_config(pdf_bytes, filename)
        
        if not full_text or not full_text.strip():
            # Return 400 Bad Request for extraction failure
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from the PDF. This could be due to: "
                       "1) The PDF contains only images or scanned content, "
                       "2) The PDF is corrupted or password-protected, "
                       "3) The PDF parser configuration is incompatible with this file type. "
                       "Try switching to a different PDF parser in settings or ensure the PDF contains extractable text."
            )
        
        return {
            "success": True,
            "text": full_text.strip(),
            "title": filename,
            "filename": filename
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging
        logger.error(f"PDF extraction failed for {filename}: {str(e)}")
        
        # Provide more specific error messages based on the exception type
        error_msg = str(e)
        if "MissingDependencyError" in error_msg or "Pandoc" in error_msg:
            detail = (f"Missing system dependency: {str(e)}. "
                     "Please install Pandoc version 2 or above on your system and ensure it's available in $PATH. "
                     "This is required for processing DOCX and other document formats.")
        elif "Parser Server" in error_msg.lower() or "cannot connect" in error_msg.lower():
            detail = (f"Remote PDF parser failed: {str(e)}. "
                     "The Parser Server server may be unavailable. "
                     "Try switching to Kreuzberg parser in settings for more reliable processing.")
        elif "pdf" in error_msg.lower() and "corrupt" in error_msg.lower():
            detail = f"PDF file appears to be corrupted: {str(e)}"
        elif "timeout" in error_msg.lower():
            detail = f"PDF processing timed out: {str(e)}. Try with a smaller file or different parser."
        else:
            detail = f"Failed to extract text from PDF: {str(e)}"
        
        raise HTTPException(status_code=500, detail=detail)

@router.get("/knowledge-bases/{kb_name}/documents")
async def get_knowledge_base_documents_endpoint(kb_name: str):
    """
    Get document titles from a knowledge base for @ mentions.
    """
    return await RAGService.get_knowledge_base_documents(knowledge_base_name=kb_name)

@router.get("/uploaded-files/{key}")
async def get_uploaded_file(key: str):
    """Get a document from the uploaded_files collection by key (SHA256 hash)."""
    try:
        from .service import RAGService
        
        document = await RAGService.get_uploaded_file_by_key(key)
        
        if not document:
            raise HTTPException(status_code=404, detail=f"Document with key {key} not found")
        
        return {
            "success": True,
            "document": document
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get uploaded file {key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")

@router.post("/documents/upload")
async def upload_document_unified(
    file: UploadFile = File(...),
    knowledge_base_name: str = Form(default="uploaded-documents")
):
    """
    Unified document upload endpoint.
    Uploads PDFs to a specified knowledge base (defaults to 'uploaded-documents' reserved KB)
    and stores full text in uploaded_files collection for @ mentions.
    Returns the content hash (SHA256) as key for mentioning.
    """
    try:
        # Validate file size (100MB limit)
        if file.size and file.size > 100 * 1024 * 1024:
            return {
                "success": False,
                "error": "File too large. Maximum size is 100MB",
                "detail": "File size exceeded limit"
            }
        
        # Read PDF content
        pdf_bytes = await file.read()
        filename = file.filename or "untitled"
        
        # Ensure the reserved knowledge base exists
        db_manager = await get_database_manager()
        kb_id = await db_manager.resolve_knowledge_base_id(knowledge_base_name)
        
        if not kb_id:
            # Create the reserved knowledge base if it doesn't exist
            logger.info(f"Creating reserved knowledge base: {knowledge_base_name}")
            
            # Get default embedding model from user config and normalize it
            user_config = await ManagerSingleton.get_user_config()
            default_embed_model = normalize_embedding_model_name(
                user_config.embed_model,
                provider=None  # Let the function infer the provider
            )
            
            kb_id = await db_manager.create_knowledge_base(
                display_name=knowledge_base_name,
                description=f"Default knowledge base for uploaded documents",
                chunk_size=1000,
                chunk_overlap=200,
                embed_model=default_embed_model
            )
            
            # Create ChromaDB collection for the new KB
            from .db import RAGDB
            # Use default embedding model from user config for new KBs
            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)
            await rag_db.get_or_create_collection(name=kb_id)
        
        # Process the PDF using the existing service method
        result = await RAGService.process_uploaded_pdf(
            pdf_bytes=pdf_bytes,
            filename=filename,
            knowledge_base_name=knowledge_base_name
        )
        
        # Standardize response format by merging the service result
        response_data = {
            "success": True,
            "message": f"Document '{filename}' uploaded successfully",
            "filename": filename,
            "knowledge_base": knowledge_base_name,
            "url": f"/api/documents/{result.get('fulltext_key') or result.get('content_hash')}",
        }
        response_data.update(result) # Merge the result from the service
        
        return response_data
        
    except HTTPException as e:
        logger.error(f"HTTP error during upload of {file.filename}: {e.detail}")
        return {
            "success": False,
            "error": e.detail,
            "detail": f"Upload failed: {e.detail}"
        }
    except Exception as e:
        logger.error(f"Failed to upload document {file.filename}: {e}")
        
        # Check for specific error types
        error_msg = str(e)
        if "MissingDependencyError" in error_msg or "Pandoc" in error_msg:
            return {
                "success": False,
                "error": "Missing system dependency: Pandoc version 2 or above is required. Please install it on your system and ensure it's available in $PATH.",
                "detail": f"System dependency error: {str(e)}"
            }
        elif "No text could be extracted" in error_msg or "No text extracted" in error_msg:
            return {
                "success": False,
                "error": "No text could be extracted from this document. This could be due to the document being scanned images, corrupted, or incompatible with the current parser.",
                "detail": f"Text extraction failed: {str(e)}"
            }
        else:
            return {
                "success": False,
                "error": f"Failed to upload document: {str(e)}",
                "detail": str(e)
            }

@router.get("/documents/{key}")
async def get_document_by_key(key: str):
    """
    Get a document's full content by its key (SHA256 hash).
    This enables @ mention functionality and document retrieval.
    """
    try:
        document = await RAGService.get_uploaded_file_by_key(key)
        
        if not document:
            raise HTTPException(
                status_code=404, 
                detail=f"Document with key {key} not found"
            )
        
        return {
            "success": True,
            "document": {
                "key": document["key"],
                "title": document["metadata"].get("title", "Unknown Document"),
                "filename": document["metadata"].get("filename", "unknown.pdf"),
                "content": document["content"],
                "knowledge_base_id": document["metadata"].get("knowledge_base_id"),
                "file_type": document["metadata"].get("file_type", "pdf"),
                "source": document["metadata"].get("source")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")

@router.post("/cleanup-uploaded-files/{kb_id}")
async def cleanup_uploaded_files_endpoint(kb_id: str):
    """Clean up uploaded_files collection for a specific knowledge base."""
    try:
        result = await RAGService.cleanup_uploaded_files_for_kb(kb_id)
        return result
    except Exception as e:
        logger.error(f"Failed to cleanup uploaded files for KB {kb_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup uploaded files: {str(e)}")

@router.delete("/uploaded-files")
async def clear_all_uploaded_files():
    """Clear all uploaded files (for testing/cleanup)."""
    try:
        result = await RAGService.clear_uploaded_files_collection()
        return result
    except Exception as e:
        logger.error(f"Failed to clear uploaded files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear uploaded files: {str(e)}")