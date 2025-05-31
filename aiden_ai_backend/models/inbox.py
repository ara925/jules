from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .user import User # Assuming emails might be linked to a user who "owns" the mailbox config

class InboxEmail(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # owner_id: int = Field(foreign_key="user.id", index=True) # For multi-user later. For now, assume one global inbox.

    message_id: str = Field(unique=True, index=True) # From email header <Message-ID>
    subject: Optional[str] = Field(default=None)
    sender_address: str = Field(index=True)
    recipient_address: Optional[str] = Field(default=None) # Typically the monitored address

    body_text: Optional[str] = Field(default=None)
    body_html: Optional[str] = Field(default=None) # Store for potential rich display

    received_at: datetime # From email 'Date' header
    processed_at: datetime = Field(default_factory=datetime.utcnow) # When we ingested it

    status: str = Field(default="unread", index=True) # e.g., unread, read, archived

    # owner: Optional["User"] = Relationship(back_populates="inbox_emails") # For multi-user later
