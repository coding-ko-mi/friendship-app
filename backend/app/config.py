"""
Настройки приложения.

Версия 2.0 — дополнена в модуле «Бэкенд: ядро».
Добавлены: JWT, Telegram Bot Token для валидации Mini App initData.

Принцип: всё через .env, никаких секретов в коде.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- База данных ---
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://friendship:friendship@localhost:5432/friendship",
)

# --- Продуктовые параметры ---
MAX_GROUP_SIZE: int = 20

# --- JWT ---
# Секрет для подписи токенов. Генерируется командой: openssl rand -hex 32
# ОБЯЗАТЕЛЬНО переопределить в .env на продакшне.
JWT_SECRET: str = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

# --- Telegram ---
# Токен бота нужен для валидации initData из Telegram Mini App.
# Получить у @BotFather командой /token.
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
