from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

DATABASE_URL = "sqlite:///scoutmind.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, index=True)
    full_name        = Column(String(100), nullable=False)
    email            = Column(String(150), unique=True, nullable=False, index=True)
    password_hash    = Column(String(255), nullable=False)
    district         = Column(String(50), nullable=False)
    group_name       = Column(String(50), nullable=False)
    unit             = Column(String(50), nullable=False)
    is_verified      = Column(Boolean, default=False)
    verify_token     = Column(String(100), nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, nullable=False, index=True)
    title        = Column(String(200), nullable=False)   # e.g. "Cubs — Friendship — 27/04/2026"
    unit         = Column(String(50), nullable=True)
    theme        = Column(String(200), nullable=True)
    meeting_date = Column(String(20), nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id         = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, nullable=False, index=True)
    user_id    = Column(Integer, nullable=False, index=True)
    role       = Column(String(20), nullable=False)   # "user" or "assistant"
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()