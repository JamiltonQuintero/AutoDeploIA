from langchain_core.tools import tool
from typing import TypedDict, Annotated, Sequence, List
from langchain_core.messages import BaseMessage, AnyMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from app.config import settings
# Add other necessary imports for a ReAct agent later (LLM, Graph, ToolNode, etc.)

# Tool Definitions (MCP Placeholders)
@tool
async def apply_terraform_plan(plan_details: str, working_directory: str) -> str:
    """Applies a Terraform plan to provision or modify infrastructure.
    Use this tool after a Terraform plan has been generated and approved.
    It represents calling the Terraform MCP (tfmcp) to execute the plan.
    Input:
        plan_details: A description or identifier of the Terraform plan to apply.
        working_directory: The directory containing the Terraform configuration files.
    Output: A message indicating the success or failure of the Terraform apply operation.
    """
    print(f"--- [Terraform Sub-Agent Tool] Applying plan in {working_directory} ---")
    print(f"--- [Terraform Sub-Agent Tool] Plan details: {plan_details} ---")
    # TODO: Implement actual tfmcp client call or terraform CLI logic
    apply_result = f"Terraform apply successful in {working_directory}. Resources created/updated."
    print(f"--- [Terraform Sub-Agent Tool] Result: {apply_result} ---")
    return apply_result

@tool
async def generate_terraform_plan(config_details: str, working_directory: str) -> str:
    """Generates a Terraform plan based on configuration files.
    Use this tool before applying changes to preview infrastructure modifications.
    It represents calling the Terraform MCP (tfmcp) to generate the plan.
    Input:
        config_details: Description of the desired infrastructure state or configuration files.
        working_directory: The directory containing the Terraform configuration files.
    Output: A summary of the Terraform plan, outlining proposed changes.
    """
    print(f"--- [Terraform Sub-Agent Tool] Generating plan in {working_directory} ---")
    print(f"--- [Terraform Sub-Agent Tool] Config details: {config_details} ---")
    # TODO: Implement actual tfmcp client call or terraform CLI logic
    plan_result = f"Terraform plan generated for {working_directory}: Plan shows 2 to add, 0 to change, 0 to destroy."
    print(f"--- [Terraform Sub-Agent Tool] Result: {plan_result} ---")
    return plan_result

# Define the LLM for this sub-agent
#terraform_llm = ChatOpenAI(temperature=0, streaming=True, api_key=settings.OPENAI_API_KEY)
terraform_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17",
    temperature=0.8,
    max_tokens=None,
    timeout=None,
    max_retries=2
)
# Create the ReAct Agent for Terraform operations
terraform_agent_graph = create_react_agent(
    model=terraform_llm,
    tools=[generate_terraform_plan, apply_terraform_plan], # Both Terraform tools
    # prompt="You are a specialized agent for managing infrastructure with Terraform..."
)

# Helper function to invoke this agent
async def invoke_terraform_agent(query: str) -> str:
    """Invokes the terraform sub-agent to plan or apply infrastructure changes."""
    print(f"--- Invoking Terraform Sub-Agent with query: {query} ---")
    input_messages: List[AnyMessage] = [("user", query)] 
    try:
        response = await terraform_agent_graph.ainvoke({"messages": input_messages})
        final_message = response["messages"][-1].content if response["messages"] else "Terraform agent finished without explicit response."
        print(f"--- Terraform Sub-Agent Result: {final_message} ---")
        return final_message
    except Exception as e:
        print(f"Error invoking terraform sub-agent: {e}")
        return f"Error during terraform operation: {str(e)}"

# TODO: Implement the ReAct graph logic for this sub-agent below 