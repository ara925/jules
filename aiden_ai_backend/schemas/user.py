from pydantic import BaseModel
from typing import Optional
from .role import UserRole # Import UserRole

class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str

class UserLogin(UserBase): # Schema for Login (though OAuth2PasswordRequestForm is used in main endpoint)
    password: str

class UserRead(UserBase):
    id: int
    is_active: bool
    is_email_verified: bool
    role: UserRole # Added role

    class Config:
        orm_mode = True

# Schemas for JWT Tokens
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[UserRole] = None # Added role to TokenData

# Schemas for Password Reset
class RequestPasswordResetPayload(BaseModel):
    email: str

class ResetPasswordPayload(BaseModel):
    token: str
    new_password: str
