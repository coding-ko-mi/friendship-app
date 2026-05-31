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

# Секрет для проверки подлинности webhook-апдейтов от Telegram. При setWebhook
# отдаём его Telegram'у; Telegram возвращает его в заголовке
# X-Telegram-Bot-Api-Secret-Token каждого апдейта — без этого заголовка любой
# внешний POST на /webhook сможет подделать апдейт. Генерируется openssl
# rand -hex 32 и кладётся в .env (ОБЯЗАТЕЛЬНО на проде). Если пусто —
# secret-проверка отключается (приемлемо в локальной разработке).
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")

# --- Параметры мэтчинга (модуль «Бэкенд: мэтчинг») ---
# Сколько часов «пропущенный» (skip) пользователь не показывается снова в ленте.
# По истечении TTL он может снова всплыть — это намеренно: анкеты обновляются,
# второй шанс полезен. Хранится в Redis, схему БД не трогает.
#
# Реализация: для каждой пары (skipper, skipped) — индивидуальный срок жизни,
# а не один общий TTL на весь сет скипов пользователя. Иначе любой новый скип
# продлевал бы скипы всех предыдущих кандидатов (см. SkipRepository).
DISCOVERY_SKIP_TTL_HOURS: int = 18

# Размер страницы ленты по умолчанию (сколько кандидатов отдаём за один запрос).
# Лента подгружается порциями по мере свайпов, а не вся сразу.
DISCOVERY_PAGE_SIZE: int = 20

# --- Параметры достижений (геймификация, итерация 2) ---
# Дата запуска продукта (ISO 8601, например "2026-06-01"). Используется для
# EARLY_BIRD: пользователю выдаётся «Ранняя пташка», если он зарегистрировался
# в течение EARLY_BIRD_WINDOW_DAYS дней после LAUNCH_DATE.
# ОБЯЗАТЕЛЬНО зафиксировать в .env до первого деплоя. После — НЕ МЕНЯТЬ
# (исторический факт, не может «переехать»).
LAUNCH_DATE: str = os.getenv("LAUNCH_DATE", "2026-06-01")
# Окно «ранней пташки» в днях. 30 — продуктовое решение из achievements_spec.md.
EARLY_BIRD_WINDOW_DAYS: int = int(os.getenv("EARLY_BIRD_WINDOW_DAYS", "30"))

# Пороги счётчиков-достижений. Меняются через .env без правки кода.
# OPEN_HEART — поставил столько лайков; POPULAR — получил столько лайков;
# CHOOSY — скипнул столько подряд без лайка; FAIR_JUDGE — проголосовал столько
# раз подряд (без пропуска заявок, которые мог проголосовать).
OPEN_HEART_THRESHOLD: int = int(os.getenv("OPEN_HEART_THRESHOLD", "10"))
POPULAR_THRESHOLD: int = int(os.getenv("POPULAR_THRESHOLD", "10"))
CHOOSY_THRESHOLD: int = int(os.getenv("CHOOSY_THRESHOLD", "20"))
FAIR_JUDGE_THRESHOLD: int = int(os.getenv("FAIR_JUDGE_THRESHOLD", "10"))

# Окно «быстрого старта»: за сколько часов от регистрации первый мэтч ещё
# считается «ранним» (FAST_FRIENDS).
FAST_FRIENDS_WINDOW_HOURS: int = int(os.getenv("FAST_FRIENDS_WINDOW_HOURS", "24"))

# --- Админ-доступ ---
# Telegram ID единственного админа. Сверяется с current_user.telegram_id в
# зависимости require_admin (см. app/api/deps.py). 0 — «админа нет» (любая
# проверка вернёт 403), это безопасный дефолт для локальной разработки.
ADMIN_TELEGRAM_ID: int = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# --- Параметры чатинга (модуль «Чатинг», v5.0) --------------------------- #
# ID Hub-супергруппы с включёнными топиками (forum). Это ОДИН общий чат, внутри
# которого каждая компания получает свой топик (тред). Создаётся ВРУЧНУЮ один
# раз (см. DEPLOY-инструкцию модуля чатинга):
#   1) создать супергруппу в Telegram;
#   2) включить «Темы» (Topics) в настройках группы;
#   3) добавить бота администратором с правами: «Управление темами» (manage_topics)
#      и «Пригласительные ссылки» (invite_users);
#   4) узнать ID чата (он отрицательный, формата -100xxxxxxxxxx) и положить сюда.
#
# Дефолт 0 = «Hub не настроен»: бот это детектит и шлёт пуш-фолбэк без ссылки,
# а не падает. Так модуль безопасен до настройки Hub на проде.
CHAT_HUB_ID: int = int(os.getenv("CHAT_HUB_ID", "0"))

# Срок жизни одноразовой invite-ссылки в Hub (минуты). Ссылка одноразовая
# (member_limit=1) и протухает по времени — чтобы не утекала и не висела вечно.
# 60 минут: человек обычно реагирует на пуш о мэтче сразу; если протупил —
# подаст заявку/получит новую ссылку. Меняется только здесь.
CHAT_INVITE_TTL_MINUTES: int = int(os.getenv("CHAT_INVITE_TTL_MINUTES", "60"))
