from typing import TypedDict, Annotated, List, Dict, Any, Sequence, Optional, Union

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import BaseTool, tool # Import tool decorator
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from app.config import settings
# Import the invocation helpers from sub-agents
from app.agents.sub_agents.analysis_agent import invoke_analysis_agent
from app.agents.sub_agents.docker_agent import invoke_docker_agent
from app.agents.sub_agents.k8s_agent import invoke_k8s_agent
from app.agents.sub_agents.terraform_agent import invoke_terraform_agent
# Keep history service and DB imports
from app.services.history_service import add_message_to_history, get_history_by_session_id
from app.database.database import AsyncSessionLocal
from app.database.models import MessageSender
import uuid

# 1. Define Supervisor State (remains the same)
class SupervisorState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]
    user_request: Dict[str, Any]
    session_id: str

# 2. Define Tools for the Supervisor (Wrappers invoking Sub-Agents)
# These tools are what the supervisor LLM will see and choose to call.
# Their docstrings guide the supervisor.

# NOTE: The input for these tools should be what the SUB-AGENT needs.
# Often, just passing the user query or relevant context is enough.
# We use 'query: str' for simplicity, but complex scenarios might need structured input.

@tool
async def analysis_sub_agent_tool(task_description: str) -> str:
    """Delegates a task to the Repository Analysis sub-agent.
    Formulate a clear and specific task_description for what this sub-agent should do.
    This description MUST include all necessary context from the user's request and previous steps
    (e.g., repository URL if analyzing a new repository, specific files or areas of focus)."""
    print(f"--- ANALYSIS SUB-AGENT TOOL: Received task_description ---\n{task_description}\n---")
    return await invoke_analysis_agent(task_description)

@tool
async def docker_sub_agent_tool(task_description: str) -> str:
    """Delegates a task to the Docker sub-agent.
    Formulate a clear and specific task_description for what this sub-agent should do (e.g., build an image).
    This description MUST include all necessary context from the user's request and previous steps
    (e.g., repository URL, project path within the repo, desired image name, Dockerfile location if non-standard)."""
    print(f"--- DOCKER SUB-AGENT TOOL: Received task_description ---\n{task_description}\n---")
    return await invoke_docker_agent(task_description)

@tool
async def k8s_sub_agent_tool(task_description: str) -> str:
    """Delegates a task to the Kubernetes sub-agent.
    Formulate a clear and specific task_description for what this sub-agent should do (e.g., deploy an application, check service status).
    This description MUST include all necessary context from the user's request and previous steps
    (e.g., Docker image name and tag, deployment name, namespace, specific configurations)."""
    print(f"--- K8S SUB-AGENT TOOL: Received task_description ---\n{task_description}\n---")
    return await invoke_k8s_agent(task_description)

@tool
async def terraform_sub_agent_tool(task_description: str) -> str:
    """Delegates a task to the Terraform sub-agent.
    Formulate a clear and specific task_description for what this sub-agent should do (e.g., plan infrastructure changes, apply a configuration).
    This description MUST include all necessary context from the user's request and previous steps
    (e.g., path to Terraform configuration files, specific variables, workspace)."""
    print(f"--- TERRAFORM SUB-AGENT TOOL: Received task_description ---\n{task_description}\n---")
    return await invoke_terraform_agent(task_description)

# List of tools available to the supervisor
supervisor_tools: List[BaseTool] = [
    analysis_sub_agent_tool,
    docker_sub_agent_tool,
    k8s_sub_agent_tool,
    terraform_sub_agent_tool
]

# 3. Define Supervisor LLM
#supervisor_llm = ChatOpenAI(temperature=0, streaming=True, api_key=settings.OPENAI_API_KEY)
supervisor_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17",
    temperature=0.8,
    max_tokens=None,
    timeout=None,
    max_retries=2
)
# Bind the *wrapper* tools to the supervisor LLM
supervisor_llm_with_wrapper_tools = supervisor_llm.bind_tools(supervisor_tools)

# 4. Define Nodes for the Supervisor Graph

async def supervisor_node(state: SupervisorState):
    """Invokes the supervisor LLM to determine the next action (call a sub-agent or respond)."""
    print(f"--- SUPERVISOR NODE: Current User Request ---\n{state['user_request']}\n---")
    print(f"--- SUPERVISOR NODE: Current Messages (excluding system prompt) ---\n{state['messages']}\n---")

    system_prompt = (
        "You are a supervisor agent. Your primary function is to understand the user's overall goal "
        "and delegate specific, well-defined tasks to specialized sub-agents. You have the following sub-agent tools available: "
        "analysis_sub_agent_tool, docker_sub_agent_tool, k8s_sub_agent_tool, terraform_sub_agent_tool. "
        "Carefully review the user's request and the conversation history. "
        "If a sub-agent is needed, choose the appropriate tool and formulate a comprehensive 'task_description' for it. "
        "This 'task_description' MUST contain all information and context the sub-agent requires to perform its job effectively. "
        "For example, if the user provided a repository URL, ensure it's included in the 'task_description' for relevant sub-agents. "
        "Extract necessary details from the user's message and prior steps. Do not perform tasks yourself. "
        "After a sub-agent completes its task, review the result and decide the next step: delegate another task or, "
        "if the overall goal is achieved, provide a final consolidated response to the user. "
        "If you are providing the final response, do not call any tools."
    )
    
    messages_for_llm = [SystemMessage(content=system_prompt)] + list(state["messages"])
    
    print(f"--- SUPERVISOR NODE: Messages sent to LLM (including system prompt) ---\n{messages_for_llm}\n---")
    # Use the LLM bound with wrapper tools
    response: AIMessage = await supervisor_llm_with_wrapper_tools.ainvoke(messages_for_llm)
    print(f"--- SUPERVISOR NODE: LLM Response ---\n{response}\n---")
    return {"messages": [response]}

# Tool Execution Node (now executes the wrapper tools that call sub-agents)
# We pass the new list of supervisor_tools (the wrappers)
sub_agent_executor_node = ToolNode(supervisor_tools) 

async def sub_agent_action_node(state: SupervisorState):
    """Executes the sub-agent wrapper tool chosen by the supervisor."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        print("--- SUB-AGENT ACTION NODE: No tool calls by supervisor. ---")
        return {"messages": []} 

    print(f"--- SUB-AGENT ACTION NODE: Supervisor Tool Calls ---\n{last_message.tool_calls}\n---")
    
    # ToolNode expects the AIMessage containing the tool calls as input.
    # It will then execute the corresponding wrapper tool.
    tool_messages = await sub_agent_executor_node.ainvoke(last_message)
    
    # Ensure result is a list for consistency
    if not isinstance(tool_messages, list):
        tool_messages = [tool_messages]
    
    print(f"--- SUB-AGENT ACTION NODE: Sub-Agent Results --- \n{tool_messages}\n---")

    # Persist the result from the sub-agent (which is now the ToolMessage content)
    async with AsyncSessionLocal() as db:
        for msg in tool_messages:
            # Ensure it's a ToolMessage before accessing attributes
            if isinstance(msg, ToolMessage):
                 # Find the original tool call name that led to this message
                 original_tool_name = "unknown_sub_agent" # Default
                 for tc in last_message.tool_calls:
                      if tc.get("id") == msg.tool_call_id:
                           original_tool_name = tc.get("name", original_tool_name)
                           break # Found the matching call
                 
                 await add_message_to_history(
                    db=db,
                    session_id=state["session_id"],
                    sender_type=MessageSender.TOOL, # Representing the output of the sub-agent tool call
                    message=str(msg.content),
                    tool_name=original_tool_name # Log the wrapper tool name
                 )
            else:
                 print(f"Warning: Expected ToolMessage from ToolNode, got {type(msg)}")

    return {"messages": tool_messages}

# 5. Define Conditional Edges (remains the same logic)
def route_to_next_step(state: SupervisorState) -> str:
    """Determines whether to call a sub-agent or end."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        print("--- SUPERVISOR ROUTER: Tool calls present, routing to Sub-Agent Action Node ---")
        return "sub_agent_action"
    print("--- SUPERVISOR ROUTER: No tool calls, routing to END ---")
    return END

# 6. Define the Supervisor Graph (using new node names)
supervisor_workflow = StateGraph(SupervisorState)
supervisor_workflow.add_node("supervisor", supervisor_node)
supervisor_workflow.add_node("sub_agent_action", sub_agent_action_node) # New node name

supervisor_workflow.set_entry_point("supervisor")

supervisor_workflow.add_conditional_edges(
    "supervisor",
    route_to_next_step,
    {
        "sub_agent_action": "sub_agent_action", # Route to new node name
        END: END
    }
)
supervisor_workflow.add_edge("sub_agent_action", "supervisor") # Loop back

# Compile the graph
multi_agent_graph = supervisor_workflow.compile()

# Helper to format history (can remain largely the same)
def _format_db_history_to_langchain_messages(db_history: List[Any]) -> List[BaseMessage]:
    lc_messages = []
    for msg in db_history:
        if msg.sender_type == MessageSender.USER.value:
            lc_messages.append(HumanMessage(content=msg.message))
        elif msg.sender_type == MessageSender.AI.value:
            lc_messages.append(AIMessage(content=msg.message))
        elif msg.sender_type == MessageSender.TOOL:
             # Representing the output of a sub-agent invocation (wrapper tool)
             lc_messages.append(ToolMessage(
                content=msg.message, 
                tool_call_id=str(uuid.uuid4()), # History replay ID is less critical here
                name=msg.tool_name or "unknown_sub_agent_tool_from_history"
            ))
    return lc_messages

# Main interaction function (remains largely the same signature and db logic)
async def run_multi_agent_interaction(session_id: str, user_message: str, repo_url: str | None) -> str:
    """Runs the multi-agent supervisor, orchestrating sub-agents."""
    async with AsyncSessionLocal() as db:
        await add_message_to_history(
            db=db, session_id=session_id, sender_type=MessageSender.USER.value, message=user_message
        )
        db_history = await get_history_by_session_id(db, session_id, limit=10)
        formatted_history = _format_db_history_to_langchain_messages(db_history[:-1])
        initial_messages = formatted_history + [HumanMessage(content=user_message)]

        initial_graph_state = SupervisorState(
            messages=initial_messages,
            user_request={"message": user_message, "repo_url": repo_url},
            session_id=session_id
        )
        
        # Invoke the compiled supervisor graph
        final_graph_state = await multi_agent_graph.ainvoke(initial_graph_state)
        
        ai_response_content = ""
        if final_graph_state and final_graph_state.get('messages'):
            # Find the last AIMessage from the supervisor that doesn't call a tool
            for msg in reversed(final_graph_state['messages']):
                if isinstance(msg, AIMessage) and not msg.tool_calls:
                    ai_response_content = msg.content
                    break
            # Fallback if the last message was a tool call result or AIMessage with tool call
            if not ai_response_content and isinstance(final_graph_state['messages'][-1], (AIMessage, ToolMessage)):
                # This might need refinement - what's the best final answer?
                # Maybe the content of the last ToolMessage if no final AIMessage exists?
                if isinstance(final_graph_state['messages'][-1], ToolMessage):
                     ai_response_content = f"Completed task with result: {final_graph_state['messages'][-1].content}"
                elif isinstance(final_graph_state['messages'][-1], AIMessage):
                     ai_response_content = final_graph_state['messages'][-1].content # Could be an AIMessage with tool calls

        if ai_response_content:
            await add_message_to_history(
                db=db, session_id=session_id, sender_type=MessageSender.AI.value, message=ai_response_content
            )
        else:
             ai_response_content = "Supervisor agent finished without a final message."
             await add_message_to_history(
                db=db, session_id=session_id, sender_type=MessageSender.AI.value, message=ai_response_content
            )

        return ai_response_content 