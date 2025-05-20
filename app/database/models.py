import uuid
from sqlalchemy import Column, String, DateTime, Text, UUID, Enum as SQLEnum
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class MessageSender(enum.Enum):
    USER = "user"
    AI = "ai"
    TOOL = "tool"

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String, index=True, nullable=False)
    sender_type = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    tool_name = Column(String, nullable=True) # Name of the tool if sender_type is TOOL
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ChatHistory(session_id='{self.session_id}', sender='{self.sender_type.value}', timestamp='{self.timestamp}')>" 