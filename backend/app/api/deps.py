"""
FastAPI dependency: get_current_user.

Читает JWT из заголовка Authorization: Bearer <token>,
декодирует, достаёт пользователя из БД.

Использует get_session() из существующего app/database.py.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ADMIN_TELEGRAM_ID
from app.core.security import decode_token
from app.database import get_session
from app.models.user import User
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_session),
) -> User:
    """
    Проверить токен и вернуть текущего пользователя.

    Raises:
        HTTP 401: невалидный/истёкший токен, пользователь не найден или забанен
    """
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверный или истёкший токен",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user_id = decode_token(credentials.credentials, expected_type="access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен истёк",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, ValueError):
        raise auth_error

    user = await UserRepository(db).get_by_id(user_id)
    if user is None or user.is_banned:
        raise auth_error

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Допустить только одного админа — пользователя с конкретным telegram_id.

    Авторизация через тот же JWT, что и у обычных пользователей: отдельного
    логина/пароля нет. Если ADMIN_TELEGRAM_ID не настроен (0) — отказываем
    всем, это безопасный дефолт.
    """
    if ADMIN_TELEGRAM_ID == 0 or current_user.telegram_id != ADMIN_TELEGRAM_ID:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Доступ запрещён")
    return current_user
