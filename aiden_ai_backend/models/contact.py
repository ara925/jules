from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .user import User

class Contact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)

    first_name: str = Field(index=True)
    last_name: Optional[str] = Field(default=None, index=True)
    email: str = Field(unique=True, index=True) # Assuming email should be unique across all contacts
    phone_number: Optional[str] = Field(default=None)
    company: Optional[str] = Field(default=None, index=True)
    notes: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    # sa_column_kwargs={"onupdate": datetime.utcnow} might need SQLAlchemy specific Column for onupdate
    # For SQLModel, usually handle updated_at manually on updates or use a DB trigger.
    # Let's stick to manual update for now for simplicity within SQLModel's direct capabilities.
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    owner: Optional["User"] = Relationship(back_populates="contacts")
