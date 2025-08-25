from langchain_core.tools import tool

from ...tools.chroma.read_tools import (
    get_document_by_id,
    query_documents_with_context,
    search_documents,
    get_collection_info,
    peek_collection,
    list_collections
)

from ...tools.web import web_meta_search_tool

tools_list = [
    # tool(query_documents_with_context),
    tool(get_document_by_id),
    tool(search_documents),
    tool(web_meta_search_tool),
    # tool(get_collection_info),
    # tool(peek_collection),
    # tool(list_collections),
]
