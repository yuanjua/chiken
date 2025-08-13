import loguru
from datetime import datetime
from typing import Dict, Any, Optional, AsyncGenerator, List, TYPE_CHECKING
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Assuming these imports are correctly set up from your project structure
from ...user_config import UserConfig
from .state import SessionState
from .prompts import get_context_aware_prompt, get_simple_query_prompt, get_academic_search_query_prompt
from .memory import (
    update_conversation_history,
    should_update_long_term_memory,
    update_conversation_summary,
    extract_and_update_entities
)
from .tools import query_documents_with_context, search_documents, get_document_by_id
from ...tools.utils import get_active_knowledge_bases
from ..utils import convert_to_basemessages, truncate_think_tag

logger = loguru.logger


def should_run_rag(state: SessionState) -> str:
    """
    This is the condition function for the RAG graph's conditional edge.
    It checks the 'run_rag' flag in the state to decide the next step.
    """
    if state.run_rag:
        return "generate_rag_query"
    else:
        return END

class AgentGraphs:
    """Manages the RAG, generation, and memory graphs for the agent."""

    def __init__(self, user_config: UserConfig, llm: BaseChatModel, checkpointer: Optional[AsyncSqliteSaver] = None):
        self.user_config = user_config
        self.checkpointer = checkpointer
        self.llm = llm
        self.rag_app = None
        self.generation_app = None
        self.memory_app = None

        self.build_rag_workflow()
        self.build_generation_workflow()
        self.build_memory_workflow()
        logger.info("✅ Agent graphs (RAG, Generation, Memory) initialized")

    # --- RAG Workflow Nodes ---
    async def decide_rag_necessity(self, state: SessionState) -> Dict[str, Any]:
        """Determines if RAG should be executed and sets the run_rag flag."""
        has_keys = bool(getattr(state, "document_keys", None))
        has_kbs = bool(await get_active_knowledge_bases())
        
        if has_keys or has_kbs:
            logger.info("RAG required: Proceeding to generate query.")
            return {"run_rag": True}
        
        logger.info("RAG not required. Skipping RAG workflow.")
        return {"run_rag": False}

    async def generate_rag_query(self, state: SessionState) -> Dict[str, Any]:
        """Generates a search query from the user's message."""
        history = ""
        recent_messages = state.messages[-4:]

        def truncate_middle(text, max_length=400):
            half = max_length // 2
            return text[:half] + " ... " + text[-half:]
        
        for msg in recent_messages:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            history += f"{role}: {truncate_middle(msg.content)}....\n"

        user_question = state.current_user_message_content
        
        # Use the academic search query prompt
        prompt = get_simple_query_prompt(user_question, history)
        
        response = await self.llm.ainvoke(prompt)
        query = truncate_think_tag(response.content.strip().replace('"', ''))
        logger.info(f"Generated RAG Query: '{query}'")
        return {"rag_query": query}

    async def perform_rag_search(self, state: SessionState) -> Dict[str, Any]:
        """Performs semantic search using the generated query."""
        query = state.rag_query
        keys = getattr(state, "document_keys", None)
        if keys:
            logger.info(f"Performing RAG search on specific keys: {keys}")
            # Import RAGService to query specific documents by keys
            from ...rag.service import RAGService
            results = await RAGService.query_documents(
                query_text=query, 
                keys=keys, 
                k=10
            )
        else:
            logger.info("Performing RAG search on all active knowledge bases.")
            results = await search_documents(query, n_results=16)
        return {"rag_results": results}

    def format_rag_context(self, state: SessionState) -> Dict[str, Any]:
        """Formats the raw search results into a clean context string."""
        results = getattr(state, "rag_results", [])
        if not results:
            return {"rag_context": ""}
        
        rag_context = "The following information from a knowledge base may be relevant to the user's question.\n\n--- RELEVANT INFORMATION ---\n"
        for result in results:
            content = result.get('content', 'N/A')
            title = result.get('metadata', {}).get('title', 'Source')
            rag_context += f"[{title}]: {content}\n\n"
        rag_context += "--- END OF INFORMATION ---\nIf this information is relevant, use it to inform your answer. If it is not relevant, ignore it and answer the user's question from your general knowledge."
        return {"rag_context": rag_context}

    # --- Generation Workflow Node ---
    def prepare_final_prompt(self, state: SessionState) -> Dict[str, Any]:
        """Prepares the final prompt, injecting conversational and RAG context."""
        logger.debug("--- Node: Prepare Final Prompt ---")
        context_memory_prompt = get_context_aware_prompt(
            state.conversation_summary, state.key_topics, state.user_preferences
        )
        effective_system_prompt = state.system_prompt_content or ""
        if context_memory_prompt:
            effective_system_prompt = f"{effective_system_prompt}\n\n{context_memory_prompt}"

        if state.rag_context:
            effective_system_prompt = f"{state.rag_context}\n{effective_system_prompt}"
            logger.info("Injecting pre-formatted RAG context into the final prompt.")

        messages_for_llm: List[BaseMessage] = [SystemMessage(content=effective_system_prompt)]
        messages_for_llm.extend(convert_to_basemessages(state.messages))
        messages_for_llm.append(HumanMessage(content=state.current_user_message_content))
        return {"prepared_messages": messages_for_llm}

    # --- Memory Workflow Nodes ---
    def save_conversation_exchange(self, state: SessionState) -> Dict[str, Any]:
        """
        Short-term memory only: do NOT mutate persistent history here.
        SessionManager is responsible for persisting the user/assistant turn.
        Keep state.messages unchanged; just keep counters in sync.
        """
        state.message_count = len(state.messages)
        return {"messages": state.messages, "message_count": state.message_count}

    def check_memory_update_needed(self, state: SessionState) -> str:
        return should_update_long_term_memory(state)

    async def update_conversation_summary(self, state: SessionState) -> Dict[str, Any]:
        return await update_conversation_summary(state, self.llm)

    async def extract_key_entities_and_preferences(self, state: SessionState) -> Dict[str, Any]:
        return await extract_and_update_entities(state, self.llm)
    
    async def generate_title(self, state: SessionState) -> Dict[str, str]:
        """Generates a title for the conversation and adds it to the state."""
        if state.title != "New Chat" or state.message_count < 2:
            return {}

        logger.debug("--- Generating title for session ---")
        # Accessing content from BaseMessage objects correctly
        first_user_msg_content = next((msg.content for msg in state.messages if isinstance(msg, HumanMessage)), "")
        
        if not first_user_msg_content:
            return {}
            
        prompt = f"Generate a short, descriptive title (3-5 words) for a conversation starting with:\n\nUser: {first_user_msg_content[:150]}\n\nRespond with only the title."
        
        try:
            response = await self.llm.ainvoke(prompt)
            title = truncate_think_tag(response.content.strip().strip('"\''))
            logger.info(f"Generated title: '{title}'")
            return {"title": title[:50]}
        except Exception as e:
            logger.error(f"Failed to generate title: {e}")
            return {}

    # --- Workflow Builders ---
    
    def build_rag_workflow(self):
        """Builds a self-contained graph for all RAG operations."""
        workflow = StateGraph(SessionState)
        
        workflow.add_node("decide_rag_necessity", self.decide_rag_necessity)
        workflow.add_node("generate_rag_query", self.generate_rag_query)
        workflow.add_node("perform_rag_search", self.perform_rag_search)
        workflow.add_node("format_rag_context", self.format_rag_context)

        workflow.set_entry_point("decide_rag_necessity")
        workflow.add_conditional_edges(
            "decide_rag_necessity",
            should_run_rag,
            {"generate_rag_query": "generate_rag_query", END: END}
        )

        workflow.add_edge("generate_rag_query", "perform_rag_search")
        workflow.add_edge("perform_rag_search", "format_rag_context")
        workflow.add_edge("format_rag_context", END)
        
        self.rag_app = workflow.compile()
        logger.info("✅ RAG workflow compiled")

    def build_generation_workflow(self):
        """Builds a simplified workflow for preparing the final LLM prompt."""
        workflow = StateGraph(SessionState)
        workflow.add_node("prepare_final_prompt", self.prepare_final_prompt)
        workflow.set_entry_point("prepare_final_prompt")
        workflow.add_edge("prepare_final_prompt", END)
        self.generation_app = workflow.compile()
        logger.info("✅ Generation workflow compiled")

    def build_memory_workflow(self):
        """Builds the memory workflow for updating history, LTM, and title."""
        workflow = StateGraph(SessionState)
        workflow.add_node("save_exchange", self.save_conversation_exchange)
        workflow.add_node("update_summary", self.update_conversation_summary)
        workflow.add_node("extract_entities", self.extract_key_entities_and_preferences)
        workflow.add_node("generate_title", self.generate_title)
        
        workflow.set_entry_point("save_exchange")
        workflow.add_conditional_edges(
            "save_exchange",
            self.check_memory_update_needed,
            {"update_summary": "update_summary", "end_turn": "generate_title"}
        )
        workflow.add_edge("update_summary", "extract_entities")
        workflow.add_edge("extract_entities", "generate_title")
        workflow.add_edge("generate_title", END)

        if self.checkpointer:
            self.memory_app = workflow.compile(checkpointer=self.checkpointer)
        else:
            self.memory_app = workflow.compile()
        logger.info("✅ Memory workflow compiled")
