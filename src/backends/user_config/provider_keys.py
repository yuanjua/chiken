"""
Provider API Keys

Simple table for storing provider-specific API keys.
"""

import aiosqlite
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class ProviderApiKeyRequest(BaseModel):
    """Request model for updating provider API key."""
    provider: str = Field(description="Provider name (e.g., 'openai', 'anthropic', 'ollama')")
    api_key: Optional[str] = Field(description="API key for the provider (null to clear)", default=None)
    base_url: Optional[str] = Field(description="Base URL for the provider (null to clear)", default=None)
    use_custom_endpoint: Optional[bool] = Field(description="Whether to use custom endpoint for this provider", default=False)


class ProviderApiKeyResponse(BaseModel):
    """Response model for provider API key."""
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    use_custom_endpoint: Optional[bool] = False
    updated_at: Optional[str] = None


# Database functions
async def get_db_path() -> str:
    """Get database path."""
    from ..manager_singleton import get_database_path
    return get_database_path()


async def get_all_provider_api_keys() -> List[ProviderApiKeyResponse]:
    """Get all provider API keys."""
    db_path = await get_db_path()
    
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT provider, api_key, base_url, use_custom_endpoint, updated_at FROM provider_api_keys")
        rows = await cursor.fetchall()
        
        return [
            ProviderApiKeyResponse(
                provider=row[0],
                api_key=row[1],
                base_url=row[2],
                use_custom_endpoint=row[3] if row[3] is not None else False,
                updated_at=row[4]
            )
            for row in rows
        ]


async def get_provider_api_key(provider: str) -> Optional[str]:
    """Get API key for a specific provider."""
    db_path = await get_db_path()
    
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT api_key FROM provider_api_keys WHERE provider = ?", 
            (provider,)
        )
        row = await cursor.fetchone()
        
        return row[0] if row else None


async def get_provider_base_url(provider: str) -> Optional[str]:
    """Get base URL for a specific provider."""
    db_path = await get_db_path()
    
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT base_url FROM provider_api_keys WHERE provider = ?", 
            (provider,)
        )
        row = await cursor.fetchone()
        
        return row[0] if row else None


async def get_provider_config(provider: str) -> Optional[dict]:
    """Get both API key and base URL for a provider."""
    db_path = await get_db_path()
    
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT api_key, base_url, use_custom_endpoint FROM provider_api_keys WHERE provider = ?", 
            (provider,)
        )
        row = await cursor.fetchone()
        
        if row:
            return {
                "api_key": row[0],
                "base_url": row[1],
                "use_custom_endpoint": row[2] if row[2] is not None else False
            }
        return None


async def set_provider_api_key(provider: str, api_key: str, base_url: Optional[str] = None, use_custom_endpoint: Optional[bool] = None) -> None:
    """Set or update API key and optionally base URL for a provider."""
    db_path = await get_db_path()
    
    async with aiosqlite.connect(db_path) as db:
        current_time = datetime.now().isoformat()
        
        # Check if provider already exists
        cursor = await db.execute(
            "SELECT provider FROM provider_api_keys WHERE provider = ?", 
            (provider,)
        )
        existing = await cursor.fetchone()
        
        if existing:
            # Update existing - build query dynamically based on what's provided
            update_fields = ["api_key = ?", "updated_at = ?"]
            update_values = [api_key, current_time]
            
            if base_url is not None:
                update_fields.append("base_url = ?")
                update_values.append(base_url)
                
            if use_custom_endpoint is not None:
                update_fields.append("use_custom_endpoint = ?")
                update_values.append(use_custom_endpoint)
            
            update_values.append(provider)  # For WHERE clause
            
            await db.execute(
                f"UPDATE provider_api_keys SET {', '.join(update_fields)} WHERE provider = ?",
                tuple(update_values)
            )
        else:
            # Create new
            await db.execute(
                "INSERT INTO provider_api_keys (provider, api_key, base_url, use_custom_endpoint, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (provider, api_key, base_url, use_custom_endpoint if use_custom_endpoint is not None else False, current_time, current_time)
            )
        
        await db.commit()


async def set_provider_base_url(provider: str, base_url: str, use_custom_endpoint: Optional[bool] = None) -> None:
    """Set or update base URL for a provider."""
    db_path = await get_db_path()
    
    async with aiosqlite.connect(db_path) as db:
        current_time = datetime.now().isoformat()
        
        # Check if provider already exists
        cursor = await db.execute(
            "SELECT provider FROM provider_api_keys WHERE provider = ?", 
            (provider,)
        )
        existing = await cursor.fetchone()
        
        if existing:
            # Update existing
            update_fields = ["base_url = ?", "updated_at = ?"]
            update_values = [base_url, current_time]
            
            if use_custom_endpoint is not None:
                update_fields.append("use_custom_endpoint = ?")
                update_values.append(use_custom_endpoint)
            
            update_values.append(provider)  # For WHERE clause
            
            await db.execute(
                f"UPDATE provider_api_keys SET {', '.join(update_fields)} WHERE provider = ?",
                tuple(update_values)
            )
        else:
            # Create new
            await db.execute(
                "INSERT INTO provider_api_keys (provider, base_url, use_custom_endpoint, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (provider, base_url, use_custom_endpoint if use_custom_endpoint is not None else False, current_time, current_time)
            )
        
        await db.commit()


async def delete_provider_api_key(provider: str) -> None:
    """Delete API key for a provider."""
    db_path = await get_db_path()
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "DELETE FROM provider_api_keys WHERE provider = ?", 
            (provider,)
        )
        await db.commit()