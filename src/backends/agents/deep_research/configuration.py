"""Configuration management for the Deep Research system."""

from typing import Any, Optional
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field


class Configuration(BaseModel):
    """Configuration for the Deep Research agent."""
    
    # Core research parameters
    allow_clarification: bool = Field(default=True)
    max_concurrent_research_units: int = Field(default=3) 
    max_researcher_iterations: int = Field(default=10)
    max_react_tool_calls: int = Field(default=15)
    max_structured_output_retries: int = Field(default=3)
    
    # Token limits for different model tasks
    clarification_max_tokens: int = Field(default=2048)
    research_brief_max_tokens: int = Field(default=4096)
    compression_max_tokens: int = Field(default=8192)
    final_report_max_tokens: int = Field(default=12000)
    tool_wrapper_max_tokens: int = Field(default=4096)

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        # Use defaults since you have your own LLM factory
        return cls()
