"""
Настройки приложения.

Версия 3.0 — дополнена в модуле «Бэкенд: мэтчинг».
История:
  • v2.0 (ядро): JWT, Telegram Bot Token для валидации Mini App initData.
  • v3.0 (мэтчинг): Redis и параметры ленты подбора.

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

# --- Redis ---
# Подключение к Redis. Дефолт — локальный Redis на стандартном порту.
# Используется для skip-пометок ленты (с TTL), позже — FSM-сторадж бота и кэш.
# Формат: redis://[:password]@host:port/db_number
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- Продуктовые параметры ---
# Максимальный размер компании на MVP. Проверяется в сервисном слое перед
# добавлением участника. После MVP условия для групп >20 меняются здесь же —
# меняется только эта константа и логика сервиса, схема БД не трогается.
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

# --- Параметры мэтчинга (модуль «Бэкенд: мэтчинг») ---
# Сколько дней «пропущенный» (skip) пользователь не показывается снова в ленте.
# По истечении TTL он может снова всплыть — это намеренно: интересы и анкеты
# меняются, второй шанс полезен. Хранится в Redis, схему БД не трогает.
DISCOVERY_SKIP_TTL_DAYS: int = 14

# Размер страницы ленты по умолчанию (сколько кандидатов отдаём за один запрос).
# Лента подгружается порциями по мере свайпов, а не вся сразу.
DISCOVERY_PAGE_SIZE: int = 20
