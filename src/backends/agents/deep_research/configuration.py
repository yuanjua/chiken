"""Configuration management for the Deep Research system."""

from typing import Any, Optional
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field


class Configuration(BaseModel):
    """Simplified configuration for the Deep Research agent."""
    
    # Core research parameters
    allow_clarification: bool = Field(default=True)
    max_concurrent_research_units: int = Field(default=3) 
    max_researcher_iterations: int = Field(default=5)
    max_react_tool_calls: int = Field(default=8)
    max_structured_output_retries: int = Field(default=3)

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        # Use defaults since you have your own LLM factory
        return cls()
