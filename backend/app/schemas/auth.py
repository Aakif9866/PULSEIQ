from pydantic import BaseModel, Field

from app.schemas.user import UserRead


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    user: UserRead
    tokens: TokenPair


class RefreshRequest(BaseModel):
    refresh_token: str = Field(max_length=2048)


class DeleteAccountRequest(BaseModel):
    password: str = Field(max_length=128)
