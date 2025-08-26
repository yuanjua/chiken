"""Utility functions and helpers for the Deep Research agent."""

from datetime import datetime, timezone
from typing import List
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from loguru import logger

from .tools import tools_list as custom_tools
from .state import ResearchComplete

def get_today_str() -> str:
    """Get today's date as a string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@tool(description="Strategic reflection tool for research planning")
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"


async def get_all_tools(config: RunnableConfig = None) -> List[BaseTool]:
    """
    Get all available tools for the research agent.
    
    Returns:
        List of research tools only (think_tool handled deterministically)
    """
    tools = [tool(ResearchComplete), think_tool]
    
    tools.extend(custom_tools)
    
    return tools


def get_model_token_limit(model_name: str) -> int:
    """
    Get the token limit for a given model.
    
    Args:
        model_name: The name of the model
        
    Returns:
        The token limit for the model
    """
    # Default token limits for common models
    token_limits = {
        # OpenAI models
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-3.5-turbo": 4096,
        
        # Anthropic models
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        "claude-3-5-sonnet": 200000,
        
        # Default fallback
        "default": 4096
    }
    
    # Check for exact match first
    if model_name in token_limits:
        return token_limits[model_name]
    
    # Check for partial matches
    for model_key, limit in token_limits.items():
        if model_key in model_name.lower():
            return limit
    
    # Return default if no match found
    return token_limits["default"]


def is_token_limit_exceeded(content: str, model_name: str, buffer: int = 1000) -> bool:
    """
    Check if content would exceed the model's token limit.
    
    Args:
        content: The content to check
        model_name: The name of the model
        buffer: Buffer to leave for response tokens
        
    Returns:
        True if the content would exceed the token limit
    """
    # Rough estimate: 1 token ≈ 4 characters
    estimated_tokens = len(content) // 4
    
    limit = get_model_token_limit(model_name)
    
    return estimated_tokens > (limit - buffer)


def get_notes_from_tool_calls(messages):
    """Extract notes from tool call results."""
    notes = []
    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'tool':
            notes.append(str(msg.content))
    return notes


def remove_up_to_last_ai_message(messages):
    """Remove messages up to the last AI message to handle token limits."""
    if not messages:
        return messages
    
    # Find last AI message
    last_ai_index = -1
    for i, msg in enumerate(messages):
        if hasattr(msg, 'type') and msg.type == 'ai':
            last_ai_index = i
    
    if last_ai_index >= 0:
        return messages[last_ai_index:]
    return messages


def openai_websearch_called(message) -> bool:
    """Check if OpenAI web search was called."""
    # This is a placeholder - implement based on your OpenAI web search detection logic
    return False


def anthropic_websearch_called(message) -> bool:
    """Check if Anthropic web search was called."""
    # This is a placeholder - implement based on your Anthropic web search detection logic
    return False
