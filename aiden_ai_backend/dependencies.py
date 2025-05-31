from fastapi import Depends, HTTPException, status, Path
from sqlmodel import Session, select
from typing import List, Tuple, Optional # Added Optional

# Assuming these are in main.py or adjust import paths accordingly
# For direct execution or if main.py imports this, these relative paths might need adjustment
# or use absolute paths if your project structure supports it (e.g. if aiden_ai_backend is a package)

# To avoid circular imports if get_current_active_user is in main.py and main.py imports this,
# it's better to pass get_current_active_user as a dependency to functions here,
# or reorganize so dependencies are more self-contained or in a shared utility.
# For now, let's assume main.py can provide get_current_active_user.
# This will likely require these dependencies to be used within main.py or a router file that has access to get_current_active_user.

# Placeholder for imports, will be resolved when integrated into main.py or router file
# from .main import get_current_active_user # This creates circular dependency if this file is imported by main
from .database import get_db
from .models.user import User as UserModel
from .models.organization import Organization as OrganizationModel
from .models.membership import Membership as MembershipModel
from .schemas.role import OrgRole


async def get_organization_from_path(
    org_id: int = Path(..., description="The ID of the target organization"),
    db: Session = Depends(get_db)
) -> OrganizationModel:
    org = db.get(OrganizationModel, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org

async def get_user_org_membership_details( # Renamed to avoid conflict, more descriptive
    user: UserModel,
    organization: OrganizationModel,
    db: Session # Pass session directly
) -> Tuple[Optional[MembershipModel], Optional[OrgRole]]:
    # This function can be called by other dependencies or route functions
    membership = db.exec(
        select(MembershipModel)
        .where(MembershipModel.user_id == user.id)
        .where(MembershipModel.organization_id == organization.id)
    ).first()
    return membership, membership.role if membership else None

# Dependency to ensure user is at least a member of the organization
# This needs get_current_active_user to be passed or defined before it.
# For now, this will be defined in main.py or where the router is, to resolve imports.
# This file will just contain the reusable logic part (get_user_org_membership_details)
# and get_organization_from_path.

# The actual dependencies get_member_of_organization and get_admin_or_owner_of_organization
# will be defined in main.py or the router file that uses them.

# This helper gets the current user's role within their primary organization.
# It needs access to get_current_active_user, so it's better placed in main.py
# or a file that main.py imports after get_current_active_user is defined,
# or get_current_active_user needs to be passed into it.

# For now, this file provides get_organization_from_path and get_user_org_membership_details.
# get_current_user_primary_org_role will be defined in main.py.
pass # No changes to this file for this specific step of creating the helper in main.py
