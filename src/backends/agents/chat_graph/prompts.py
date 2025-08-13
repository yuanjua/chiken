"""
Prompts for the LangGraph Chat Agent.

This module contains prompt templates for various LangGraph workflow operations.
"""

import json
from typing import Any


def get_summarization_prompt(messages_text: str) -> str:
    """Generate a prompt for conversation summarization."""
    return f"Please summarize the following conversation concisely:\n\n{messages_text}\n\nSummary:"


def get_memory_update_prompt(user_message: str, assistant_response: str) -> str:
    """Generate a prompt for extracting memory updates from a conversation exchange."""
    return (
        "Analyze the following exchange:\n"
        f"User: {user_message}\n"
        f"Assistant: {assistant_response}\n\n"
        "Extract the following:\n"
        "Topics: [list of new, comma-separated topics discussed, if any. Otherwise, write 'None']\n"
        "Preferences: [key: value pairs of user preferences revealed, if any. Otherwise, write 'None']\n"
        "Important: [any new critical piece of information to remember, if any. Otherwise, write 'None']\n"
    )


def get_context_aware_prompt(conversation_summary: str, key_topics: list[str], user_preferences: dict[str, Any]) -> str:
    """Generate a context-aware prompt that includes conversation memory."""
    context_parts = []
    if conversation_summary:
        context_parts.append(f"Previous Summary: {conversation_summary}")
    if key_topics:
        context_parts.append(f"Key Topics: {', '.join(key_topics)}")
    if user_preferences:
        context_parts.append(f"User Preferences: {json.dumps(user_preferences)}")

    if not context_parts:
        return ""
    return "Remember the following context:\n" + "\n".join(context_parts)


def get_simple_query_prompt(user_question: str, history: str) -> str:
    """Generate a simple query prompt for user questions."""
    return (
        "Based on the latest user message, and the conversation history **only if** relevant to the current user question,\n"
        "generate a concise, one-sentence search query of 1-4 key phrases. The query should synthesize the context to accurately find relevant documents.\n\n"
        "<Conversation_History>\n"
        f"{history}\n"
        "</Conversation_History>\n\n"
        f'Latest User Message: "{user_question}"\n\n'
        "Search Query:"
    )


def get_academic_search_query_prompt(user_question: str, history: str = "") -> str:
    """Generate a prompt for converting user questions into academic search queries."""
    prompt = (
        "You are an expert research assistant. Your task is to convert a user's question and the preceding conversation into a high-quality search query. "
        "This query will be used to find relevant academic papers and scientific literature.\n\n"
        "<Instructions>\n"
        "1.  **Analyze the Goal:** Identify the core research question, hypothesis, methodology, or concept the user is asking about.\n"
        "2.  **Extract Key Terms:** Pull out specific, technical terminology, model names, contextual keywords, or scientific concepts from conversation histories and user questions. Avoid generic words.\n"
        "3.  **Formulate the Query:** Construct a concise query that a researcher would type into a search engine like Google Scholar or arXiv. The query should be a statement of concepts, not a natural language question.\n"
        "</Instructions>\n\n"
        "<Conversation_History>\n"
        f"{history}\n"
        "</Conversation_History>\n\n"
        f'Latest User Message: "{user_question}"\n\n'
        "Based on the instructions and examples, generate the optimal academic search query.\n\n"
        "Academic Search Query:"
    )
    return prompt


DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. You provide clear, accurate, and helpful responses to user questions. \n"
    "You are friendly, professional, and aim to be as helpful as possible while being concise and to the point.\n\n"
    "Guidelines:\n"
    "- Be helpful and informative\n"
    "- Keep responses concise but complete\n"
    "- If you don't know something, say so honestly\n"
    "- Be friendly and conversational\n"
    "- Avoid overly technical jargon unless specifically asked"
)
