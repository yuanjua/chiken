"""
Prompts for the LangGraph Chat Agent.

This module contains prompt templates for various LangGraph workflow operations.
"""

import json
from typing import List, Dict, Any


def get_summarization_prompt(messages_text: str) -> str:
    """Generate a prompt for conversation summarization."""
    return f"Please summarize the following conversation concisely:\n\n{messages_text}\n\nSummary:"


def get_memory_update_prompt(user_message: str, assistant_response: str) -> str:
    """Generate a prompt for extracting memory updates from a conversation exchange."""
    return f"""
Analyze the following exchange:
User: {user_message}
Assistant: {assistant_response}

Extract the following:
Topics: [list of new, comma-separated topics discussed, if any. Otherwise, write 'None']
Preferences: [key: value pairs of user preferences revealed, if any. Otherwise, write 'None']
Important: [any new critical piece of information to remember, if any. Otherwise, write 'None']
"""


def get_context_aware_prompt(conversation_summary: str, key_topics: List[str], user_preferences: Dict[str, Any]) -> str:
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
    return f"""Based on the latest user message, and the conversation history **only if** relevant to the current user question,
generate a concise, one-sentence search query of 1-4 key phrases. The query should synthesize the context to accurately find relevant documents.

<Conversation_History>
{history}
</Conversation_History>

Latest User Message: "{user_question}"

Search Query:"""

def get_academic_search_query_prompt(user_question: str, history: str = "") -> str:
    """Generate a prompt for converting user questions into academic search queries."""
    prompt = f"""You are an expert research assistant. Your task is to convert a user's question and the preceding conversation into a high-quality search query. This query will be used to find relevant academic papers and scientific literature.

<Instructions>
1.  **Analyze the Goal:** Identify the core research question, hypothesis, methodology, or concept the user is asking about.
2.  **Extract Key Terms:** Pull out specific, technical terminology, model names, contextual keywords, or scientific concepts from conversation histories and user questions. Avoid generic words.
3.  **Formulate the Query:** Construct a concise query that a researcher would type into a search engine like Google Scholar or arXiv. The query should be a statement of concepts, not a natural language question.
</Instructions>

<Conversation_History>
{history}
</Conversation_History>

Latest User Message: "{user_question}"

Based on the instructions and examples, generate the optimal academic search query.

Academic Search Query:"""
    return prompt


DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant. You provide clear, accurate, and helpful responses to user questions. 
You are friendly, professional, and aim to be as helpful as possible while being concise and to the point.

Guidelines:
- Be helpful and informative
- Keep responses concise but complete
- If you don't know something, say so honestly
- Be friendly and conversational
- Avoid overly technical jargon unless specifically asked"""