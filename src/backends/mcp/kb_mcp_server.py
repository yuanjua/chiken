from fastmcp import FastMCP

mcp = FastMCP("chiken-knowledge-bases")

from ..tools.read_tools import (
    list_collections,
    get_collection_info,
    peek_collection,
    search_documents,
    query_documents_with_context,
    get_document_by_id
)
from ..tools.web import meta_search_tool

mcp.tool()(search_documents)
mcp.tool()(query_documents_with_context)
mcp.tool()(get_document_by_id)

mcp.tool()(list_collections)
mcp.tool()(get_collection_info)
mcp.tool()(peek_collection)

mcp.tool()(meta_search_tool)