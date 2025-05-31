from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class ContactBase(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: EmailStr # Ensures email format validation
    phone_number: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None

class ContactCreate(ContactBase):
    pass # Inherits all fields from ContactBase

class ContactUpdate(BaseModel): # For partial updates, all fields are optional
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None

class ContactRead(ContactBase):
    id: int
    owner_id: int # To know who owns this contact
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
