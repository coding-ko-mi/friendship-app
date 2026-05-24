# CLAUDE_CODE_PROMPT — сборка Mini App + точки стыковки

Промпт для Claude Code. Цель: разложить фронт Mini App по проекту и добавить
два недостающих эндпоинта на бэке, чтобы всё собралось без участия основателя.

Бэкенд лежит в `backend/`. Фронт — новая папка `frontend/` рядом с `backend/`.

---

## ЧАСТЬ A. Разложить фронтенд

Создай папку `frontend/` в корне проекта (`D:\ko_mi\friendship-app\frontend\`)
и положи туда файлы из приложенного архива РОВНО по этой структуре:

```
frontend/
  .env.example
  .gitignore
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  README.md
  src/
    main.tsx
    App.tsx
    index.css
    vite-env.d.ts
    config.ts
    types/
      api.ts
    api/
      client.ts
      endpoints.ts
    services/
      telegram.ts
      auth.ts
    store/
      router.ts
    components/
      PhotoImage.tsx
      StatusViews.tsx
    screens/
      OnboardingScreen.tsx
      FeedScreen.tsx
      GroupScreen.tsx
```

Затем:

```bash
cd frontend
npm install
npm run typecheck   # должен пройти без ошибок
npm run build       # должен собраться без ошибок
```

`.env` создаётся из `.env.example`. Для локальной разработки оставь
`VITE_API_BASE_URL` пустым, если фронт и API на одном origin; иначе укажи
адрес API (например `https://api.<домен>`).

НИЧЕГО в `src/` не переписывай — структура самодостаточна и уже проверена
(tsc + build зелёные).

---

## ЧАСТЬ B. Добавить на бэк ДВА эндпоинта (фронт их ждёт)

> Принцип проекта: при правке существующего файла — ДОПОЛНЯТЬ, не заменять.
> Все файлы UTF-8. Слои: router → service/repository, как в соседних модулях.

### B.1 GET /api/v1/interests — справочник интересов

Фронт грузит интересы с сервера (`src/api/endpoints.ts` → `interestsApi.list()`),
ожидает `200 → [{ "id": int, "name": str }]`.

Создай `backend/app/api/v1/interests.py`:

```python
"""Справочник интересов — только чтение (для онбординга Mini App)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.interest import Interest
from pydantic import BaseModel, ConfigDict


class InterestCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


router = APIRouter(prefix="/interests", tags=["interests"])


@router.get("", response_model=list[InterestCard])
async def list_interests(
    session: AsyncSession = Depends(get_session),
) -> list[Interest]:
    """Весь справочник интересов. Без авторизации: данные публичные."""
    result = await session.execute(select(Interest).order_by(Interest.id))
    return list(result.scalars().all())
```

Подключи в `backend/app/main.py` (ДОПОЛНИ список импортов и include_router,
не переписывай файл):

```python
from app.api.v1 import auth, profiles, questionnaire, discovery, interests  # + interests
# ...
app.include_router(interests.router, prefix="/api/v1")
```

Убедись, что справочник наполнен: `python -m app.scripts.seed_interests`.

### B.2 GET /api/v1/photo/{file_id} — прокси фото по Telegram file_id

`User.photo_file_id` — это Telegram file_id, не URL. Фронт указывает
`<img src>` на этот прокси (`src/api/endpoints.ts` → `photoUrl()`).

Прокси должен: по file_id вызвать Bot API `getFile` → получить `file_path` →
скачать `https://api.telegram.org/file/bot<TOKEN>/<file_path>` → отдать байты
со `StreamingResponse`/`Response` и корректным `media_type`.

Создай `backend/app/api/v1/photo.py` (набросок — адаптируй под стиль проекта,
используй `TELEGRAM_BOT_TOKEN` из `app.config`, асинхронный httpx):

```python
"""Прокси фото: Telegram file_id → байты картинки (для <img> в Mini App)."""
import httpx
from fastapi import APIRouter, HTTPException, Response, status

from app.config import TELEGRAM_BOT_TOKEN

router = APIRouter(prefix="/photo", tags=["photo"])

_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
_FILE = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"


@router.get("/{file_id}")
async def get_photo(file_id: str) -> Response:
    async with httpx.AsyncClient(timeout=10) as client:
        meta = await client.get(f"{_API}/getFile", params={"file_id": file_id})
        if meta.status_code != 200 or not meta.json().get("ok"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Фото не найдено")
        file_path = meta.json()["result"]["file_path"]
        data = await client.get(f"{_FILE}/{file_path}")
        if data.status_code != 200:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Фото недоступно")
    # Кэшируем на клиенте: file_id стабилен.
    return Response(
        content=data.content,
        media_type=data.headers.get("content-type", "image/jpeg"),
        headers={"Cache-Control": "public, max-age=86400"},
    )
```

Подключи в `main.py` так же, как interests. Добавь `httpx` в
`backend/requirements.txt`, если его там нет.

ВНИМАНИЕ по приватности: эндпоинт раздаёт фото по file_id без авторизации.
Для MVP приемлемо (file_id неугадываем), но в проде стоит закрыть его
`Depends(get_current_user)` и проверять, что запрашивающий имеет право видеть
это фото (есть в ленте/компании). На фронте `photoUrl()` тогда нужно будет
переключить на запрос с Bearer (сейчас это просто `<img src>`).

---

## ЧАСТЬ C. Сверить контракты (правки — ТОЛЬКО во фронте, в типах)

Эти файлы бэка отсутствовали в knowledge — фронт построен по handoff. Сверь с
реальным кодом и при расхождении поправь ТОЛЬКО `frontend/src/types/api.ts`:

1. **`backend/app/schemas/registration.py`** — поля тела `POST /registration`.
   Фронт ждёт: `init_data, name, age, about, city, interest_ids`.
   Если на бэке `initData`/`interests`/иное — поправь интерфейс
   `RegistrationRequest`. Если ответ регистрации содержит токены — поправь
   `RegistrationResponse` (фронт умеет оба варианта).

2. **`backend/app/schemas/auth.py`** — поля `TokenResponse`.
   Фронт ждёт: `access_token, refresh_token, token_type, is_registered`.
   Расхождение → правь интерфейс `TokenResponse`.

3. **`backend/app/core/security.py`** — связано с 4.3 из handoff_4 (валидация
   initData в registration-роутере). Это задача бэка, фронт не затрагивает,
   но без неё `/registration` и `/auth/telegram` не заработают на живых данных.

После любых правок типов прогони во `frontend/`: `npm run typecheck`.

---

## Итог проверки готовности

```bash
# фронт
cd frontend && npm install && npm run build   # зелёный

# бэк
cd ../backend
python -m app.scripts.seed_interests          # интересы наполнены
uvicorn app.main:app --reload                 # /interests и /photo отвечают
python -m app.bot.main                         # бот (для регистрации/пушей)
```
