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
from litellm import completion
from loguru import logger


class ToolCall(BaseModel):
    """Structured representation of a tool call."""
    name: str = Field(description="Name of the tool to call")
    args: Dict[str, Any] = Field(description="Arguments to pass to the tool")
    reasoning: Optional[str] = Field(description="Why this tool was chosen", default=None)


class ToolChoice(BaseModel):
    """Structured output for tool selection."""
    should_use_tool: bool = Field(description="Whether a tool should be used")
    tool_calls: List[ToolCall] = Field(description="List of tool calls to make", default_factory=list)
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
        base_url: str = "http://localhost:11435"
    ):
        """
        Initialize the tool wrapper.
        
        Args:
            model: Model name (e.g., "ollama/gemma3:27b")
            tools: List of LangChain tools to bind
            parallel_tool_calls: Whether to allow parallel tool calls
            tool_choice: Tool choice strategy ("auto", "any", "none", or tool name)
            base_url: Base URL for the model API
        """
        # Convert model name for LiteLLM compatibility
        self.model = model.replace("ollama:", "ollama/") if "ollama:" in model else model
        self.tools = tools or []
        self.parallel_tool_calls = parallel_tool_calls
        self.tool_choice = tool_choice
        self.base_url = base_url
        
        # Create instructor client
        self.client = instructor.from_litellm(
            completion,
            mode=instructor.Mode.JSON
        )
        
        # Build tool descriptions for the prompt using LangChain's built-in renderer
        try:
            print(f"🔧 ToolWrapperLLM: Initializing with {len(self.tools)} tools")
            for i, tool in enumerate(self.tools):
                print(f"   Tool {i}: {type(tool)} - {getattr(tool, 'name', 'NO_NAME')} - {getattr(tool, 'description', 'NO_DESC')[:50]}...")
            
            self._tool_descriptions = render_text_description(self.tools) if self.tools else "No tools available."
            print(f"✅ Tool descriptions rendered successfully")
        except Exception as e:
            print(f"❌ Failed to render tool descriptions: {e}")
            # Fallback to manual description
            descriptions = []
            for tool in self.tools:
                tool_name = getattr(tool, 'name', getattr(tool, '__name__', str(tool)))
                tool_desc = getattr(tool, 'description', 'No description available')
                descriptions.append(f"- {tool_name}: {tool_desc}")
            self._tool_descriptions = "\n".join(descriptions) if descriptions else "No tools available."
    
    def _create_tool_prompt(self, messages: List[Dict]) -> str:
        """Create a prompt that encourages tool usage when appropriate."""
        
        # Get the last user message - handle both dict and LangChain message objects
        user_content = ""
        for msg in reversed(messages):
            # Handle both dict and LangChain message objects
            if hasattr(msg, 'type'):  # LangChain message
                if getattr(msg, 'type', '') == 'human':
                    user_content = getattr(msg, 'content', '')
                    break
            elif isinstance(msg, dict):  # Dictionary format
                if msg.get("role") == "user":
                    user_content = msg.get("content", "")
                    break
        
        tool_choice_instruction = ""
        if self.tool_choice == "any":
            tool_choice_instruction = "You MUST use at least one tool to respond."
        elif self.tool_choice == "none":
            tool_choice_instruction = "Do NOT use any tools. Respond directly."
        else:  # auto or specific tool
            tool_choice_instruction = "Use tools if they would be helpful for this request."
        
        prompt = f"""You are an AI assistant with access to tools. Analyze the user's request and determine if you should use any tools.

Available Tools:
{self._tool_descriptions}

User Request: {user_content}

Instructions:
- {tool_choice_instruction}
- If using tools, provide the exact tool name and arguments needed
- Think step by step about whether tools would be helpful
- You can use multiple tools if needed (parallel_tool_calls={self.parallel_tool_calls})

Respond with your tool usage decision and reasoning."""

        return prompt
    
    def _convert_messages_to_dict(self, messages: List) -> List[Dict]:
        """Convert LangChain message objects to dictionary format."""
        converted_messages = []
        for msg in messages:
            if hasattr(msg, 'type'):  # LangChain message
                msg_type = getattr(msg, 'type', 'unknown')
                content = getattr(msg, 'content', '')
                
                if msg_type == 'human':
                    converted_messages.append({"role": "user", "content": content})
                elif msg_type == 'ai':
                    converted_messages.append({"role": "assistant", "content": content})
                elif msg_type == 'system':
                    converted_messages.append({"role": "system", "content": content})
                else:
                    converted_messages.append({"role": "user", "content": str(content)})
            elif isinstance(msg, dict):
                converted_messages.append(msg)
            else:
                # Fallback for unknown message types
                converted_messages.append({"role": "user", "content": str(msg)})
        
        return converted_messages
    
    async def ainvoke(self, messages: List, config: Dict = None) -> AIMessage:
        """
        Async invoke with tool calling capability.
        
        Args:
            messages: List of message dictionaries
            config: Optional configuration
            
        Returns:
            AIMessage with potential tool calls
        """
        print(f"🚀 ToolWrapperLLM.ainvoke called with model: {self.model}")
        print(f"   Messages: {len(messages)} messages")
        print(f"   Tools available: {len(self.tools)}")
        
        # Convert messages to dict format for processing
        messages_dict = self._convert_messages_to_dict(messages)
        print(f"   Converted to {len(messages_dict)} dict messages")
        
        if not self.tools:
            print("⚠️  No tools available, calling model directly")
            # No tools bound, just call the model directly
            response = await completion(
                model=self.model,
                messages=messages_dict,
                base_url=self.base_url
            )
            return AIMessage(content=response.choices[0].message.content)
        
        # Create tool selection prompt
        tool_prompt = self._create_tool_prompt(messages)
        
        # Use instructor to get structured tool choice
        print(f"🤔 Making tool decision with prompt length: {len(tool_prompt)}")
        try:
            tool_decision = self.client.chat.completions.create(
                model=self.model,
                response_model=ToolChoice,
                messages=[{"role": "user", "content": tool_prompt}],
                base_url=self.base_url,
                max_retries=2
            )
            print(f"✅ Tool decision successful: should_use_tool={tool_decision.should_use_tool}, tool_calls={len(tool_decision.tool_calls) if tool_decision.tool_calls else 0}")
        except Exception as e:
            print(f"❌ Tool decision failed: {e}")
            print(f"   Falling back to direct model call")
            # Fallback: call model directly
            response = await completion(
                model=self.model,
                messages=messages_dict,
                base_url=self.base_url
            )
            return AIMessage(content=response.choices[0].message.content)
        
        # If no tools should be used, get direct response
        if not tool_decision.should_use_tool or not tool_decision.tool_calls:
            response = await completion(
                model=self.model,
                messages=messages_dict,
                base_url=self.base_url
            )
            return AIMessage(content=response.choices[0].message.content)
        
        # Execute tool calls
        tool_calls_data = []
        tool_results = []
        
        # Create tools lookup
        tools_by_name = {}
        for tool in self.tools:
            tool_name = getattr(tool, 'name', getattr(tool, '__name__', str(tool)))
            tools_by_name[tool_name] = tool
        
        for i, tool_call in enumerate(tool_decision.tool_calls):
            if tool_call.name not in tools_by_name:
                continue
                
            tool = tools_by_name[tool_call.name]
            call_id = f"call_{i}"
            
            # Add to tool calls data (for AIMessage)
            tool_calls_data.append({
                "name": tool_call.name,
                "args": tool_call.args,
                "id": call_id,
                "type": "tool_call"
            })
            
            # Execute tool with proper argument handling
            try:
                # Handle DuckDuckGo search special case - convert query to queries list
                args = tool_call.args
                if tool_call.name == "duckduckgo_search" and "query" in args and "queries" not in args:
                    args = {**args, "queries": [args.pop("query")]}
                
                print(f"🔧 Executing {tool_call.name} with args: {str(args)[:100]}...")
                
                if asyncio.iscoroutinefunction(tool.func):
                    result = await tool.ainvoke(args)
                else:
                    result = tool.invoke(args)
                    
                print(f"✅ {tool_call.name} completed: {str(result)[:200]}...")
                tool_results.append(result)
            except Exception as e:
                error_msg = f"Error executing {tool_call.name}: {str(e)}"
                print(f"❌ {error_msg}")
                tool_results.append(error_msg)
        
        # Now generate final response incorporating tool results
        if tool_results:
            print(f"🔧 Tool execution completed. Generating final response with {len(tool_results)} results...")
            
            # Create a comprehensive prompt with tool results
            tool_results_text = ""
            for i, (tool_call, result) in enumerate(zip(tool_decision.tool_calls, tool_results)):
                tool_results_text += f"\n\nTool {i+1} ({tool_call.name}) Results:\n{str(result)[:2000]}..."
            
            final_prompt = f"""Based on the original user request and the tool execution results below, provide a comprehensive final response.

Original request: {messages_dict[-1].get('content', '') if messages_dict else ''}

Tool execution results:{tool_results_text}

Your reasoning: {tool_decision.reasoning}

Please provide a comprehensive, well-structured response that incorporates the information gathered from the tools. Be specific, cite sources when available, and provide detailed analysis."""

            # Get final response from the model
            try:
                from litellm import acompletion
                final_response = await acompletion(
                    model=self.model,
                    messages=[{"role": "user", "content": final_prompt}],
                    base_url=self.base_url
                )
                final_content = final_response.choices[0].message.content
                print(f"✅ Final response generated: {len(final_content)} chars")
                
                # Create AI message with tool calls and comprehensive content
                ai_message = AIMessage(
                    content=final_content,
                    tool_calls=tool_calls_data
                )
                
                return ai_message
                
            except Exception as e:
                print(f"❌ Failed to generate final response: {e}")
                # Fallback to basic response with tool results
                combined_content = f"{tool_decision.reasoning}\n\nTool Results Summary:{tool_results_text[:1000]}..."
                
                ai_message = AIMessage(
                    content=combined_content,
                    tool_calls=tool_calls_data
                )
                
                return ai_message
        else:
            # No tool results - return reasoning only
            ai_message = AIMessage(
                content=f"I'll help you with that. Let me use the available tools.\n\nReasoning: {tool_decision.reasoning}",
                tool_calls=tool_calls_data
            )
            
            return ai_message
    
    def invoke(self, messages: List[Dict], config: Dict = None) -> AIMessage:
        """Synchronous invoke wrapper."""
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.ainvoke(messages, config))
                    return future.result()
            else:
                return loop.run_until_complete(self.ainvoke(messages, config))
        except RuntimeError:
            # No event loop, safe to use asyncio.run
            return asyncio.run(self.ainvoke(messages, config))


def bind_tools_with_instructor(
    model: str,
    tools: List[BaseTool],
    parallel_tool_calls: bool = True,
    tool_choice: str = "auto",
    base_url: str = "http://localhost:11435"
) -> ToolWrapperLLM:
    """
    Create a tool-wrapped LLM that mimics LangChain's .bind_tools() behavior.
    
    This is a drop-in replacement for models that don't support native tool calling.
    
    Args:
        model: Model name (e.g., "ollama/gemma3:27b")
        tools: List of LangChain tools to bind
        parallel_tool_calls: Whether to allow parallel tool calls
        tool_choice: Tool choice strategy
        base_url: Base URL for the model API
    
    Returns:
        ToolWrapperLLM instance that can be used like a bound LangChain model
    """
    return ToolWrapperLLM(
        model=model,
        tools=tools,
        parallel_tool_calls=parallel_tool_calls,
        tool_choice=tool_choice,
        base_url=base_url
    )


# Example usage and test functions
async def test_tool_wrapper():
    """Test the tool wrapper with a simple tool."""
    from langchain_core.tools import tool
    
    @tool
    def add_numbers(a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b
    
    @tool
    def get_weather(city: str) -> str:
        """Get weather information for a city."""
        return f"The weather in {city} is sunny and 75°F"
    
    # Create tool wrapper
    wrapped_llm = bind_tools_with_instructor(
        model="ollama/gemma3:27b",
        tools=[add_numbers, get_weather],
        tool_choice="auto"
    )
    
    # Test tool calling
    messages = [
        {"role": "user", "content": "What's 15 + 27? Also, what's the weather like in San Francisco?"}
    ]
    
    try:
        result = await wrapped_llm.ainvoke(messages)
        print("Tool wrapper test result:")
        print(f"Content: {result.content}")
        print(f"Tool calls: {result.tool_calls}")
        return True
    except Exception as e:
        print(f"Tool wrapper test failed: {e}")
        return False


if __name__ == "__main__":
    # Run test
    print("Testing Tool Wrapper Library...")
    success = asyncio.run(test_tool_wrapper())
    if success:
        print("Tool wrapper is working!")
    else:
        print("Tool wrapper test failed.")
