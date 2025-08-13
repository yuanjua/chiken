from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, END
from .chat_graph.state import SessionState

def convert_to_basemessages(messages: List[Any]) -> List[BaseMessage]:
    """Convert a list of message-like objects to LangChain BaseMessage instances."""
    converted = []
    for msg in messages:
        role = getattr(msg, 'role', 'user').lower()
        content = getattr(msg, 'content', str(msg))
        if role == 'user' or role == 'human':
            converted.append(HumanMessage(content=content))
        elif role == 'assistant' or role == 'ai':
            converted.append(AIMessage(content=content))
        elif role == 'system':
            converted.append(SystemMessage(content=content))
    return converted

def truncate_think_tag(text: str) -> str:
    """
    Remove <think>...</think> tags if present in the text.
    
    Args:
        text: Text to process
        
    Returns:
        Clean text without think tags
    """
    if "<think>" in text and "</think>" in text:
        return text.split("<think>")[0].strip() + text.split("</think>")[1].strip()
    return text.strip()