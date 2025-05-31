from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

import uuid # Import uuid for verification token

# JWT Configuration
SECRET_KEY = "your-super-secret-key-please-change-in-prod"  # KEEP SECRET!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # Token validity: 30 minutes
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS = 24 # For email verification
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 1 # For password reset

def create_verification_token() -> str:
    """Generates a unique token (e.g., UUID) for email verification."""
    return str(uuid.uuid4())

def create_password_reset_token() -> str:
    """Generates a unique token (e.g., UUID) for password reset."""
    return str(uuid.uuid4())

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    # Data should now include 'sub' (subject, e.g., email) and 'role'
    to_encode = data.copy()
    if "sub" not in to_encode or "role" not in to_encode:
        # Basic check, ideally this is ensured by the caller
        raise ValueError("Missing 'sub' or 'role' in data for JWT creation")

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]: # This already returns the full payload
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
