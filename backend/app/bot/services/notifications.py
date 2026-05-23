"""
Сервис уведомлений — отправка пушей пользователям через Bot API.

Это переиспользуемый слой: и consumer событий из Redis, и (при желании) любой
другой код бота шлёт пуши через эти функции, а не дёргает bot.send_message
напрямую. Так тексты и обработка ошибок собраны в одном месте.

Важная деталь Telegram: пользователю нельзя написать первым, если он не нажимал
/start у бота или заблокировал его. Такой send_message бросит TelegramForbiddenError.
Мы это ловим и НЕ роняем бота — просто логируем (пуш недоставлен, это нормально).

Для адресации нужен telegram_id (chat_id), а в событиях из бэкенда приходит
внутренний user_id. Перевод user_id → telegram_id делаем здесь чтением из БД.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select

from app.bot import texts
from app.database import async_session_factory
from app.models.user import User

logger = logging.getLogger(__name__)


async def _resolve_telegram_id(user_id: int) -> int | None:
    """Внутренний user_id → telegram_id (chat_id для отправки). None — если нет."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(User.telegram_id).where(User.id == user_id)
        )
        return result.scalar_one_or_none()


async def _safe_send(bot: Bot, *, user_id: int, text: str, markup) -> bool:
    """
    Отправить сообщение пользователю по внутреннему user_id.

    Возвращает True, если доставлено. Глушит «ожидаемые» ошибки доставки
    (пользователь не начинал диалог / заблокировал бота), чтобы один
    недоставленный пуш не ронял обработку очереди.
    """
    telegram_id = await _resolve_telegram_id(user_id)
    if telegram_id is None:
        logger.warning("Уведомление: user_id=%s не найден в БД", user_id)
        return False

    try:
        await bot.send_message(chat_id=telegram_id, text=text, reply_markup=markup)
        return True
    except TelegramForbiddenError:
        # Пользователь заблокировал бота или не нажимал /start — не наша вина.
        logger.info("Уведомление не доставлено (бот заблокирован): user_id=%s", user_id)
        return False
    except TelegramRetryAfter as e:
        # Flood control. На MVP не делаем сложную очередь ретраев — логируем.
        logger.warning("Flood limit при отправке user_id=%s: retry after %s s", user_id, e.retry_after)
        return False


# --------------------------------------------------------------------- #
#  Конкретные уведомления (по одному на тип события)                    #
# --------------------------------------------------------------------- #
async def notify_match(bot: Bot, *, user_id: int, partner_name: str) -> bool:
    """Пуш о новом мэтче. Импорт клавиатуры внутри — избегаем цикла на старте."""
    from app.bot import keyboards

    return await _safe_send(
        bot,
        user_id=user_id,
        text=texts.NOTIFY_MATCH.format(name=partner_name),
        markup=keyboards.open_app_keyboard(register=False),
    )


async def notify_vote_result(
    bot: Bot, *, user_id: int, group_name: str, accepted: bool
) -> bool:
    """Пуш о результате голосования по заявке (принят / отклонён)."""
    from app.bot import keyboards

    template = texts.NOTIFY_VOTE_ACCEPTED if accepted else texts.NOTIFY_VOTE_REJECTED
    return await _safe_send(
        bot,
        user_id=user_id,
        text=template.format(group_name=group_name),
        markup=keyboards.open_app_keyboard(register=False),
    )
