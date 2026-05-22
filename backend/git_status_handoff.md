# Состояние репозитория: модуль «Бэкенд: ядро»

> Документ фиксирует фактическое состояние кода на конец модуля «Бэкенд: ядро».
> Версия от 22 мая 2026.

---

## TL;DR для следующего чата

Модуль «Бэкенд: ядро» **завершён**. Добавлены FastAPI-приложение, авторизация
через Telegram Mini App, профили и анкеты. Код совместим с существующей
инфраструктурой (модели SQLAlchemy, миграции Alembic, docker-compose из чата «БД»).

Следующий модуль по дорожной карте — **Бэкенд: мэтчинг**
(алгоритм подбора, свайпы, лайки, просмотр ленты).

---

## 1. Git — текущее состояние

- Репозиторий: `D:\ko_mi\friendship-app` → `https://github.com/coding-ko-mi/friendship-app.git`
- Ветка: `main`
- ОС: Windows, терминал PowerShell
- Коммиты:
  - `d709506` — Initial commit (модуль «БД + модели», 21 файл)
  - `(новый)` — feat: backend core (auth, profiles, questionnaire)

---

## 2. Фактическая структура проекта (источник правды)

```
D:\ko_mi\friendship-app\
└── backend/
    ├── .env                   # секреты (НЕ в git)
    ├── .env.example           # шаблон (в git)
    ├── .gitignore
    ├── alembic.ini
    ├── docker-compose.yml     # PostgreSQL 16 (friendship/friendship/friendship)
    ├── requirements.txt       # обновлён: добавлены fastapi, uvicorn, pydantic, pyjwt
    ├── app/
    │   ├── __init__.py
    │   ├── config.py          # обновлён: + JWT_SECRET, TELEGRAM_BOT_TOKEN
    │   ├── database.py        # без изменений: engine + get_session()
    │   ├── main.py            # НОВЫЙ: точка входа FastAPI
    │   ├── core/
    │   │   ├── __init__.py
    │   │   ├── security.py    # НОВЫЙ: JWT create/decode
    │   │   └── telegram_auth.py  # НОВЫЙ: валидация Mini App initData
    │   ├── api/
    │   │   ├── __init__.py
    │   │   ├── deps.py        # НОВЫЙ: get_current_user dependency
    │   │   └── v1/
    │   │       ├── __init__.py
    │   │       ├── auth.py         # НОВЫЙ: POST /auth/telegram, /auth/refresh
    │   │       ├── profiles.py     # НОВЫЙ: GET/PATCH /me/profile, GET /users/{id}/profile
    │   │       └── questionnaire.py  # НОВЫЙ: GET/PATCH /me/questionnaire
    │   ├── models/
    │   │   ├── __init__.py    # обновлён: + Profile, Questionnaire
    │   │   ├── base.py        # без изменений
    │   │   ├── enums.py       # без изменений
    │   │   ├── user.py        # без изменений (авторизация по telegram_id)
    │   │   ├── interest.py    # без изменений
    │   │   ├── group.py       # без изменений
    │   │   ├── matching.py    # без изменений
    │   │   ├── membership.py  # без изменений
    │   │   ├── achievement.py # без изменений
    │   │   ├── profile.py     # НОВЫЙ: Profile (gender, geo, extra_photos, is_visible)
    │   │   └── questionnaire.py  # НОВЫЙ: Questionnaire (looking_for, lifestyle, preferences)
    │   ├── repositories/
    │   │   ├── __init__.py
    │   │   ├── user_repository.py         # НОВЫЙ
    │   │   ├── profile_repository.py      # НОВЫЙ
    │   │   └── questionnaire_repository.py  # НОВЫЙ
    │   ├── schemas/
    │   │   ├── __init__.py
    │   │   ├── auth.py          # НОВЫЙ
    │   │   ├── profile.py       # НОВЫЙ
    │   │   └── questionnaire.py # НОВЫЙ
    │   └── services/
    │       ├── __init__.py
    │       ├── auth_service.py          # НОВЫЙ
    │       ├── profile_service.py       # НОВЫЙ
    │       └── questionnaire_service.py # НОВЫЙ
    └── migrations/
        ├── env.py             # обновлён: импортирует все модели через app.models
        ├── script.py.mako
        └── versions/
            ├── 20260521_357e7b0dc368_initial_schema.py  # без изменений (11 таблиц)
            └── 20260522_7feaadaf12bd_add_profile_questionnaire.py  # НОВЫЙ
```

---

## 3. Слой API — что готово

### Эндпоинты
```
POST  /api/v1/auth/telegram              Авторизация через Telegram initData
POST  /api/v1/auth/refresh               Обновление access-токена

GET   /api/v1/me/profile                 Свой профиль (полные данные)
PATCH /api/v1/me/profile                 Обновить профиль (display_name, gender, geo, фото)
GET   /api/v1/users/{user_id}/profile    Публичная карточка другого пользователя

GET   /api/v1/me/questionnaire           Своя анкета + % заполненности
PATCH /api/v1/me/questionnaire           Обновить анкету (цель, образ жизни, предпочтения)

GET   /health                            Проверка работоспособности
```

### Авторизация
- **Метод:** Telegram Mini App initData (HMAC-SHA256)
- **Токены:** JWT access (30 мин) + refresh (30 дней)
- **Идентификатор:** `users.telegram_id` → `users.id` → JWT `sub`
- **Регистрация:** через Telegram-бот (aiogram), не через API

### Архитектура слоёв
```
api/v1 (роутер) → services (логика) → repositories (БД) → models (ORM)
```

---

## 4. Схема БД — текущее состояние

### Таблицы из чата «БД + модели» (без изменений)
`users · interests · user_interests · groups · group_members · likes · matches ·
membership_requests · votes · achievements · user_achievements`

### Новые таблицы (добавлены в этом чате)
**profiles:**
- `user_id` FK → users.id (CASCADE)
- `display_name`, `gender` (строка: male/female/other)
- `latitude`, `longitude` (Numeric 9,6 — только себе, другим округляем)
- `extra_photos_urls` (Text, разделитель `|`)
- `is_visible` (bool, видимость в ленте)

**questionnaires:**
- `user_id` FK → users.id (CASCADE)
- `looking_for` (строка: group/friends/both)
- `smoking`, `alcohol`, `sport` (строка: never/sometimes/often)
- `partner_age_min`, `partner_age_max`, `partner_max_distance_km` (Integer)

**Что НЕ добавлено (намеренно):**
- Интересы в анкете — уже есть таблица `user_interests`. Мэтчинг по ней.
- OTP/SMS-коды — авторизация через Telegram, не телефон.

---

## 5. Ключевые договорённости (важны для следующих модулей)

- **`get_session()`** — из `app/database.py`. Использовать везде как FastAPI Depends.
- **`Base`** — из `app/models/base.py`. Все новые модели наследуют от него.
- **`User.telegram_id`** — идентификатор для авторизации. `User.id` — внутренний PK.
- **`User.is_banned`** — флаг блокировки (не `is_active`). Забаненным отказываем.
- **Profile и User разделены:** User-поля (name, age, about, city) меняет бот, Profile-поля меняет Mini App.
- **Интересы** — через существующую `user_interests`. В анкете их нет.
- **Миграции** — в `migrations/versions/`. `down_revision` новой всегда указывает на предыдущую.
- **config.py** — стиль `os.getenv()`, не pydantic-settings. Так в проекте.

---

## 6. Локальный запуск

```powershell
# Из папки backend/
docker compose up -d                         # поднять PostgreSQL
pip install -r requirements.txt
alembic upgrade head                         # применить обе миграции
uvicorn app.main:app --reload                # запустить API
# Открыть: http://localhost:8000/docs
```

Для работы авторизации нужны в `.env`:
```
JWT_SECRET=<openssl rand -hex 32>
TELEGRAM_BOT_TOKEN=<токен из @BotFather>
```

---

## 7. Что делать следующему чату («Бэкенд: мэтчинг»)

1. Опираться на существующие модели `Like` и `Match` из `app/models/matching.py`.
2. Алгоритм подбора: пересечение интересов (таблица `user_interests`) + фильтр по городу (`User.city`) + возраст из анкеты.
3. Лента свайпов: пагинированный список пользователей которых ещё не лайкали.
4. Использовать `get_session()` из `app/database.py`.
5. Новые зависимости — дописывать в `requirements.txt`.
6. По завершении: `git add . → git commit → git push` и выгрузить handoff в проект.

---

## 8. Открытые вопросы (перенесены в следующие чаты)

| Вопрос | Чат |
|---|---|
| Seed-скрипт для справочников (`interests`, `achievements`) | Бэкенд: мэтчинг |
| Алгоритм весов при мэтчинге (интересы vs возраст vs расстояние) | Бэкенд: мэтчинг |
| Создание Telegram-групп ботом (Telethon/Pyrogram) | Бот |
| Слияние компаний: кто голосует | Бэкенд: компании + голосование |

---

*Версия: 1.0 | Дата: 22 мая 2026 | Статус: модуль «Бэкенд: ядро» завершён*
