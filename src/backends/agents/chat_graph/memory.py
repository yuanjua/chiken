"""
Memory utility functions for the LangGraph Chat Agent.

This module contains utility functions for managing conversation memory,
including summarization, entity extraction, and memory updates.
"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from loguru import logger

from .prompts import get_memory_update_prompt, get_summarization_prompt
from .state import SessionState

# logger is imported from loguru


def update_conversation_history(state: SessionState) -> dict[str, Any]:
    """
    Update conversation history with the new exchange.

    Args:
        state: The current session state

    Returns:
        Dict containing updated messages and message_count
    """
    logger.debug("--- Node: Update Conversation History ---")

    # Create the new messages
    user_message = HumanMessage(content=state.current_user_message_content)
    ai_message = AIMessage(content=state.current_ai_response_content)

    # Add to the conversation
    state.messages.append(user_message)
    state.messages.append(ai_message)
    state.message_count += 2

    # Track new messages for database persistence (use valid field name)
    if not hasattr(state, "new_messages_to_save"):
        state.new_messages_to_save = []
    state.new_messages_to_save.extend([user_message, ai_message])

    if len(state.messages) > state.max_history_length * 2:
        state.messages = state.messages[-state.max_history_length * 2 :]

    return {
        "messages": state.messages,
        "message_count": state.message_count,
    }


def should_update_long_term_memory(state: SessionState) -> str:
    """
    Conditional edge: decide if long-term memory should be updated.

    Args:
        state: The current session state

    Returns:
        str: "update_summary" if memory should be updated, "end_turn" otherwise
    """
    logger.debug("--- Conditional Edge: Should Update Long-Term Memory? ---")
    if state.message_count > 0 and (state.message_count // 2) % state.memory_update_frequency == 0:
        logger.debug("Decision: YES, update long-term memory.")
        return "update_summary"
    logger.debug("Decision: NO, skip long-term memory update.")
    return "end_turn"


async def update_conversation_summary(state: SessionState, llm: BaseChatModel) -> dict[str, Any]:
    """
    Update conversation summary using async LLM calls.

    Args:
        state: The current session state
        llm: The language model to use for summarization

    Returns:
        Dict containing updated conversation_summary or empty dict if error
    """
    logger.debug("--- Node: Update Summary ---")
    history_to_summarize = format_messages_for_llm_text(state.messages[-8:])

    prompt = get_summarization_prompt(history_to_summarize)
    try:
        summary_response = await llm.ainvoke([HumanMessage(content=prompt)])
        new_summary = summary_response.content
        updated_summary = (new_summary + "\n" + state.conversation_summary)[:500]
        return {"conversation_summary": updated_summary.strip()}
    except Exception as e:
        logger.error(f"Error during summarization: {e}")
        return {}


async def extract_and_update_entities(state: SessionState, llm: BaseChatModel) -> dict[str, Any]:
    """
    Extract and update key topics and user preferences using async LLM calls.

    Args:
        state: The current session state
        llm: The language model to use for entity extraction

    Returns:
        Dict containing updated key_topics and user_preferences or empty dict if error
    """
    logger.debug("--- Node: Extract and Update Entities ---")
    if not llm or not getattr(llm, "is_available", False):
        return {}

    user_msg = state.current_user_message_content
    ai_msg = state.current_ai_response_content

    if not user_msg or not ai_msg:
        return {}

    prompt = get_memory_update_prompt(user_msg, ai_msg)
    try:
        analysis_response = await llm.ainvoke([HumanMessage(content=prompt)])
        updates = parse_memory_analysis(analysis_response.content)

        new_topics = state.key_topics.copy()
        for topic in updates.get("topics", []):
            if topic not in new_topics:
                new_topics.append(topic)

        new_preferences = state.user_preferences.copy()
        new_preferences.update(updates.get("preferences", {}))

        return {
            "key_topics": new_topics[-10:],
            "user_preferences": {k: new_preferences[k] for k in list(new_preferences.keys())[-10:]},
        }
    except Exception as e:
        logger.error(f"Error during entity extraction: {e}")
        return {}


def format_messages_for_llm_text(messages: list[BaseMessage]) -> str:
    """
    Helper to format messages into a single string for text-based operations.

    Args:
        messages: List of LangChain BaseMessage instances

    Returns:
        str: Formatted message history as text
    """
    texts = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            texts.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            texts.append(f"Assistant: {msg.content}")
    return "\n".join(texts)


def format_messages_for_llm_prompt(messages: list[BaseMessage]) -> str:
    """
    Format a list of LangChain messages into a complete prompt string.

    Args:
        messages: List of LangChain BaseMessage instances

    Returns:
        str: Complete formatted prompt with role prefixes
    """
    parts = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            parts.append(f"System: {msg.content}")
        elif isinstance(msg, HumanMessage):
            parts.append(f"Human: {msg.content}")
        elif isinstance(msg, AIMessage):
            parts.append(f"Assistant: {msg.content}")

    parts.append("Assistant:")
    return "\n\n".join(parts)


def parse_memory_analysis(analysis_text: str) -> dict[str, Any]:
    """
    Parse memory analysis text into structured data.

    Args:
        analysis_text: Raw text output from LLM memory analysis

    Returns:
        Dict containing parsed topics, preferences, and important information
    """
    updates = {"topics": [], "preferences": {}, "important": []}
    lines = analysis_text.split("\n")
    for line in lines:
        line_l = line.lower().strip()
        if line_l.startswith("topics:"):
            topics_text = line.split(":", 1)[1].strip()
            if topics_text.lower() not in ["none", "[list of topics]", ""]:
                updates["topics"] = [t.strip() for t in topics_text.split(",") if t.strip()]
        elif line_l.startswith("preferences:"):
            prefs_text = line.split(":", 1)[1].strip()
            if prefs_text.lower() not in ["none", "[key: value pairs]", ""]:
                for pref in prefs_text.split(","):
                    if ":" in pref:
                        key, value = pref.split(":", 1)
                        updates["preferences"][key.strip()] = value.strip()
        elif line_l.startswith("important:"):
            important_text = line.split(":", 1)[1].strip()
            if important_text.lower() not in ["none", "[key information to remember]", ""]:
                updates["important"] = [important_text]
    return updates
