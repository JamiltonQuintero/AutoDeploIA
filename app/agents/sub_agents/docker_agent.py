from langchain_core.tools import tool
from typing import TypedDict, Annotated, Sequence, List
from langchain_core.messages import BaseMessage, AnyMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from app.config import settings

# Tool Definition (MCP Placeholder)
@tool
async def build_docker_image(repo_url: str, project_path: str, image_name: str) -> str:
    """Builds a Docker image for a project located at a given path (potentially cloned from repo_url).
    Use this tool after analyzing a repository and determining a Dockerfile exists or can be generated.
    Input:
        repo_url: The original repository URL (for context).
        project_path: The local file system path to the project code.
        image_name: The desired name for the Docker image (e.g., myapp:latest).
    Output: A message indicating success or failure of the Docker image build, and the image ID if successful.
    This represents calling the Docker MCP (mcp-server-docker).
    """
    print(f"--- [Docker Sub-Agent Tool] Building image for {project_path} as {image_name} ---")
    # TODO: Implement actual mcp-server-docker client call
    build_result = f"Docker image {image_name} built successfully. Image ID: sha256:123abc456def"
    print(f"--- [Docker Sub-Agent Tool] Result: {build_result} ---")
    return build_result

# Define the LLM for this sub-agent
#docker_llm = ChatOpenAI(temperature=0, streaming=True, api_key=settings.OPENAI_API_KEY)
docker_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17",
    temperature=0.8,
    max_tokens=None,
    timeout=None,
    max_retries=2
)
# Create the ReAct Agent for Docker operations
docker_agent_graph = create_react_agent(
    model=docker_llm,
    tools=[build_docker_image], # Only Docker tool
    # prompt="You are a specialized agent for building Docker images..."
)

# Helper function to invoke this agent
async def invoke_docker_agent(query: str) -> str:
    """Invokes the docker sub-agent to build an image."""
    print(f"--- Invoking Docker Sub-Agent with query: {query} ---")
    input_messages: List[AnyMessage] = [("user", query)] 
    try:
        response = await docker_agent_graph.ainvoke({"messages": input_messages})
        final_message = response["messages"][-1].content if response["messages"] else "Docker agent finished without explicit response."
        print(f"--- Docker Sub-Agent Result: {final_message} ---")
        return final_message
    except Exception as e:
        print(f"Error invoking docker sub-agent: {e}")
        return f"Error during docker build: {str(e)}"