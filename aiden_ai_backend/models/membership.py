from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from ..schemas.role import OrgRole # Import OrgRole

if TYPE_CHECKING:
    from .user import User
    from .organization import Organization

class Membership(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    organization_id: int = Field(foreign_key="organization.id", index=True)

    role: OrgRole = Field(default=OrgRole.MEMBER)
    joined_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: Optional["User"] = Relationship(back_populates="memberships")
    organization: Optional["Organization"] = Relationship(back_populates="memberships")

    # Add unique constraint for user_id and organization_id pair
    # This ensures a user can only have one membership (and thus one role) per organization.
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_user_organization_membership"),)
