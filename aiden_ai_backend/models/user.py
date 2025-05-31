from sqlmodel import SQLModel, Field, Relationship # Added Relationship
from typing import Optional, List, TYPE_CHECKING # Added List, TYPE_CHECKING
from datetime import datetime
from ..schemas.role import UserRole

if TYPE_CHECKING:
    from .chat import ChatMessage
    from .contact import Contact # Add this for type hinting

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_email_verified: bool = Field(default=False)
    email_verification_token: Optional[str] = Field(default=None, index=True)
    verification_token_expires_at: Optional[datetime] = Field(default=None)
    password_reset_token: Optional[str] = Field(default=None, index=True)
    password_reset_token_expires_at: Optional[datetime] = Field(default=None)
    role: UserRole = Field(default=UserRole.USER)

    sent_messages: List["ChatMessage"] = Relationship(back_populates="sender")
    contacts: List["Contact"] = Relationship(back_populates="owner")
