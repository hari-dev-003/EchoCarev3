from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

ALGO = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(user_id: str, extra: dict | None = None) -> str:
    s = get_settings()
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=s.ACCESS_TOKEN_MINUTES), **(extra or {})}
    return jwt.encode(payload, s.SECRET_KEY, algorithm=ALGO)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().SECRET_KEY, algorithms=[ALGO])
    except jwt.PyJWTError:
        return None
