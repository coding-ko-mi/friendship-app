"""
События бэкенд → бот (общий контракт + producer).

Зачем: мэтч, голосование, достижения считаются в API (uvicorn), а действия в
Telegram (пуши, создание топиков, invite-ссылки) выполняет бот (отдельный
процесс). Связываем их через Redis-список EVENTS_QUEUE_KEY:
  • API кладёт событие  → enqueue_event()  (RPUSH)
  • бот забирает событие → consumer (BLPOP, см. app/bot/events_consumer.py)

Событие — это JSON-строка с полем "type" и полезной нагрузкой. Формат описан
здесь один раз и используется обеими сторонами, чтобы они не разошлись.

Этот модуль лежит в app/services (не в app/bot), потому что им пользуется
бэкенд-сторона (producer). Бот импортирует отсюда только описания типов.

Версия v5.0 (чатинг): добавлены события CHAT_CREATE_TOPIC / CHAT_ADD_MEMBER /
CHAT_POST_MESSAGE — ими API поручает боту работу с Hub-супергруппой.
"""
from __future__ import annotations

import json
from enum import StrEnum

from redis.asyncio import Redis

from app.config import EVENTS_QUEUE_KEY


class EventType(StrEnum):
    """Типы событий, на которые реагирует бот."""

    MATCH = "match"                       # взаимный лайк → уведомить обоих
    VOTE_RESULT = "vote_result"           # заявка принята/отклонена → уведомить заявителя
    ACHIEVEMENT = "achievement"           # выдано достижение → уведомить получателя
    # --- Чатинг (модуль «Чатинг», вариант Б) --- #
    CHAT_CREATE_TOPIC = "chat_create_topic"  # создать топик компании в Hub + позвать участников
    CHAT_ADD_MEMBER = "chat_add_member"       # пригласить нового участника в Hub (его компания уже есть)
    CHAT_POST_MESSAGE = "chat_post_message"   # системное сообщение в топик компании


async def enqueue_event(redis: Redis, event: dict) -> None:
    """
    Положить событие в очередь для бота (RPUSH в конец списка).

    event — словарь с обязательным ключом "type" (значение из EventType) и
    полями полезной нагрузки. Сериализуем в JSON: Redis-список хранит строки.

    Вызывается из бэкенд-сервисов ПОСЛЕ успешного коммита изменения состояния,
    чтобы не уведомить/не действовать по тому, что не зафиксировалось в БД.
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


def achievement_event(*, user_id: int, achievement_name: str) -> dict:
    """
    Событие выдачи достижения для ОДНОГО пользователя.

    Достижение всегда персональное (даже пороговые «Без границ» / «Полный
    состав» выдаются каждому участнику отдельно), поэтому одно событие = один
    получатель. Бэкенд кладёт по событию на каждого, кому достижение выдано
    ВПЕРВЫЕ (повторных выдач не бывает — см. achievement_service.grant).

    achievement_name — человекочитаемое имя (не code): боту его сразу
    показывать пользователю, без обращения к справочнику.
    """
    return {
        "type": EventType.ACHIEVEMENT.value,
        "user_id": user_id,
        "achievement_name": achievement_name,
    }


# --------------------------------------------------------------------- #
#  Чатинг                                                               #
# --------------------------------------------------------------------- #
def chat_create_topic_event(
    *, group_id: int, group_name: str, user_ids: list[int]
) -> dict:
    """
    Поручить боту создать топик для НОВОЙ компании и позвать в Hub участников.

    Шлётся после create_group. Бот: createForumTopic → сохранит chat_id+thread_id
    в groups → каждому из user_ids выпустит invite-ссылку и пришлёт её в личку.
    """
    return {
        "type": EventType.CHAT_CREATE_TOPIC.value,
        "group_id": group_id,
        "group_name": group_name,
        "user_ids": user_ids,
    }


def chat_add_member_event(
    *, group_id: int, group_name: str, user_id: int
) -> dict:
    """
    Поручить боту пригласить ОДНОГО нового участника в Hub.

    Шлётся когда join/invite принят голосованием. Топик компании уже существует;
    боту нужно лишь выдать новому участнику invite-ссылку и прислать её в личку.
    """
    return {
        "type": EventType.CHAT_ADD_MEMBER.value,
        "group_id": group_id,
        "group_name": group_name,
        "user_id": user_id,
    }


def chat_post_message_event(*, group_id: int, text: str) -> dict:
    """
    Поручить боту отправить системное сообщение в топик компании.

    Применение: поздравление с FULL_HOUSE, контент-подборки, объявления.
    Бот сам найдёт message_thread_id компании по group_id.
    """
    return {
        "type": EventType.CHAT_POST_MESSAGE.value,
        "group_id": group_id,
        "text": text,
    }
