from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SearchState(BaseModel):
    # Input
    current_user_message_content: str = ""
    mention_documents: List[Dict[str, Any]] = Field(default_factory=list)

    # Intermediate
    generated_query: Optional[str] = None
    search_results: List[Dict[str, Any]] = Field(default_factory=list)

    # Output
    ranked_results: List[Dict[str, Any]] = Field(default_factory=list)


