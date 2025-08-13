"""
Simple keychain loader for environment variables.
Stores all env vars as a single JSON dict in keychain.
"""

import os
import json
from loguru import logger
import keyring
import getpass

SERVICE_NAME = "chiken"
ENV_VARS_KEY = getpass.getuser()

def load_env_from_keychain(user_config=None) -> dict[str, str]:
    """
    Single entry point to load and apply environment variables.

    - Reads the JSON dict from keychain (canonical source)
    - Sets all variables into os.environ
    - If user_config is provided:
        - Unsets any variables that were previously tracked in user_config.env_keys
          but are no longer present in keychain
        - Updates user_config.env_keys to reflect current keychain keys

    Returns the dict of variables loaded from keychain.
    """
    # Read JSON dict from keychain
    env_dict: dict[str, str]
    try:
        env_json = keyring.get_password(SERVICE_NAME, ENV_VARS_KEY)
        env_dict = json.loads(env_json) if env_json else {}
    except Exception as e:
        logger.error(f"Failed to read env vars from keychain: {e}")
        env_dict = {}

    # 1) Project keychain vars into process environment
    for name, value in env_dict.items():
        if isinstance(name, str) and name and isinstance(value, str) and value:
            os.environ[name] = value

    # 2) Reconcile tracked keys (if provided)
    if user_config is not None:
        try:
            tracked = set(getattr(user_config, "env_keys", []) or [])
            current = set(env_dict.keys())
            # Remove variables that were tracked but are no longer in keychain
            for name in sorted(tracked - current):
                os.environ.pop(name, None)
            # Update tracked list to current state
            user_config.env_keys = sorted(env_dict.keys())
        except Exception as e:
            logger.warning(f"Failed to sync env_keys with keychain: {e}")

    logger.info(f"Loaded {len(env_dict)} environment variables from keychain: {list(env_dict.keys())}")
    return env_dict


def get_env_dict_from_keychain() -> dict[str, str]:
    """
    Get environment variables dict from keychain without applying to os.environ.
    Used for reading current state.
    """
    try:
        env_json = keyring.get_password(SERVICE_NAME, ENV_VARS_KEY)
        env_dict = json.loads(env_json) if env_json else {}
        logger.info(f"Retrieved {len(env_dict)} environment variables from keychain: {list(env_dict.keys())}")
        return env_dict
    except Exception as e:
        logger.error(f"Failed to get env vars from keychain: {e}")
        return {}


def save_env_dict_to_keychain(env_dict: dict[str, str]) -> bool:
    """
    Save environment variables dict to keychain.
    Used for updating stored state.
    """
    try:
        env_json = json.dumps(env_dict)
        keyring.set_password(SERVICE_NAME, ENV_VARS_KEY, env_json)
        logger.info(f"Saved {len(env_dict)} environment variables to keychain: {list(env_dict.keys())}")
        return True
    except Exception as e:
        logger.error(f"Failed to save env vars to keychain: {e}")
        return False

