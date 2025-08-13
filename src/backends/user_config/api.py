"""
User Configuration API

Provides API endpoints for managing user configuration (single-user system).
"""

from loguru import logger
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
import os

# Import with lazy loading to avoid circular imports
def get_manager_singleton():
    from ..manager_singleton import ManagerSingleton
    return ManagerSingleton

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
        
        # Compute effective base_url from env for display
        effective_base_url = None
        try:
            if (user_config.provider or "").lower() == "ollama":
                effective_base_url = os.environ.get("OLLAMA_API_BASE")
            elif (user_config.provider or "").lower() == "openai":
                effective_base_url = os.environ.get("OPENAI_BASE_URL")
        except Exception:
            effective_base_url = None

        return ConfigResponse(
            config_id=user_config.config_id or "default",
            provider=user_config.provider,
            model_name=user_config.model_name,
            base_url=(effective_base_url or user_config.base_url or ""),
            
            
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
        
        # Load + reconcile environment variables after configuration update
        try:
            from .keychain_loader import load_env_from_keychain
            load_env_from_keychain(updated_config)
            await ManagerSingleton.save_user_config(updated_config)
        except Exception as sync_error:
            logger.error(f"Environment load from keychain failed during config update: {sync_error}")
        
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
    """Reload the current configuration from database and sync environment variables."""
    try:
        ManagerSingleton = get_manager_singleton()
        reloaded_config = await ManagerSingleton.reload_user_config()
        
        # Also reload environment variables from keychain
        try:
            from .keychain_loader import load_env_from_keychain
            env_dict = load_env_from_keychain(reloaded_config)
            await ManagerSingleton.save_user_config(reloaded_config)
        except Exception as env_error:
            logger.warning(f"Failed to reload env vars during config reload: {env_error}")
        
        return {
            "success": True,
            "message": "Configuration and environment variables reloaded",
            "config_id": reloaded_config.config_id,
            "updated_at": reloaded_config.updated_at
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload configuration: {str(e)}")


@router.get("/env-vars")
async def get_env_vars():
    """Get keyring stored environment variables."""
    from .keychain_loader import get_env_dict_from_keychain
    vars = get_env_dict_from_keychain()
    return list(vars.keys())