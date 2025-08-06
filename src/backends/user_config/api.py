"""
User Configuration API

Provides API endpoints for managing user configuration (single-user system).
"""

from loguru import logger
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import with lazy loading to avoid circular imports
def get_manager_singleton():
    from ..manager_singleton import ManagerSingleton
    return ManagerSingleton

# Import models
from .provider_keys import (
    ProviderApiKeyRequest, 
    ProviderApiKeyResponse,
    get_all_provider_api_keys,
    get_provider_api_key,
    get_provider_base_url,
    get_provider_config,
    set_provider_api_key,
    set_provider_base_url,
    delete_provider_api_key
)

# Router setup
router = APIRouter(prefix="/config", tags=["Configuration"])


# Request/Response Models
class ConfigUpdateRequest(BaseModel):
    """Request model for configuration updates."""
    provider: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    num_ctx: Optional[int] = None
    base_url: Optional[str] = None
    
    # Core configuration only - no API keys here
    system_prompt: Optional[str] = None
    max_history_length: Optional[int] = None
    memory_update_frequency: Optional[int] = None
    embed_model: Optional[str] = None
    embed_provider: Optional[str] = None
    max_tokens: Optional[int] = None
    pdf_parser_type: Optional[str] = None
    pdf_parser_url: Optional[str] = None
    search_engine: Optional[str] = None
    search_endpoint: Optional[str] = None
    search_api_key: Optional[str] = None
    mcp_transport: Optional[str] = None
    mcp_port: Optional[int] = None
    active_knowledge_base_ids: Optional[List[str]] = None
    use_custom_endpoints: Optional[bool] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    enable_reference_filtering: Optional[bool] = None


class ConfigResponse(BaseModel):
    """Response model for configuration."""
    config_id: str
    provider: str
    model_name: str
    base_url: str
    
    # Core configuration only - API keys handled separately
    temperature: float
    num_ctx: int
    max_tokens: Optional[int] = None
    embed_model: str
    embed_provider: str
    system_prompt: Optional[str] = None
    max_history_length: int
    memory_update_frequency: int
    pdf_parser_type: str
    pdf_parser_url: Optional[str] = None
    search_engine: str
    search_endpoint: Optional[str] = None
    search_api_key: Optional[str] = None
    mcp_transport: str
    mcp_port: Optional[int] = None
    active_knowledge_base_ids: List[str]
    created_at: str
    updated_at: str
    use_custom_endpoints: bool
    chunk_size: int
    chunk_overlap: int
    enable_reference_filtering: bool
    # Computed fields
    provider_type: str = Field(description="Provider type derived from model_name")


# Configuration Endpoints (Single User)
@router.get("/", response_model=ConfigResponse)
async def get_current_configuration():
    """Get the current system configuration."""
    try:
        ManagerSingleton = get_manager_singleton()
        user_config = await ManagerSingleton.get_user_config()
        
        # Generate current timestamp for missing values
        current_timestamp = datetime.now().isoformat()
        
        return ConfigResponse(
            config_id=user_config.config_id or "default",
            provider=user_config.provider,
            model_name=user_config.model_name,
            base_url=user_config.base_url or "",
            
            
            temperature=user_config.temperature,
            num_ctx=user_config.num_ctx,
            max_tokens=user_config.max_tokens,
            embed_model=user_config.embed_model,
            embed_provider=user_config.embed_provider,
            system_prompt=user_config.system_prompt,
            max_history_length=user_config.max_history_length,
            memory_update_frequency=user_config.memory_update_frequency,
            pdf_parser_type=user_config.pdf_parser_type,
            pdf_parser_url=user_config.pdf_parser_url,
            search_engine=user_config.search_engine,
            search_endpoint=user_config.search_endpoint,
            search_api_key=user_config.search_api_key,
            mcp_transport=user_config.mcp_transport,
            mcp_port=user_config.mcp_port,
            active_knowledge_base_ids=user_config.active_knowledge_base_ids or [],
            created_at=user_config.created_at or current_timestamp,
            updated_at=user_config.updated_at or current_timestamp,
            use_custom_endpoints=user_config.use_custom_endpoints,
            chunk_size=user_config.chunk_size,
            chunk_overlap=user_config.chunk_overlap,
            enable_reference_filtering=user_config.enable_reference_filtering,
            provider_type=user_config.provider_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {str(e)}")


@router.post("/")
async def update_current_configuration(request: ConfigUpdateRequest):
    """Update the current system configuration."""
    try:
        # Filter out None values
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        
        if not updates:
            raise HTTPException(status_code=400, detail="No valid updates provided")
        
        # Update configuration
        ManagerSingleton = get_manager_singleton()
        updated_config = await ManagerSingleton.update_user_config(**updates)
        
        return {
            "success": True,
            "message": "Configuration updated successfully",
            "config_id": updated_config.config_id,
            "updated_fields": list(updates.keys()),
            "updated_at": updated_config.updated_at
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


@router.post("/reload")
async def reload_configuration():
    """Reload the current configuration from database."""
    try:
        ManagerSingleton = get_manager_singleton()
        reloaded_config = await ManagerSingleton.reload_user_config()
        return {
            "success": True,
            "message": "Configuration reloaded from database",
            "config_id": reloaded_config.config_id,
            "updated_at": reloaded_config.updated_at
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload configuration: {str(e)}")


# Provider API Key Endpoints
@router.get("/provider-keys", response_model=List[ProviderApiKeyResponse])
async def get_all_provider_keys():
    """Get all provider API keys."""
    try:
        return await get_all_provider_api_keys()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get provider keys: {str(e)}")


@router.get("/provider-keys/{provider}")
async def get_provider_key(provider: str):
    """Get API key and base URL for a specific provider."""
    try:
        config = await get_provider_config(provider)
        if config is None:
            raise HTTPException(status_code=404, detail=f"No configuration found for provider: {provider}")
        return {
            "provider": provider, 
            "api_key": config.get("api_key"),
            "base_url": config.get("base_url"),
            "use_custom_endpoint": config.get("use_custom_endpoint", False)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get provider config: {str(e)}")

@router.post("/provider-keys")
async def set_provider_key(request: ProviderApiKeyRequest):
    """Set or update API key and/or base URL for a provider."""
    logger.info(f"Received set_provider_key request: {request.dict()}")
    try:
        if not request.provider or not isinstance(request.provider, str) or not request.provider.strip():
            logger.error(f"Missing or invalid provider field: {request.provider}")
            raise HTTPException(status_code=400, detail="Provider field is required and must be a non-empty string.")

        # Log incoming fields (excluding sensitive data)
        logger.info(f"base_url: {request.base_url}, use_custom_endpoint: {request.use_custom_endpoint}")

        if request.api_key is not None and request.base_url is not None:
            await set_provider_api_key(request.provider, request.api_key, request.base_url, request.use_custom_endpoint)
            message = f"API key and base URL set for provider: {request.provider}"
        elif request.api_key is not None:
            await set_provider_api_key(request.provider, request.api_key, use_custom_endpoint=request.use_custom_endpoint)
            message = f"API key set for provider: {request.provider}"
        elif request.base_url is not None:
            await set_provider_base_url(request.provider, request.base_url, request.use_custom_endpoint)
            message = f"Base URL set for provider: {request.provider}"
        else:
            logger.error("Neither api_key nor base_url provided in request.")
            raise HTTPException(status_code=400, detail="Either api_key or base_url must be provided.")

        logger.info(f"Provider key update successful for {request.provider}")
        return {
            "success": True,
            "message": message,
            "provider": request.provider
        }
    except HTTPException as he:
        logger.error(f"HTTPException: {he.detail}")
        raise
    except Exception as e:
        logger.exception(f"Unhandled error in set_provider_key: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set provider config: {str(e)}")


@router.delete("/provider-keys/{provider}")
async def delete_provider_key(provider: str):
    """Delete API key for a provider."""
    try:
        await delete_provider_api_key(provider)
        return {
            "success": True,
            "message": f"API key deleted for provider: {provider}",
            "provider": provider
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete provider key: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete provider auth: {str(e)}")