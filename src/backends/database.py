"""
Consolidated Database Management

Handles initialization and management of the consolidated SQLite database
that stores user configurations, sessions, and other application data.
"""

import os
from loguru import logger
import aiosqlite
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

# logger is imported from loguru


class DatabaseManager:
    """Manages the consolidated application database."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        if not self.db_path:
            raise ValueError("Database path cannot be empty.")
        self._initialized = False
    
    async def initialize(self):
        """Initialize the database and create all necessary tables."""
        if self._initialized:
            return
        
        logger.info(f"Initializing consolidated database: {self.db_path}")
        
        async with aiosqlite.connect(self.db_path) as db:
            # Configure SQLite for better concurrency handling
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging for better concurrency
            await db.execute("PRAGMA synchronous = NORMAL")  # Balance between performance and safety
            await db.execute("PRAGMA cache_size = 10000")  # Increase cache size
            await db.execute("PRAGMA temp_store = memory")  # Use memory for temp storage
            await db.execute("PRAGMA mmap_size = 268435456")  # 256MB memory-mapped I/O
            await db.execute("PRAGMA busy_timeout = 30000")  # 30 second timeout for locks
            
            # Create user_configs table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_configs (
                    config_id TEXT PRIMARY KEY,
                    config_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Create index for user_configs
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_configs_updated_at 
                ON user_configs(updated_at)
            """)
            
            # Create knowledge_bases table (embed_model column added in v0.3, enable_reference_filtering added in v0.4)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_bases (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    chunk_size INTEGER DEFAULT 1600,
                    chunk_overlap INTEGER DEFAULT 200,
                    embed_model TEXT,
                    enable_reference_filtering BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # --- Migration: add embed_model column when upgrading from earlier versions ---
            pragma_info = await db.execute("PRAGMA table_info(knowledge_bases)")
            columns = [row[1] for row in await pragma_info.fetchall()]
            if "embed_model" not in columns:
                await db.execute("ALTER TABLE knowledge_bases ADD COLUMN embed_model TEXT")
            
            # --- Migration: add enable_reference_filtering column when upgrading from earlier versions ---
            if "enable_reference_filtering" not in columns:
                await db.execute("ALTER TABLE knowledge_bases ADD COLUMN enable_reference_filtering BOOLEAN DEFAULT 1")
            
            # Create index for knowledge_bases display_name
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_knowledge_bases_display_name 
                ON knowledge_bases(display_name)
            """)
            
            # Create chat message history table for persistent chat memory
            await db.execute("""
                CREATE TABLE IF NOT EXISTS message_store (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for chat messages
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_store_session_id 
                ON message_store(session_id)
            """)
            
            # Create sessions metadata table for session info
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions_metadata (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT 'New Chat',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0
                )
            """)
            
            await db.commit()
        
        self._initialized = True
        logger.info("✅ Consolidated database initialized")
    
    def get_connection(self):
        """Get a database connection context manager."""
        return aiosqlite.connect(self.db_path)
    
    # Knowledge Base Management Methods
    from .constants import CHUNK_SIZE, CHUNK_OVERLAP
    async def create_knowledge_base(self, display_name: str, description: str = None, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP, embed_model: str | None = None, enable_reference_filtering: bool = True) -> str:
        """Create a new knowledge base entry and return the generated ID."""
        await self.initialize()
        
        # Use the name as the ID for the special 'uploaded-documents' KB
        kb_id = display_name if display_name == "uploaded-documents" else str(uuid.uuid4())
        now = datetime.now().isoformat()
        final_description = description or f"Knowledge base: {display_name}"
        
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO knowledge_bases (id, display_name, description, chunk_size, chunk_overlap, embed_model, enable_reference_filtering, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (kb_id, display_name, final_description, chunk_size, chunk_overlap, embed_model, enable_reference_filtering, now, now))
                await db.commit()
                return kb_id
            except aiosqlite.IntegrityError as e:
                if "display_name" in str(e).lower():
                    raise ValueError(f"Knowledge base with name '{display_name}' already exists")
                else:
                    raise ValueError(f"Database constraint error: {e}")
    
    async def list_knowledge_bases(self) -> List[Dict[str, Any]]:
        """List all knowledge bases from the database."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, display_name, description, chunk_size, chunk_overlap, embed_model, enable_reference_filtering, created_at, updated_at
                FROM knowledge_bases
                ORDER BY created_at DESC
            """)
            
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "display_name": row[1],
                    "description": row[2],
                    "chunk_size": row[3],
                    "chunk_overlap": row[4],
                    "embed_model": row[5],
                    "enable_reference_filtering": bool(row[6]),
                    "created_at": row[7],
                    "updated_at": row[8]
                }
                for row in rows
            ]
    
    async def get_knowledge_base_by_id(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """Get knowledge base by ID."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, display_name, description, chunk_size, chunk_overlap, embed_model, enable_reference_filtering, created_at, updated_at
                FROM knowledge_bases
                WHERE id = ?
            """, (kb_id,))
            
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "display_name": row[1],
                    "description": row[2],
                    "chunk_size": row[3],
                    "chunk_overlap": row[4],
                    "embed_model": row[5],
                    "enable_reference_filtering": bool(row[6]),
                    "created_at": row[7],
                    "updated_at": row[8]
                }
            return None
    
    async def get_knowledge_base_by_display_name(self, display_name: str) -> Optional[Dict[str, Any]]:
        """Get knowledge base by display name."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, display_name, description, chunk_size, chunk_overlap, embed_model, enable_reference_filtering, created_at, updated_at
                FROM knowledge_bases
                WHERE display_name = ?
            """, (display_name,))
            
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "display_name": row[1],
                    "description": row[2],
                    "chunk_size": row[3],
                    "chunk_overlap": row[4],
                    "embed_model": row[5],
                    "enable_reference_filtering": bool(row[6]),
                    "created_at": row[7],
                    "updated_at": row[8]
                }
            return None
    
    async def delete_knowledge_base(self, kb_id: str) -> bool:
        """Delete knowledge base entry from database."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))
            await db.commit()
            return cursor.rowcount > 0
    
    async def resolve_knowledge_base_id(self, name_or_id: str) -> Optional[str]:
        """
        Resolve a display name or ID to a ChromaDB collection ID.
        Returns the ID if found, None if not found.
        """
        await self.initialize()

        # If the name is the special default KB name, check for it directly.
        if name_or_id == "uploaded-documents":
            kb_info = await self.get_knowledge_base_by_id(name_or_id)
            if kb_info:
                return name_or_id
        
        # First check if it's a valid UUID (our current ID format)
        try:
            uuid.UUID(name_or_id)
            # It's a valid UUID, check if it exists in database
            kb_info = await self.get_knowledge_base_by_id(name_or_id)
            if kb_info:
                return name_or_id
        except ValueError:
            pass
        
        # Not a UUID, treat as display name
        kb_info = await self.get_knowledge_base_by_display_name(name_or_id)
        if kb_info:
            return kb_info["id"]
        
        return None
    
    async def get_database_info(self) -> dict:
        """Get information about the database."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Get table information
            cursor = await db.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                ORDER BY name
            """)
            tables = [row[0] for row in await cursor.fetchall()]
            
            # Get database size
            stat = os.stat(self.db_path)
            size_mb = stat.st_size / (1024 * 1024)
            
            return {
                "database_path": self.db_path,
                "size_mb": round(size_mb, 2),
                "tables": tables,
                "initialized": self._initialized
            }
    
    async def vacuum_database(self):
        """Vacuum the database to reclaim space."""
        await self.initialize()
        
        logger.info("Vacuuming database...")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("VACUUM")
        logger.info("✅ Database vacuumed")
    
    async def backup_database(self, backup_path: str):
        """Create a backup of the database."""
        await self.initialize()
        
        logger.info(f"Creating database backup: {backup_path}")
        
        # Create backup directory if it doesn't exist
        backup_dir = os.path.dirname(backup_path)
        if backup_dir and not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        async with aiosqlite.connect(self.db_path) as source:
            async with aiosqlite.connect(backup_path) as backup:
                await source.backup(backup)
        
        logger.info("✅ Database backup created")

    # User Config Management Methods
    async def get_user_config(self, config_id: str = "default") -> Optional[Dict[str, Any]]:
        """Get user configuration by ID from database."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT config_id, config_data, created_at, updated_at
                FROM user_configs
                WHERE config_id = ?
            """, (config_id,))
            
            row = await cursor.fetchone()
            if row:
                import json
                try:
                    config_data = json.loads(row[1])
                    config_data.update({
                        "config_id": row[0],
                        "created_at": row[2],
                        "updated_at": row[3]
                    })
                    return config_data
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse config data for {config_id}: {e}")
                    return None
            return None

    async def save_user_config(self, config_id: str, config_data: Dict[str, Any]) -> bool:
        """Save user configuration to database."""
        await self.initialize()
        
        import json
        now = datetime.now().isoformat()
        
        # Remove metadata fields from config_data before serializing
        config_copy = config_data.copy()
        config_copy.pop('config_id', None)
        config_copy.pop('created_at', None)
        config_copy.pop('updated_at', None)
        
        config_json = json.dumps(config_copy)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Check if config exists
            cursor = await db.execute("SELECT config_id FROM user_configs WHERE config_id = ?", (config_id,))
            exists = await cursor.fetchone()
            
            if exists:
                # Update existing config
                await db.execute("""
                    UPDATE user_configs 
                    SET config_data = ?, updated_at = ?
                    WHERE config_id = ?
                """, (config_json, now, config_id))
            else:
                # Insert new config
                await db.execute("""
                    INSERT INTO user_configs (config_id, config_data, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (config_id, config_json, now, now))
            
            await db.commit()
            return True

    async def list_user_configs(self) -> List[Dict[str, Any]]:
        """List all user configurations from database."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT config_id, created_at, updated_at
                FROM user_configs
                ORDER BY updated_at DESC
            """)
            
            rows = await cursor.fetchall()
            return [
                {
                    "config_id": row[0],
                    "created_at": row[1],
                    "updated_at": row[2]
                }
                for row in rows
            ]

    async def delete_user_config(self, config_id: str) -> bool:
        """Delete user configuration from database."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM user_configs WHERE config_id = ?", (config_id,))
            await db.commit()
            return cursor.rowcount > 0

    # Session Metadata Management Methods
    async def save_session_metadata(self, session_id: str, title: str = "New Chat", message_count: int = 0) -> bool:
        """Save or update session metadata."""
        await self.initialize()
        
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Check if session exists
            cursor = await db.execute("SELECT session_id FROM sessions_metadata WHERE session_id = ?", (session_id,))
            exists = await cursor.fetchone()
            
            if exists:
                # Update existing session
                await db.execute("""
                    UPDATE sessions_metadata 
                    SET title = ?, updated_at = ?, message_count = ?
                    WHERE session_id = ?
                """, (title, now, message_count, session_id))
            else:
                # Insert new session
                await db.execute("""
                    INSERT INTO sessions_metadata (session_id, title, created_at, updated_at, message_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, title, now, now, message_count))
            
            await db.commit()
            return True

    async def get_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session metadata."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT session_id, title, created_at, updated_at, message_count
                FROM sessions_metadata 
                WHERE session_id = ?
            """, (session_id,))
            
            row = await cursor.fetchone()
            if row:
                return {
                    "session_id": row[0],
                    "title": row[1],
                    "created_at": row[2],
                    "updated_at": row[3],
                    "message_count": row[4]
                }
            return None

    async def list_sessions_metadata(self) -> List[Dict[str, Any]]:
        """List all session metadata, sorted by updated_at (newest first)."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT session_id, title, created_at, updated_at, message_count
                FROM sessions_metadata 
                ORDER BY updated_at DESC
            """)
            
            sessions = []
            async for row in cursor:
                sessions.append({
                    "session_id": row[0],
                    "title": row[1],
                    "created_at": row[2],
                    "updated_at": row[3],
                    "message_count": row[4]
                })
            
            return sessions

    async def delete_session_metadata(self, session_id: str) -> bool:
        """Delete session metadata and associated messages."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Delete messages first
            await db.execute("DELETE FROM message_store WHERE session_id = ?", (session_id,))
            # Delete metadata
            cursor = await db.execute("DELETE FROM sessions_metadata WHERE session_id = ?", (session_id,))
            await db.commit()
            return cursor.rowcount > 0

# Compatibility wrapper for existing code
async def get_database_manager() -> DatabaseManager:
    """Get the database manager through ManagerSingleton."""
    from .manager_singleton import ManagerSingleton
    return await ManagerSingleton.get_database_manager()