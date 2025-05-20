from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.schemas.chat import ChatInput, ChatResponse, HistoryResponse, ChatMessageOutput
from app.services.history_service import get_history_by_session_id # add_message_to_history is used by agent
from app.database.database import get_db
from app.agents.supervisor_agent import run_multi_agent_interaction
from app.database.models import MessageSender # For mapping to ChatMessageOutput

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    chat_input: ChatInput,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint for interacting with the multi-agent supervisor."""
    try:
        ai_final_response = await run_multi_agent_interaction(
            session_id=chat_input.session_id,
            user_message=chat_input.message,
            repo_url=chat_input.repo_url
        )
        
        # Retrieve the latest history to include in the response
        updated_db_history = await get_history_by_session_id(db, chat_input.session_id, limit=20)
        
        # Map DB history to ChatMessageOutput schema
        formatted_history_output: List[ChatMessageOutput] = [
            ChatMessageOutput(
                id=msg.id,
                session_id=msg.session_id,
                sender_type=msg.sender_type, # Direct mapping if MessageSender enum values match strings
                message=msg.message,
                tool_name=msg.tool_name,
                timestamp=msg.timestamp
            )
            for msg in updated_db_history
        ]

        return ChatResponse(
            session_id=chat_input.session_id,
            ai_response=ai_final_response,
            history=formatted_history_output
        )
    except Exception as e:
        # Log the exception for debugging
        print(f"Error in /chat endpoint: {e}")
        # Potentially re-raise or return a more specific HTTP error
        raise HTTPException(status_code=500, detail=f"Agent interaction failed: {str(e)}")

@router.get("/chat/history/{session_id}", response_model=HistoryResponse)
async def get_chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint to retrieve chat history for a given session ID."""
    db_history = await get_history_by_session_id(db, session_id)
    if not db_history:
        raise HTTPException(status_code=404, detail="Chat history not found for this session ID.")

    # Map DB history to ChatMessageOutput schema
    formatted_history_output: List[ChatMessageOutput] = [
        ChatMessageOutput(
            id=msg.id,
            session_id=msg.session_id,
            sender_type=msg.sender_type, # Direct mapping
            message=msg.message,
            tool_name=msg.tool_name,
            timestamp=msg.timestamp
        )
        for msg in db_history
    ]
    
    return HistoryResponse(session_id=session_id, history=formatted_history_output) 