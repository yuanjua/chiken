from typing import Any

from loguru import logger

from ..database import get_database_manager
from ..manager_singleton import ManagerSingleton
from ..zotero.service import zotero_service


async def get_active_knowledge_bases() -> list[dict[str, Any]]:
    """Helper function to get active knowledge bases directly from the database
    (Force reload from database since we are in a subprocess)

    Returns:
        List of knowledge base dictionaries with standardized fields:
        - id: primary key
        - display_name: user-facing name
        - description, chunk_size, chunk_overlap, embed_model: other fields
    """
    try:
        db_manager = await get_database_manager()
        all_kbs = await db_manager.list_knowledge_bases()

        user_config = await ManagerSingleton.reload_user_config()
        active_ids = set(user_config.active_knowledge_base_ids or [])

        active_kbs = [kb for kb in all_kbs if kb["id"] in active_ids]
        # Ensure all knowledge bases have display_name (fallback to id if missing)
        for kb in active_kbs:
            if not kb.get("display_name"):
                kb["display_name"] = kb.get("id", "Unknown")
        return active_kbs
    except Exception as e:
        logger.error(f"Error getting active knowledge bases from DB: {e}")
        return []


async def get_abstract_by_keys(keys: list[str]) -> dict[str, str]:
    """Return mapping of zotero item key -> abstractNote (may be empty string)."""
    result: dict[str, str] = {}
    for key in keys or []:
        try:
            item = await zotero_service.get_item(key)
            abs_note = item.get("data", {}).get("abstractNote", "") or ""
            result[key] = abs_note
        except Exception:
            result[key] = ""
    return result
