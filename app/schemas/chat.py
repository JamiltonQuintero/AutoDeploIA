from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.database.models import MessageSender

class ChatInput(BaseModel):
    session_id: str = Field(..., description="Unique identifier for the chat session.")
    message: str = Field(..., description="The user's message.")
    repo_url: Optional[str] = Field(None, description="URL of the repository to deploy (if applicable).")

class ChatMessageOutput(BaseModel):
    id: UUID
    session_id: str
    sender_type: MessageSender
    message: str
    tool_name: Optional[str] = None
    timestamp: datetime

    class Config:
        orm_mode = True # Compatibility with SQLAlchemy models
        # Pydantic V2 uses from_attributes instead of orm_mode
        # from_attributes = True # Uncomment if using Pydantic V2

class ChatResponse(BaseModel):
    session_id: str
    ai_response: str
    history: List[ChatMessageOutput]

class HistoryResponse(BaseModel):
    session_id: str
    history: List[ChatMessageOutput] 