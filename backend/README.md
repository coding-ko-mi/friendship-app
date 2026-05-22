# Backend — слой БД и модели

Модуль «БД + модели» MVP: SQLAlchemy 2.0 (async) модели, схема из 11 таблиц
и Alembic-миграции.

## Структура

```
backend/
├── app/
│   ├── config.py            # DATABASE_URL и продуктовые параметры (MAX_GROUP_SIZE)
│   ├── database.py          # async-движок и фабрика сессий
│   └── models/              # ORM-модели (по файлу на смысловой блок)
│       ├── base.py          # Base + TimestampMixin
│       ├── enums.py         # RequestType, RequestStatus
│       ├── user.py          # User
│       ├── interest.py      # Interest + user_interests
│       ├── group.py         # Group + GroupMember
│       ├── matching.py      # Like + Match
│       ├── membership.py    # MembershipRequest + Vote
│       └── achievement.py   # Achievement + UserAchievement
├── migrations/              # Alembic (env.py, versions/)
├── alembic.ini
├── requirements.txt
└── .env.example
```

## Запуск

```bash
# 1. Зависимости (лучше в виртуальном окружении)
pip install -r requirements.txt

# 2. Настройки: скопировать .env.example -> .env и указать свою БД
cp .env.example .env

# 3. Создать БД в PostgreSQL (один раз)
createdb friendship

# 4. Применить миграции (создаст все таблицы)
alembic upgrade head
```

## Работа с миграциями

```bash
alembic upgrade head            # применить все миграции
alembic downgrade -1            # откатить последнюю
alembic history                 # история миграций
alembic revision --autogenerate -m "описание"   # новая миграция после правки моделей
```

После любого изменения моделей: меняешь модель → `alembic revision --autogenerate`
→ проверяешь сгенерированный файл → `alembic upgrade head`.

## 11 таблиц

users · interests · user_interests · groups · group_members · likes · matches ·
membership_requests · votes · achievements · user_achievements
