from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class InboxEmailRead(BaseModel):
    id: int
    message_id: str
    subject: Optional[str]
    sender_address: EmailStr # Or str if parsing is tricky, EmailStr is better
    recipient_address: Optional[EmailStr] # Or str
    body_text: Optional[str]
    # body_html: Optional[str] # Excluded for now for list view brevity
    received_at: datetime
    processed_at: datetime
    status: str

    class Config:
        orm_mode = True
