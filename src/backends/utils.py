import os
import httpx
from typing import Dict, Any, List, Union, Optional
from markdownify import markdownify
from datetime import datetime
from loguru import logger

def get_config_value(value: Any) -> str:
    """
    Convert configuration values to string format, handling both string and enum types.
    
    Args:
        value (Any): The configuration value to process. Can be a string or an Enum.
    
    Returns:
        str: The string representation of the value.
    """
    return value if isinstance(value, str) else value.value

def get_current_date() -> str:
    """Get current date in a readable format."""
    return datetime.now().strftime("%B %d, %Y")

def deduplicate_and_format_sources(
    search_response: Union[Dict[str, Any], List[Dict[str, Any]]], 
    max_tokens_per_source: int = 1000, 
    fetch_full_page: bool = False
) -> str:
    """
    Format and deduplicate search responses from various search APIs.
    
    Args:
        search_response: Either a dict with 'results' key or list of search results
        max_tokens_per_source: Maximum number of tokens to include for each source's content
        fetch_full_page: Whether to include the full page content
            
    Returns:
        str: Formatted string with deduplicated sources
    """
    # Convert input to list of results
    if isinstance(search_response, dict):
        sources_list = search_response.get('results', [])
    elif isinstance(search_response, list):
        sources_list = []
        for response in search_response:
            if isinstance(response, dict) and 'results' in response:
                sources_list.extend(response['results'])
            elif isinstance(response, dict):
                sources_list.append(response)
            else:
                sources_list.extend(response)
    else:
        return "No sources available."
    
    if not sources_list:
        return "No sources found."
    
    # Deduplicate by URL
    unique_sources = {}
    for source in sources_list:
        url = source.get('url', '')
        if url and url not in unique_sources:
            unique_sources[url] = source
    
    # Format output
    formatted_text = "Sources:\n\n"
    for i, source in enumerate(unique_sources.values(), 1):
        title = source.get('title', 'Untitled')
        url = source.get('url', '')
        content = source.get('content', '')
        
        formatted_text += f"Source {i}: {title}\n===\n"
        formatted_text += f"URL: {url}\n===\n"
        formatted_text += f"Most relevant content from source: {content}\n===\n"
        
        if fetch_full_page:
            # Using rough estimate of 4 characters per token
            char_limit = max_tokens_per_source * 4
            raw_content = source.get('raw_content', '')
            if raw_content is None:
                raw_content = content
            if len(raw_content) > char_limit:
                raw_content = raw_content[:char_limit] + "... [truncated]"
            formatted_text += f"Full source content limited to {max_tokens_per_source} tokens: {raw_content}\n\n"
        else:
            formatted_text += "\n"
                
    return formatted_text.strip()

def format_sources(search_results: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
    """
    Format search results into a bullet-point list of sources with URLs.
    
    Args:
        search_results: Search response containing results
        
    Returns:
        str: Formatted string with sources as bullet points
    """
    if isinstance(search_results, dict):
        results = search_results.get('results', [])
    else:
        results = search_results
    
    if not results:
        return "No sources available."
        
    return '\n'.join(
        f"* {source.get('title', 'Untitled')} : {source.get('url', '')}"
        for source in results
        if source.get('url')
    )

def fetch_raw_content(url: str) -> Optional[str]:
    """
    Fetch HTML content from a URL and convert it to markdown format.
    
    Args:
        url: The URL to fetch content from
        
    Returns:
        Optional[str]: The fetched content converted to markdown if successful
    """
    try:                
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return markdownify(response.text)
    except Exception as e:
        logger.warning(f"Warning: Failed to fetch full page content for {url}: {str(e)}")
        return None

def duckduckgo_search(query: str, max_results: int = 3, fetch_full_page: bool = False) -> List[Dict[str, Any]]:
    """
    Search the web using DuckDuckGo and return formatted results.
    
    Args:
        query: The search query to execute
        max_results: Maximum number of results to return
        fetch_full_page: Whether to fetch full page content from result URLs
        
    Returns:
        List of search result dictionaries
    """
    try:
        # Import here to avoid startup issues
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = []
            # Set shorter timeout for DDGS
            search_results = list(ddgs.text(query, max_results=max_results, safesearch='moderate'))
            
            for r in search_results:
                url = r.get('href')
                title = r.get('title')
                content = r.get('body')
                
                if not all([url, title, content]):
                    logger.warning(f"Warning: Incomplete result from DuckDuckGo: {r}")
                    continue

                raw_content = content
                if fetch_full_page:
                    try:
                        raw_content = fetch_raw_content(url) or content
                    except Exception as e:
                        logger.warning(f"Failed to fetch full content for {url}: {e}")
                        raw_content = content
                
                result = {
                    "title": title,
                    "url": url,
                    "content": content,
                    "raw_content": raw_content
                }
                results.append(result)
            
            return results
            
    except ImportError:
        logger.error("Error: duckduckgo_search package not installed")
        return []
    except Exception as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            logger.warning(f"DuckDuckGo search timeout for query '{query}' - network may be slow")
        else:
            logger.error(f"Error in DuckDuckGo search for '{query}': {error_msg}")
        return []

def format_zotero_results(zotero_items: List[Dict[str, Any]]) -> str:
    """
    Format Zotero search results into a readable string.
    
    Args:
        zotero_items: List of Zotero item dictionaries
        
    Returns:
        str: Formatted string with Zotero sources
    """
    if not zotero_items:
        return "No Zotero sources found."
    
    formatted_text = "Zotero Sources:\n\n"
    for i, item in enumerate(zotero_items, 1):
        title = item.get('title', 'Unknown Title')
        authors = item.get('authors', [])
        year = item.get('year', 'Unknown Year')
        
        author_str = ', '.join(authors) if authors else 'Unknown Author'
        formatted_text += f"{i}. {title} ({author_str}, {year})\n"
        
        if 'abstract' in item:
            abstract = item['abstract'][:200] + "..." if len(item['abstract']) > 200 else item['abstract']
            formatted_text += f"   Abstract: {abstract}\n"
        formatted_text += "\n"
    
    return formatted_text.strip()

def safe_llm_invoke(llm, messages, fallback_content="Unable to process due to LLM unavailability"):
    """Safely invoke LLM with fallback."""
    try:
        return llm.invoke(messages)
    except Exception as e:
        logger.warning(f"LLM call failed: {e}, using fallback")
        return type('Response', (), {'content': fallback_content})()

def create_llm_instance(base_url: str, model: str, temperature: float = 0.1, format: Optional[str] = None):
    """Create LLM instance with error handling - legacy compatibility function."""
    # Import the new LLM factory
    from .llm.factory import create_llm_instance as new_create_llm_instance
    
    # Use the new factory method which maintains backward compatibility
    return new_create_llm_instance(base_url, model, temperature, format) 