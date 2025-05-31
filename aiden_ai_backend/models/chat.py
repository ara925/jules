from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .user import User

class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sender_id: int = Field(foreign_key="user.id")
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    conversation_id: str = Field(index=True) # Simple conversation/room identifier

    sender: Optional["User"] = Relationship(back_populates="sent_messages")
