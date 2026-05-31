"""
Consumer событий бэкенд → бот.

Бесконечный цикл: BLPOP из очереди EVENTS_QUEUE_KEY → разобрать JSON →
вызвать нужный пуш из notifications. Запускается как фоновая задача рядом
с polling-ом бота (см. app/bot/main.py).

Почему BLPOP: блокирующее чтение «спит» без событий и мгновенно просыпается,
когда API сделал RPUSH. Никакого busy-loop и лишней нагрузки на Redis.

Устойчивость: одно битое или неизвестное событие не должно ронять цикл —
ловим исключения по каждому событию и продолжаем.
"""
from __future__ import annotations

import asyncio
import json
import logging

from aiogram import Bot
from redis.asyncio import Redis

from app.bot.services import chat_manager, notifications
from app.config import EVENTS_QUEUE_KEY
from app.services.events import EventType

logger = logging.getLogger(__name__)


async def _dispatch(bot: Bot, event: dict) -> None:
    """Разобрать тип события и вызвать соответствующий пуш."""
    event_type = event.get("type")

    if event_type == EventType.MATCH.value:
        await notifications.notify_match(
            bot,
            user_id=event["user_id"],
            partner_name=event["partner_name"],
        )
    elif event_type == EventType.VOTE_RESULT.value:
        await notifications.notify_vote_result(
            bot,
            user_id=event["user_id"],
            group_name=event["group_name"],
            accepted=event["accepted"],
        )
    elif event_type == EventType.ACHIEVEMENT.value:
        await notifications.notify_achievement(
            bot,
            user_id=event["user_id"],
            achievement_name=event["achievement_name"],
        )
    elif event_type == EventType.CHAT_CREATE_TOPIC.value:
        # Новая компания: создать топик в Hub и позвать участников.
        await chat_manager.create_topic_for_group(
            bot,
            group_id=event["group_id"],
            group_name=event["group_name"],
            user_ids=event["user_ids"],
        )
    elif event_type == EventType.CHAT_ADD_MEMBER.value:
        # Принят новый участник: выдать ему invite-ссылку в уже существующий Hub.
        await chat_manager.invite_user_to_chat(
            bot,
            user_id=event["user_id"],
            group_id=event["group_id"],
            group_name=event["group_name"],
        )
    elif event_type == EventType.CHAT_POST_MESSAGE.value:
        # Системное сообщение в топик компании (поздравления, подборки).
        await chat_manager.post_to_group_topic(
            bot,
            group_id=event["group_id"],
            text=event["text"],
        )
    else:
        # Неизвестный тип — логируем и игнорируем (не роняем consumer).
        logger.warning("Неизвестный тип события: %r", event_type)


async def run_events_consumer(bot: Bot, redis: Redis) -> None:
    """
    Запустить бесконечный цикл обработки событий.

    BLPOP с таймаутом 0 = ждать бесконечно. Возвращает кортеж (key, value)
    или None при таймауте; с timeout=0 None не приходит, но проверяем на всякий.
    """
    logger.info("Consumer событий запущен (очередь %s)", EVENTS_QUEUE_KEY)
    while True:
        try:
            item = await redis.blpop(EVENTS_QUEUE_KEY, timeout=0)
            if item is None:
                continue
            # item = (key, value). value — JSON-строка события.
            _, raw = item
            event = json.loads(raw)
        except asyncio.CancelledError:
            # Корректная остановка при завершении бота — выходим из цикла.
            logger.info("Consumer событий остановлен")
            raise
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Битое событие в очереди, пропускаю: %s", e)
            continue

        try:
            await _dispatch(bot, event)
        except KeyError as e:
            # В событии не хватает поля — структура не совпала с контрактом.
            logger.error("В событии нет поля %s: %r", e, event)
        except Exception:  # noqa: BLE001
            # Любая иная ошибка отправки не должна убивать цикл.
            logger.exception("Ошибка обработки события: %r", event)
