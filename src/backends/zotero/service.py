"""
Zotero Service Layer

This module contains the business logic for Zotero operations,
separated from the API layer for better maintainability.
"""

import os
import random
from datetime import datetime
from typing import Any
from urllib.parse import unquote  # Import unquote

import aiohttp
from fastapi import HTTPException
from loguru import logger
from pyzotero import zotero

# logger is imported from loguru


class ZoteroService:
    """Service class for Zotero operations."""

    def __init__(
        self,
        library_id: str = "0",
        library_type: str = "user",
        api_key: str = None,
        is_local: bool = True,
    ):
        """Initialize Zotero client."""
        self.zot = None
        self.is_local = is_local
        self.library_id = library_id
        self.library_type = library_type
        self.api_key = api_key
        try:
            self.zot = zotero.Zotero(library_id=library_id, library_type=library_type, api_key=api_key, local=is_local)
        except Exception as e:
            logger.error(f"Error initializing Zotero client: {e}")

    async def is_locally_connected(self) -> dict[str, Any]:
        """Check if Zotero is locally connected."""
        return {
            "connected": bool(self.zot),
            "error": None if self.zot else "Zotero client not initialized",
        }

    async def list_collections(self) -> list[dict[str, Any]]:
        """List all Zotero collections."""
        try:
            return self.zot.collections()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error listing collections: {e}")

    async def get_library_as_json(self) -> list[dict[str, Any]]:
        """Get the entire Zotero library as JSON."""
        try:
            return self.zot.library()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error getting library as JSON: {e}")

    async def get_item(self, item_key: str) -> dict[str, Any]:
        """Get a specific Zotero item by key."""
        try:
            if self.is_local:
                async with aiohttp.ClientSession() as session:
                    url = f"http://localhost:23119/api/users/{self.library_id}/items/{item_key}"
                    async with session.get(url) as response:
                        if response.status != 200:
                            text = await response.text()
                            logger.error(f"Zotero API returned status {response.status} for key {item_key}: {text}")
                            raise HTTPException(
                                status_code=502,
                                detail=f"Error getting item: Zotero API returned {response.status}",
                            )

                        try:
                            data = await response.json()
                        except aiohttp.ContentTypeError as e:
                            text = await response.text()
                            logger.error(f"Failed to decode JSON for key {item_key}: {e}, raw response: {text}")
                            raise HTTPException(status_code=502, detail="Error getting item: Invalid JSON response")

                        if not data:
                            logger.error(f"Empty response for key {item_key}")
                            raise HTTPException(status_code=502, detail="Error getting item: Empty response")

                        return data
            else:
                data = self.zot.item(item_key)
                if not data:
                    logger.error(f"Empty response from pyzotero for key {item_key}")
                    raise HTTPException(status_code=502, detail="Error getting item: Empty response from pyzotero")
                return data
        except Exception as e:
            logger.error(f"Exception in get_item for key {item_key}: {e}")
            raise HTTPException(status_code=502, detail=f"Error getting item: {e}")

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
        """Get the PDF bytes for a given item key."""

        try:
            return self.zot.file(item_key)
        except Exception as e:
            logger.error(f"Exception in zot.file for key {item_key}: {e}, trying to get local file path...")

        # If the item is a local file, get the path and read the file
        if self.is_local:
            try:
                path = await self.get_pdf_path(item_key)
                with open(path, "rb") as f:
                    logger.info("Successfully read from path")
                    return f.read()
            except Exception as e:
                logger.error(f"Exception in get_pdf_path for key {item_key}: {e}")
                raise HTTPException(status_code=502, detail=f"Error getting PDF bytes: {e}")

        raise HTTPException(
            status_code=502,
            detail="Error getting PDF bytes: both zot.item() and get_pdf_path() failed",
        )

    async def get_zotero_collections_json(self, limit: int = None) -> dict[str, Any]:
        """
        Get Zotero collections as structured JSON data for frontend tree display.

        Args:
            limit: Maximum number of collections to retrieve

        Returns:
            Dictionary with collections data suitable for tree structure
        """
        if not self.zot:
            return {"error": "Zotero client not initialized", "collections": []}

        try:
            collections_data = self.zot.collections(limit=limit)

            if not collections_data:
                return {
                    "collections": [],
                    "total_count": 0,
                    "message": "No collections found in your Zotero library",
                }

            formatted_collections = []
            for coll in collections_data:
                formatted_coll = {
                    "key": coll["key"],
                    "data": {
                        "name": coll["data"].get("name", "Unnamed Collection"),
                        "parentCollection": coll["data"].get("parentCollection"),
                    },
                    "meta": {
                        "numItems": coll.get("meta", {}).get("numItems", 0),
                    },
                    "version": coll.get("version", 0),
                    "library": coll.get("library", {}),
                }
                formatted_collections.append(formatted_coll)

            return {
                "collections": formatted_collections,
                "total_count": len(formatted_collections),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error getting collections JSON: {e}")

    async def get_zotero_collections_keys(self) -> list[str]:
        """Get the keys of all Zotero collections."""
        try:
            return [coll["key"] for coll in self.zot.collections()]
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error getting collections keys: {e}")

    async def get_collection_items(self, collection_keys: str | list[str]) -> dict[str, Any]:
        """Get items in a specific Zotero collection."""
        items = []
        try:
            if isinstance(collection_keys, str):
                collection_keys = [collection_keys]
            for collection_key in collection_keys:
                items.extend(self.zot.collection_items(collection_key))
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
                    children = self.zot.children(key)
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
