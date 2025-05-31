from sqlmodel import SQLModel, Field, Relationship # Added Relationship
from typing import Optional, List, TYPE_CHECKING # Added List, TYPE_CHECKING
from datetime import datetime
from ..schemas.role import UserRole
from sqlmodel import Field, JSON # Ensure JSON is imported if not already for sa_column=JSON

if TYPE_CHECKING:
    from .chat import ChatMessage
    from .contact import Contact
    from .organization import Organization
    from .membership import Membership # Added Membership import

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

    # 2FA Fields
    is_2fa_enabled: bool = Field(default=False)
    # IMPORTANT: totp_secret should be ENCRYPTED in a real application. Storing plain text is a risk.
    totp_secret: Optional[str] = Field(default=None, unique=True) # unique to prevent accidental reuse if not null
    # Backup codes should be HASHED if stored. For this example, direct storage (not recommended for prod).
    backup_codes: Optional[List[str]] = Field(default=None, sa_column=JSON)

    # Organization link (Primary/current organization for the user)
    organization_id: Optional[int] = Field(default=None, foreign_key="organization.id", nullable=True, index=True)
    # This relationship loads the Organization object based on organization_id.
    # Since Organization.users was replaced by Organization.memberships,
    # this direct back_populates is no longer to a simple List[User] on Organization.
    # We will make this a one-way link for now, or rely on SQLModel to handle it if foreign_keys are specified.
    # For SQLModel, usually explicit back_populates are good.
    # If Organization needs a list of users for whom it's their *primary* org, that's a different relationship.
    organization: Optional["Organization"] = Relationship(sa_relationship_kwargs={'foreign_keys': '[User.organization_id]'})
    # An alternative, if Organization *did* have `primary_users: List["User"] = Relationship(back_populates="organization")`:
    # organization: Optional["Organization"] = Relationship(back_populates="primary_users")


    # Memberships link (details about user's role in potentially multiple organizations)
    memberships: List["Membership"] = Relationship(back_populates="user")

    # New Profile Fields
    full_name: Optional[str] = Field(default=None, index=True)
    job_title: Optional[str] = Field(default=None)
    profile_picture_url: Optional[str] = Field(default=None)

    # Timestamps for the user record itself
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # For SQLModel, onupdate is often handled manually in PUT operations for the main object
    # For related objects or specific fields, SQLAlchemy's onupdate can be used via sa_column_kwargs
    # Let's ensure updated_at is set manually on user profile updates.
    updated_at: datetime = Field(default_factory=datetime.utcnow)


    sent_messages: List["ChatMessage"] = Relationship(back_populates="sender")
    contacts: List["Contact"] = Relationship(back_populates="owner")
