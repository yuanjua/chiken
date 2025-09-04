"""
Zotero Service Layer

This module contains the business logic for Zotero operations,
separated from the API layer for better maintainability.
"""

import os
import random
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import aiohttp
from fastapi import HTTPException
from loguru import logger
from pyzotero import zotero


class ZoteroService:
    """Service class for Zotero operations."""

    LOCAL_BASE = "http://localhost:23119/api"  # Zotero local server proxy base

    def __init__(
        self,
        library_id: str = "0",
        library_type: str = "user",
        api_key: Optional[str] = None,
        is_local: bool = True,
    ):
        """Initialize Zotero client."""
        self.zot = None
        self.is_local = is_local
        self.library_id = str(library_id)
        self.library_type = library_type
        self.api_key = api_key
        try:
            # Try different initialization approaches for different pyzotero versions
            try:
                self.zot = zotero.Zotero(library_id=self.library_id, library_type=self.library_type, api_key=self.api_key, local=is_local)
            except TypeError:
                # Older pyzotero versions expect positional args
                self.zot = zotero.Zotero(self.library_id, self.library_type, self.api_key)
        except Exception as e:
            logger.error(f"Error initializing Zotero client: {e}")
            self.zot = None

    async def _local_get(self, path: str, params: dict = None) -> Any:
        """
        Generic helper to GET from the Zotero local HTTP server.
        
        Args:
            path: path with leading slash, e.g. "/users/123/collections"
            params: query parameters
            
        Returns:
            parsed json on 200, raises HTTPException otherwise.
        """
        url = f"{self.LOCAL_BASE}{path}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        logger.error("Local Zotero server returned %s for %s: %s", resp.status, url, text)
                        raise HTTPException(status_code=502, detail=f"Local Zotero returned {resp.status} for {url}: {text}")
                    try:
                        return await resp.json()
                    except aiohttp.ContentTypeError:
                        # Some local endpoints may return non-json; return raw text
                        return text
        except aiohttp.ClientConnectorError as e:
            logger.error("Cannot connect to Zotero local server at %s: %s", url, e)
            raise HTTPException(status_code=502, detail="Cannot connect to Zotero local server. Is Zotero Desktop running?")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Unexpected error querying local Zotero server %s: %s", url, e)
            raise HTTPException(status_code=502, detail=f"Error querying local Zotero server: {e}")


    async def is_locally_connected(self) -> Dict[str, Any]:
        """Check if Zotero is locally connected."""
        if not self.is_local:
            return {"connected": False, "error": "is_local flag is False"}
        # Try a cheap local call: /users/<id>/collections
        try:
            await self._local_get(f"/users/{self.library_id}/collections")
            return {"connected": True, "error": None}
        except HTTPException as e:
            return {"connected": False, "error": str(e.detail)}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def list_collections(self) -> List[Dict[str, Any]]:
        """List all Zotero collections (includes user + groups via local pyzotero)."""
        if not self.zot:
            raise HTTPException(status_code=502, detail="Zotero client not initialized")
            
        collections: List[Dict[str, Any]] = []

        try:
            # 1) Get user collections
            user_cols = self.zot.collections()
            # Annotate with library context
            for c in user_cols:
                c.setdefault("library", {})
                c["library"].update({"type": "user", "id": str(self.library_id), "name": "My Library"})
                collections.append(c)
            logger.info(f"Added {len(user_cols)} user collections")

            # 2) Get groups and their collections via local pyzotero
            try:
                groups = self.zot.groups()
                logger.info(f"Found {len(groups)} groups")
                
                for group in groups:
                    gid = str(group.get("data", {}).get("id", group.get("id", "")))
                    gname = group.get("data", {}).get("name", f"Group {gid}")
                    
                    try:
                        # Create group client for local access
                        group_client = zotero.Zotero(library_id=gid, library_type="group", local=self.is_local)
                        gcols = group_client.collections()
                        
                        for c in gcols:
                            c.setdefault("library", {})
                            c["library"].update({"type": "group", "id": gid, "name": gname})
                            collections.append(c)
                        logger.info(f"Added {len(gcols)} collections from group '{gname}'")
                    except Exception as e:
                        logger.warning(f"Failed to fetch collections for group {gname}: {e}")
                        
            except Exception as e:
                logger.warning(f"Failed to get groups: {e}")

            return collections
            
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error listing collections: {e}")

    async def get_library_as_json(self) -> list[dict[str, Any]]:
        """Get the entire Zotero library as JSON."""
        try:
            return self.zot.library()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error getting library as JSON: {e}")

    async def get_item(self, item_key: str) -> Dict[str, Any]:
        """Get a specific Zotero item by key (searches both user and group libraries)."""
        if not self.zot:
            raise HTTPException(status_code=502, detail="Zotero client not initialized")
            
        logger.debug(f"Searching for item {item_key}")
        
        try:
            # Try user library first
            try:
                logger.debug(f"Trying user library for item {item_key}")
                data = self.zot.item(item_key)
                if data:
                    logger.debug(f"Found item {item_key} in user library")
                    return data
            except Exception as e:
                logger.debug(f"Item {item_key} not in user library: {e}")
            
            # Try group libraries
            try:
                groups = self.zot.groups()
                logger.debug(f"Found {len(groups)} groups to search")
                
                for group in groups:
                    gid = str(group.get("data", {}).get("id", group.get("id", "")))
                    gname = group.get("data", {}).get("name", f"Group {gid}")
                    logger.debug(f"Searching group {gname} (ID: {gid}) for item {item_key}")
                    
                    try:
                        # Create group-specific client (like in the test script)
                        group_client = zotero.Zotero(library_id=gid, library_type="group", local=self.is_local)
                        data = group_client.item(item_key)
                        if data:
                            logger.info(f"Found item {item_key} in group {gname}")
                            return data
                        else:
                            logger.debug(f"Item {item_key} not found in group {gname}")
                    except Exception as e:
                        logger.debug(f"Error searching group {gname} for item {item_key}: {e}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Failed to search groups for item {item_key}: {e}")
            
            # Item not found in any library
            logger.error(f"Item {item_key} not found in user or group libraries")
            raise HTTPException(status_code=404, detail=f"Item {item_key} not found")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Exception in get_item for key {item_key}: {e}")
            raise HTTPException(status_code=502, detail=f"Error getting item: {e}")

    async def _get_children_from_any_library(self, item_key: str) -> List[Dict[str, Any]]:
        """Get children (attachments) of an item from any library (user or group)."""
        if not self.zot:
            return []
            
        # Try user library first
        try:
            children = self.zot.children(item_key)
            if children:
                logger.debug(f"Found {len(children)} children for item {item_key} in user library")
                return children
        except Exception as e:
            logger.debug(f"No children for item {item_key} in user library: {e}")
            
        # Try group libraries
        try:
            groups = self.zot.groups()
            for group in groups:
                gid = str(group.get("data", {}).get("id", group.get("id", "")))
                gname = group.get("data", {}).get("name", f"Group {gid}")
                
                try:
                    group_client = zotero.Zotero(library_id=gid, library_type="group", local=self.is_local)
                    children = group_client.children(item_key)
                    if children:
                        logger.debug(f"Found {len(children)} children for item {item_key} in group {gname}")
                        return children
                except Exception as e:
                    logger.debug(f"No children for item {item_key} in group {gname}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to search groups for children of item {item_key}: {e}")
            
        logger.debug(f"No children found for item {item_key} in any library")
        return []

    async def get_pdf_path(self, item_key: str) -> str:
        """Get the path of a PDF attachment for a given item key."""

        def parse_file_url(file_url):  # Get the URL and remove the 'file://' prefix
            if file_url.startswith("file:///"):
                local_path = file_url[len("file:///") :]
            elif file_url.startswith("file://"):
                local_path = file_url[len("file://") :]
            else:
                local_path = file_url
            if os.name != "nt":
                local_path = "/" + local_path  # Add a slash to the path if it's not a Windows path
            local_path = unquote(local_path)
            local_path = os.path.normpath(local_path)
            return local_path

        try:
            item = await self.get_item(item_key)
            if "links" in item and "enclosure" in item["links"]:
                file_url = item["links"]["enclosure"]["href"]
                return parse_file_url(file_url)
            else:
                logger.error(f"No enclosure link found for key {item_key}")
                raise HTTPException(status_code=502, detail="Error getting PDF path: No enclosure link found")
        except Exception as e:
            logger.error(f"Exception in get_pdf_path for key {item_key}: {e}")
            raise HTTPException(status_code=502, detail=f"Error getting PDF path: {e}")

    async def get_pdf_bytes(self, item_key: str) -> bytes:
        """Get the PDF bytes for a given item key (searches both user and group libraries)."""
        
        # Try user library first
        try:
            pdf_bytes = self.zot.file(item_key)
            if pdf_bytes:
                logger.debug(f"Retrieved PDF bytes for {item_key} from user library")
                return pdf_bytes
        except Exception as e:
            logger.debug(f"Failed to get PDF from user library for {item_key}: {e}")

        # Try group libraries
        try:
            groups = self.zot.groups()
            for group in groups:
                gid = str(group.get("data", {}).get("id", group.get("id", "")))
                gname = group.get("data", {}).get("name", f"Group {gid}")
                
                try:
                    group_client = zotero.Zotero(library_id=gid, library_type="group", local=self.is_local)
                    pdf_bytes = group_client.file(item_key)
                    if pdf_bytes:
                        logger.debug(f"Retrieved PDF bytes for {item_key} from group {gname}")
                        return pdf_bytes
                except Exception as e:
                    logger.debug(f"Failed to get PDF from group {gname} for {item_key}: {e}")
                    continue
        except Exception as e:
            logger.warning(f"Failed to search groups for PDF of {item_key}: {e}")

        # If local file approach fails, try to get the path and read directly
        if self.is_local:
            try:
                path = await self.get_pdf_path(item_key)
                with open(path, "rb") as f:
                    logger.info(f"Successfully read PDF from local path for {item_key}")
                    return f.read()
            except Exception as e:
                logger.error(f"Exception in get_pdf_path for key {item_key}: {e}")

        raise HTTPException(
            status_code=502,
            detail=f"Error getting PDF bytes for {item_key}: not found in any library",
        )

    async def get_zotero_collections_json(self, limit: int = None) -> Dict[str, Any]:
        """
        Get Zotero collections as flat list for frontend tree display.
        
        This method returns only actual collections (not library container nodes) to avoid
        item count duplication. The frontend should create library groupings for UI display
        but should only count actual collections when calculating totals.

        Args:
            limit: Maximum number of collections to retrieve

        Returns:
            Dictionary with flat collections array suitable for frontend tree building
        """
        if not (self.zot or self.is_local):
            return {"error": "Zotero client not initialized", "collections": []}

        try:
            if self.is_local:
                collections_data = await self.list_collections()
            else:
                collections_data = self.zot.collections(limit=limit)

            if not collections_data:
                return {
                    "collections": [],
                    "total_count": 0,
                    "message": "No collections found in your Zotero library",
                }

            formatted_collections = []
            for coll in collections_data:
                # Normalize collection data (handle both local server and pyzotero formats)
                key = coll.get("key") or coll.get("data", {}).get("key")
                data = coll.get("data", {}) if "data" in coll else coll
                name = data.get("name") or data.get("title") or data.get("collectionName") or "Unnamed Collection"
                parent = data.get("parentCollection") or data.get("parentCollectionID") or None
                meta_count = coll.get("meta", {}).get("numItems", 0)
                lib_meta = coll.get("library", {})
                
                formatted_coll = {
                    "key": key,
                    "data": {
                        "name": name,
                        "parentCollection": parent,
                    },
                    "meta": {
                        "numItems": meta_count,
                    },
                    "version": coll.get("version", 0),
                    "library": lib_meta,
                }
                formatted_collections.append(formatted_coll)

            return {
                "collections": formatted_collections,
                "total_count": len(formatted_collections),
                "timestamp": datetime.now().isoformat(),
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error getting collections JSON: {e}")

    async def get_zotero_collections_keys(self) -> List[str]:
        """Get the keys of all Zotero collections."""
        try:
            cols = await self.list_collections() if self.is_local else self.zot.collections()
            return [c.get("key") or c.get("data", {}).get("key") for c in cols]
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error getting collections keys: {e}")

    async def get_collection_items(self, collection_keys: str | List[str]) -> Dict[str, Any]:
        """Get items in specific Zotero collections (searches both user and group libraries)."""
        if not self.zot:
            raise HTTPException(status_code=502, detail="Zotero client not initialized")
            
        items = []
        try:
            if isinstance(collection_keys, str):
                collection_keys = [collection_keys]
            
            # First, get all collections to know which library each collection belongs to
            all_collections = await self.list_collections()
            collection_library_map = {
                col["key"]: col["library"] for col in all_collections
            }
                
            for collection_key in collection_keys:
                # Check which library this collection belongs to
                collection_library = collection_library_map.get(collection_key)
                
                if not collection_library:
                    logger.warning(f"Collection {collection_key} not found in any library")
                    continue
                
                library_type = collection_library.get("type")
                library_id = collection_library.get("id")
                
                try:
                    if library_type == "user":
                        # Get items from user library
                        user_items = self.zot.collection_items(collection_key)
                        items.extend(user_items)
                    elif library_type == "group":
                        # Get items from specific group library
                        group_client = zotero.Zotero(library_id=library_id, library_type="group", local=self.is_local)
                        group_items = group_client.collection_items(collection_key)
                        items.extend(group_items)
                    else:
                        logger.warning(f"Unknown library type '{library_type}' for collection {collection_key}")
                        
                except Exception as e:
                    logger.error(f"Failed to get items for collection {collection_key} in {library_type} library {library_id}: {e}")
                    
            return {
                "items": items,
                "collection_keys": collection_keys,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get collection items: {str(e)}")

    async def extract_items_meta(self, keys: str | list[str]) -> list[dict]:
        """Extract metadata from a list of Zotero items, with error handling for missing/invalid items."""
        if isinstance(keys, str):
            keys = [keys]
        items = []
        for key in keys:
            try:
                item = await self.get_item(key)
                items.append(item)
            except Exception as e:
                logger.error(f"Error extracting metadata for key '{key}': {e}")
                items.append({"key": key, "data": {}, "error": str(e)})
        return [
            {
                "key": item.get("key", ""),
                "title": item.get("data", {}).get("title", "Untitled"),
                "itemType": item.get("data", {}).get("itemType", "Unknown"),
                "url": item.get("data", {}).get("url", ""),
                "date": item.get("data", {}).get("date", ""),
                "tags": item.get("data", {}).get("tags", []),
                "collections": item.get("data", {}).get("collections", []),
                "error": item.get("error", None),
            }
            for item in items
        ]

    async def get_pdf_attachment_keys(self, keys: str | list[str]) -> list[str]:
        """
        Get PDF attachment keys from parent item keys.
        If a key is already a PDF attachment, return it as-is.
        If a key is a parent item, find its PDF attachment child.
        """
        if isinstance(keys, str):
            keys = [keys]

        attachment_keys = []
        for key in keys:
            try:
                # Get the item's metadata to check its type
                item_details = await self.get_item(key)
                item_type = item_details.get("data", {}).get("itemType")

                if item_type == "attachment":
                    # The provided key is already an attachment
                    if (
                        item_details.get("data", {}).get("contentType") == "application/pdf"
                        and item_details.get("data", {}).get("linkMode") != "linked_file"
                    ):
                        attachment_keys.append(key)
                    else:
                        logger.warning(
                            f"Item '{key}' is an attachment, but either not a PDF or is a linked file. Skipping."
                        )
                else:
                    # The key is for a parent item. Find its PDF child attachment.
                    logger.info(f"Key '{key}' is a parent item. Searching for child PDF attachment...")
                    children = await self._get_children_from_any_library(key)
                    found = False
                    for child in children:
                        if (
                            child.get("data", {}).get("itemType") == "attachment"
                            and child.get("data", {}).get("contentType") == "application/pdf"
                        ):
                            # Skip linked files (local paths) as Zotero API cannot return bytes
                            if child.get("data", {}).get("linkMode") == "linked_file":
                                logger.warning(
                                    "Skipping linked-file attachment %s because Zotero API cannot provide file bytes.",
                                    child["key"],
                                )
                                continue
                            attachment_keys.append(child["key"])
                            logger.info(f"Found PDF attachment with key '{child['key']}' for parent '{key}'.")
                            found = True
                            break

                    if not found:
                        logger.warning(f"No PDF attachment found for item key '{key}'.")

            except Exception as e:
                logger.error(f"Error processing key '{key}': {e}")

        return attachment_keys

    async def get_pdf_bytes_by_keys(self, keys: str | list[str]) -> list[bytes]:
        """Get PDF file as bytes for given keys."""
        if isinstance(keys, str):
            keys = [keys]

        # First get the actual PDF attachment keys
        attachment_keys = await self.get_pdf_attachment_keys(keys)

        # Then get the PDF bytes for those attachment keys
        pdf_bytes_list = []
        for key in attachment_keys:
            try:
                item_details = await self.get_item(key)
                if item_details.get("data", {}).get("linkMode") == "linked_file":
                    file_path = item_details.get("data", {}).get("path")
                    if file_path and os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            pdf_bytes = f.read()
                        pdf_bytes_list.append(pdf_bytes)
                    else:
                        logger.error(f"File not found for key '{key}': {file_path}")
                        pdf_bytes_list.append(None)
                else:
                    pdf_bytes = await self.get_pdf_bytes(key)
                    pdf_bytes_list.append(pdf_bytes)
            except Exception as e:
                logger.error(f"Error getting PDF bytes for key '{key}': {e}")
                pdf_bytes_list.append(None)

        return pdf_bytes_list

    async def get_random_pdf_key(self) -> str | None:
        """
        For testing. Retrieves the key of a random PDF attachment from the Zotero library.
        """
        if not self.zot:
            raise HTTPException(status_code=502, detail="Zotero client not initialized")

        try:
            logger.info("Searching for PDF attachments in the library...")

            # Search for items that are attachments and have a PDF content type.
            # We limit to 100 to get a good random sample without fetching the whole library.
            pdf_attachments = self.zot.items(itemType="attachment", contentType="application/pdf", limit=100)

            if not pdf_attachments:
                logger.warning("No PDF attachments found in the Zotero library.")
                return None

            # Select a random item from the list
            random_pdf = random.choice(pdf_attachments)

            pdf_key = random_pdf.get("key")
            logger.info(f"Selected random PDF for testing with key: {pdf_key}")

            return pdf_key

        except Exception as e:
            logger.error(f"Failed to get a random PDF key: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get a random PDF key: {str(e)}")


# Global service instance
zotero_service = ZoteroService()
