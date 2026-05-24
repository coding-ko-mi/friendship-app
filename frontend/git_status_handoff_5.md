# Git Status / Handoff — Модуль «Mini App (фронтенд)»

Дата: 2026-05-24 · Стек фронта: React 19 + TypeScript + Vite · SDK: @telegram-apps/sdk-react 3.3.9

---

## TL;DR

Сделан фронтенд Telegram Mini App: онбординг (анкета) → лента подбора
(свайпы/лайки) → компании и голосование. Чистая послойная архитектура,
все контракты сверены с реальными файлами бэкенда. **Typecheck (tsc) и
прод-сборка (vite build) проходят без ошибок** (51 модуль, 84 KB gzip) —
проверено реально, не на словах. Бэкенд не трогался: два недостающих
эндпоинта оформлены как точки стыковки для Claude Code (см. ниже и
CLAUDE_CODE_PROMPT.md).

---

## 1. Что сделано

| Слой | Файл | Назначение |
|---|---|---|
| Типы | `src/types/api.ts` | Контракты бэка (единый источник правды) |
| Конфиг | `src/config.ts` | Адрес API из .env |
| API | `src/api/client.ts` | HTTP-клиент: Bearer, авто-refresh, ApiError |
| API | `src/api/endpoints.ts` | Типизированные вызовы всех эндпоинтов |
| Сервис | `src/services/telegram.ts` | Изоляция Telegram SDK (initData, тема, BackButton) |
| Сервис | `src/services/auth.ts` | initData → JWT, авто-перелогин |
| Стор | `src/store/router.ts` | Стейт-роутер (стек экранов, без URL) |
| UI | `src/components/PhotoImage.tsx` | Фото по file_id через прокси + заглушка |
| UI | `src/components/StatusViews.tsx` | Spinner, ErrorView |
| Экран | `src/screens/OnboardingScreen.tsx` | Анкета регистрации |
| Экран | `src/screens/FeedScreen.tsx` | Лента, лайк/скип, мэтч |
| Экран | `src/screens/GroupScreen.tsx` | Компания, заявки, голосование |
| Корень | `src/App.tsx` | Бутстрап + рендер экрана |
| Вход | `src/main.tsx`, `index.html`, `src/index.css` | Точка входа, стили на теме TG |

---

## 2. Ключевые решения (зафиксированы)

| Решение | Почему |
|---|---|
| React + TS + Vite | Стандарт Mini App, типы переиспользуются при переезде на RN |
| JWT в памяти (не localStorage) | initData в Telegram всегда «свежий» → хранить токен надолго незачем; меньше поверхность атаки |
| Свой стейт-роутер | Mini App — экраны, а не URL; стек переносится на RN один-в-один |
| @telegram-apps/sdk-react v3 | Типизирован, активно поддерживается, даёт сырой initData |
| Веб-специфика изолирована | `fetch`/`window`/SDK только в client.ts и telegram.ts → RN-перенос меняет 2 файла |

---

## 3. РАСХОЖДЕНИЕ С ТЗ ЧАТА — разрешено в пользу реального бэка

ТЗ чата говорило «авторизация всех запросов через initData». **Реальный код
бэка устроен иначе** (auth.py, discovery.py, deps.get_current_user):

- `initData` отправляется ОДИН раз на `/api/v1/auth/telegram` → бэк отдаёт JWT.
- Все защищённые эндпоинты читают `Authorization: Bearer <access_token>`.

Фронт построен по факту бэка: initData → JWT → Bearer. Иначе пришлось бы
переписывать `get_current_user` и все роутеры. Если это нежелательно —
обсудить ДО интеграции.

---

## 4. ТОЧКИ СТЫКОВКИ С БЭКЕНДОМ (бэк не трогали — нужны правки)

### 4.1 GET /api/v1/interests — НЕТ на бэке, нужен
Фронт грузит справочник интересов с сервера (зашивать копию опасно: id на
фронте обязаны совпасть с id в БД, а seed присваивает их по порядку вставки).
Контракт: `200 → [{ "id": int, "name": str }]`. Источник данных — таблица
`interests` (модель уже есть, `seed_interests.py` наполняет 22 категории).
**Реализация описана в CLAUDE_CODE_PROMPT.md.**

### 4.2 GET /api/v1/photo/{file_id} — НЕТ на бэке, нужен
`User.photo_file_id` — это Telegram file_id, а НЕ URL. Браузер по нему
картинку не покажет. Нужен прокси: бэк по file_id берёт байты через Bot API
(getFile → download) и отдаёт как image. До его появления фронт показывает
заглушку с инициалом (не падает). **Реализация в CLAUDE_CODE_PROMPT.md.**

### 4.3 POST /api/v1/registration — сверить имена полей
Файл `schemas/registration.py` отсутствует в knowledge — поля взяты из
handoff_4: `init_data, name, age, about, city, interest_ids[]`. Фронт шлёт
именно так. **Сверить реальную схему**; при расхождении (`initData` vs
`init_data`, `interest_ids` vs `interests`) поправить ТОЛЬКО `src/types/api.ts`
(интерфейс `RegistrationRequest`).

### 4.4 TokenResponse — сверить имена полей
`schemas/auth.py` отсутствует в knowledge. Фронт ожидает
`access_token, refresh_token, token_type, is_registered`. Сверить; правка —
в `src/types/api.ts` (интерфейс `TokenResponse`).

### 4.5 RegistrationResponse — поведение токенов
Фронт умеет два варианта: (а) регистрация сразу вернула токены → использует их;
(б) токенов в ответе нет → делает отдельный `/auth/telegram`. Достаточно, чтобы
бэк делал ЛИБО одно, ЛИБО другое. Если ответ регистрации иной — поправить
`RegistrationResponse` в типах.

---

## 5. Проверки (выполнено реально)

- `npx tsc --noEmit` → **0 ошибок** (strict-режим, noUnusedLocals/Parameters).
- `npm run build` → **успех**: 51 модуль, dist/index.js 267 KB (84 KB gzip).
- Версия SDK и его API (`init`, `retrieveRawInitData`, `bindMiniAppCssVars`,
  `backButton`, `miniApp.ready`, `viewport.expand`) проверены на реально
  установленном пакете 3.3.9, методы не выдуманы.
- Все файлы UTF-8. Временные артефакты (dist, tsbuildinfo) удалены перед выгрузкой.

---

## 6. Что осталось / следующий чат

- Реализовать на бэке 4.1 и 4.2 (или подтвердить заглушки на MVP).
- Сверить 4.3–4.5 с реальными schemas/registration.py и schemas/auth.py.
- Не реализованы (вне объёма этого чата, при необходимости — отдельно):
  редактирование своего профиля/анкеты (`/me/profile`, `/me/questionnaire`
  на бэке есть, экранов на фронте нет); список своих компаний (бэк отдаёт
  компанию по id, эндпоинта «мои компании» нет — фронт пока ведёт в компанию
  только сразу после создания из мэтча).
- Свайп-жесты сейчас реализованы кнопками (Нравится/Пропустить). Drag-жест
  можно добавить поверх без смены контрактов.
