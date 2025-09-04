import base64
import hashlib
import json
import os
import secrets
import string
from typing import Dict

from cryptography.fernet import Fernet
from loguru import logger

ENCRYPTION_KEY_NAME = "CHIKEN_ENV_ENCRYPTION_KEY"


def derive_key_from_password(password: str) -> bytes:
    password_bytes = password.encode('utf-8')
    key_hash = hashlib.sha256(password_bytes).digest()
    return base64.urlsafe_b64encode(key_hash)


def generate_random_encryption_key() -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(32))


def get_or_create_encryption_key() -> str:
    env_key = os.environ.get(ENCRYPTION_KEY_NAME)
    if env_key:
        logger.info("Using encryption key from environment variable")
        return env_key
    
    try:
        from .keychain_loader import get_env_dict_from_keychain, save_env_dict_to_keychain
        
        env_dict = get_env_dict_from_keychain()
        if ENCRYPTION_KEY_NAME in env_dict:
            logger.info("Using encryption key from keyring")
            return env_dict[ENCRYPTION_KEY_NAME]
        
        new_key = generate_random_encryption_key()
        env_dict[ENCRYPTION_KEY_NAME] = new_key
        save_env_dict_to_keychain(env_dict)
        logger.info("Generated and saved new encryption key to keyring")
        return new_key
        
    except Exception as e:
        logger.error(f"Failed to get/create encryption key: {e}")
        logger.warning("Using temporary encryption key (not persisted)")
        return generate_random_encryption_key()


def get_cached_encryption_key() -> str:
    from ..manager_singleton import ManagerSingleton
    
    if ManagerSingleton._initialized:
        cached_key = ManagerSingleton.get_encryption_key()
        if cached_key:
            logger.debug(f"Using cached encryption key: {cached_key[:8]}...")
            return cached_key
    
    logger.warning("Manager not initialized or no cached key, creating new one")
    key = get_or_create_encryption_key()
    logger.debug(f"Created new encryption key: {key[:8]}...")
    return key


def encrypt_env_vars(env_vars: Dict[str, str], encryption_key: str) -> str:
    json_data = json.dumps(env_vars)
    key = derive_key_from_password(encryption_key)
    cipher = Fernet(key)
    encrypted_data = cipher.encrypt(json_data.encode('utf-8'))
    return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')


def decrypt_env_vars(encrypted_data: str, encryption_key: str) -> Dict[str, str]:
    encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
    key = derive_key_from_password(encryption_key)
    cipher = Fernet(key)
    decrypted_data = cipher.decrypt(encrypted_bytes)
    json_str = decrypted_data.decode('utf-8')
    return json.loads(json_str)


def apply_env_vars_to_process(env_vars: Dict[str, str]):
    for name, value in env_vars.items():
        if isinstance(name, str) and name and isinstance(value, str):
            os.environ[name] = value
            logger.debug(f"Applied environment variable: {name}")


async def sync_keyring_to_encrypted_db():
    try:
        from .keychain_loader import get_env_dict_from_keychain
        from ..manager_singleton import ManagerSingleton
        
        keyring_vars = get_env_dict_from_keychain()
        if not keyring_vars:
            logger.info("No keyring environment variables to sync")
            return
        
        env_vars_to_sync = {k: v for k, v in keyring_vars.items() if k != ENCRYPTION_KEY_NAME}
        if not env_vars_to_sync:
            logger.info("No environment variables to sync (only encryption key found)")
            return
        
        encryption_key = get_cached_encryption_key()
        db_manager = await ManagerSingleton.get_database_manager()
        existing_data = await db_manager.get_encrypted_env_vars()
        if existing_data:
            logger.info("Encrypted environment variables already exist, skipping sync")
            return
        
        encrypted_data = encrypt_env_vars(env_vars_to_sync, encryption_key)
        await db_manager.save_encrypted_env_vars(encrypted_data)
        apply_env_vars_to_process(env_vars_to_sync)
        
        logger.info(f"Synced {len(env_vars_to_sync)} environment variables from keyring to encrypted database")
        
    except Exception as e:
        logger.error(f"Failed to sync keyring to encrypted database: {e}")