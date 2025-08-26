from langchain_core.tools import tool

from ...tools.chroma.read_tools import get_document_by_id, query_documents_with_context, search_documents

tools_list = [tool(search_documents), tool(query_documents_with_context), tool(get_document_by_id)]
