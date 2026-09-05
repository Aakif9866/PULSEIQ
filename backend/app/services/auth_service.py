from sqlalchemy.orm import Session

from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPair
from app.schemas.user import UserCreate, UserLogin

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: Session) -> None:
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
        return user, self._issue_tokens(user)

    def login(self, payload: UserLogin) -> tuple[User, TokenPair]:
        user = self._repo.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            logger.info("login_failed", email=payload.email)
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError()

        logger.info("user_logged_in", user_id=str(user.id))
        return user, self._issue_tokens(user)

    @staticmethod
    def _issue_tokens(user: User) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )
