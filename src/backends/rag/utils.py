"""
Utility functions for RAG text processing.
"""

import re

from langchain_core.documents import Document


# slow on some os, to be implemented in onnx
def remove_references(texts: list[Document], threshold: float = 0.5) -> list[Document]:
    """
    Removes references and citations from a string.
    """
    pass


def remove_extra_newlines(text: str) -> str:
    """
    Removes newline characters (\n) from a string unless they mark the end of a
    sentence. This is useful for cleaning up text extracted from PDFs where
    line breaks are often inserted arbitrarily.

    Args:
        text: The input string with potentially misplaced newlines.

    Returns:
        A cleaned string with unnecessary newlines removed.
    """
    if not text:
        return text

    # First preserve paragraph breaks (double newlines) by replacing them temporarily
    text = text.replace("\n\n", "<!PARAGRAPH_BREAK!>")

    # Replace all remaining single newlines with spaces
    # This ensures tables with numbers and other content don't get corrupted
    cleaned_text = text.replace("\n", " ")

    # Restore paragraph breaks
    cleaned_text = cleaned_text.replace("<!PARAGRAPH_BREAK!>", "\n\n")

    # Clean up multiple spaces that might have been created
    cleaned_text = re.sub(r" +", " ", cleaned_text)

    return cleaned_text.strip()
