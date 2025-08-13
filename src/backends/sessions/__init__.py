"""
Session Management Module

This module provides session management functionality for chat agents,
including persistence, state management, and lifecycle handling.
"""

from .manager import SessionManager, get_session_manager

__all__ = ["SessionManager", "get_session_manager"]
