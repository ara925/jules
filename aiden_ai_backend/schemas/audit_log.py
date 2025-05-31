from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class AuditLogRead(BaseModel):
    id: int
    timestamp: datetime
    user_id: Optional[int] = None # Made optional as per model
    actor_email: Optional[str] = None # Made optional as per model
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None # Made optional as per model

    class Config:
        orm_mode = True
