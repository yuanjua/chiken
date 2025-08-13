"""
Custom exceptions for the RAG service layer.
These exceptions should be caught and converted to HTTP responses in the API layer.
"""

class RAGServiceError(Exception):
    """Base exception for all RAG service errors."""
    pass

class KnowledgeBaseNotFound(RAGServiceError):
    """Raised when a knowledge base cannot be found."""
    pass

class KnowledgeBaseAlreadyExists(RAGServiceError):
    """Raised when trying to create a knowledge base that already exists."""
    pass

class DocumentProcessingError(RAGServiceError):
    """Raised when document processing fails."""
    pass

class DuplicateDocumentError(RAGServiceError):
    """Raised when a document already exists in the knowledge base."""
    pass

class InvalidDocumentError(RAGServiceError):
    """Raised when a document is invalid or cannot be processed."""
    pass

class EmbeddingError(RAGServiceError):
    """Raised when embedding operations fail."""
    pass

class DatabaseError(RAGServiceError):
    """Raised when database operations fail."""
    pass

class ValidationError(RAGServiceError):
    """Raised when input validation fails."""
    pass
