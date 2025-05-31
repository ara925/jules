from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select, func
from datetime import timedelta, datetime, timezone
from typing import Dict, List

# Project specific imports
from .database import engine, create_db_and_tables, get_db
from . import security
from . import schemas
from . import models
from .websocket_manager import manager
from .bot_logic import get_bot_response, BOT_USER_EMAIL, BOT_CONVERSATION_ID_TRIGGER
# Import for email ingestion service and its config (for credential check)
from .email_ingestion_service import ingest_emails_from_mailbox, IMAP_USER as INGEST_IMAP_USER, IMAP_PASS as INGEST_IMAP_PASS

app = FastAPI(title="Aiden AI Backend", version="0.1.0")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database and table creation on startup
@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Aiden AI Backend"}

# WebSocket Chat Endpoint
@app.websocket("/ws/chat/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    current_user: models.user.User # Use models.user.User
    try:
        payload = security.decode_access_token(token)
        if payload is None:
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return

        email: str | None = payload.get("sub")
        if email is None:
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token missing subject")
            return

        user_in_db = db.exec(select(models.user.User).where(models.user.User.email == email)).first()
        if user_in_db is None or not user_in_db.is_active or not user_in_db.is_email_verified:
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found, inactive, or email not verified.")
            return
        current_user = user_in_db
    except Exception as auth_ex:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Authentication failed: {str(auth_ex)}")
        return

    await manager.connect(websocket, conversation_id)
    try:
        while True:
            data = await websocket.receive_text()

            chat_message_db = models.chat.ChatMessage(
                sender_id=current_user.id,
                message=data,
                conversation_id=conversation_id,
                timestamp=datetime.utcnow()
            )
            db.add(chat_message_db)
            db.commit()
            db.refresh(chat_message_db)

            user_message_payload = {
                "sender_id": current_user.id,
                "sender_email": current_user.email,
                "message": data,
                "conversation_id": conversation_id,
                "timestamp": chat_message_db.timestamp.isoformat()
            }
            await manager.broadcast_to_conversation(user_message_payload, conversation_id)

            if conversation_id == BOT_CONVERSATION_ID_TRIGGER:
                bot_response_text = get_bot_response(data)
                if bot_response_text:
                    bot_user = db.exec(select(models.user.User).where(models.user.User.email == BOT_USER_EMAIL)).first()
                    if not bot_user:
                        bot_user = models.user.User(
                            email=BOT_USER_EMAIL,
                            hashed_password=security.get_password_hash("a_very_secure_bot_password_replace_me"),
                            is_active=True,
                            is_email_verified=True,
                            role=schemas.role.UserRole.USER
                        )
                        db.add(bot_user)
                        db.commit()
                        db.refresh(bot_user)

                    bot_sender_id = bot_user.id
                    bot_message_db = models.chat.ChatMessage(
                        sender_id=bot_sender_id,
                        message=bot_response_text,
                        conversation_id=conversation_id,
                        timestamp=datetime.utcnow()
                    )
                    db.add(bot_message_db)
                    db.commit()
                    db.refresh(bot_message_db)

                    bot_response_payload = {
                        "sender_id": bot_sender_id,
                        "sender_email": BOT_USER_EMAIL,
                        "message": bot_response_text,
                        "conversation_id": conversation_id,
                        "timestamp": bot_message_db.timestamp.isoformat()
                    }
                    await manager.broadcast_to_conversation(bot_response_payload, conversation_id)
    except WebSocketDisconnect:
        print(f"Client {current_user.email} disconnected from conversation {conversation_id}")
    except Exception as e:
        print(f"Error in websocket (conv: {conversation_id}, user: {current_user.email}): {e}")
    finally:
        manager.disconnect(websocket, conversation_id)

# User Authentication and Management Endpoints
@app.post("/users/register", response_model=Dict[str, str])
async def register_user(user_in: schemas.user.UserCreate, db: Session = Depends(get_db)):
    db_user_exists = db.exec(select(models.user.User).where(models.user.User.email == user_in.email)).first()
    if db_user_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hashed_password = security.get_password_hash(user_in.password)
    verification_token = security.create_verification_token()
    token_expires_at = datetime.now(timezone.utc) + timedelta(hours=security.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)

    users_count_result = db.exec(select(func.count(models.user.User.id))).one_or_none()
    users_count = users_count_result if users_count_result is not None else 0
    user_role = schemas.role.UserRole.ADMIN if users_count == 0 else schemas.role.UserRole.USER

    db_user = models.user.User(
        email=user_in.email,
        hashed_password=hashed_password,
        is_active=True,
        email_verification_token=verification_token,
        verification_token_expires_at=token_expires_at,
        role=user_role
    )
    db.add(db_user)
    db.commit()

    verification_link = f"http://localhost:8080/verify-email.html?token={verification_token}"
    print(f"VERIFICATION LINK (for {user_in.email}): {verification_link}")
    return {"message": "Registration successful. Please check your email to verify your account."}

@app.post("/users/login", response_model=schemas.user.Token)
async def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.exec(select(models.user.User).where(models.user.User.email == form_data.username)).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not verified. Please check your inbox.",
        )
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email, "role": user.role.value}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/verify-email/{token}", response_model=Dict[str, str])
async def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.exec(select(models.user.User).where(models.user.User.email_verification_token == token)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token.")
    if user.verification_token_expires_at is None or datetime.now(timezone.utc) > user.verification_token_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token expired.")
    if user.is_email_verified:
         return {"message": "Email already verified."}
    user.is_email_verified = True
    user.email_verification_token = None
    user.verification_token_expires_at = None
    db.add(user)
    db.commit()
    return {"message": "Email successfully verified. You can now login."}

@app.post("/users/request-password-reset", response_model=Dict[str, str])
async def request_password_reset(payload: schemas.user.RequestPasswordResetPayload, db: Session = Depends(get_db)):
    user = db.exec(select(models.user.User).where(models.user.User.email == payload.email)).first()
    if user:
        password_reset_token = security.create_password_reset_token()
        token_expires_at = datetime.now(timezone.utc) + timedelta(hours=security.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
        user.password_reset_token = password_reset_token
        user.password_reset_token_expires_at = token_expires_at
        db.add(user)
        db.commit()
        reset_link = f"http://localhost:8080/reset-password.html?token={password_reset_token}"
        print(f"PASSWORD RESET LINK (for {user.email}): {reset_link}")
    return {"message": "If an account with that email exists, a password reset link has been sent."}

@app.post("/users/reset-password", response_model=Dict[str, str])
async def reset_password(payload: schemas.user.ResetPasswordPayload, db: Session = Depends(get_db)):
    user = db.exec(select(models.user.User).where(models.user.User.password_reset_token == payload.token)).first()
    if not user or user.password_reset_token_expires_at is None or datetime.now(timezone.utc) > user.password_reset_token_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired password reset token.")
    user.hashed_password = security.get_password_hash(payload.new_password)
    user.password_reset_token = None
    user.password_reset_token_expires_at = None
    db.add(user)
    db.commit()
    return {"message": "Password has been successfully reset."}

# Current User Dependency
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.user.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data_dict = security.decode_access_token(token)
    if token_data_dict is None:
        raise credentials_exception

    token_data = schemas.user.TokenData(email=token_data_dict.get("sub"), role=token_data_dict.get("role"))
    if token_data.email is None:
        raise credentials_exception

    user = db.exec(select(models.user.User).where(models.user.User.email == token_data.email)).first()
    if user is None:
        raise credentials_exception
    return user

@app.get("/users/me", response_model=schemas.user.UserRead)
async def read_users_me(current_user: models.user.User = Depends(get_current_user)):
    return current_user

# Admin-Specific Endpoints and Dependencies
async def get_current_active_admin(current_user: models.user.User = Depends(get_current_user)):
    if current_user.role != schemas.role.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this resource. Admin role required."
        )
    return current_user

@app.get("/admin/dashboard-summary", response_model=Dict[str, str])
async def admin_dashboard_summary(admin_user: models.user.User = Depends(get_current_active_admin)):
    return {"message": f"Welcome Admin {admin_user.email}! This is your dashboard summary."}

# Message History Endpoint
@app.get("/chat/{conversation_id}/messages", response_model=List[schemas.chat.ChatMessageRead])
async def get_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: models.user.User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100)
):
    messages_from_db = db.exec(
        select(models.chat.ChatMessage)
        .where(models.chat.ChatMessage.conversation_id == conversation_id)
        .order_by(models.chat.ChatMessage.timestamp.desc())
        .limit(limit)
    ).all()
    response_messages = []
    for msg_db in reversed(messages_from_db):
        sender_user = db.get(models.user.User, msg_db.sender_id)
        sender_email = sender_user.email if sender_user else "Unknown User"
        msg_read = schemas.chat.ChatMessageRead(
            id=msg_db.id,
            sender_id=msg_db.sender_id,
            sender_email=sender_email,
            message=msg_db.message,
            timestamp=msg_db.timestamp,
            conversation_id=msg_db.conversation_id
        )
        response_messages.append(msg_read)
    return response_messages

# Contact Management Router
contact_router = APIRouter(
    prefix="/contacts",
    tags=["contacts"],
    dependencies=[Depends(get_current_user)] # Protected by default
)

@contact_router.post("/", response_model=schemas.contact.ContactRead, status_code=status.HTTP_201_CREATED)
def create_contact(
    contact_in: schemas.contact.ContactCreate,
    db: Session = Depends(get_db),
    current_user: models.user.User = Depends(get_current_user)
):
    existing_contact = db.exec(select(models.contact.Contact).where(models.contact.Contact.email == contact_in.email)).first()
    if existing_contact:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contact with this email already exists globally.")

    db_contact = models.contact.Contact(**contact_in.dict(), owner_id=current_user.id)
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@contact_router.get("/", response_model=List[schemas.contact.ContactRead])
def read_contacts(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.user.User = Depends(get_current_user)
):
    contacts = db.exec(
        select(models.contact.Contact)
        .where(models.contact.Contact.owner_id == current_user.id)
        .offset(skip).limit(limit)
        .order_by(models.contact.Contact.first_name)
    ).all()
    return contacts

@contact_router.get("/{contact_id}", response_model=schemas.contact.ContactRead)
def read_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: models.user.User = Depends(get_current_user)
):
    contact = db.get(models.contact.Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    if contact.owner_id != current_user.id and current_user.role != schemas.role.UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this contact")
    return contact

@contact_router.put("/{contact_id}", response_model=schemas.contact.ContactRead)
def update_contact(
    contact_id: int,
    contact_in: schemas.contact.ContactUpdate,
    db: Session = Depends(get_db),
    current_user: models.user.User = Depends(get_current_user)
):
    contact = db.get(models.contact.Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    if contact.owner_id != current_user.id and current_user.role != schemas.role.UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this contact")

    update_data = contact_in.dict(exclude_unset=True)
    if 'email' in update_data and update_data['email'] != contact.email:
        existing_email_contact = db.exec(select(models.contact.Contact).where(models.contact.Contact.email == update_data['email'])).first()
        if existing_email_contact and existing_email_contact.id != contact_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This email is already in use by another contact.")

    for key, value in update_data.items():
        setattr(contact, key, value)

    contact.updated_at = datetime.utcnow() # Manually update updated_at
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact

@contact_router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: models.user.User = Depends(get_current_user)
):
    contact = db.get(models.contact.Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    if contact.owner_id != current_user.id and current_user.role != schemas.role.UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this contact")

    db.delete(contact)
    db.commit()
    return # FastAPI handles 204 response

app.include_router(contact_router)

# Inbox Router
inbox_router = APIRouter(
    prefix="/inbox",
    tags=["inbox"]
)

@inbox_router.post("/ingest-emails", dependencies=[Depends(get_current_active_admin)])
async def trigger_email_ingestion():
    # Basic check if placeholder credentials are still in use
    if INGEST_IMAP_USER == "your_test_email@gmail.com" or INGEST_IMAP_PASS == "your_gmail_app_password":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IMAP credentials are placeholders. Please configure them in email_ingestion_service.py before use."
        )

    # For production, consider background tasks:
    # from fastapi import BackgroundTasks
    # async def wrapper(background_tasks: BackgroundTasks):
    #     background_tasks.add_task(ingest_emails_from_mailbox)
    #     return {"message": "Email ingestion process started in the background."}
    # return await wrapper(background_tasks) # if using background tasks

    result = ingest_emails_from_mailbox() # Synchronous call for MVP

    # Check if 'errors' key exists and has content
    if result.get("errors") and len(result["errors"]) > 0 :
        return {"message": "Email ingestion process completed with errors.", "ingested_count": result.get("new_emails_ingested", 0), "errors": result["errors"]}

    return {"message": "Email ingestion process completed successfully.", "ingested_count": result.get("new_emails_ingested", 0), "info": result.get("message", "")}


@inbox_router.get("/emails", response_model=List[schemas.inbox.InboxEmailRead], dependencies=[Depends(get_current_user)])
async def list_ingested_emails(
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db)
    # current_user: models.user.User = Depends(get_current_user) # Already in router dependencies if applied globally
):
    emails = db.exec(
        select(models.inbox.InboxEmail)
        .order_by(models.inbox.InboxEmail.received_at.desc())
        .offset(skip).limit(limit)
    ).all()
    return emails

app.include_router(inbox_router)
