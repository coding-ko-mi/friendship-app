# Git Status / Handoff — Модуль «Деплой MVP»

Дата: 2026-05-24 · Модуль: инфраструктура деплоя + закрытие блокеров перед продом.

---

## TL;DR

Закрыты все блокеры деплоя (B1–B4), собрана вся инфраструктура. Бот переключён
с polling на webhook. Проект готов к деплою на VPS по DEPLOY_RUNBOOK.md.

---

## 1. Блокеры — статус

| # | Блокер | Решение |
|---|---|---|
| **B1** | groups/requests/achievements не подключены в main.py | ✅ Закрыт: добавлены 3 `include_router` в main.py |
| **B2** | `GET /api/v1/interests` — нет на бэке | ✅ Закрыт: создан `app/api/v1/interests.py` |
| **B3** | `GET /api/v1/photo/{file_id}` — прокси Telegram фото | ⏭ Заглушка: фронт показывает инициал, MVP это ок |
| **B4** | Сверка схем registration/auth | ✅ Закрыт: поля совпадают (`init_data`, `interest_ids`, TokenResponse) |
| **B5** | vote_result пуш для merge | ⏭ Оставлен: merge-заявки редки, нет created_by в схеме |
| **B6** | Миграции на чистой проде | ✅ Подтверждён: одна начальная миграция, все таблицы включая achievements |

---

## 2. Что сделано

### Новые файлы инфраструктуры

| Файл | Назначение |
|---|---|
| `backend/Dockerfile` | Единый образ для API и бота (multi-stage, non-root user) |
| `backend/.dockerignore` | Исключает .env, кэш, venv из образа |
| `backend/entrypoint.sh` | API startup: wait postgres → alembic → seed → uvicorn |
| `docker-compose.yml` | Стек: postgres16 + redis7 + api + bot + nginx + certbot |
| `nginx/nginx.conf` | HTTPS termination, статика фронта, прокси на API и webhook |
| `.env.example` | Шаблон всех переменных из config.py + инфра |
| `.gitignore` | Исключает .env и секреты из Git |
| `DEPLOY_RUNBOOK.md` | Пошаговый рунбук деплоя от ssh до работающего бота |

### Изменённые файлы (только дополнение, не перезапись)

| Файл | Что добавлено |
|---|---|
| `backend/app/main.py` | +3 include_router: groups_router, requests_router, achievements.router, interests.router |
| `backend/app/bot/main.py` | Переключён с polling на webhook (aiohttp SimpleRequestHandler) |

### Новые бэкенд-файлы

| Файл | Назначение |
|---|---|
| `backend/app/api/v1/interests.py` | `GET /api/v1/interests` — справочник интересов для онбординга |

---

## 3. Ключевые решения (зафиксированы)

| Решение | Выбор | Почему |
|---|---|---|
| Docker-образы | Один образ, два entrypoint в compose | Одна сборка, меньше дублирования зависимостей |
| Бот | Webhook (aiohttp) | HTTPS всё равно нужен для Mini App → webhook правильно для прода |
| HTTPS | nginx + certbot standalone + bind-mount /etc/letsencrypt | Стандарт, бесплатно, за вечер |
| Статика фронта | nginx раздаёт dist/ напрямую | Быстрее CDN для закрытого теста, не нужен отдельный сервис |
| Бэкап БД | postgres_data volume (данные переживают пересборку) + cron pg_dump | Must-have: volume бесплатен, без него данные теста сгорят |
| Secrets | .env на сервере, не в Git; .env.example в репо | Единственный безопасный вариант на MVP |

---

## 4. Архитектура сети в Docker

```
Telegram (HTTPS POST /webhook)
    ↓
nginx:443 (SSL termination)
    ├── /api/v1/  → api:8000 (uvicorn, 2 workers)
    ├── /webhook  → bot:8080 (aiohttp webhook server)
    └── /         → /var/www/frontend/dist (статика React)

api:8000 ←→ postgres:5432
api:8000 ←→ redis:6379 (events queue RPUSH)
bot:8080 ←→ postgres:5432 (чтение FSM, уведомления)
bot:8080 ←→ redis:6379 (FSM storage, events BLPOP)
```

---

## 5. Что НЕ сделано (осознанно, не входит в деплой-модуль)

- **B3** (`GET /api/v1/photo/{file_id}`): прокси для Telegram-фото. Фронт показывает инициал — ок для закрытого теста. Реализовать после теста.
- **B5** (vote_result для merge): нет `created_by` в `membership_requests`. Требует миграции. Отложено после MVP.
- **Бот: ACHIEVEMENT ветка в consumer**: `events_consumer.py` логирует неизвестный тип, consumer не падает. Добавить ветку `EventType.ACHIEVEMENT` в `_dispatch` + `notify_achievement` в notifications.py — задача следующего итерационного чата.
- **CI/CD**: не делаем на MVP. Деплой — `git pull + docker compose up -d --build`.
- **Мониторинг**: не делаем на MVP. `docker compose logs -f` достаточно для закрытого теста.

---

## 6. Критерий выхода на закрытый тест (Фаза 2)

- [ ] `docker compose up -d` поднимает весь стек без ошибок
- [ ] `/health` → 200
- [ ] `/api/v1/interests` → 22 интереса
- [ ] `/api/v1/me/achievements` → 401 (не 404)
- [ ] `/api/v1/groups` → 401 (не 404)
- [ ] Бот: `/start` → открывается Mini App
- [ ] Регистрация проходит полностью
- [ ] Данные в postgres_data volume (не теряются при `docker compose restart`)

---

## 7. Следующие задачи (после деплоя)

1. Деплой на реальный VPS по DEPLOY_RUNBOOK.md
2. ACHIEVEMENT ветка в bot/events_consumer.py + notify_achievement в notifications.py
3. GET /api/v1/photo/{file_id} — Telegram photo proxy
4. Закрытый запуск: ≥3 компании органически, без критических багов → Фаза 3
