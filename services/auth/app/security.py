from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from services.auth.app.config import settings


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(user_id: str, role: str, email: str, expires_in_minutes: int | None = None) -> tuple[str, int]:
    expires_minutes = expires_in_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expires_delta = timedelta(minutes=expires_minutes)
    expire_time = datetime.now(timezone.utc) + expires_delta
    expires_in_seconds = int(expires_delta.total_seconds())

    to_encode = {
        "sub": str(user_id),
        "id": str(user_id),
        "role": role,
        "email": email,
        "exp": expire_time
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt, expires_in_seconds
