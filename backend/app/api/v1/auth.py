from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_storage
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
)
from app.core.rate_limit import client_ip, hit, rate_limit
from app.core.security import InvalidTokenError, verify_password
from app.models.user import User
from app.schemas.auth import AuthResponse, DeleteAccountRequest, RefreshRequest, TokenPair
from app.schemas.user import UserCreate, UserLogin, UserRead
from app.services.auth_service import AuthService
from app.storage import StorageProvider

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("signup", 5, 3600))],
)
def signup(payload: UserCreate, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        user, tokens = AuthService(db).signup(payload)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc
    return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    # Per IP stops one client guessing many accounts; per email stops many
    # clients guessing one account.
    hit("login-ip", client_ip(request), 10, 60)
    hit("login-email", payload.email.lower(), 10, 900)
    try:
        user, tokens = AuthService(db).login(payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        ) from exc
    return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)


@router.post(
    "/refresh",
    response_model=TokenPair,
    dependencies=[Depends(rate_limit("refresh", 30, 60))],
)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        return AuthService(db).refresh(payload.refresh_token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        ) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> None:
    AuthService(db).logout(payload.refresh_token)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get(
    "/me/export",
    dependencies=[Depends(rate_limit("export", 5, 3600))],
)
def export_my_data(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> JSONResponse:
    """Everything stored about the caller, as one JSON download."""
    data: dict[str, Any] = AuthService(db).export_account(current_user)
    return JSONResponse(
        content=jsonable_encoder(data),
        headers={"Content-Disposition": 'attachment; filename="pulseiq-export.json"'},
    )


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("delete-account", 5, 3600))],
)
def delete_my_account(
    payload: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> None:
    if settings.DEMO_USER_EMAIL and current_user.email == settings.DEMO_USER_EMAIL.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The shared demo account can't be deleted.",
        )
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect password.")
    AuthService(db).delete_account(current_user, storage)
