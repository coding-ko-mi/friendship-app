"""
События бэкенд → бот (общий контракт + producer).

Зачем: мэтч и голосование считаются в API (uvicorn), а пуши шлёт бот (отдельный
процесс). Связываем их через Redis-список EVENTS_QUEUE_KEY:
  • API кладёт событие  → enqueue_event()  (RPUSH)
  • бот забирает событие → consumer (BLPOP, см. app/bot/events_consumer.py)

Событие — это JSON-строка с полем "type" и полезной нагрузкой. Формат описан
здесь один раз и используется обеими сторонами, чтобы они не разошлись.

Этот модуль лежит в app/services (не в app/bot), потому что им пользуется
бэкенд-сторона (producer). Бот импортирует отсюда только описания типов.
"""
from __future__ import annotations

import json
from enum import StrEnum

from redis.asyncio import Redis

from app.config import EVENTS_QUEUE_KEY


class EventType(StrEnum):
    """Типы событий, на которые бот шлёт пуш."""

    MATCH = "match"               # взаимный лайк → уведомить обоих
    VOTE_RESULT = "vote_result"   # заявка принята/отклонена → уведомить заявителя


async def enqueue_event(redis: Redis, event: dict) -> None:
    """
    Положить событие в очередь для бота (RPUSH в конец списка).

    event — словарь с обязательным ключом "type" (значение из EventType) и
    полями полезной нагрузки. Сериализуем в JSON: Redis-список хранит строки.

    Вызывается из бэкенд-сервисов ПОСЛЕ успешного коммита изменения состояния
    (мэтч создан / голосование подсчитано), чтобы не уведомить о том, что не
    зафиксировалось в БД.
    """
    await redis.rpush(EVENTS_QUEUE_KEY, json.dumps(event))


# --------------------------------------------------------------------- #
#  Хелперы-конструкторы событий (чтобы бэкенд не собирал dict руками)   #
# --------------------------------------------------------------------- #
def match_event(*, user_id: int, partner_name: str) -> dict:
    """
    Событие мэтча для ОДНОГО пользователя.

    Мэтч взаимный, поэтому бэкенд обычно кладёт ДВА таких события — по одному
    на каждого участника, с именем другого как partner_name.
    """
    return {
        "type": EventType.MATCH.value,
        "user_id": user_id,
        "partner_name": partner_name,
    }


def vote_result_event(*, user_id: int, group_name: str, accepted: bool) -> dict:
    """Событие результата голосования для заявителя."""
    return {
        "type": EventType.VOTE_RESULT.value,
        "user_id": user_id,
        "group_name": group_name,
        "accepted": accepted,
    }
