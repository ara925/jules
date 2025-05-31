from pydantic import BaseModel

from pydantic import BaseModel # Ensure BaseModel is imported
from datetime import datetime # Ensure datetime is imported

class ChatMessageCreate(BaseModel): # This might be deprecated if only WS is used for sending
    text: str

class ChatMessageRead(BaseModel):
    id: int
    sender_id: int
    sender_email: str # Added for convenience
    message: str
    timestamp: datetime
    conversation_id: str

    class Config:
        orm_mode = True
