from pydantic import BaseModel, EmailStr, HttpUrl, Field as PydanticField # Use PydanticField to avoid conflict with SQLModel Field
from typing import Optional
from datetime import datetime
from .role import UserRole, OrgRole # Import OrgRole as well

class UserBase(BaseModel):
    email: EmailStr # Use EmailStr for validation

class UserCreate(UserBase):
    password: str

class UserLogin(UserBase):
    password: str

class UserRead(UserBase):
    id: int
    is_active: bool
    is_email_verified: bool
    role: UserRole # System-level role
    organization_id: Optional[int] = None
    current_organization_role: Optional[OrgRole] = None # Role within the primary/current organization

    # New Profile Fields for UserRead
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    profile_picture_url: Optional[str] = None # Display as string, validated as HttpUrl on update
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# New Schema for User Profile Update
class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = PydanticField(None, min_length=1, max_length=100)
    job_title: Optional[str] = PydanticField(None, max_length=100)
    profile_picture_url: Optional[HttpUrl] = None # Validate as HttpUrl on input

    # User should not be able to update email, role, auth settings etc. via this specific endpoint
    class Config:
        orm_mode = True # Useful if we ever load this from an ORM object, though typically for input.

# Schemas for JWT Tokens
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[EmailStr] = None # Use EmailStr
    role: Optional[UserRole] = None
    user_id: Optional[int] = None # Added user_id to TokenData as it's in the token

# Schemas for Password Reset
class RequestPasswordResetPayload(BaseModel):
    email: EmailStr

class ResetPasswordPayload(BaseModel):
    token: str
    new_password: str

# Schemas for 2FA
class TwoFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str

class TwoFAEnablePayload(BaseModel):
    totp_code: str

class LoginResponseStep1(BaseModel):
    message: str
    interim_token: str

class LoginResponseStep2FA(BaseModel):
    interim_token: str
    totp_code: str
