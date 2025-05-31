from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class OrganizationBase(BaseModel):
    name: str

class OrganizationCreate(OrganizationBase):
    # owner_id will be set based on the authenticated user creating the organization
    pass

class OrganizationRead(OrganizationBase):
    id: int
    owner_id: Optional[int] = None # Owner can be optional or hidden based on policy
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# For adding a member to an organization
class AddMemberPayload(BaseModel):
    user_email: EmailStr # Use EmailStr for validation
    role: OrgRole = OrgRole.MEMBER # Default role to member

# For updating a member's role
class UpdateMemberRolePayload(BaseModel):
    role: OrgRole
