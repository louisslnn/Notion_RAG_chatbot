import os
from datetime import timedelta


class BaseConfig:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(os.path.dirname(__file__), '..', 'instance', 'app.db')}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "uploads")),
    )
    VECTOR_STORE_FOLDER = os.getenv(
        "VECTOR_STORE_FOLDER",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "vectorstore")),
    )
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload limit
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
    RATE_LIMIT = os.getenv("RATE_LIMIT", "60/minute")
    FRONTEND_ORIGINS = [origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    JWT_COOKIE_SECURE = True

