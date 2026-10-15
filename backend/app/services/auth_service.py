import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
)
from app.core.logging import get_logger
from app.core.security import (
    InvalidTokenError,
    burn_password_check,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models import (
    AiUsageLog,
    Anomaly,
    Dashboard,
    Dataset,
    Insight,
    Monitor,
    QueryHistory,
    SavedQuery,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPair
from app.schemas.user import UserCreate, UserLogin
from app.storage.base import StorageProvider

logger = get_logger(__name__)

# Everything a user owns, for the data export. Order is the export's order.
_OWNED_MODELS: list[tuple[str, Any]] = [
    ("datasets", Dataset),
    ("dashboards", Dashboard),
    ("insights", Insight),
    ("saved_queries", SavedQuery),
    ("query_history", QueryHistory),
    ("monitors", Monitor),
    ("anomalies", Anomaly),
    ("ai_usage", AiUsageLog),
]


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {c.key: getattr(row, c.key) for c in row.__table__.columns}


class AuthService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = UserRepository(db)

    def signup(self, payload: UserCreate) -> tuple[User, TokenPair]:
        if self._repo.get_by_email(payload.email) is not None:
            raise EmailAlreadyRegisteredError(payload.email)

        user = self._repo.create(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
        )
        logger.info("user_signed_up", user_id=str(user.id))
        return user, self._issue_tokens(user.id)

    def login(self, payload: UserLogin) -> tuple[User, TokenPair]:
        user = self._repo.get_by_email(payload.email)
        if user is None:
            burn_password_check(payload.password)  # same timing as a wrong password
            logger.info("login_failed")
            raise InvalidCredentialsError()
        if not verify_password(payload.password, user.hashed_password):
            logger.info("login_failed", user_id=str(user.id))
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError()

        logger.info("user_logged_in", user_id=str(user.id))
        return user, self._issue_tokens(user.id)

    def refresh(self, refresh_token: str) -> TokenPair:
        """Rotates: the presented token is revoked and a new pair issued.
        Presenting an already-revoked token means it was copied, so every
        session for that user is revoked."""
        user_id, jti = decode_refresh_token(refresh_token)
        row = self._db.get(RefreshToken, jti)
        now = datetime.now(UTC)
        if row is None or row.user_id != user_id or row.expires_at <= now:
            raise InvalidTokenError("Unknown or expired refresh token")
        if row.revoked_at is not None:
            logger.warning("refresh_token_reuse_detected", user_id=str(user_id))
            self._revoke_all(user_id)
            raise InvalidTokenError("Refresh token already used")

        user = self._repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError("User not found")

        row.revoked_at = now
        return self._issue_tokens(user_id)

    def logout(self, refresh_token: str) -> None:
        try:
            _, jti = decode_refresh_token(refresh_token)
        except InvalidTokenError:
            return  # already unusable
        row = self._db.get(RefreshToken, jti)
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            self._db.commit()

    def export_account(self, user: User) -> dict[str, Any]:
        data: dict[str, Any] = {
            "exported_at": datetime.now(UTC),
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "created_at": user.created_at,
            },
        }
        for name, model in _OWNED_MODELS:
            rows = self._db.scalars(select(model).where(model.owner_id == user.id)).all()
            data[name] = [_row_to_dict(r) for r in rows]
        return data

    def delete_account(self, user: User, storage: StorageProvider) -> None:
        """Deletes the stored files, then the user; every owned row goes
        with it through ON DELETE CASCADE."""
        keys = self._db.scalars(
            select(Dataset.storage_key).where(Dataset.owner_id == user.id)
        ).all()
        for key in keys:
            try:
                storage.delete(key)
            except Exception:  # noqa: BLE001 - one missing file mustn't block deletion
                logger.exception("account_delete_storage_failed", user_id=str(user.id))
        self._db.delete(user)
        self._db.commit()
        logger.info("account_deleted", user_id=str(user.id), files=len(keys))

    def _revoke_all(self, user_id: uuid.UUID) -> None:
        self._db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        self._db.commit()

    def _issue_tokens(self, user_id: uuid.UUID) -> TokenPair:
        refresh_token, jti, expires_at = create_refresh_token(user_id)
        self._db.add(RefreshToken(jti=jti, user_id=user_id, expires_at=expires_at))
        self._db.commit()
        return TokenPair(
            access_token=create_access_token(user_id), refresh_token=refresh_token
        )
