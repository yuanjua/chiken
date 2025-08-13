from typing import Any

from pydantic import BaseModel, Field


class SearchState(BaseModel):
    # Input
    current_user_message_content: str = ""
    mention_documents: list[dict[str, Any]] = Field(default_factory=list)

    # Intermediate
    generated_query: str | None = None
    search_results: list[dict[str, Any]] = Field(default_factory=list)

    # Output
    ranked_results: list[dict[str, Any]] = Field(default_factory=list)
