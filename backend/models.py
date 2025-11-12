from datetime import datetime
from typing import Optional

from sqlalchemy import func

from .extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)

    chat_sessions = db.relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    documents = db.relationship("UploadedDocument", back_populates="user", cascade="all, delete-orphan")
    usage_logs = db.relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User {self.email}>"


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="chat_sessions")
    messages = db.relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<ChatSession {self.id} user={self.user_id}>"


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False)  # "user" | "assistant"
    content = db.Column(db.Text, nullable=False)
    sources = db.Column(db.JSON, nullable=True)
    response_time_ms = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    session = db.relationship("ChatSession", back_populates="messages")


class UploadedDocument(db.Model):
    __tablename__ = "uploaded_documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    filename = db.Column(db.String(512), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    chunk_count = db.Column(db.Integer, default=0, nullable=False)
    metadata = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="documents")


class UsageLog(db.Model):
    __tablename__ = "usage_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    endpoint = db.Column(db.String(128), nullable=False)
    latency_ms = db.Column(db.Float, nullable=False)
    tokens_used = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User", back_populates="usage_logs")


def calculate_usage_summary(user_id: Optional[int] = None):
    query = db.session.query(
        func.count(UsageLog.id).label("total_calls"),
        func.avg(UsageLog.latency_ms).label("average_latency"),
    )
    if user_id:
        query = query.filter(UsageLog.user_id == user_id)

    row = query.one()
    return {
        "total_calls": row.total_calls or 0,
        "average_latency_ms": float(row.average_latency or 0),
    }

