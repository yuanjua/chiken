"""
Tool Wrapper Library for LLM Models without Native Tool Support

This library enables tool calling for models that don't natively support it
(like gemma3:27b) using Instructor + LiteLLM for structured output extraction.

It provides a drop-in replacement for .bind_tools() that works with any model.
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, Union, Callable
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, render_text_description
import instructor
import litellm
from loguru import logger
from ...llm.chatlitellm import LLM


class ToolCall(BaseModel):
    """Structured representation of a tool call."""
    name: str = Field(description="Name of the tool to call")
    args: Dict[str, Any] = Field(description="Arguments to pass to the tool")
    reasoning: Optional[str] = Field(description="Why this tool was chosen", default=None)


class ToolChoice(BaseModel):
    """Structured output for tool selection - focused on research tools only."""
    should_use_tool: bool = Field(description="Whether a research tool should be used")
    tool_calls: List[ToolCall] = Field(description="List of research tool calls to make", default_factory=list)
    reasoning: str = Field(description="Reasoning for tool usage decision")


class ToolWrapperLLM:
    """
    Wrapper that adds tool calling capability to any LLM using Instructor + LiteLLM.
    
    This provides a drop-in replacement for LangChain's .bind_tools() functionality
    for models that don't natively support tool calling.
    """
    
    def __init__(
        self, 
        model: str, 
        tools: List[BaseTool] = None,
        parallel_tool_calls: bool = True,
        tool_choice: str = "auto",
    ):
        """
        Initialize the tool wrapper.
        
        Args:
            model: Model name (e.g., "ollama/gemma3:27b")
            tools: List of LangChain tools to bind
            parallel_tool_calls: Whether to allow parallel tool calls
            tool_choice: Tool choice strategy ("auto", "any", "none", or tool name)
        """
        # Convert model name for LiteLLM compatibility
        self.model = model
        self.tools = tools or []
        self.parallel_tool_calls = parallel_tool_calls
        self.tool_choice = tool_choice
        
        # Filter out think_tool since we'll handle that deterministically
        self.research_tools = [t for t in self.tools if getattr(t, 'name', '') != 'think_tool']
        
        self.client = instructor.from_litellm(
            litellm.acompletion,  # Use async completion
            mode=instructor.Mode.JSON
        )
                    
        self._tool_descriptions = render_text_description(self.research_tools) if self.research_tools else "No tools available."
    
    def _create_tool_prompt(self, messages: List[Dict]) -> str:
        """Create a focused prompt for research tool selection only."""
        
        # Convert the conversation history into a readable format
        formatted_history = []
        for msg in messages:
            if hasattr(msg, 'type'):  # LangChain message
                msg_type = getattr(msg, 'type', 'unknown')
                content = getattr(msg, 'content', '')
                
                if msg_type == 'human':
                    formatted_history.append(f"<human>: {content}")
                elif msg_type == 'ai':
                    formatted_history.append(f"<assistant>: {content}")
                    # Include tool calls if present
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            tool_name = tool_call.get('name', 'unknown_tool')
                            tool_args = tool_call.get('args', {})
                            formatted_history.append(f"<assistant_tool_call>: {tool_name}({tool_args})")
                elif msg_type == 'system':
                    formatted_history.append(f"<system>: {content}")
                elif msg_type == 'tool':
                    tool_name = getattr(msg, 'name', 'unknown_tool')
                    formatted_history.append(f"<tool_result:{tool_name}>: {content}")
                else:
                    formatted_history.append(f"<{msg_type}>: {content}")
            elif isinstance(msg, dict):
                # Convert dict to readable format
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                formatted_history.append(f"<{role}>: {content}")
        
        conversation = "\n".join(formatted_history)
        
        prompt = f"""
<conversation_history>
{conversation}
</conversation_history>

<available_research_tools>
{self._tool_descriptions}
</available_research_tools>

You are a research assistant. Based on this conversation, analyze if any RESEARCH TOOLS should be used to gather more information.

Your focus should be on calling research tools to gather information:
- **search_documents**: Search internal knowledge base 
- **web_meta_search_tool**: Search the web for current information
- **get_document_by_id**: Retrieve specific documents

Guidelines for research tool usage:
1. Use research tools when you need to search for information or access external systems
2. Don't use tools if you can answer directly from conversation context
3. If multiple research tools are needed, you can call them in parallel
4. Always provide reasoning for your tool choice decisions
5. Focus on RESEARCH TOOLS ONLY - thinking will be handled separately

Think step by step:
1. What information is the human asking for?
2. Do I have enough information from the conversation to answer directly?
3. If not, which research tool(s) would help gather the needed information?
4. What arguments should I pass to each research tool?

"""
        return prompt
    
    async def ainvoke(self, messages: List[Any]) -> AIMessage:
        """
        Async version of invoke that processes messages and returns an AIMessage with tool calls.
        """
        prompt = self._create_tool_prompt(messages)
        
        try:
            # Extract the actual content from messages for LiteLLM
            formatted_messages = []
            for msg in messages:
                if hasattr(msg, 'type') and hasattr(msg, 'content'):
                    role = "user" if msg.type == "human" else "assistant" if msg.type == "ai" else "system"
                    formatted_messages.append({"role": role, "content": str(msg.content)})
                elif isinstance(msg, dict):
                    formatted_messages.append(msg)
            
            # Add the tool analysis prompt as the latest user message
            formatted_messages.append({"role": "user", "content": prompt})
            
            # Get structured output from the model
            result = await self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                response_model=ToolChoice,
                max_tokens=4096,
                temperature=0.1
            )
            
            # Convert to AIMessage format
            if result.should_use_tool and result.tool_calls:
                # Format tool calls for LangChain and normalize them
                raw_tool_calls = [
                    {
                        "name": tool_call.name,
                        "args": tool_call.args,
                        "id": f"call_{i}"
                    }
                    for i, tool_call in enumerate(result.tool_calls)
                ]
                
                # Apply normalization to fix missing/malformatted arguments
                tool_calls = normalize_tool_calls(raw_tool_calls)
                
                return AIMessage(
                    content=result.reasoning,
                    tool_calls=tool_calls
                )
            else:
                # No tools needed, return regular response
                return AIMessage(content=result.reasoning)
                    
        except Exception as e:
            logger.error(f"Error in ToolWrapperLLM: {e}")
            # Fallback to simple text response
            return AIMessage(content="I need to search for more information to answer your question properly.")
        
    def invoke(self, messages: List[Any]) -> AIMessage:
        """
        Synchronous version of ainvoke.
        """
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we need to use run_in_executor or similar
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.ainvoke(messages))
                    return future.result()
            else:
                return loop.run_until_complete(self.ainvoke(messages))
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(self.ainvoke(messages))


def bind_tools_with_instructor(
    model: str,
    tools: List[BaseTool],
    parallel_tool_calls: bool = True,
    tool_choice: str = "auto"
) -> ToolWrapperLLM:
    """
    Create a tool-wrapped LLM instance that can be used as a drop-in replacement 
    for LangChain's .bind_tools() method.
    
    Args:
        model: Model identifier for LiteLLM
        tools: List of LangChain tools to bind
        parallel_tool_calls: Whether to allow parallel tool execution
        tool_choice: Tool choice strategy
    
    Returns:
        ToolWrapperLLM instance that can make tool calls
    
    Example:
        ```python
        tools = [search_tool, calculator_tool]
        model_with_tools = bind_tools_with_instructor(
            model="ollama/gemma3:27b",
            tools=tools
        )
        
        response = await model_with_tools.ainvoke([
            HumanMessage(content="Search for the latest AI news")
        ])
        ```
    """
    return ToolWrapperLLM(
        model=model,
        tools=tools,
        parallel_tool_calls=parallel_tool_calls,
        tool_choice=tool_choice
    )

def normalize_tool_calls(tool_calls):
    """Normalize tool calls to ensure consistent format."""
    normalized_calls = []
    
    for tc in tool_calls:
        # Create a new normalized tool call
        norm_tc = {
            "id": tc.get("id", f"call_{len(normalized_calls)}"),
            "name": tc.get("name", ""),
            "args": {}
        }
        
        # Extract args properly based on different possible formats
        args = tc.get("args", {})
        if isinstance(args, dict):
            norm_tc["args"] = args
        elif isinstance(args, str):
            # Try to parse JSON string args
            try:
                norm_tc["args"] = json.loads(args)
            except:
                # If not valid JSON, use as single argument
                if tc.get("name") == "ConductResearch":
                    norm_tc["args"] = {"research_topic": args}
                else:
                    norm_tc["args"] = {"text": args}
        
        # For ConductResearch, ensure research_topic exists
        if tc.get("name") == "ConductResearch" and "research_topic" not in norm_tc["args"]:
            # If there's only one arg and it's not named, assume it's research_topic
            if len(norm_tc["args"]) == 1 and "text" in norm_tc["args"]:
                norm_tc["args"]["research_topic"] = norm_tc["args"]["text"]
                del norm_tc["args"]["text"]
            elif len(norm_tc["args"]) == 1:
                # If only one arg with any name, use its value as research_topic
                first_key = list(norm_tc["args"].keys())[0]
                norm_tc["args"]["research_topic"] = norm_tc["args"][first_key]
        
        normalized_calls.append(norm_tc)
    
    return normalized_calls

def create_model_with_tools(llm: LLM, tools: List[BaseTool], config_dict: dict, retries: int = 3):
    """
    Create a model with tools, using smart fallback from native to wrapper.
    
    Args:
        model_name: The model name (e.g., "ollama:gemma3:27b")
        tools: List of tools to bind
        config_dict: Model configuration dictionary
        retries: Number of retries for structured output
    
    Returns:
        Model with tools bound, either natively or via wrapper
    """
    # Try native binding first for all models
    model_name = llm.model_name
    try:
        # TODO: implement real tool wrapper
        # assert litellm.supports_function_calling(model_name)
        native_model = (
            llm
            .bind_tools(tools)
            .with_retry(stop_after_attempt=retries)
            .with_config(config_dict)
        )
        logger.info(f"Native tool binding successful for {model_name}")
        return native_model
        
    except Exception:        
        # Fallback to tool wrapper
        try:
            wrapper_model = bind_tools_with_instructor(
                model=model_name,
                tools=tools,
                tool_choice="any",
            )
            logger.info(f"Tool wrapper binding successful for {model_name}")
            return wrapper_model
            
        except Exception as wrapper_error:
            logger.error(f"Tool wrapper binding failed for {model_name}: {wrapper_error}")
            raise wrapper_error
