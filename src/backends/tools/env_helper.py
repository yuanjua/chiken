"""
Environment Variable Helper for Tools

Provides on-demand loading of environment variables from encrypted storage
for tools that need them (web search, academic APIs, etc.)
"""

import os
from typing import Optional

from loguru import logger


async def get_env_var_on_demand(var_name: str) -> Optional[str]:
    """
    Get environment variable value on-demand from encrypted storage.
    
    This respects user settings: if user removes a variable from settings UI,
    it should not be used. Only loads from database, does not check os.environ
    to ensure sync with user settings.
    """
    # Load from encrypted database only (respect user settings)
    try:
        from ..user_config.encryption import decrypt_env_vars, get_cached_encryption_key
        from ..manager_singleton import ManagerSingleton
        
        db_manager = await ManagerSingleton.get_database_manager()
        encrypted_data = await db_manager.get_encrypted_env_vars()
        
        if not encrypted_data:
            logger.debug(f"No encrypted environment variables found for {var_name}")
            return None
            
        encryption_key = get_cached_encryption_key()
        env_vars = decrypt_env_vars(encrypted_data, encryption_key)
        
        value = env_vars.get(var_name)
        if value:
            logger.debug(f"Loaded {var_name} from encrypted storage")
            return value
        else:
            logger.debug(f"Variable {var_name} not found in encrypted storage")
            return None
            
    except Exception as e:
        logger.error(f"Failed to load {var_name} from encrypted storage: {e}")
        return None


# Common environment variables used by tools
ACADEMIC_ENV_VARS = {
    "ACADEMIC_MAILTO",
    "SEMANTIC_SCHOLAR_API_KEY", 
    "NCBI_API_KEY",
    "PUBMED_API_KEY",
}

OTHER_TOOL_ENV_VARS = {
    "HF_TOKEN",
    "REPLICATE_API_KEY",
    "COHERE_API_KEY", 
    "OPENROUTER_API_KEY",
    "TOGETHERAI_API_KEY",
}
