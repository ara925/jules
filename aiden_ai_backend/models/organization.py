from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from .user import User
    from .membership import Membership # Added Membership import

class Organization(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id", nullable=True, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship: Memberships linking users and their roles to this organization
    memberships: List["Membership"] = Relationship(back_populates="organization")

    # Note: The 'users' direct relationship (Organization.users -> User.organization)
    # still exists on the User model side if User.organization_id points here.
    # This 'memberships' relationship is now the primary way to get users *and their roles* within this org.
    # The old Organization.users should be removed if it was directly linking User objects.
    # The User.organization relationship (linking a user to their primary org) is still valid.
    # The back_populates="organization" on Membership.organization matches this.
    # The back_populates="users" on User.organization means an Organization has many users.
    # This seems fine. The change is that Organization now sees its members via the Membership table.

    # Relationship: The owner of the organization (a user)
    # The `back_populates` on the User side would be something like `owned_organizations: List["Organization"]`
    # if a user could own multiple orgs, or `owned_organization: Optional["Organization"]` if one.
    # For now, we'll rely on owner_id and can add this explicit relationship later if needed.
    # owner: Optional["User"] = Relationship(sa_relationship_kwargs={'foreign_keys': '[Organization.owner_id]'})
    # The above `owner` relationship needs a corresponding `back_populates` on the User model.
    # Let's keep it simple and use owner_id primarily. If we need to load the owner object,
    # we can do so via a query.
    # If we did add it, User model would need:
    # owned_org: Optional["Organization"] = Relationship(back_populates="owner_user_obj") # Example name
    # And Organization model:
    # owner_user_obj: Optional["User"] = Relationship(sa_relationship_kwargs={'foreign_keys': '[Organization.owner_id]'}, back_populates="owned_org")

    # For now, the `users` list is for members. `owner_id` indicates the creator/primary admin.
    # A user is associated with ONE organization via User.organization_id.
    # An organization has ONE owner via Organization.owner_id.
    # An organization can have MANY users via Organization.users (back_populates from User.organization).

    # Let's define the relationship to the owner User model, assuming an org has one owner.
    # This will require a corresponding `owned_organization: Optional["Organization"]` on the User model.
    # For simplicity in this step, we will OMIT this direct 'owner' object relationship from Org -> User
    # and rely on querying by `owner_id` if needed. The `users` list is for members.
    # The User model will link to its Organization via `User.organization_id`.
    # The Organization model will link to its Owner (a User) via `Organization.owner_id`.
    pass # End of class definition
