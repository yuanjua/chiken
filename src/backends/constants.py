"""
Constants for the RAG service.
Centralizes magic strings and configuration values.
"""

import os
import sys


def get_app_data_directory():
    """Get the application data directory, creating it if it doesn't exist."""
    if getattr(sys, "frozen", False):
        # Running as a packaged app
        if sys.platform == "darwin":  # macOS
            app_data_dir = os.path.expanduser("~/Library/Application Support/ChiKen")
        elif sys.platform == "win32":  # Windows
            app_data_dir = os.path.join(os.getenv("APPDATA", ""), "ChiKen")
        else:  # Linux
            app_data_dir = os.path.expanduser("~/.local/share/ChiKen")
    else:
        # Running in development
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))  # Go up two levels from src/backends/
        app_data_dir = project_root

    # Create the directory if it doesn't exist
    os.makedirs(app_data_dir, exist_ok=True)
    return app_data_dir


def get_database_path():
    """Get the SQLite database path."""
    return os.path.join(get_app_data_directory(), "app_data.db")


def get_chroma_db_path():
    """Get the ChromaDB directory path."""
    chroma_path = os.path.join(get_app_data_directory(), "chroma_db")
    os.makedirs(chroma_path, exist_ok=True)
    return chroma_path


# Collection names
UPLOADED_FILES_COLLECTION_NAME = "uploaded_files"

# File types
PDF_FILE_TYPE = "pdf"
UNKNOWN_FILE_TYPE = "unknown"

# Metadata keys
CONTENT_HASH_KEY = "content_hash"
FILE_HASH_KEY = "file_hash"
KB_REFS_KEY = "knowledge_base_refs"
ZOTERO_KEY = "zotero_key"
TITLE_KEY = "title"
SOURCE_KEY = "source"
FILENAME_KEY = "filename"
FILE_TYPE_KEY = "file_type"

# Processing defaults
DEFAULT_BATCH_SIZE = 4
DEFAULT_QUERY_RESULTS = 10
DEFAULT_SLEEP_BETWEEN_BATCHES = 0.1

CHUNK_SIZE = 1600
CHUNK_OVERLAP = 100
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Status values
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_ALREADY_EXISTS = "already_exists"
STATUS_SKIPPED = "skipped"
STATUS_PROCESSING = "processing"
