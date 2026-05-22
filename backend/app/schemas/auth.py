"""Схемы авторизации через Telegram Mini App."""

from pydantic import BaseModel


class TelegramAuthRequest(BaseModel):
    """
    Запрос авторизации.
    init_data — строка из window.Telegram.WebApp.initData на клиенте.
    """
    init_data: str


class TokenResponse(BaseModel):
    """JWT-токены после успешной авторизации."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # True если пользователь ещё не зарегистрирован через бота
    is_registered: bool = True


class RefreshRequest(BaseModel):
    refresh_token: str
