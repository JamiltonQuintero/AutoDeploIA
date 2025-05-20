from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc # Import desc
from typing import List

from app.database.models import ChatHistory, MessageSender
from app.schemas.chat import ChatMessageOutput

async def add_message_to_history(
    db: AsyncSession,
    session_id: str,
    sender_type: MessageSender,
    message: str,
    tool_name: str | None = None
) -> ChatHistory:
    """Adds a single message to the chat history."""
    db_message = ChatHistory(
        session_id=session_id,
        sender_type=sender_type,
        message=message,
        tool_name=tool_name
    )
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    return db_message

async def get_history_by_session_id(
    db: AsyncSession, session_id: str, limit: int = 100
) -> List[ChatHistory]:
    """Retrieves chat history for a given session ID, ordered by timestamp."""
    result = await db.execute(
        select(ChatHistory)
        .where(ChatHistory.session_id == session_id)
        .order_by(desc(ChatHistory.timestamp)) # Order by timestamp descending
        .limit(limit)
    )
    history = result.scalars().all()
    return list(reversed(history)) # Reverse to get chronological order 