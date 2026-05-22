"""Auth router — авторизация через Telegram Mini App."""

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.database import get_session
from app.schemas.auth import RefreshRequest, TelegramAuthRequest, TokenResponse
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_service(db: AsyncSession = Depends(get_session)) -> AuthService:
    return AuthService(db)


@router.post("/telegram", response_model=TokenResponse)
async def auth_telegram(
    body: TelegramAuthRequest,
    service: AuthService = Depends(_get_service),
) -> TokenResponse:
    """
    Авторизация через Telegram Mini App.

    Клиент передаёт window.Telegram.WebApp.initData.
    Сервер проверяет подпись и выдаёт JWT.

    is_registered=False означает: пользователь открыл Mini App,
    но ещё не прошёл регистрацию через бота → перенаправить в бота.
    """
    try:
        return await service.authenticate_telegram(body.init_data)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    service: AuthService = Depends(_get_service),
) -> TokenResponse:
    """Обновить access-токен через refresh-токен."""
    try:
        user_id = decode_token(body.refresh_token, expected_type="refresh")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh-токен истёк. Нужна повторная авторизация.",
        )
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный refresh-токен.",
        )

    try:
        return await service.refresh_tokens(user_id)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
