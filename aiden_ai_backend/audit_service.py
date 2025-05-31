from sqlmodel import Session
from datetime import datetime
from typing import Optional, Dict, Any
from .models.audit_log import AuditLog
from .models.user import User as UserModel # To get actor_email if user object is passed

def create_audit_log_entry(
    db: Session,
    action: str,
    current_user: Optional[UserModel] = None, # The user performing the action
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None, # Allow Any for target_id, will be stringified
    details: Optional[Dict[str, Any]] = None
):
    user_id_val: Optional[int] = None
    actor_email_val: Optional[str] = None

    if current_user:
        # Ensure current_user is a valid User model instance if provided
        if isinstance(current_user, UserModel) and hasattr(current_user, 'id') and hasattr(current_user, 'email'):
            user_id_val = current_user.id
            actor_email_val = current_user.email
        else:
            # Handle cases where current_user might be passed but not a full UserModel instance
            # Or log a warning, though FastAPI dependencies should ensure correct type.
            # For now, we'll assume if current_user is passed, it's the correct type.
            pass

    target_id_str: Optional[str] = str(target_id) if target_id is not None else None

    audit_entry = AuditLog(
        timestamp=datetime.utcnow(), # Ensure this is UTC
        user_id=user_id_val,
        actor_email=actor_email_val,
        action=action,
        target_type=target_type,
        target_id=target_id_str,
        details=details if details is not None else {} # Ensure details is at least an empty dict if None
    )
    db.add(audit_entry)
    # The calling function should handle db.commit() as part of its transaction.
    # db.refresh(audit_entry) # Usually not needed by caller immediately
    return audit_entry
