from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware # Added CORS
from sqlmodel import Session
from .database import engine, create_db_and_tables
from .schemas.user import UserCreate, UserRead
from .schemas.chat import ChatMessageCreate, ChatMessageRead # Added chat schemas
from .models.user import User

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

def get_db():
    with Session(engine) as session:
        yield session

@app.get("/")
async def root():
    return {"message": "Welcome to Aiden AI Backend"}

@app.post("/chat/", response_model=ChatMessageRead)
async def chat_endpoint(message: ChatMessageCreate):
    # Simple echo bot logic for now
    return ChatMessageRead(text=f"You said: {message.text}", sender="bot_echo")

@app.post("/users/register", response_model=UserRead)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # In a real app, hash the password here
    db_user = User(email=user.email, hashed_password=user.password, is_active=True)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/users/login")
async def login_user(user: UserCreate): # Assuming UserCreate for login for now
    # In a real app, verify password and create JWT token
    return {"message": "Login successful", "token": "dummy_token"}
