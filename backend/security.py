from datetime import datetime
from typing import Optional

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(raw_password: str) -> str:
    return generate_password_hash(raw_password, method="pbkdf2:sha256", salt_length=16)


def verify_password(raw_password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, raw_password)


def timestamp_now() -> datetime:
    return datetime.utcnow()

