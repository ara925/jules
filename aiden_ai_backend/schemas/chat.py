from pydantic import BaseModel

class ChatMessageCreate(BaseModel):
    text: str

class ChatMessageRead(BaseModel):
    text: str
    sender: str # "user" or "bot"
