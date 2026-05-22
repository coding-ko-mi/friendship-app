"""
AuthService — авторизация через Telegram Mini App.

Флоу:
1. Клиент открывает Mini App → Telegram передаёт initData
2. Клиент отправляет initData на POST /auth/telegram
3. Сервер валидирует HMAC-подпись (функция validate_init_data)
4. Извлекает telegram_id из initData
5. Ищет пользователя в БД по telegram_id
6. Если найден → выдаёт JWT, is_registered=True
7. Если НЕ найден → выдаёт JWT с is_registered=False
   (пользователь должен пройти регистрацию через бот — там FSM заполняет анкету)

Важно: пользователь создаётся ТОЛЬКО через Telegram-бот (aiogram).
API не создаёт пользователей — только аутентифицирует существующих.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_token_pair
from app.core.telegram_auth import TelegramAuthError, validate_init_data
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

    async def authenticate_telegram(self, init_data_raw: str) -> TokenResponse:
        """
        Авторизовать пользователя по initData из Telegram Mini App.

        Raises:
            AuthError: невалидный initData или заблокированный пользователь
        """
        try:
            tg_user = validate_init_data(init_data_raw)
        except TelegramAuthError as e:
            raise AuthError(str(e))

        telegram_id = tg_user["id"]
        user = await self.user_repo.get_by_telegram_id(telegram_id)

        # Пользователь заблокирован — отказываем
        if user is not None and user.is_banned:
            raise AuthError("Аккаунт заблокирован.")

        is_registered = user is not None

        # Даже незарегистрированному выдаём токен (sub = telegram_id в этом случае)
        # чтобы клиент мог обратиться к боту для регистрации.
        token_subject = user.id if user else telegram_id
        tokens = create_token_pair(token_subject)

        return TokenResponse(**tokens, is_registered=is_registered)

    async def refresh_tokens(self, user_id: int) -> TokenResponse:
        """Выдать новую пару токенов по проверенному user_id."""
        user = await self.user_repo.get_by_id(user_id)
        if user is None or user.is_banned:
            raise AuthError("Пользователь не найден или заблокирован.")
        tokens = create_token_pair(user.id)
        return TokenResponse(**tokens)
