from sqlmodel import SQLModel, Field, Column # Removed Relationship as it's not used here
from sqlalchemy.dialects.sqlite import JSON as SQLITEJSON # For SQLite JSON type
# For PostgreSQL, use: from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from typing import Optional, Dict, Any # For JSON field

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)

    user_id: Optional[int] = Field(default=None, foreign_key="user.id", nullable=True, index=True) # Actor user ID
    actor_email: Optional[str] = Field(default=None, index=True) # Denormalized for easier querying if user is deleted

    action: str = Field(index=True) # e.g., "USER_LOGIN_SUCCESS"

    target_type: Optional[str] = Field(default=None, index=True) # e.g., "User", "Contact", "Organization"
    target_id: Optional[str] = Field(default=None, index=True) # Changed to str to accommodate non-int IDs

    # Using SQLITEJSON for SQLite. For other DBs, this might need adjustment.
    # SQLModel handles JSON type well with Pydantic v2 and appropriate DB driver.
    # The Column(JSON) is a fallback for more explicit SQLAlchemy column type definition.
    details: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(SQLITEJSON))
