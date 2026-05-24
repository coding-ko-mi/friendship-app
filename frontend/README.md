# Friendship — Telegram Mini App (фронт)

Фронтенд Telegram Mini App: онбординг (анкета) → лента подбора → компании и голосование.

## Стек

React 19 + TypeScript + Vite. Telegram SDK: `@telegram-apps/sdk-react` v3.

## Запуск

```bash
npm install
cp .env.example .env   # при необходимости укажите VITE_API_BASE_URL
npm run dev            # разработка
npm run build          # прод-сборка (tsc -b + vite build)
npm run typecheck      # только проверка типов
```

Mini App открывается внутри Telegram (вне Telegram нет `initData` — покажется
экран ошибки, это ожидаемо).

## Архитектура (чистая, послойно)

```
src/
  types/api.ts        контракты бэкенда (единый источник правды)
  config.ts           адрес API из .env
  api/
    client.ts         HTTP-клиент: Bearer-токен, авто-refresh, ApiError
    endpoints.ts      типизированные вызовы всех эндпоинтов
  services/
    telegram.ts       изоляция Telegram SDK (initData, тема, BackButton)
    auth.ts           initData → JWT, авто-перелогин
  store/
    router.ts         стейт-роутер (стек экранов, без URL)
  components/         PhotoImage, Spinner, ErrorView
  screens/            Onboarding, Feed, Group
  App.tsx             бутстрап + рендер активного экрана
```

Веб-специфика (`fetch`, `window`, Telegram SDK) изолирована в `api/client.ts`
и `services/telegram.ts` — при переезде на React Native меняются только они.

## Авторизация

`initData` отправляется на `/api/v1/auth/telegram` ОДИН раз → бэк отдаёт JWT.
Дальше все запросы идут с `Authorization: Bearer`. Токен живёт в памяти; при
401 клиент сам делает refresh, при провале — перелогин через `initData`.

## Точки стыковки с бэкендом

Фронт ожидает два эндпоинта, которых пока нет на бэке (см. `CLAUDE_CODE_PROMPT.md`):

- `GET /api/v1/interests` — справочник интересов `[{id, name}]`.
- `GET /api/v1/photo/{file_id}` — прокси фото по Telegram file_id (отдаёт байты).

До их появления: интересы не загрузятся (экран онбординга покажет ошибку с
кнопкой повтора), фото в ленте заменяются заглушкой с инициалом.
