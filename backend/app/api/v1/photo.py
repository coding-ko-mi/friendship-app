"""
Прокси фото: Telegram file_id → байты картинки (для <img> в Mini App).

User.photo_file_id — это идентификатор Telegram, а не URL. Чтобы фронт мог
показать аватар обычным <img src="...">, бэкенд проксирует выдачу:
  1. GET https://api.telegram.org/bot<TOKEN>/getFile?file_id=...   → file_path
  2. GET https://api.telegram.org/file/bot<TOKEN>/<file_path>      → байты
  3. отдаём байты клиенту с media_type из заголовков Telegram.

ВАЖНО (приватность, MVP):
  Эндпоинт открыт — file_id неугадываем, но в проде стоит закрыть его
  Depends(get_current_user) и проверять, что запрашивающий имеет право
  видеть это фото (есть в общей ленте/компании). Тогда на фронте
  photoUrl() надо переключить с обычного <img src> на запрос с Bearer.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Response, status

from app.config import TELEGRAM_BOT_TOKEN

router = APIRouter(prefix="/photo", tags=["photo"])

_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
_FILE_BASE = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"


@router.get("/{file_id}")
async def get_photo(file_id: str) -> Response:
    """Скачать фото по Telegram file_id и отдать байтами браузеру."""
    async with httpx.AsyncClient(timeout=10) as client:
        meta = await client.get(f"{_API_BASE}/getFile", params={"file_id": file_id})
        if meta.status_code != 200 or not meta.json().get("ok"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Фото не найдено"
            )
        file_path = meta.json()["result"].get("file_path")
        if not file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Фото недоступно"
            )
        data = await client.get(f"{_FILE_BASE}/{file_path}")
        if data.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Фото недоступно"
            )

    return Response(
        content=data.content,
        media_type=data.headers.get("content-type", "image/jpeg"),
        # file_id у Telegram стабилен — даём браузеру кэшировать на сутки.
        headers={"Cache-Control": "public, max-age=86400"},
    )
