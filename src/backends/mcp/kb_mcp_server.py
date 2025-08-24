from fastmcp import FastMCP

mcp = FastMCP("chiken-knowledge-bases")

from ..tools.chroma.read_tools import (
    get_collection_info,
    get_document_by_id,
    list_collections,
    peek_collection,
    query_documents_with_context,
    search_documents,
)
from ..tools.web import web_meta_search_tool

mcp.tool()(search_documents)
mcp.tool()(query_documents_with_context)
mcp.tool()(get_document_by_id)

mcp.tool()(list_collections)
mcp.tool()(get_collection_info)
mcp.tool()(peek_collection)

mcp.tool()(web_meta_search_tool)
