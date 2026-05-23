"""
Хранилище «ожидающего фото» (Redis) — сторона бота.

Гибридная регистрация (Вариант A): бот получает фото, кладёт его file_id сюда,
а API позже забирает при создании User. Это контракт между двумя процессами:
формат ключа ДОЛЖЕН совпадать с app/services/registration_service.py.

Почему Redis, а не FSM-стейт бота: фото должно быть доступно ДРУГОМУ процессу
(uvicorn с API), а FSM-стейт привязан к процессу бота. Redis общий — идеально.
TTL гарантирует, что брошенная регистрация не оставит мусор навсегда.
"""
from __future__ import annotations

from redis.asyncio import Redis

from app.config import PENDING_PHOTO_TTL_SECONDS


def pending_photo_key(telegram_id: int) -> str:
    """
    Redis-ключ ожидающего фото.

    ВНИМАНИЕ: формат продублирован в registration_service.pending_photo_key
    (на стороне API). Если меняешь здесь — меняй и там. Это намеренный контракт
    между процессами, который нельзя импортировать в одну сторону без связности.
    """
    return f"pending_photo:{telegram_id}"


async def save_pending_photo(
    redis: Redis, *, telegram_id: int, file_id: str
) -> None:
    """
    Сохранить file_id присланного фото с TTL.

    set(..., ex=TTL) ставит значение и срок жизни одной командой. Повторная
    отправка фото просто перезапишет ключ и обновит TTL — пользователь может
    переслать другое фото до завершения анкеты.
    """
    await redis.set(
        pending_photo_key(telegram_id),
        file_id,
        ex=PENDING_PHOTO_TTL_SECONDS,
    )
