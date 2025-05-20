from langchain_core.tools import tool
from typing import TypedDict, Annotated, Sequence, List
from langchain_core.messages import BaseMessage, AnyMessage
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from app.config import settings
# Add other necessary imports for a ReAct agent later (LLM, Graph, ToolNode, etc.)
from langchain_google_genai import ChatGoogleGenerativeAI


# Define the LLM for this sub-agent
# Could use a smaller/cheaper model if the task is simple enough
#analysis_llm = ChatOpenAI(temperature=0, streaming=True, api_key=settings.OPENAI_API_KEY)
analysis_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17",
    temperature=0.8,
    max_tokens=None,
    timeout=None,
    max_retries=2
)
# Create the ReAct Agent for Analysis
# Note: create_react_agent uses a predefined AgentState internally
analysis_agent_graph = create_react_agent(
    model=analysis_llm,
    tools=[], # Only provide the relevant tool
    # We could add a specific system prompt here if needed
    # prompt="You are a specialized agent for analyzing code repositories..."
)

# Helper function to invoke this agent (used by the supervisor)
async def invoke_analysis_agent(query: str) -> str:
    """Invokes the analysis sub-agent to analyze a repository."""
    print(f"--- Invoking Analysis Sub-Agent with query: {query} ---")
    # The input message format for create_react_agent is typically {"messages": [("user", query)]}
    # or a list of BaseMessages
    input_messages: List[AnyMessage] = [("user", query)] 
    try:
        # create_react_agent doesn't directly support async invocation easily without channels
        # For simplicity here, we run sync in async context, replace with proper async if needed
        # Or reconstruct the graph manually for full async control.
        # Using .ainvoke directly might work depending on LangGraph version and setup.
        response = await analysis_agent_graph.ainvoke({"messages": input_messages})
        # Extract the final response message
        final_message = response["messages"][-1].content if response["messages"] else "Analysis agent finished without explicit response."
        print(f"--- Analysis Sub-Agent Result: {final_message} ---")
        return final_message
    except Exception as e:
        print(f"Error invoking analysis sub-agent: {e}")
        return f"Error during analysis: {str(e)}"
