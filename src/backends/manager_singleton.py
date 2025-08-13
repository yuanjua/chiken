"""
Manager Singleton

Simplified singleton pattern for managing global instances without heavy configuration management.
"""

import os

from loguru import logger

from .constants import get_app_data_directory, get_database_path
from .database import DatabaseManager
from .sessions.manager import SessionManager
from .user_config.models import UserConfig, create_chat_config

# logger is imported from loguru


class ManagerSingleton:
    _database_manager: DatabaseManager | None = None
    _session_manager: SessionManager | None = None
    _user_config: UserConfig | None = None
    _initialized: bool = False

    @classmethod
    async def initialize(cls):
        if cls._initialized:
            return

        logger.info("Initializing ManagerSingleton...")

        # Get proper database path
        app_data_dir = get_app_data_directory()
        db_path = get_database_path()
        logger.info(f"Using database path: {db_path}")

        # Initialize DatabaseManager
        cls._database_manager = DatabaseManager(db_path=db_path)
        await cls._database_manager.initialize()
        logger.info(f"✅ DatabaseManager initialized with path: {db_path}")

        # Load or create user config with migration support
        try:
            config_data = await cls._database_manager.get_user_config("default")
            if config_data:
                # Convert dict to UserConfig model
                cls._user_config = UserConfig(**config_data)
                logger.info("✅ User config loaded from database.")
            else:
                logger.warning("No user config found, creating default.")
                cls._user_config = create_chat_config(config_id="default")
                # Convert UserConfig model to dict and save
                config_dict = cls._user_config.model_dump()
                await cls._database_manager.save_user_config("default", config_dict)
                logger.info("✅ Default user config created and saved.")
        except Exception as e:
            logger.error(f"Error loading user config: {e}. Creating default config.")
            cls._user_config = create_chat_config(config_id="default")
            try:
                # Convert UserConfig model to dict and save
                config_dict = cls._user_config.model_dump()
                await cls._database_manager.save_user_config("default", config_dict)
                logger.info("✅ Default user config created and saved after error.")
            except Exception as save_error:
                logger.error(f"Error saving default config: {save_error}")
                # Continue with in-memory config

        # Load and reconcile environment variables with keychain
        try:
            from .user_config.keychain_loader import load_env_from_keychain

            load_env_from_keychain(cls._user_config)
            # Persist env_keys if they changed
            config_dict = cls._user_config.model_dump()
            await cls._database_manager.save_user_config("default", config_dict)
        except Exception as e:
            logger.error(f"Error loading environment variables from keychain: {e}")

        # Initialize SessionManager
        cls._session_manager = SessionManager(user_config=cls._user_config, db_path=db_path)
        logger.info("✅ SessionManager initialized.")

        # Ensure default knowledge base exists
        await cls._ensure_default_knowledge_base()

        cls._initialized = True
        logger.info("✅ ManagerSingleton initialized successfully.")

    @classmethod
    async def get_database_manager(cls) -> DatabaseManager:
        if not cls._database_manager:
            await cls.initialize()
        return cls._database_manager

    @classmethod
    async def get_session_manager(cls) -> SessionManager:
        if not cls._session_manager:
            await cls.initialize()
        return cls._session_manager

    @classmethod
    async def get_user_config(cls) -> UserConfig:
        if not cls._user_config:
            await cls.initialize()
        return cls._user_config

    @classmethod
    async def save_user_config(cls, config: UserConfig):
        cls._user_config = config
        if cls._database_manager:
            # Convert UserConfig model to dict and save
            config_dict = config.model_dump()
            await cls._database_manager.save_user_config(config.config_id or "default", config_dict)
        if cls._session_manager:
            cls._session_manager.user_config = config
            # Clear agent cache to force recreation with new config
            cls._session_manager.agents.clear()

    @classmethod
    async def update_user_config(cls, **updates) -> UserConfig:
        """Update the global user config and persist to database."""
        current_config = await cls.get_user_config()
        current_dict = current_config.model_dump()
        current_dict.update(updates)

        # Add/update timestamp
        from datetime import datetime

        current_dict["updated_at"] = datetime.now().isoformat()

        cls._user_config = UserConfig(**current_dict)

        # Save to database
        await cls.save_user_config(cls._user_config)

        # Update session manager's user config reference if it exists
        if cls._session_manager:
            cls._session_manager.user_config = cls._user_config
            # Clear agent cache to force recreation with new config
            cls._session_manager.agents.clear()
            logger.info("Updated user config, saved to database, and cleared agent cache")

        return cls._user_config

    @classmethod
    async def reload_user_config(cls) -> UserConfig:
        """Reload user config from database."""
        if not cls._database_manager:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")

        # Force reload from database
        try:
            config_data = await cls._database_manager.get_user_config("default")
            if config_data:
                # Convert dict to UserConfig model
                cls._user_config = UserConfig(**config_data)
                logger.info("✅ User config reloaded from database.")
            else:
                logger.warning("No user config found during reload, using current config.")
                if not cls._user_config:
                    cls._user_config = create_chat_config(config_id="default")
        except Exception as e:
            logger.error(f"Error reloading user config: {e}. Keeping current config.")
            if not cls._user_config:
                cls._user_config = create_chat_config(config_id="default")

        # Update session manager's user config reference if it exists
        if cls._session_manager:
            cls._session_manager.user_config = cls._user_config
            # Clear agent cache to force recreation with new config
            cls._session_manager.agents.clear()
            logger.info("Reloaded user config from database and cleared agent cache")

        return cls._user_config

    @classmethod
    async def get_system_status(cls) -> dict:
        """Get simplified system status information."""
        await cls.initialize()

        # Database info
        db_manager = await cls.get_database_manager()
        db_info = await db_manager.get_database_info()

        # Session info
        session_manager = await cls.get_session_manager()
        sessions = await session_manager.get_all_session_metadata()

        # Current config
        user_config = await cls.get_user_config()

        return {
            "status": "healthy",
            "initialized": cls._initialized,
            "current_config_id": user_config.config_id or "default",
            "database": {
                "path": db_info["database_path"],
                "size_mb": db_info["size_mb"],
                "tables": db_info["tables"],
            },
            "configurations": {
                "total_count": 1,  # Simplified - just one config
                "current": {
                    "model_name": user_config.model_name,
                    "provider": user_config.provider,
                    "base_url": user_config.base_url,
                    "temperature": user_config.temperature,
                },
            },
            "sessions": {
                "total_count": len(sessions),
                "active_sessions": [s["session_id"] for s in sessions],
            },
            "managers": {
                "database_manager": cls._database_manager is not None,
                "session_manager": cls._session_manager is not None,
            },
        }

    @classmethod
    async def backup_system(cls, backup_dir: str = "backups") -> dict:
        """Create a backup of the database."""
        from datetime import datetime

        await cls.initialize()

        # Create backup directory
        os.makedirs(backup_dir, exist_ok=True)

        # Create database backup
        db_manager = await cls.get_database_manager()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"app_data_backup_{timestamp}.db")
        await db_manager.backup_database(backup_path)

        return {
            "backup_created": True,
            "backup_path": backup_path,
            "timestamp": timestamp,
            "database_size_mb": (await db_manager.get_database_info())["size_mb"],
        }

    @classmethod
    async def _ensure_default_knowledge_base(cls):
        """
        Ensure the default 'uploaded-documents' knowledge base is cleared and
        recreated on startup.
        """
        try:
            from .rag.db import RAGDB
            from .rag.embedding import get_embedding_function

            default_kb_name = "uploaded-documents"
            db_manager = cls._database_manager

            # --- Clear existing default KB ---
            existing_kb_id = await db_manager.resolve_knowledge_base_id(default_kb_name)
            if existing_kb_id:
                logger.info(f"Clearing existing default knowledge base: '{default_kb_name}' (ID: {existing_kb_id})")

                # Delete from ChromaDB
                try:
                    embeddings = await get_embedding_function()
                    rag_db = RAGDB(embeddings=embeddings)
                    rag_db.delete_collection(name=existing_kb_id)
                    logger.info(f"Removed ChromaDB collection for '{default_kb_name}'.")
                except Exception as e:
                    # It's okay if the collection doesn't exist.
                    logger.debug(f"Could not remove ChromaDB collection for '{default_kb_name}': {e}")

                # Delete from database
                await db_manager.delete_knowledge_base(existing_kb_id)
                logger.info(f"Removed database entry for '{default_kb_name}'.")

            # --- Recreate the default KB ---
            logger.info(f"Creating default knowledge base: {default_kb_name}")
            from .constants import CHUNK_OVERLAP, CHUNK_SIZE

            new_kb_id = await db_manager.create_knowledge_base(
                display_name=default_kb_name,
                description="Default knowledge base for uploaded documents. Cleared on restart.",
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
            )

            # Pre-create the ChromaDB collection as well
            embeddings = await get_embedding_function()
            rag_db = RAGDB(embeddings=embeddings)
            await rag_db.get_or_create_collection(name=new_kb_id)

            logger.info(f"✅ Default knowledge base recreated with ID: {new_kb_id}")

        except Exception as e:
            logger.error(f"Failed to ensure default knowledge base: {e}")
            # Don't fail startup if KB creation fails

    @classmethod
    async def close_all(cls):
        """Close all singleton instances."""
        if cls._session_manager:
            await cls._session_manager.aclose()
            cls._session_manager = None
            logger.info("✅ SessionManager closed")

        cls._database_manager = None
        cls._user_config = None
        cls._initialized = False
        logger.info("✅ All singleton instances closed")
