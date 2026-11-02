"""Database models used by AuditAI's OTP authentication system."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    full_name = Column(String(200), nullable=True)
    role = Column(String(50), nullable=False, default="auditor")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    refresh_sessions = relationship("RefreshSession", back_populates="user", cascade="all, delete-orphan")


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(320), nullable=False, index=True)
    code_digest = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_digest = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="refresh_sessions")
