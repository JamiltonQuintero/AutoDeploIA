from langchain_core.tools import tool
from typing import TypedDict, Annotated, Sequence, List
from langchain_core.messages import BaseMessage, AnyMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from app.config import settings
# Add other necessary imports for a ReAct agent later (LLM, Graph, ToolNode, etc.)

# Tool Definition (MCP Placeholder)
@tool
async def deploy_to_kubernetes(image_name: str, deployment_name: str, namespace: str = "default") -> str:
    """Deploys a previously built Docker image to a Kubernetes cluster.
    Use this tool after a Docker image has been successfully built.
    Input:
        image_name: The name and tag of the Docker image to deploy (e.g., myapp:latest).
        deployment_name: The desired name for the Kubernetes deployment resource.
        namespace: The Kubernetes namespace to deploy into (defaults to 'default').
    Output: A message indicating the success or failure of the Kubernetes deployment.
    This represents calling the Kubernetes MCP (mcp-server-kubernetes).
    """
    print(f"--- [K8s Sub-Agent Tool] Deploying {image_name} as {deployment_name} to ns {namespace} ---")
    # TODO: Implement actual mcp-server-kubernetes client call
    deploy_result = f"Deployment {deployment_name} created successfully in namespace {namespace} using image {image_name}."
    print(f"--- [K8s Sub-Agent Tool] Result: {deploy_result} ---")
    return deploy_result

# Define the LLM for this sub-agent
#k8s_llm = ChatOpenAI(temperature=0, streaming=True, api_key=settings.OPENAI_API_KEY)
k8s_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17",
    temperature=0.8,
    max_tokens=None,
    timeout=None,
    max_retries=2
)
# Create the ReAct Agent for Kubernetes operations
k8s_agent_graph = create_react_agent(
    model=k8s_llm,
    tools=[deploy_to_kubernetes], # Only K8s tool
    # prompt="You are a specialized agent for deploying applications to Kubernetes..."
)

# Helper function to invoke this agent
async def invoke_k8s_agent(query: str) -> str:
    """Invokes the kubernetes sub-agent to deploy an application."""
    print(f"--- Invoking K8s Sub-Agent with query: {query} ---")
    input_messages: List[AnyMessage] = [("user", query)] 
    try:
        response = await k8s_agent_graph.ainvoke({"messages": input_messages})
        final_message = response["messages"][-1].content if response["messages"] else "K8s agent finished without explicit response."
        print(f"--- K8s Sub-Agent Result: {final_message} ---")
        return final_message
    except Exception as e:
        print(f"Error invoking k8s sub-agent: {e}")
        return f"Error during k8s deployment: {str(e)}"

# TODO: Implement the ReAct graph logic for this sub-agent below 