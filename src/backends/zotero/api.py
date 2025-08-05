"""
Zotero API

This module provides API endpoints for Zotero integration,
including collections, items, and PDF processing.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Query, HTTPException

from .service import zotero_service

# Router setup  
router = APIRouter(prefix="/zotero", tags=["Zotero"])


@router.get("/status")
async def get_zotero_status():
    """Check Zotero connection status."""
    try:
        return await zotero_service.is_locally_connected()
    except Exception as e:
        return {"connected": False, "error": str(e)}

@router.get("/collections")
async def get_zotero_collections(
    limit: int = Query(None, description="Maximum number of collections to retrieve")
):
    """Get Zotero collections as JSON for tree display."""
    try:
        return await zotero_service.get_zotero_collections_json(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Zotero collections: {str(e)}")

@router.get("/collections/{collection_id}/items")
async def get_zotero_collection_items(collection_id: str):
    """Get items in a specific Zotero collection."""
    return await zotero_service.get_collection_items(collection_id)

@router.post("/collections/items")
async def get_zotero_collection_items_batch(collection_ids: List[str]):
    """Get items in multiple Zotero collections."""
    return await zotero_service.get_collection_items(collection_ids)

@router.get("/pdf/random")
async def get_random_pdf_key():
    """Get a random PDF key for testing purposes."""
    key = await zotero_service.get_random_pdf_key()
    return {'key': key}