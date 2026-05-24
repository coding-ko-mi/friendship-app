"""
Настройки приложения.

Версия 4.0 — дополнена в модуле «Бот (aiogram)».
История:
  • v2.0 (ядро): JWT, Telegram Bot Token для валидации Mini App initData.
  • v3.0 (мэтчинг): Redis и параметры ленты подбора.
  • v4.0 (бот): URL Mini App, TTL ожидающего фото, имя Redis-очереди событий.

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
# Используется для skip-пометок ленты (с TTL), FSM-сторадж бота, очередь событий.
# Формат: redis://[:password]@host:port/db_number
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- Продуктовые параметры ---
# Максимальный размер компании на MVP. Проверяется в сервисном слое перед
# добавлением участника. После MVP условия для групп >20 меняются здесь же —
# меняется только эта константа и логика сервиса, схема БД не трогается.
MAX_GROUP_SIZE: int = 20

# Размер «полного состава» — порог достижения FULL_HOUSE («прохождение игры»).
# Продукт-док допускает 8 или 10 (точное число определяется тестированием),
# поэтому вынесено в env: меняется без правки кода. MAX_GROUP_SIZE (потолок
# компании) выше — это другая величина, совпадать с FULL_HOUSE_SIZE не обязана.
FULL_HOUSE_SIZE: int = int(os.getenv("FULL_HOUSE_SIZE", "8"))

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

# --- Параметры бота (модуль «Бот (aiogram)») ---
# URL Telegram Mini App. Бот открывает его кнопкой после получения фото —
# там пользователь дозаполняет анкету (имя/возраст/о себе/город/интересы).
# На проде это адрес задеплоенного фронтенда (https-домен, требование Telegram).
MINI_APP_URL: str = os.getenv("MINI_APP_URL", "https://example.com/app")

# Сколько секунд «ожидающее фото» живёт в Redis до записи анкеты из Mini App.
# Гибридная регистрация: бот кладёт file_id в Redis, затем фронт шлёт остальные
# поля в POST /registration, и API забирает фото отсюда. Если человек прислал
# фото, но так и не заполнил анкету — фото само истечёт через этот TTL.
# 24 часа: с запасом на то, что регистрацию закончат не сразу.
PENDING_PHOTO_TTL_SECONDS: int = int(os.getenv("PENDING_PHOTO_TTL_SECONDS", "86400"))

# Имя Redis-списка, через который БЭКЕНД (API) передаёт боту события для пушей
# (мэтч, результат голосования). API делает RPUSH, бот — BLPOP. Так два процесса
# (uvicorn и бот) связаны без общего кода и без HTTP между ними.
EVENTS_QUEUE_KEY: str = os.getenv("EVENTS_QUEUE_KEY", "bot:events")

# --- Параметры мэтчинга (модуль «Бэкенд: мэтчинг») ---
# Сколько дней «пропущенный» (skip) пользователь не показывается снова в ленте.
# По истечении TTL он может снова всплыть — это намеренно: интересы и анкеты
# меняются, второй шанс полезен. Хранится в Redis, схему БД не трогает.
DISCOVERY_SKIP_TTL_DAYS: int = 14

# Размер страницы ленты по умолчанию (сколько кандидатов отдаём за один запрос).
# Лента подгружается порциями по мере свайпов, а не вся сразу.
DISCOVERY_PAGE_SIZE: int = 20
