from typing import TypedDict, Annotated, List, Dict, Any, Sequence

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from app.config import settings
from app.agents.tools.repo_analyzer import analyze_repository
from app.agents.tools.docker_tool import build_docker_image
from app.agents.tools.kubernetes_tool import deploy_to_kubernetes
from app.services.history_service import add_message_to_history, get_history_by_session_id
from app.database.database import AsyncSessionLocal
from app.database.models import MessageSender
import uuid # For generating unique tool call IDs

# 1. Define Agent State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]
    # Store the original user request, especially if it contains specific details like repo_url
    user_request: Dict[str, Any]
    # To store the session_id for history
    session_id: str

# 2. Define Tools
tools: List[BaseTool] = [analyze_repository, build_docker_image, deploy_to_kubernetes]
tool_executor = ToolNode(tools)

# 3. Define LLM
# Ensure OPENAI_API_KEY is set in your environment or through settings
#model = ChatOpenAI(temperature=0, streaming=True, api_key=settings.OPENAI_API_KEY)
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17",
    temperature=0.8,
    max_tokens=None,
    timeout=None,
    max_retries=2
)
# Bind tools to the model
model_with_tools = model.bind_tools(tools)

# 4. Define Nodes
async def agent_node(state: AgentState):
    """Invokes the LLM to determine the next action or respond to the user."""
    print(f"--- AGENT NODE: Current Messages ---\n{state['messages']}\n---")
    response = await model_with_tools.ainvoke(state["messages"])
    print(f"--- AGENT NODE: LLM Response ---\n{response}\n---")
    # The response is already an AIMessage, potentially with tool_calls
    return {"messages": [response]}

async def action_node(state: AgentState):
    """Executes tools if called by the LLM, or finishes if no tools are called."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        print("--- ACTION NODE: No tool calls, finishing. ---")
        return {"messages": []} # Or could be END, depending on desired final state

    print(f"--- ACTION NODE: Tool Calls ---\n{last_message.tool_calls}\n---")
    
    tool_messages = []
    async with AsyncSessionLocal() as db:
        for tool_call in last_message.tool_calls:
            # Ensure tool_call.id is unique for each call
            tool_call_id = tool_call.get("id", str(uuid.uuid4())) # Use existing or generate new ID
            tool_call["id"] = tool_call_id # Ensure 'id' is in the dict for ToolMessage

            action_response = await tool_executor.ainvoke([ToolMessage(
                content=str(tool_call["args"]), # Ensure content is string
                name=tool_call["name"],
                tool_call_id=tool_call_id,
            )])
            # action_response is a list containing one ToolMessage
            executed_tool_message = action_response[0]
            
            print(f"--- ACTION NODE: Tool {tool_call['name']} Executed, Response ---\n{executed_tool_message.content}\n---")
            tool_messages.append(executed_tool_message)
            
            # Persist tool message to history
            await add_message_to_history(
                db=db,
                session_id=state["session_id"],
                sender_type=MessageSender.TOOL,
                message=str(executed_tool_message.content), # Ensure content is string
                tool_name=tool_call["name"]
            )
    return {"messages": tool_messages}


# 5. Define Conditional Edges
def should_continue(state: AgentState) -> str:
    """Determines whether to continue the loop or end."""
    last_message = state["messages"][-1]
    # If there are no tool calls, then we finish
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        print("--- CONDITIONAL EDGE: No tool calls, routing to END ---")
        return END
    # Otherwise, we continue calling tools
    print("--- CONDITIONAL EDGE: Tool calls present, routing to Action ---")
    return "action"

# 6. Define the graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("action", action_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "action": "action",
        END: END
    }
)
workflow.add_edge("action", "agent") # Loop back to agent after action

# Compile the graph
agent_graph = workflow.compile()

# Helper to format history for the agent
def _format_db_history_to_langchain_messages(db_history: List[Any]) -> List[BaseMessage]:
    lc_messages = []
    for msg in db_history:
        if msg.sender_type == MessageSender.USER.value:
            lc_messages.append(HumanMessage(content=msg.message))
        elif msg.sender_type == MessageSender.AI.value:
            lc_messages.append(AIMessage(content=msg.message)) # Tool calls are not stored directly here yet for AIMessage
        elif msg.sender_type == MessageSender.TOOL:
            # This part needs careful handling if we want to re-inject tool calls and results
            # For now, we'll represent tool results simply.
            # A more robust solution might store tool_call_id and reconstruct ToolMessage with it.
            lc_messages.append(ToolMessage(content=msg.message, tool_call_id=str(uuid.uuid4()), name=msg.tool_name or "unknown_tool"))
    return lc_messages

async def run_agent_interaction(session_id: str, user_message: str, repo_url: str | None) -> str:
    """Runs the agent with the given user message and session history."""
    async with AsyncSessionLocal() as db:
        # Add current user message to DB
        await add_message_to_history(
            db=db,
            session_id=session_id,
            sender_type=MessageSender.USER.value,
            message=user_message
        )

        # Retrieve history
        db_history = await get_history_by_session_id(db, session_id, limit=10) # Limit history length
        
        # Format history for LangGraph
        # The initial message is the current user input
        # The history should be older messages
        formatted_history = _format_db_history_to_langchain_messages(db_history[:-1]) # Exclude current user message
        
        initial_messages = formatted_history + [HumanMessage(content=user_message)]

        # Construct the initial state
        # user_request can store more context if needed by tools later
        initial_agent_state = AgentState(
            messages=initial_messages,
            user_request={"message": user_message, "repo_url": repo_url},
            session_id=session_id
        )

        final_state = await agent_graph.ainvoke(initial_agent_state)
        
        ai_response_message = ""
        # The final response from AI is usually the last AIMessage without tool calls
        for msg in reversed(final_state['messages']):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                ai_response_message = msg.content
                break
        
        if not ai_response_message and final_state['messages'] and isinstance(final_state['messages'][-1], AIMessage):
             ai_response_message = final_state['messages'][-1].content # Fallback if no clean AIMessage

        # Persist final AI response to history
        if ai_response_message: # Only add if there's a non-tool-calling AI response
            await add_message_to_history(
                db=db,
                session_id=session_id,
                sender_type=MessageSender.AI.value,
                message=ai_response_message
            )
        
        return ai_response_message if isinstance(ai_response_message, str) else "Agent finished." 