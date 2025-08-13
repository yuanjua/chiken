from typing import List


def paper_comment_prompt(user_question: str, title: str, abstract: str, source: str) -> str:
    return (
        "You are a meticulous research assistant. Given a user's question and a paper candidate, "
        "write a concise 1-2 sentence assessment of the paper's relevance and what insight it may offer. "
        "Avoid generic statements. Reference concrete aspects from the title/abstract that connect to the user question.\n\n"
        f"User Question: {user_question}\n"
        f"Source: {source}\n"
        f"Title: {title}\n"
        f"Abstract: {abstract[:1200]}\n\n"
        "Comment:"
    )



def get_search_query_prompt(user_question: str, history_context: str, context_hint: str) -> str:
    """Prompt to generate a focused arXiv search query string.
    Returns plain-text query; no quotes or code fences.
    """
    return (
        "You are a research scientist. Produce a focused arXiv search query for the latest user message.\n"
        "Prioritize the latest message and the mentioned documents. Use previous context only if it clearly disambiguates pronouns or references like 'same/continue'.\n"
        "Constraints: Output ONLY a plain text query without site prefixes and without quotes or code fences.\n"
        "Do not repeat document titles verbatim; extract core concepts, models, tasks, and methods instead.\n"
        "Prefer precise technical terms (models, datasets, tasks, methods) over generic words. Keep 5–12 tokens.\n\n"
        f"Latest User Message: {user_question}\n\n"
        f"{context_hint}"
        f"{history_context}"
    )


def get_rank_prompt(user_question: str, serialized_candidates: str) -> str:
    """Prompt to rank candidates with concise justification."""
    return (
        "You are an expert research scientist. Rank the following papers for relevance to the user's question.\n"
        "Return a JSON array of objects with fields: id (original index), relevance_score (1-10), justification (≤8 words, factual, specific).\n"
        "Be concise. No extra text before or after the JSON.\n\n"
        f"User Question: {user_question}\n\n"
        f"Candidates (use id from bracket):\n{serialized_candidates}\n\n"
        "JSON:"
    )


def get_synthesis_prompt(user_question: str, context_snippets: List[str]) -> str:
    """Prompt to synthesize a brief 3-5 sentence summary from top papers."""
    return (
        "You are an expert research scientist. Given the user's question and top candidate papers, "
        "write a brief synthesis (3-5 sentences) that summarizes key findings and how they relate to the user's question. "
        "Be concise, factual, and avoid speculation.\n\n"
        f"User Question: {user_question}\n\n"
        f"Top Papers:\n" + "\n".join(context_snippets) + "\n\n"
        "Synthesis:"
    )

