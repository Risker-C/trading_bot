import os
from typing import Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api import auth as auth_utils

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _resolve_credentials() -> Tuple[str, str]:
    username = os.getenv("API_USERNAME", "admin")
    password_hash = os.getenv("API_PASSWORD_HASH")
    fallback_password = os.getenv("API_PASSWORD")

    if not password_hash and fallback_password:
        password_hash = auth_utils.get_password_hash(fallback_password)

    if not password_hash:
        password_hash = auth_utils.get_password_hash(os.getenv("API_DEFAULT_PASSWORD", "admin123"))

    return username, password_hash


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    expected_username, hashed_password = _resolve_credentials()
    if payload.username != expected_username or not auth_utils.verify_password(payload.password, hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = auth_utils.create_access_token({"sub": expected_username})
    expires_in = auth_utils.EXPIRE_MINUTES * 60

    return LoginResponse(access_token=token, expires_in=expires_in)
