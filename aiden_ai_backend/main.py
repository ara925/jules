import logging
from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, WebSocket, WebSocketDisconnect, Query, Request, Path
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select, func
from datetime import timedelta, datetime, timezone
from typing import Dict, List, Optional, Tuple

# Rate limiting imports
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Project specific imports
from .database import engine, create_db_and_tables, get_db
from . import security
from . import schemas
from . import models
from . import two_factor_auth
from .websocket_manager import manager
from .bot_logic import get_bot_response, BOT_USER_EMAIL, BOT_CONVERSATION_ID_TRIGGER
from .email_ingestion_service import ingest_emails_from_mailbox, IMAP_USER as INGEST_IMAP_USER, IMAP_PASS as INGEST_IMAP_PASS
from .pii_masking import mask_pii_in_text
from .dependencies import get_organization_from_path, get_user_org_membership_details


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])
app = FastAPI(title="Aiden AI Backend", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
def on_startup(): create_db_and_tables(); logger.info("Application startup: Database and tables created.")

# --- Routers ---
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
user_router = APIRouter(prefix="/users", tags=["Users"])
contact_router = APIRouter(prefix="/contacts", tags=["Contacts"]) # Default dependency will be added per-route for contacts
inbox_router = APIRouter(prefix="/inbox", tags=["Inbox"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(get_current_active_admin)])
organization_router = APIRouter(prefix="/organizations", tags=["Organizations"])


# --- Utility Dependencies ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.user.User:
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        token_data_dict = security.decode_access_token(token)
        if token_data_dict is None or token_data_dict.get("type") == "2fa_interim":
            if token_data_dict and token_data_dict.get("type") == "2fa_interim": logger.warning("Interim 2FA token to get_current_user.")
            raise credentials_exception
        user_id = token_data_dict.get("user_id")
        if user_id is None: logger.warning("Token missing user_id."); raise credentials_exception
        user = db.get(models.user.User, user_id)
        if user is None: raise credentials_exception
        return user
    except JWTError: raise credentials_exception

async def get_current_active_user(current_user: models.user.User = Depends(get_current_user)):
    if not current_user.is_active: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

async def get_current_active_admin(current_user: models.user.User = Depends(get_current_active_user)):
    if current_user.role != schemas.role.UserRole.ADMIN:
        logger.warning(f"Non-admin {current_user.email} tried admin route.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")
    return current_user

# --- Organization Permission Dependencies ---
async def get_current_user_primary_org_role(
    current_user: models.user.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Tuple[models.user.User, Optional[schemas.role.OrgRole]]:
    if not current_user.organization_id:
        return current_user, None
    membership = db.exec(
        select(models.membership.Membership)
        .where(models.membership.Membership.user_id == current_user.id)
        .where(models.membership.Membership.organization_id == current_user.organization_id)
    ).first()
    return current_user, membership.role if membership else None

async def get_member_of_organization(
    organization: models.organization.Organization = Depends(get_organization_from_path),
    current_user: models.user.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Tuple[models.user.User, models.organization.Organization, schemas.role.OrgRole]:
    membership, org_role = await get_user_org_membership_details(current_user, organization, db)
    if not membership or org_role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organization.")
    return current_user, organization, org_role

async def get_admin_or_owner_of_organization(
    user_org_role_tuple: Tuple[models.user.User, models.organization.Organization, schemas.role.OrgRole] = Depends(get_member_of_organization)
) -> Tuple[models.user.User, models.organization.Organization, schemas.role.OrgRole]:
    _, _, org_role = user_org_role_tuple
    if org_role not in [schemas.role.OrgRole.ADMIN, schemas.role.OrgRole.OWNER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not an admin or owner of this organization.")
    return user_org_role_tuple

# --- Root Endpoint ---
@app.get("/")
@limiter.limit("100/minute")
async def root(request: Request): return {"message": "Welcome to Aiden AI Backend"}

# --- Authentication Endpoints (auth_router) ---
# ... (register_user, login_for_access_token, etc. - as previously defined, ensuring correct model/schema paths)
@auth_router.post("/register", response_model=Dict[str, str])
@limiter.limit("5/hour")
async def register_user(request: Request, user_in: schemas.user.UserCreate, db: Session = Depends(get_db)):
    db_user_exists = db.exec(select(models.user.User).where(models.user.User.email == user_in.email)).first()
    if db_user_exists: logger.warning(f"Reg attempt existing email: {user_in.email}"); raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    hashed_password = security.get_password_hash(user_in.password)
    verification_token = security.create_verification_token()
    token_expires_at = datetime.now(timezone.utc) + timedelta(hours=security.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)
    users_count = db.exec(select(func.count(models.user.User.id))).one_or_none() or 0
    user_role = schemas.role.UserRole.ADMIN if users_count == 0 else schemas.role.UserRole.USER
    db_user = models.user.User(email=user_in.email, hashed_password=hashed_password, is_active=True, email_verification_token=verification_token, verification_token_expires_at=token_expires_at, role=user_role)
    db.add(db_user); db.commit(); db.refresh(db_user)
    org_name = f"{db_user.email}'s Organization"; new_organization = models.organization.Organization(name=org_name, owner_id=db_user.id)
    db.add(new_organization); db.commit(); db.refresh(new_organization)
    db_user.organization_id = new_organization.id
    db.add(db_user); db.commit(); db.refresh(db_user)
    new_membership = models.membership.Membership(user_id=db_user.id, organization_id=new_organization.id, role=schemas.role.OrgRole.OWNER)
    db.add(new_membership); db.commit(); db.refresh(new_membership)
    logger.info(f"User {db_user.email} (ID: {db_user.id}) registered as {user_role.value}, created Org ID {new_organization.id}, Owner role in org.")
    verification_link = f"http://localhost:8080/verify-email.html?token={verification_token}"; print(f"VERIF LINK ({user_in.email}): {verification_link}")
    return {"message": "Registration successful. Please check your email."}

@auth_router.post("/login")
@limiter.limit("10/minute")
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.exec(select(models.user.User).where(models.user.User.email == form_data.username)).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password): logger.warning(f"Failed login: {form_data.username}"); raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email/password", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active: logger.warning(f"Inactive user login: {form_data.username}"); raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user.")
    if not user.is_email_verified: logger.warning(f"Unverified email login: {form_data.username}"); raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email not verified.")
    if user.is_2fa_enabled:
        if not user.totp_secret: logger.error(f"User {user.email} 2FA enabled, no secret."); raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="2FA config error.")
        interim_token = security.create_access_token(data={"sub": user.email, "type": "2fa_interim", "user_id": user.id}, expires_delta=timedelta(minutes=5))
        logger.info(f"User {user.email} passed pass step, 2FA required."); return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"message": "2FA code required", "interim_token": interim_token})
    else:
        access_token = security.create_access_token(data={"sub": user.email, "role": user.role.value, "user_id": user.id}, expires_delta=timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES))
        logger.info(f"User {user.email} logged in (2FA not enabled)."); return schemas.user.Token(access_token=access_token, token_type="bearer")

@auth_router.post("/login/verify-2fa", response_model=schemas.user.Token)
@limiter.limit("5/minute")
async def login_verify_2fa(request: Request, payload: schemas.user.LoginResponseStep2FA, db: Session = Depends(get_db)):
    try:
        interim_payload = security.decode_access_token(payload.interim_token)
        if interim_payload is None or interim_payload.get("type") != "2fa_interim": raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid/expired interim token.")
        user_id = interim_payload.get("user_id"); email = interim_payload.get("sub")
        if not user_id or not email: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interim token missing info.")
    except JWTError: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid/expired interim token (decode).")
    user = db.get(models.user.User, user_id)
    if not user or not user.is_active or not user.is_2fa_enabled or not user.totp_secret or user.email != email:
        logger.warning(f"2FA verify for ID {user_id} failed: User state invalid."); raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user state for 2FA.")
    if not two_factor_auth.verify_totp_code(user.totp_secret, payload.totp_code):
        logger.warning(f"Invalid TOTP for {user.email}."); raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code.")
    access_token = security.create_access_token(data={"sub": user.email, "role": user.role.value, "user_id": user.id}, expires_delta=timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES))
    logger.info(f"User {user.email} completed 2FA and logged in."); return schemas.user.Token(access_token=access_token, token_type="bearer")

@auth_router.get("/verify-email/{token}", response_model=Dict[str, str])
@limiter.limit("20/minute")
async def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    user = db.exec(select(models.user.User).where(models.user.User.email_verification_token == token)).first()
    if not user: logger.warning(f"Invalid email verify token: {token}"); raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token.")
    if user.verification_token_expires_at is None or datetime.now(timezone.utc) > user.verification_token_expires_at: logger.warning(f"Expired token for {user.email}: {token}"); raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token expired.")
    if user.is_email_verified: logger.info(f"Email already verified for {user.email}"); return {"message": "Email already verified."}
    user.is_email_verified = True; user.email_verification_token = None; user.verification_token_expires_at = None
    db.add(user); db.commit(); logger.info(f"Email verified for {user.email}")
    return {"message": "Email successfully verified."}

@auth_router.post("/request-password-reset", response_model=Dict[str, str])
@limiter.limit("5/minute")
async def request_password_reset_endpoint(request: Request, payload: schemas.user.RequestPasswordResetPayload, db: Session = Depends(get_db)):
    logger.info(f"Pass reset req for {payload.email}")
    user = db.exec(select(models.user.User).where(models.user.User.email == payload.email)).first()
    if user:
        token = security.create_password_reset_token()
        user.password_reset_token = token; user.password_reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=security.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
        db.add(user); db.commit(); print(f"PASS RESET LINK for {user.email}: http://localhost:8080/reset-password.html?token={token}")
    return {"message": "If account exists, link sent."}

@auth_router.post("/reset-password", response_model=Dict[str, str])
@limiter.limit("5/minute")
async def reset_password_endpoint(request: Request, payload: schemas.user.ResetPasswordPayload, db: Session = Depends(get_db)):
    user = db.exec(select(models.user.User).where(models.user.User.password_reset_token == payload.token)).first()
    if not user or user.password_reset_token_expires_at is None or datetime.now(timezone.utc) > user.password_reset_token_expires_at:
        logger.warning(f"Invalid/expired pass reset token: {payload.token}"); raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid/expired token.")
    user.hashed_password = security.get_password_hash(payload.new_password)
    user.password_reset_token = None; user.password_reset_token_expires_at = None
    db.add(user); db.commit(); logger.info(f"Pass reset for {user.email}")
    return {"message": "Password successfully reset."}

# --- User Specific Endpoints (user_router) ---
user_router.dependencies.append(Depends(get_current_active_user)) # Add default dependency

@user_router.get("/me", response_model=schemas.user.UserRead)
@limiter.limit("60/minute")
async def read_users_me(request: Request, current_user: models.user.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    org_role: Optional[schemas.role.OrgRole] = None
    if current_user.organization_id:
        membership = db.exec(select(models.membership.Membership).where(models.membership.Membership.user_id == current_user.id, models.membership.Membership.organization_id == current_user.organization_id)).first()
        if membership: org_role = membership.role
    user_read_data = schemas.user.UserRead.from_orm(current_user); user_read_data.current_organization_role = org_role
    return user_read_data

@user_router.put("/me", response_model=schemas.user.UserRead)
@limiter.limit("30/minute")
async def update_current_user_profile(
    request: Request,
    profile_update_payload: schemas.user.UserProfileUpdate,
    current_user: models.user.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    update_data = profile_update_payload.dict(exclude_unset=True)
    if not update_data: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No data provided for update.")
    for field, value in update_data.items(): setattr(current_user, field, value)
    current_user.updated_at = datetime.utcnow()
    db.add(current_user); db.commit(); db.refresh(current_user)

    # Re-fetch/set current_organization_role for the response
    org_role: Optional[schemas.role.OrgRole] = None
    if current_user.organization_id:
        membership = db.exec(select(models.membership.Membership).where(models.membership.Membership.user_id == current_user.id, models.membership.Membership.organization_id == current_user.organization_id)).first()
        if membership: org_role = membership.role

    user_read_response = schemas.user.UserRead.from_orm(current_user)
    user_read_response.current_organization_role = org_role
    logger.info(f"User profile updated for {current_user.email}")
    return user_read_response

@user_router.post("/2fa/setup", response_model=schemas.user.TwoFASetupResponse)
@limiter.limit("5/minute")
async def initiate_2fa_setup(request: Request, current_user: models.user.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.is_2fa_enabled: logger.warning(f"User {current_user.email} re-setup 2FA."); raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA already enabled.")
    secret = two_factor_auth.generate_totp_secret()
    current_user.totp_secret = secret
    db.add(current_user); db.commit(); db.refresh(current_user)
    uri = two_factor_auth.get_totp_provisioning_uri(current_user.email, secret)
    logger.info(f"2FA setup initiated for {current_user.email}.")
    return {"secret": secret, "provisioning_uri": uri}

@user_router.post("/2fa/enable", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def enable_2fa(request: Request, payload: schemas.user.TwoFAEnablePayload, current_user: models.user.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.is_2fa_enabled: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA already enabled.")
    if not current_user.totp_secret: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA setup not initiated.")
    if not two_factor_auth.verify_totp_code(current_user.totp_secret, payload.totp_code):
        logger.warning(f"Invalid TOTP for 2FA enable: {current_user.email}."); raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code.")
    current_user.is_2fa_enabled = True
    db.add(current_user); db.commit()
    logger.info(f"2FA enabled for {current_user.email}.")
    return {"message": "2FA enabled successfully."}

@user_router.get("/me/organization", response_model=Optional[schemas.organization.OrganizationRead])
async def read_user_organization(current_user: models.user.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if not current_user.organization_id: return None
    organization = db.get(models.organization.Organization, current_user.organization_id)
    if not organization: logger.error(f"Data integrity: User {current_user.id} org_id {current_user.organization_id} not found."); raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Org data error.")
    return organization

# --- Organization Member & Role Management Endpoints (organization_router) ---
# Moved dependencies to be defined before router to ensure they are available
organization_router.dependencies.append(Depends(get_current_active_user))

@organization_router.post("/{org_id}/members", response_model=schemas.membership.MembershipRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def add_organization_member(
    request: Request, org_id: int, payload: schemas.organization.AddMemberPayload,
    admin_user_org_tuple: Tuple[models.user.User, models.organization.Organization, schemas.role.OrgRole] = Depends(get_admin_or_owner_of_organization),
    db: Session = Depends(get_db)
):
    _, organization, _ = admin_user_org_tuple
    if organization.id != org_id: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path org_id does not match.")
    user_to_add = db.exec(select(models.user.User).where(models.user.User.email == payload.user_email)).first()
    if not user_to_add: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with email {payload.user_email} not found.")
    existing_membership, _ = await get_user_org_membership_details(user_to_add, organization, db)
    if existing_membership: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member.")
    if user_to_add.organization_id != organization.id: user_to_add.organization_id = organization.id ; db.add(user_to_add); logger.info(f"User {user_to_add.email}'s primary org updated to {organization.name}.")
    new_membership = models.membership.Membership(user_id=user_to_add.id, organization_id=organization.id, role=payload.role)
    db.add(new_membership); db.commit(); db.refresh(new_membership)
    logger.info(f"User {user_to_add.email} added to org {organization.name} as {payload.role.value}.")
    return new_membership

@organization_router.get("/{org_id}/members", response_model=List[schemas.membership.MembershipRead])
@limiter.limit("60/minute")
async def list_organization_members(
    request: Request, org_id: int,
    member_user_org_tuple: Tuple[models.user.User, models.organization.Organization, schemas.role.OrgRole] = Depends(get_member_of_organization),
):
    _, organization, _ = member_user_org_tuple
    if organization.id != org_id: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path org_id does not match.")
    return organization.memberships

@organization_router.put("/{org_id}/members/{member_user_id}", response_model=schemas.membership.MembershipRead)
@limiter.limit("30/minute")
async def update_organization_member_role(
    request: Request, org_id: int, member_user_id: int, payload: schemas.organization.UpdateMemberRolePayload,
    admin_user_org_tuple: Tuple[models.user.User, models.organization.Organization, schemas.role.OrgRole] = Depends(get_admin_or_owner_of_organization),
    db: Session = Depends(get_db)
):
    req_user, org, req_role = admin_user_org_tuple
    if org.id != org_id: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path org_id mismatch.")
    target_membership = db.exec(select(models.membership.Membership).where(models.membership.Membership.user_id == member_user_id, models.membership.Membership.organization_id == org.id)).first()
    if not target_membership: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found.")
    if target_membership.user_id == org.owner_id and target_membership.role == schemas.role.OrgRole.OWNER and payload.role != schemas.role.OrgRole.OWNER: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner's role cannot be changed from OWNER this way.")
    if target_membership.role == schemas.role.OrgRole.OWNER and req_role == schemas.role.OrgRole.ADMIN: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin cannot change Owner's role.")
    if target_membership.user_id == req_user.id and req_role == schemas.role.OrgRole.OWNER and payload.role != schemas.role.OrgRole.OWNER: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner cannot demote self.")
    target_membership.role = payload.role
    db.add(target_membership); db.commit(); db.refresh(target_membership)
    logger.info(f"Role of member {member_user_id} in org {org.id} changed to {payload.role.value} by {req_user.email}.")
    return target_membership

@organization_router.delete("/{org_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def remove_organization_member(
    request: Request, org_id: int, member_user_id: int,
    admin_user_org_tuple: Tuple[models.user.User, models.organization.Organization, schemas.role.OrgRole] = Depends(get_admin_or_owner_of_organization),
    db: Session = Depends(get_db)
):
    req_user, org, _ = admin_user_org_tuple
    if org.id != org_id: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path org_id mismatch.")
    if member_user_id == org.owner_id: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove org owner.")
    if member_user_id == req_user.id: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove self.")
    membership_to_delete = db.exec(select(models.membership.Membership).where(models.membership.Membership.user_id == member_user_id, models.membership.Membership.organization_id == org.id)).first()
    if not membership_to_delete: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found.")
    target_user = db.get(models.user.User, member_user_id)
    if target_user and target_user.organization_id == org.id: target_user.organization_id = None; db.add(target_user); logger.info(f"User {target_user.email}'s primary org link removed from org {org.id}.")
    db.delete(membership_to_delete); db.commit()
    logger.info(f"Member {member_user_id} removed from org {org.id} by {req_user.email}.")
    return

# --- Admin Endpoints (admin_router already defined with dependency) ---
@admin_router.get("/dashboard-summary", response_model=Dict[str, str])
@limiter.limit("60/minute")
async def admin_dashboard_summary(request: Request, admin_user: models.user.User = Depends(get_current_active_admin)):
    logger.info(f"Admin {admin_user.email} accessed dashboard.")
    return {"message": f"Welcome Admin {admin_user.email}! Dashboard summary."}

# --- WebSocket Chat & History Endpoints (on main app) ---
@app.websocket("/ws/chat/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str, token: str = Query(...), db: Session = Depends(get_db)):
    # ... (Full WebSocket endpoint logic as previously defined, ensure it uses models.user.User etc.)
    current_user: models.user.User
    try: payload = security.decode_access_token(token)
    except Exception as auth_ex: logger.warning(f"WS auth failed: {str(auth_ex)}"); await websocket.accept(); await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Auth failed: {str(auth_ex)}"); return
    if payload is None: await websocket.accept(); await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"); return
    user_id = payload.get("user_id")
    if user_id is None: await websocket.accept(); await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token missing user_id"); return
    user_in_db = db.get(models.user.User, user_id)
    if not (user_in_db and user_in_db.is_active and user_in_db.is_email_verified): await websocket.accept(); await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found/inactive/unverified."); return
    current_user = user_in_db
    logger.info(f"User {current_user.email} connected to WS for conv {conversation_id}")
    await manager.connect(websocket, conversation_id)
    try:
        while True:
            data = await websocket.receive_text(); logger.debug(f"WS msg from {current_user.email} in {conversation_id}: {data[:50]}...")
            sanitized_message_text = mask_pii_in_text(data)
            chat_msg_db = models.chat.ChatMessage(sender_id=current_user.id, message=sanitized_message_text, conversation_id=conversation_id, timestamp=datetime.utcnow())
            db.add(chat_msg_db); db.commit(); db.refresh(chat_msg_db)
            user_msg_payload = {"sender_id": current_user.id, "sender_email": current_user.email, "message": sanitized_message_text, "conversation_id": conversation_id, "timestamp": chat_msg_db.timestamp.isoformat()}
            await manager.broadcast_to_conversation(user_msg_payload, conversation_id)
            if conversation_id == BOT_CONVERSATION_ID_TRIGGER:
                bot_response = get_bot_response(sanitized_message_text)
                if bot_response:
                    bot_user = db.exec(select(models.user.User).where(models.user.User.email == BOT_USER_EMAIL)).first()
                    if not bot_user: bot_user = models.user.User(email=BOT_USER_EMAIL, hashed_password=security.get_password_hash("bot_pass"), is_active=True, is_email_verified=True, role=schemas.role.UserRole.USER); db.add(bot_user); db.commit(); db.refresh(bot_user)
                    bot_msg_db = models.chat.ChatMessage(sender_id=bot_user.id, message=bot_response, conversation_id=conversation_id, timestamp=datetime.utcnow())
                    db.add(bot_msg_db); db.commit(); db.refresh(bot_msg_db)
                    bot_msg_payload = {"sender_id": bot_user.id, "sender_email": BOT_USER_EMAIL, "message": bot_response, "conversation_id": conversation_id, "timestamp": bot_msg_db.timestamp.isoformat()}
                    await manager.broadcast_to_conversation(bot_msg_payload, conversation_id)
    except WebSocketDisconnect: logger.info(f"Client {current_user.email} disconnected from conv {conversation_id}")
    except Exception as e: logger.error(f"Error in WS (conv: {conversation_id}, user: {current_user.email}): {e}", exc_info=True)
    finally: manager.disconnect(websocket, conversation_id)


@app.get("/chat/{conversation_id}/messages", response_model=List[schemas.chat.ChatMessageRead], tags=["Chat"], dependencies=[Depends(get_current_active_user)])
@limiter.limit("100/minute")
async def get_conversation_messages(request: Request, conversation_id: str, db: Session = Depends(get_db), current_user: models.user.User = Depends(get_current_active_user), limit: int = Query(50, ge=1, le=100)):
    messages_from_db = db.exec(select(models.chat.ChatMessage).where(models.chat.ChatMessage.conversation_id == conversation_id).order_by(models.chat.ChatMessage.timestamp.desc()).limit(limit)).all()
    response_messages = [schemas.chat.ChatMessageRead.from_orm(msg_db, update={'sender_email': (db.get(models.user.User, msg_db.sender_id).email if db.get(models.user.User, msg_db.sender_id) else "Unknown")}) for msg_db in reversed(messages_from_db)]
    return response_messages

# --- Contact Management Endpoints (contact_router) ---
contact_router.dependencies.append(Depends(get_current_user_primary_org_role)) # Apply new default dependency

@contact_router.post("/", response_model=schemas.contact.ContactRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def create_contact(request: Request, contact_in: schemas.contact.ContactCreate, user_and_role_tuple: Tuple[models.user.User, Optional[schemas.role.OrgRole]] = Depends(get_current_user_primary_org_role), db: Session = Depends(get_db)):
    current_user, _ = user_and_role_tuple # Role not strictly needed for create, but user must be active
    if not current_user.organization_id: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not associated with an organization.")
    existing_contact = db.exec(select(models.contact.Contact).where(models.contact.Contact.email == contact_in.email)).first()
    if existing_contact: logger.warning(f"User {current_user.email} duplicate contact email: {contact_in.email}"); raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contact email exists.")
    db_contact = models.contact.Contact(**contact_in.dict(), owner_id=current_user.id)
    db.add(db_contact); db.commit(); db.refresh(db_contact)
    logger.info(f"User {current_user.email} created contact {db_contact.id}")
    return db_contact

@contact_router.get("/", response_model=List[schemas.contact.ContactRead])
@limiter.limit("60/minute")
def read_contacts(request: Request, skip: int = 0, limit: int = 100, user_and_role_tuple: Tuple[models.user.User, Optional[schemas.role.OrgRole]] = Depends(get_current_user_primary_org_role), db: Session = Depends(get_db)):
    current_user, user_org_role = user_and_role_tuple
    if not current_user.organization_id: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not associated with an organization.")
    if user_org_role in [schemas.role.OrgRole.OWNER, schemas.role.OrgRole.ADMIN]:
        org_member_users_stmt = select(models.user.User.id).where(models.user.User.organization_id == current_user.organization_id)
        contacts = db.exec(select(models.contact.Contact).where(models.contact.Contact.owner_id.in_(org_member_users_stmt)).offset(skip).limit(limit).order_by(models.contact.Contact.first_name)).all() # type: ignore
    else:
        contacts = db.exec(select(models.contact.Contact).where(models.contact.Contact.owner_id == current_user.id).offset(skip).limit(limit).order_by(models.contact.Contact.first_name)).all()
    return contacts

@contact_router.get("/{contact_id}", response_model=schemas.contact.ContactRead)
@limiter.limit("60/minute")
def read_contact(request: Request, contact_id: int, user_and_role_tuple: Tuple[models.user.User, Optional[schemas.role.OrgRole]] = Depends(get_current_user_primary_org_role), db: Session = Depends(get_db)):
    current_user, user_org_role = user_and_role_tuple
    contact = db.get(models.contact.Contact, contact_id)
    if not contact: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    if not current_user.organization_id: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not in an organization.")
    contact_owner = db.get(models.user.User, contact.owner_id)
    if not contact_owner or contact_owner.organization_id != current_user.organization_id: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized (cross-org).")
    if user_org_role in [schemas.role.OrgRole.OWNER, schemas.role.OrgRole.ADMIN] or contact.owner_id == current_user.id: return contact
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")

@contact_router.put("/{contact_id}", response_model=schemas.contact.ContactRead)
@limiter.limit("30/minute")
def update_contact(request: Request, contact_id: int, contact_in: schemas.contact.ContactUpdate, user_and_role_tuple: Tuple[models.user.User, Optional[schemas.role.OrgRole]] = Depends(get_current_user_primary_org_role), db: Session = Depends(get_db)):
    current_user, user_org_role = user_and_role_tuple
    contact = db.get(models.contact.Contact, contact_id)
    if not contact: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    if not current_user.organization_id: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not in an organization.")
    contact_owner = db.get(models.user.User, contact.owner_id)
    if not contact_owner or contact_owner.organization_id != current_user.organization_id: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized (cross-org).")
    can_update = user_org_role in [schemas.role.OrgRole.OWNER, schemas.role.OrgRole.ADMIN] or contact.owner_id == current_user.id
    if not can_update: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")
    update_data = contact_in.dict(exclude_unset=True)
    if 'email' in update_data and update_data['email'] != contact.email:
        existing = db.exec(select(models.contact.Contact).where(models.contact.Contact.email == update_data['email'])).first()
        if existing and existing.id != contact_id: logger.warning(f"Contact update conflict email: {update_data['email']}"); raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email in use.")
    for k, v in update_data.items(): setattr(contact, k, v)
    contact.updated_at = datetime.utcnow()
    db.add(contact); db.commit(); db.refresh(contact)
    logger.info(f"User {current_user.email} updated contact {contact_id}")
    return contact

@contact_router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
def delete_contact(request: Request, contact_id: int, user_and_role_tuple: Tuple[models.user.User, Optional[schemas.role.OrgRole]] = Depends(get_current_user_primary_org_role), db: Session = Depends(get_db)):
    current_user, user_org_role = user_and_role_tuple
    contact = db.get(models.contact.Contact, contact_id)
    if not contact: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    if not current_user.organization_id: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not in an organization.")
    contact_owner = db.get(models.user.User, contact.owner_id)
    if not contact_owner or contact_owner.organization_id != current_user.organization_id: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized (cross-org).")
    can_delete = user_org_role in [schemas.role.OrgRole.OWNER, schemas.role.OrgRole.ADMIN] or contact.owner_id == current_user.id
    if not can_delete: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")
    db.delete(contact); db.commit()
    logger.info(f"User {current_user.email} deleted contact {contact_id}")
    return

# --- Inbox Endpoints (inbox_router is already defined) ---
@inbox_router.post("/ingest-emails", dependencies=[Depends(get_current_active_admin)])
@limiter.limit("2/minute")
async def trigger_email_ingestion(request: Request):
    if INGEST_IMAP_USER == "your_test_email@gmail.com" or INGEST_IMAP_PASS == "your_gmail_app_password": logger.error("Ingestion with placeholder creds."); raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="IMAP creds placeholders.")
    logger.info(f"Email ingestion started by admin.")
    result = ingest_emails_from_mailbox()
    if result.get("errors") and len(result["errors"]) > 0 : logger.error(f"Ingestion errors: {result['errors']}"); return {"message": "Ingestion errors.", "ingested": result.get("new_emails_ingested",0), "errors": result["errors"]}
    logger.info(f"Ingestion success. Ingested: {result.get('new_emails_ingested',0)}. Info: {result.get('message', '')}")
    return {"message": "Ingestion success.", "ingested": result.get("new_emails_ingested",0), "info": result.get("message", "")}

@inbox_router.get("/emails", response_model=List[schemas.inbox.InboxEmailRead], dependencies=[Depends(get_current_active_user)])
@limiter.limit("60/minute")
async def list_ingested_emails(request: Request, skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return db.exec(select(models.inbox.InboxEmail).order_by(models.inbox.InboxEmail.received_at.desc()).offset(skip).limit(limit)).all()

# Include all routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(contact_router)
app.include_router(inbox_router)
app.include_router(organization_router)
