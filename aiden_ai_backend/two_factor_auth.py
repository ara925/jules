import pyotp
import os
from dotenv import load_dotenv # To load APP_NAME if it's in .env

load_dotenv() # Load .env file if APP_NAME is defined there

# Normally, app_name would come from config or be more dynamic
APP_NAME = os.getenv("APP_NAME", "AidenAI")

def generate_totp_secret() -> str:
    return pyotp.random_base32()

def get_totp_provisioning_uri(email: str, secret: str) -> str:
    # Ensure email is properly encoded if it contains special characters, though usually it's fine.
    # pyotp.totp.TOTP handles this fairly well.
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=APP_NAME)

def verify_totp_code(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    # verify() checks the current, previous, and next code windows by default
    return totp.verify(code)

# Backup codes (Simplified for now - HASHING IS CRITICAL IN PRODUCTION)
# from typing import List
# from .security import pwd_context # Example: If you use passlib for hashing

# def generate_backup_codes(count: int = 5, length: int = 10) -> List[str]:
#     """Generates a list of unique backup codes."""
#     codes = set()
#     while len(codes) < count:
#         # Generate a more user-friendly code if desired, e.g., numeric or alphanumeric
#         # pyotp.random_base32() is good for secrets, maybe too complex for user backup codes
#         # For simplicity, using it here but consider alternatives for user-facing codes

#         # Example: Generate 8-digit numeric codes
#         # code = "".join([str(random.randint(0,9)) for _ in range(length)])

#         # Using pyotp.random_base32 for simplicity for now, but these are not very user-friendly
#         codes.add(pyotp.random_base32(length))
#     return list(codes)

# def hash_backup_code(code: str) -> str:
#     """Hashes a backup code using the application's password hashing context."""
#     return pwd_context.hash(code)

# def verify_backup_code(plain_code: str, hashed_codes: List[str]) -> bool:
#     """Verifies a plain backup code against a list of hashed codes.
#        IMPORTANT: If a code is used, it should be invalidated (removed from the list).
#        This logic needs to be implemented in the endpoint using it.
#     """
#     for hashed_code in hashed_codes:
#         if pwd_context.verify(plain_code, hashed_code):
#             return True
#     return False
