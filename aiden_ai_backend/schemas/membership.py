from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .role import OrgRole
# from .user import UserRead # Optional: For embedding user details in MembershipRead
# from .organization import OrganizationRead # Optional: For embedding org details

class MembershipBase(BaseModel):
    role: OrgRole = OrgRole.MEMBER

class MembershipCreate(MembershipBase):
    user_id: int
    organization_id: int
    # Role can be set during creation, defaults to MEMBER if not provided by MembershipBase

class MembershipRead(MembershipBase):
    id: int # Membership record ID
    user_id: int
    organization_id: int
    joined_at: datetime
    # Optionally include nested UserRead and OrganizationRead if needed for richer API responses
    user_email: Optional[str] = None # Added to include user's email directly
    # user: Optional[UserRead] = None
    # organization: Optional[OrganizationRead] = None

    class Config:
        orm_mode = True
