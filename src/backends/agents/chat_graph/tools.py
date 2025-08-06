from langchain_core.tools import tool

from ...tools.read_tools import (
    search_documents,
    query_documents_with_context,
    get_document_by_id
)

tools_list = [
    tool(search_documents),
    tool(query_documents_with_context),
    tool(get_document_by_id)
]
