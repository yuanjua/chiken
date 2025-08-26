"""
Modified from https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/deep_researcher.py
"""

import asyncio
import json
from typing import Literal
from collections import defaultdict

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    filter_messages,
    get_buffer_string,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, render_text_description
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from loguru import logger

from .configuration import Configuration
from .prompts import (
    clarify_with_user_instructions,
    compress_research_simple_human_message,
    compress_research_system_prompt,
    final_report_generation_prompt,
    lead_researcher_prompt,
    research_system_prompt,
    transform_messages_into_research_topic_prompt,
)
from .state import (
    AgentInputState,
    AgentState,
    ClarifyWithUser,
    ConductResearch,
    ResearchComplete,
    ResearcherOutputState,
    ResearcherState,
    ResearchQuestion,
    SupervisorState,
)
from .utils import (
    get_all_tools,
    get_today_str,
    get_model_token_limit,
    is_token_limit_exceeded,
)
from .tool_wrapper import create_model_with_tools
from .utils import think_tool

# Helper function to get LLM for specific tasks
def get_llm_for_task(config: RunnableConfig, schema=None, max_tokens=None, retries=3):
    """Get the user's LLM instance configured for a specific task."""
    llm = config.get("configurable", {}).get("llm_instance")
    if not llm:
        raise ValueError("No LLM instance provided in config")
    
    # Configure for this specific task
    if schema:
        llm = llm.with_structured_output(schema)
    if retries:
        llm = llm.with_retry(stop_after_attempt=retries)
    if max_tokens:
        llm = llm.with_config({"max_tokens": max_tokens})
    
    return llm


def get_notes_from_tool_calls(messages):
    """Extract notes from tool call results."""
    notes = []
    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'tool':
            notes.append(str(msg.content))
    return notes


def remove_up_to_last_ai_message(messages):
    """Remove messages up to the last AI message to handle token limits."""
    if not messages:
        return messages
    
    # Find last AI message
    last_ai_index = -1
    for i, msg in enumerate(messages):
        if hasattr(msg, 'type') and msg.type == 'ai':
            last_ai_index = i
    
    if last_ai_index >= 0:
        return messages[last_ai_index:]
    return messages


# ==================== MAIN WORKFLOW NODES ====================

async def clarify_with_user(state: AgentState, config: RunnableConfig) -> Command[Literal["write_research_brief", "__end__"]]:
    """Analyze user messages and ask clarifying questions if the research scope is unclear."""
    configurable = Configuration.from_runnable_config(config)
    if not configurable.allow_clarification:
        return Command(goto="write_research_brief")
    
    messages = state["messages"]
    clarification_model = get_llm_for_task(
        config,
        schema=ClarifyWithUser,
        max_tokens=configurable.clarification_max_tokens,
        retries=configurable.max_structured_output_retries
    )
    
    prompt_content = clarify_with_user_instructions.format(
        messages=get_buffer_string(messages), 
        date=get_today_str()
    )
    response = await clarification_model.ainvoke([HumanMessage(content=prompt_content)])
    
    # Handle response
    try:
        if response is None:
            raise ValueError("Empty structured response")
        if not hasattr(response, "need_clarification"):
            if isinstance(response, dict):
                response = ClarifyWithUser.model_validate(response)
            else:
                response = ClarifyWithUser(
                    need_clarification=False,
                    question="",
                    verification="Acknowledged. Proceeding with research based on your request."
                )
    except Exception:
        response = ClarifyWithUser(
            need_clarification=False,
            question="",
            verification="Acknowledged. Proceeding with research based on your request."
        )
    
    if response.need_clarification:
        return Command(
            goto=END, 
            update={"messages": [AIMessage(content=response.question)]}
        )
    else:
        return Command(
            goto="write_research_brief", 
            update={"messages": [AIMessage(content=response.verification)]}
        )


async def write_research_brief(state: AgentState, config: RunnableConfig) -> Command[Literal["research_supervisor"]]:
    """Transform user messages into a structured research brief and initialize supervisor."""
    configurable = Configuration.from_runnable_config(config)
    research_model = get_llm_for_task(
        config,
        schema=ResearchQuestion,
        max_tokens=configurable.research_brief_max_tokens,
        retries=configurable.max_structured_output_retries
    )
    
    prompt_content = transform_messages_into_research_topic_prompt.format(
        messages=get_buffer_string(state.get("messages", [])),
        date=get_today_str()
    )
    response = await research_model.ainvoke([HumanMessage(content=prompt_content)])
    
    # Handle response
    try:
        if response is None:
            raise ValueError("Empty structured response")
        if not hasattr(response, "research_brief"):
            if isinstance(response, dict):
                response = ResearchQuestion.model_validate(response)
            else:
                fallback_brief = get_buffer_string(state.get("messages", [])) or "Research the user's request."
                response = ResearchQuestion(research_brief=fallback_brief)
    except Exception:
        fallback_brief = get_buffer_string(state.get("messages", [])) or "Research the user's request."
        response = ResearchQuestion(research_brief=fallback_brief)
    
    supervisor_system_prompt = lead_researcher_prompt.format(
        date=get_today_str(),
        max_concurrent_research_units=configurable.max_concurrent_research_units,
        max_researcher_iterations=configurable.max_researcher_iterations
    )
    
    return Command(
        goto="research_supervisor", 
        update={
            "research_brief": response.research_brief,
            "supervisor_messages": {
                "type": "override",
                "value": [
                    SystemMessage(content=supervisor_system_prompt),
                    HumanMessage(content=response.research_brief)
                ]
            }
        }
    )


async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor_tools"]]:
    """Lead research supervisor that plans research strategy and delegates to researchers."""
    configurable = Configuration.from_runnable_config(config)
    # Do not expose think_tool to the LLM; we'll inject reflections deterministically in the graph
    lead_researcher_tools = [tool(ConductResearch), tool(ResearchComplete), think_tool]
    
    llm = config.get("configurable", {}).get("llm_instance")
    if not llm:
        raise ValueError("No LLM instance provided in config")
    
    # Use wrapper chooser to avoid native function-calling on unsupported models
    research_model = create_model_with_tools(
        llm=llm,
        tools=lead_researcher_tools,
        config_dict={},
        retries=configurable.max_structured_output_retries,
        max_tokens=configurable.tool_wrapper_max_tokens,
    )
    
    supervisor_messages = state.get("supervisor_messages", [])
    response = await research_model.ainvoke(supervisor_messages)
    
    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": [response],
            "research_iterations": state.get("research_iterations", 0) + 1
        }
    )


async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor", "__end__"]]:
    """Execute tools called by the supervisor, including research delegation and strategic thinking.
    
    This function handles three types of supervisor tool calls:
    1. think_tool - Strategic reflection that continues the conversation
    2. ConductResearch - Delegates research tasks to sub-researchers
    3. ResearchComplete - Signals completion of research phase
    
    Args:
        state: Current supervisor state with messages and iteration count
        config: Runtime configuration with research limits and model settings
        
    Returns:
        Command to either continue supervision loop or end research phase
    """
    # Step 1: Extract current state and check exit conditions
    configurable = Configuration.from_runnable_config(config)
    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    most_recent_message = supervisor_messages[-1]
    
    # Define exit criteria for research phase
    exceeded_allowed_iterations = research_iterations > configurable.max_researcher_iterations
    no_tool_calls = not most_recent_message.tool_calls
    research_complete_tool_call = any(
        tool_call["name"] == "ResearchComplete" 
        for tool_call in most_recent_message.tool_calls
    )
    
    # Exit if any termination condition is met
    if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
        return Command(
            goto=END,
            update={
                "notes": get_notes_from_tool_calls(supervisor_messages),
                "research_brief": state.get("research_brief", "")
            }
        )
    
    # Step 2: Process all tool calls together (both think_tool and ConductResearch)
    all_tool_messages = []
    update_payload = {"supervisor_messages": []}
    
    # Handle think_tool calls (strategic reflection)
    think_tool_calls = [
        tool_call for tool_call in most_recent_message.tool_calls 
        if tool_call["name"] == "think_tool"
    ]
    
    for tool_call in think_tool_calls:
        reflection_content = tool_call["args"]["reflection"]
        all_tool_messages.append(ToolMessage(
            content=f"Reflection recorded: {reflection_content}",
            name="think_tool",
            tool_call_id=tool_call["id"]
        ))
    
    # Handle ConductResearch calls (research delegation)
    conduct_research_calls = [
        tool_call for tool_call in most_recent_message.tool_calls 
        if tool_call["name"] == "ConductResearch"
    ]
    
    if conduct_research_calls:
        try:
            # Limit concurrent research units to prevent resource exhaustion
            allowed_conduct_research_calls = conduct_research_calls[:configurable.max_concurrent_research_units]
            overflow_conduct_research_calls = conduct_research_calls[configurable.max_concurrent_research_units:]
            
            # Execute research tasks in parallel
            research_tasks = [
                researcher_subgraph.ainvoke({
                    "researcher_messages": [
                        HumanMessage(content=tool_call["args"]["research_topic"])
                    ],
                    "research_topic": tool_call["args"]["research_topic"]
                }, config) 
                for tool_call in allowed_conduct_research_calls
            ]
            
            tool_results = await asyncio.gather(*research_tasks)
            
            # Create tool messages with research results
            for observation, tool_call in zip(tool_results, allowed_conduct_research_calls):
                all_tool_messages.append(ToolMessage(
                    content=observation.get("compressed_research", "Error synthesizing research report: Maximum retries exceeded"),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"]
                ))
            
            # Handle overflow research calls with error messages
            for overflow_call in overflow_conduct_research_calls:
                all_tool_messages.append(ToolMessage(
                    content=f"Error: Did not run this research as you have already exceeded the maximum number of concurrent research units. Please try again with {configurable.max_concurrent_research_units} or fewer research units.",
                    name="ConductResearch",
                    tool_call_id=overflow_call["id"]
                ))
            
            # Aggregate raw notes from all research results
            raw_notes_concat = "\n".join([
                "\n".join(observation.get("raw_notes", [])) 
                for observation in tool_results
            ])
            
            if raw_notes_concat:
                update_payload["raw_notes"] = [raw_notes_concat]
                
        except Exception as e:
            # Handle research execution errors
            if is_token_limit_exceeded(e, configurable.research_model) or True:
                # Token limit exceeded or other error - end research phase
                return Command(
                    goto=END,
                    update={
                        "notes": get_notes_from_tool_calls(supervisor_messages),
                        "research_brief": state.get("research_brief", "")
                    }
                )
    
    # Step 3: Return command with all tool results
    update_payload["supervisor_messages"] = all_tool_messages
    return Command(
        goto="supervisor",
        update=update_payload
    )


# ==================== RESEARCHER SUBGRAPH ====================

async def researcher(state: ResearcherState, config: RunnableConfig) -> Command[Literal["researcher_tools"]]:
    """Individual researcher that conducts focused research with enhanced duplicate prevention."""
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError("No tools found to conduct research")
    
    tools_description = render_text_description(tools)
    researcher_prompt = research_system_prompt.format(
        tools_description=tools_description,
        mcp_prompt="",  # No MCP
        date=get_today_str()
    )
    
    llm = config.get("configurable", {}).get("llm_instance")
    if not llm:
        raise ValueError("No LLM instance provided in config")
    
    # Use wrapper chooser to avoid native function-calling on unsupported models
    research_model = create_model_with_tools(
        llm=llm,
        tools=tools,
        config_dict={},
        retries=configurable.max_structured_output_retries,
        max_tokens=configurable.tool_wrapper_max_tokens,
    )
    
    messages = [SystemMessage(content=researcher_prompt)] + researcher_messages
    response = await research_model.ainvoke(messages)
    
    return Command(
        goto="researcher_tools",
        update={
            "researcher_messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1
        }
    )


async def researcher_tools(state: ResearcherState, config: RunnableConfig) -> Command[Literal["researcher", "compress_research"]]:
    """Execute tools called by the researcher with robust duplicate prevention based on successful execution."""
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    most_recent_message = researcher_messages[-1]
    
    # Early exit if no tool calls
    if not most_recent_message.tool_calls:
        return Command(goto="compress_research")
    
    tools = await get_all_tools(config)
    tools_by_name = {
        tool.name if hasattr(tool, "name") else tool.get("name", "web_search"): tool 
        for tool in tools
    }
    
    # Step 1: Identify the IDs of all tool calls that were successfully executed (i.e., have a ToolMessage)
    executed_tool_call_ids = {
        getattr(msg, "tool_call_id", "") 
        for msg in researcher_messages[:-1] 
        if getattr(msg, "type", "") == "tool"
    }

    # Step 2: Build a history of prior SUCCESSFUL calls by looking at AIMessages that have a corresponding ToolMessage
    prior_calls = set()
    tool_call_counts = defaultdict(int)
    
    for prior_msg in researcher_messages[:-1]:
        if getattr(prior_msg, "type", "") == "ai" and getattr(prior_msg, "tool_calls", None):
            for prior_call in prior_msg.tool_calls:
                # Only consider it a "prior call" if it was actually executed
                if prior_call.get("id") in executed_tool_call_ids:
                    tool_name = prior_call.get("name", "unknown")
                    args = prior_call.get("args", {})
                    
                    tool_call_counts[tool_name] += 1
                    
                    # Add exact key for de-duplication
                    exact_key = (tool_name, json.dumps(args, sort_keys=True))
                    prior_calls.add(exact_key)

                    # Add normalized key for search tools
                    if tool_name in ["web_meta_search_tool", "search_documents"]:
                        normalized_args = {}
                        for k, v in args.items():
                            if isinstance(v, str):
                                normalized_args[k.lower().strip()] = v.lower().strip()
                            else:
                                normalized_args[k.lower().strip()] = v
                        normalized_key = (tool_name.lower(), json.dumps(normalized_args, sort_keys=True))
                        prior_calls.add(normalized_key)

    # Step 3: Filter the current batch of proposed tool calls against the history of successful ones
    tool_calls = most_recent_message.tool_calls
    seen_current = set()
    exec_calls = []
    duplicate_outputs = []
    current_tool_counts = defaultdict(int)
    
    for tc in tool_calls:
        tool_name = tc.get("name", "unknown")
        args = tc.get("args") or {}
        
        # Create exact key for the current call
        exact_key = (tool_name, json.dumps(args, sort_keys=True))
        
        # Check for exact duplicates
        if exact_key in prior_calls or exact_key in seen_current:
            logger.debug(f"Skipping exact duplicate: {tool_name} with args {args}")
            duplicate_outputs.append(ToolMessage(
                content=f"🚫 Duplicate call skipped: This exact tool call was already successfully executed.",
                name=tool_name,
                tool_call_id=tc.get("id")
            ))
            continue
            
        # For search tools, check normalized duplicates
        if tool_name in ["web_meta_search_tool", "search_documents"]:
            normalized_args = {k.lower().strip(): v.lower().strip() if isinstance(v, str) else v for k, v in args.items()}
            normalized_key = (tool_name.lower(), json.dumps(normalized_args, sort_keys=True))
            
            if normalized_key in prior_calls or normalized_key in seen_current:
                logger.debug(f"Skipping similar search: {tool_name} with normalized args {normalized_args}")
                duplicate_outputs.append(ToolMessage(
                    content=f"🚫 Similar search skipped: A very similar query was already successfully executed.",
                    name=tool_name,
                    tool_call_id=tc.get("id")
                ))
                continue
            seen_current.add(normalized_key)
        
        # Apply rate limiting
        total_calls_for_tool = tool_call_counts[tool_name] + current_tool_counts[tool_name]
        if total_calls_for_tool >= 4:
            logger.debug(f"Rate limiting {tool_name}: {total_calls_for_tool} calls already made")
            duplicate_outputs.append(ToolMessage(
                content=f"🚦 Rate limit reached for {tool_name}. Try a different tool or finalize the research.",
                name=tool_name,
                tool_call_id=tc.get("id")
            ))
            continue
        
        # Approved for execution
        seen_current.add(exact_key)
        current_tool_counts[tool_name] += 1
        exec_calls.append(tc)

    # Step 4: Execute the approved, non-duplicate tool calls
    async def execute_tool_safely(tool, args, config):
        try:
            return await tool.ainvoke(args, config)
        except Exception as e:
            return f"Error executing tool: {str(e)}"

    tool_execution_tasks = [execute_tool_safely(tools_by_name[tc["name"]], tc["args"], config) for tc in exec_calls]
    observations = await asyncio.gather(*tool_execution_tasks) if tool_execution_tasks else []
    
    tool_outputs = [
        ToolMessage(
            content=str(observation),
            name=tool_call["name"],
            tool_call_id=tool_call.get("id")
        ) for observation, tool_call in zip(observations, exec_calls)
    ] + duplicate_outputs
        
    # Check exit conditions
    exceeded_iterations = state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls
    research_complete_called = any(tool_call["name"] == "ResearchComplete" for tool_call in most_recent_message.tool_calls)
    
    if exceeded_iterations or research_complete_called:
        return Command(goto="compress_research", update={"researcher_messages": tool_outputs})
    
    return Command(goto="researcher", update={"researcher_messages": tool_outputs})


async def compress_research(state: ResearcherState, config: RunnableConfig):
    """Compress and synthesize research findings into a concise, structured summary."""
    configurable = Configuration.from_runnable_config(config)
    synthesizer_model = get_llm_for_task(config, max_tokens=configurable.compression_max_tokens)
    
    researcher_messages = state.get("researcher_messages", [])
    researcher_messages.append(HumanMessage(content=compress_research_simple_human_message))
    
    synthesis_attempts = 0
    max_attempts = 3
    
    while synthesis_attempts < max_attempts:
        try:
            compression_prompt = compress_research_system_prompt.format(date=get_today_str())
            messages = [SystemMessage(content=compression_prompt)] + researcher_messages
            
            response = await synthesizer_model.ainvoke(messages)
            
            raw_notes_content = "\n".join([
                str(message.content) 
                for message in filter_messages(researcher_messages, include_types=["tool", "ai"])
            ])
            
            return {
                "compressed_research": str(response.content),
                "raw_notes": [raw_notes_content]
            }
            
        except Exception as e:
            synthesis_attempts += 1
            
            if is_token_limit_exceeded(str(e), "user_model"):
                researcher_messages = remove_up_to_last_ai_message(researcher_messages)
                continue
            
            continue
    
    # Fallback
    raw_notes_content = "\n".join([
        str(message.content) 
        for message in filter_messages(researcher_messages, include_types=["tool", "ai"])
    ])
    
    return {
        "compressed_research": "Error synthesizing research report: Maximum retries exceeded",
        "raw_notes": [raw_notes_content]
    }


# ==================== FINAL REPORT GENERATION ====================

async def final_report_generation(state: AgentState, config: RunnableConfig):
    """Generate the final comprehensive research report with retry logic."""
    notes = state.get("notes", [])
    cleared_state = {"notes": {"type": "override", "value": []}}
    findings = "\n".join(notes)
    
    configurable = Configuration.from_runnable_config(config)
    
    max_retries = 3
    current_retry = 0
    
    while current_retry <= max_retries:
        try:
            final_report_prompt = final_report_generation_prompt.format(
                research_brief=state.get("research_brief", ""),
                messages=get_buffer_string(state.get("messages", [])),
                findings=findings,
                date=get_today_str()
            )
            
            report_model = get_llm_for_task(config, max_tokens=configurable.final_report_max_tokens)
            final_report = await report_model.ainvoke([
                HumanMessage(content=final_report_prompt)
            ])
            
            return {
                "final_report": final_report.content, 
                "messages": [final_report],
                **cleared_state
            }
            
        except Exception as e:
            if is_token_limit_exceeded(str(e), "user_model"):
                # Truncate findings by 30% and retry
                findings = findings[:int(len(findings) * 0.7)]
                current_retry += 1
                continue
            
            # Non-token errors
            current_retry += 1
            if current_retry > max_retries:
                return {
                    "final_report": f"Error generating final report: {str(e)}", 
                    "messages": [AIMessage(content=f"Error generating final report: {str(e)}")],
                    **cleared_state
                }
    
    # Max retries exceeded
    return {
        "final_report": "Error generating final report: Maximum retries exceeded", 
        "messages": [AIMessage(content="Error generating final report: Maximum retries exceeded")],
        **cleared_state
    }


# ==================== GRAPH CONSTRUCTION ====================

# Researcher Subgraph
researcher_builder = StateGraph(
    ResearcherState, 
    output=ResearcherOutputState, 
    config_schema=Configuration
)

researcher_builder.add_node("researcher", researcher)
researcher_builder.add_node("researcher_tools", researcher_tools)
researcher_builder.add_node("compress_research", compress_research)

researcher_builder.add_edge(START, "researcher")
researcher_builder.add_edge("compress_research", END)

researcher_subgraph = researcher_builder.compile()

# Supervisor Subgraph
supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)

supervisor_builder.add_node("supervisor", supervisor)
supervisor_builder.add_node("supervisor_tools", supervisor_tools)

supervisor_builder.add_edge(START, "supervisor")

supervisor_subgraph = supervisor_builder.compile()

# Main Agent Graph
builder = StateGraph(AgentState, input=AgentInputState, config_schema=Configuration)

builder.add_node("clarify_with_user", clarify_with_user)
builder.add_node("write_research_brief", write_research_brief)
builder.add_node("research_supervisor", supervisor_subgraph)
builder.add_node("final_report_generation", final_report_generation)

builder.add_edge(START, "clarify_with_user")
builder.add_edge("write_research_brief", "research_supervisor")
builder.add_edge("research_supervisor", "final_report_generation")
builder.add_edge("final_report_generation", END)

enhanced_deep_research_graph = builder.compile()
