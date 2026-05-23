"""
JWT-утилиты: создание и верификация токенов.

Используют настройки из app.config (не из pydantic Settings —
для совместимости с существующим config.py проекта).

Также реэкспортирует validate_init_data из app.core.telegram_auth —
это единая точка входа для валидации Telegram initData во всём проекте.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.core.telegram_auth import validate_init_data as validate_init_data  # noqa: F401

TokenType = Literal["access", "refresh"]


def create_token(user_id: int, token_type: TokenType) -> str:
    """
    Создать JWT-токен.

    Args:
        user_id:    id из таблицы users (Integer PK)
        token_type: "access" (30 мин) или "refresh" (30 дней)
    """
    now = datetime.now(timezone.utc)

    if token_type == "access":
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "type": token_type,
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: TokenType) -> int:
    """
    Декодировать и проверить JWT.

    Returns: user_id

    Raises:
        jwt.ExpiredSignatureError — токен истёк
        jwt.InvalidTokenError    — невалидный токен
        ValueError               — неверный тип токена
    """
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    if payload.get("type") != expected_type:
        raise ValueError(
            f"Ожидался '{expected_type}', получен '{payload.get('type')}'"
        )

    return int(payload["sub"])


def create_token_pair(user_id: int) -> dict[str, str]:
    """Создать пару access + refresh токенов."""
    return {
        "access_token": create_token(user_id, "access"),
        "refresh_token": create_token(user_id, "refresh"),
    }
