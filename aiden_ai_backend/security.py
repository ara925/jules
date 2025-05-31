import os # Added
from dotenv import load_dotenv # Added
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv() # Load .env file variables

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

import uuid

# JWT Configuration / Settings from Environment Variables
SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "a_very_sensible_default_secret_key_for_development_only")
ALGORITHM = "HS256" # Usually not changed via env for basic security
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS = int(os.getenv("AUTH_EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS", "24"))
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = int(os.getenv("AUTH_PASSWORD_RESET_TOKEN_EXPIRE_HOURS", "1"))

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
