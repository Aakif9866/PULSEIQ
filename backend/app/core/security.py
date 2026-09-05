"""Password hashing and JWT issuance/verification."""
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: UUID, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: UUID) -> str:
    return _create_token(
        user_id, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(user_id: UUID) -> str:
    return _create_token(
        user_id, "refresh", timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    )


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, expected_type: TokenType = "access") -> UUID:
    """Decode and validate a JWT, returning the subject user id.

    Raises InvalidTokenError on any failure (expired, bad signature, wrong
    type, malformed subject) so callers have a single exception to handle.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise InvalidTokenError("Token could not be decoded") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError("Unexpected token type")

    sub = payload.get("sub")
    if not sub:
        raise InvalidTokenError("Token missing subject")

    try:
        return UUID(sub)
    except ValueError as exc:
        raise InvalidTokenError("Token subject is not a valid user id") from exc
