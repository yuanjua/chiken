import os
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from loguru import logger

from .models import UserConfig

router = APIRouter()

def get_manager_singleton():
    from ..manager_singleton import ManagerSingleton
    return ManagerSingleton


@router.get("/")
async def get_config() -> Dict[str, Any]:
    ManagerSingleton = get_manager_singleton()
    config = await ManagerSingleton.get_user_config()
    
    return {
        "success": True,
        "config": config.model_dump(),
        "config_id": config.config_id,
        "updated_at": config.updated_at,
    }


@router.put("/")
async def update_config(update_data: Dict[str, Any]):
    ManagerSingleton = get_manager_singleton()
    
    try:
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        updated_config = await ManagerSingleton.update_user_config(**update_data)
        
        return {
            "success": True,
            "message": "Configuration updated successfully",
            "config": updated_config.model_dump(),
            "config_id": updated_config.config_id,
            "updated_at": updated_config.updated_at,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


@router.post("/reload")
async def reload_config():
    try:
        from .keychain_loader import load_env_from_keychain
        from .encryption import get_cached_encryption_key, decrypt_env_vars, apply_env_vars_to_process
        
        ManagerSingleton = get_manager_singleton()
        reloaded_config = await ManagerSingleton.reload_user_config()

        try:
            env_dict = load_env_from_keychain(reloaded_config)
            
            try:
                db_manager = await ManagerSingleton.get_database_manager()
                encrypted_data = await db_manager.get_encrypted_env_vars()
                if encrypted_data:
                    encryption_key = get_cached_encryption_key()
                    encrypted_vars = decrypt_env_vars(encrypted_data, encryption_key)
                    apply_env_vars_to_process(encrypted_vars)
                    logger.info(f"Loaded {len(encrypted_vars)} encrypted environment variables")
            except Exception as enc_error:
                logger.warning(f"Failed to load encrypted env vars: {enc_error}")
            
            await ManagerSingleton.save_user_config(reloaded_config)
        except Exception as env_error:
            logger.warning(f"Failed to reload env vars during config reload: {env_error}")

        return {
            "success": True,
            "message": "Configuration and environment variables reloaded",
            "config_id": reloaded_config.config_id,
            "updated_at": reloaded_config.updated_at,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload configuration: {str(e)}")


@router.get("/env-vars")
async def get_env_vars():
    from .keychain_loader import get_env_dict_from_keychain

    vars = get_env_dict_from_keychain()
    return list(vars.keys())


@router.post("/env-vars/encrypted")
async def get_encrypted_env_vars(request: dict):
    try:
        from .encryption import decrypt_env_vars, get_cached_encryption_key, apply_env_vars_to_process
        
        encryption_key = request.get("encryption_key") or get_cached_encryption_key()
        logger.debug(f"Getting env vars with encryption key: {encryption_key[:8] if encryption_key else 'None'}...")
        
        from ..manager_singleton import ManagerSingleton
        db_manager = await ManagerSingleton.get_database_manager()
        encrypted_data = await db_manager.get_encrypted_env_vars()
        
        if not encrypted_data:
            logger.debug("No encrypted data found, returning empty dict")
            return {}
        
        logger.debug(f"Found encrypted data, decrypting...")
        env_vars = decrypt_env_vars(encrypted_data, encryption_key)
        apply_env_vars_to_process(env_vars)
        logger.debug(f"Successfully decrypted {len(env_vars)} environment variables")
        return env_vars
        
    except Exception as e:
        import traceback
        logger.error(f"Failed to get encrypted env vars: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get encrypted environment variables: {str(e)}")


@router.put("/env-vars/encrypted")
async def set_encrypted_env_var(request: dict):
    from .encryption import encrypt_env_vars, decrypt_env_vars, get_cached_encryption_key, apply_env_vars_to_process
    
    try:
        name = request.get("name")
        value = request.get("value")
        encryption_key = request.get("encryption_key") or get_cached_encryption_key()
        logger.debug(f"Setting env var {name} with encryption key: {encryption_key[:8] if encryption_key else 'None'}...")
        
        if not name or value is None:
            raise HTTPException(status_code=400, detail="Name and value are required")
        
        from ..manager_singleton import ManagerSingleton
        db_manager = await ManagerSingleton.get_database_manager()
        existing_encrypted_data = await db_manager.get_encrypted_env_vars()
        
        if existing_encrypted_data:
            try:
                env_vars = decrypt_env_vars(existing_encrypted_data, encryption_key)
            except Exception as e:
                logger.error(f"Failed to decrypt existing data: {e}")
                raise HTTPException(status_code=400, detail="Invalid encryption key")
        else:
            env_vars = {}
        
        env_vars[name] = value
        encrypted_data = encrypt_env_vars(env_vars, encryption_key)
        await db_manager.save_encrypted_env_vars(encrypted_data)
        apply_env_vars_to_process({name: value})
        
        return {"success": True, "message": f"Environment variable '{name}' set successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Failed to set encrypted env var: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to set encrypted environment variable: {str(e)}")


@router.delete("/env-vars/encrypted")
async def delete_encrypted_env_var(request: dict):
    from .encryption import encrypt_env_vars, decrypt_env_vars, get_cached_encryption_key
    
    try:
        name = request.get("name")
        encryption_key = request.get("encryption_key") or get_cached_encryption_key()
        
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        
        from ..manager_singleton import ManagerSingleton
        db_manager = await ManagerSingleton.get_database_manager()
        existing_encrypted_data = await db_manager.get_encrypted_env_vars()
        
        if not existing_encrypted_data:
            raise HTTPException(status_code=404, detail="No environment variables found")
        
        try:
            env_vars = decrypt_env_vars(existing_encrypted_data, encryption_key)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid encryption key")
        
        if name not in env_vars:
            raise HTTPException(status_code=404, detail=f"Environment variable '{name}' not found")
        
        del env_vars[name]
        os.environ.pop(name, None)
        
        encrypted_data = encrypt_env_vars(env_vars, encryption_key)
        await db_manager.save_encrypted_env_vars(encrypted_data)
        
        return {"success": True, "message": f"Environment variable '{name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete encrypted env var: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete encrypted environment variable: {str(e)}")