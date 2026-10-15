"""Password hashing and JWT issuance/verification."""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]

# bcrypt only reads the first 72 bytes. Signup rejects longer passwords;
# verification truncates the same way, so hashes made by the old passlib
# setup (which truncated silently) still verify.
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:BCRYPT_MAX_BYTES], bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode()[:BCRYPT_MAX_BYTES], hashed_password.encode())
    except ValueError:  # malformed stored hash
        return False


# Checked against when the email doesn't exist, so a failed login takes the
# same time either way and response time doesn't reveal registered emails.
_DUMMY_HASH = hash_password("timing-equalizer")


def burn_password_check(plain_password: str) -> None:
    verify_password(plain_password, _DUMMY_HASH)


def _create_token(
    subject: UUID, token_type: TokenType, expires_delta: timedelta, jti: UUID | None = None
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if jti is not None:
        payload["jti"] = str(jti)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: UUID) -> str:
    return _create_token(
        user_id, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(user_id: UUID) -> tuple[str, UUID, datetime]:
    """Returns (token, jti, expires_at); the caller stores the jti so the
    token can be rotated and revoked server-side."""
    jti = uuid.uuid4()
    expires_delta = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    token = _create_token(user_id, "refresh", expires_delta, jti=jti)
    return token, jti, datetime.now(UTC) + expires_delta


class InvalidTokenError(Exception):
    pass


def _decode(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Token could not be decoded") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError("Unexpected token type")
    return payload


def _uuid_claim(payload: dict[str, Any], claim: str) -> UUID:
    value = payload.get(claim)
    if not value:
        raise InvalidTokenError(f"Token missing {claim}")
    try:
        return UUID(value)
    except (ValueError, TypeError) as exc:
        raise InvalidTokenError(f"Token {claim} is not a valid id") from exc


def decode_token(token: str, expected_type: TokenType = "access") -> UUID:
    """Decode and validate a JWT, returning the subject user id.

    Raises InvalidTokenError on any failure (expired, bad signature, wrong
    type, malformed subject) so callers have a single exception to handle.
    """
    return _uuid_claim(_decode(token, expected_type), "sub")


def decode_refresh_token(token: str) -> tuple[UUID, UUID]:
    """Returns (user_id, jti)."""
    payload = _decode(token, "refresh")
    return _uuid_claim(payload, "sub"), _uuid_claim(payload, "jti")
