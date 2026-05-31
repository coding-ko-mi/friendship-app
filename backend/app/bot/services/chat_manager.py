"""
Менеджер чата компаний (модуль «Чатинг», вариант Б).

Отвечает за всё, что бот делает в Hub-супергруппе:
  • создать топик новой компании (createForumTopic) и сохранить привязку в БД;
  • выпустить одноразовую invite-ссылку участнику (createChatInviteLink);
  • отправить системное сообщение в топик компании.

Почему Hub-супергруппа, а не отдельная группа на компанию: Telegram Bot API
НЕ умеет программно создавать группы и добавлять в них людей. Зато умеет
создавать ТОПИКИ в существующей forum-супергруппе и выдавать invite-ссылки.
Поэтому одна общая Hub-группа + топик на компанию — единственный путь на чистом
Bot API без нарушения ToS. Подробности и ограничения — в доке модуля.

Почему invite-ссылка, а не addChatMember: добавить пользователя в группу без
его согласия бот не может. Одноразовая ссылка (member_limit=1) с TTL — обход.

Контракт с БД: единственный писатель в groups — этот менеджер пишет только
telegram_chat_id и message_thread_id (привязку треда). Остальные поля groups
по-прежнему пишет API. Конфликта нет: эти две колонки больше никто не трогает.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select, update

from app.config import CHAT_HUB_ID, CHAT_INVITE_TTL_MINUTES
from app.database import async_session_factory
from app.models.group import Group
from app.models.user import User

logger = logging.getLogger(__name__)


def _hub_configured() -> bool:
    """
    Настроен ли Hub. CHAT_HUB_ID=0 → не настроен (см. config).

    Все публичные операции проверяют это первым делом и при отсутствии Hub
    тихо выходят (с логом), а не падают: модуль безопасен до настройки на проде.
    """
    if CHAT_HUB_ID == 0:
        logger.warning("Чатинг: CHAT_HUB_ID не настроен — операция пропущена")
        return False
    return True


# --------------------------------------------------------------------- #
#  Доступ к данным (короткие сессии — как в notifications.py)           #
# --------------------------------------------------------------------- #
async def _get_group(group_id: int) -> Group | None:
    """Достать компанию по id (нужны её name и привязка треда)."""
    async with async_session_factory() as session:
        return await session.get(Group, group_id)


async def _resolve_telegram_id(user_id: int) -> int | None:
    """Внутренний user_id → telegram_id. None — если пользователь не найден."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(User.telegram_id).where(User.id == user_id)
        )
        return result.scalar_one_or_none()


async def _save_topic_binding(
    group_id: int, *, chat_id: int, thread_id: int
) -> None:
    """Сохранить привязку компании к треду Hub (единственное, что бот пишет в groups)."""
    async with async_session_factory() as session:
        await session.execute(
            update(Group)
            .where(Group.id == group_id)
            .values(telegram_chat_id=chat_id, message_thread_id=thread_id)
        )
        await session.commit()


# --------------------------------------------------------------------- #
#  Публичные операции (вызываются из events_consumer)                   #
# --------------------------------------------------------------------- #
async def create_topic_for_group(
    bot: Bot, *, group_id: int, group_name: str, user_ids: list[int]
) -> None:
    """
    Создать топик для новой компании и пригласить её участников в Hub.

    Идемпотентность: если у компании уже есть message_thread_id — выходим
    (защита от повторной доставки события из очереди).

    Порядок:
      1) createForumTopic в Hub → thread_id;
      2) сохранить привязку (chat_id, thread_id) в БД;
      3) приветствие в топик;
      4) каждому участнику — личная invite-ссылка (через invite_user_to_chat).
    """
    if not _hub_configured():
        return

    group = await _get_group(group_id)
    if group is None:
        logger.error("Чатинг: компания group_id=%s не найдена", group_id)
        return
    if group.message_thread_id is not None:
        logger.info("Чатинг: топик уже создан для group_id=%s — пропуск", group_id)
        return

    # 1. Топик. Имя темы Telegram ограничивает 128 символами.
    try:
        topic = await bot.create_forum_topic(
            chat_id=CHAT_HUB_ID, name=group_name[:128]
        )
    except TelegramAPIError as e:
        # Частые причины: бот не админ Hub / нет права manage_topics / темы выключены.
        logger.error("Чатинг: createForumTopic упал для group_id=%s: %s", group_id, e)
        return

    # 2. Привязка треда в БД.
    await _save_topic_binding(
        group_id, chat_id=CHAT_HUB_ID, thread_id=topic.message_thread_id
    )

    # 3. Приветствие в топик (не критично — ошибку глушим).
    try:
        await bot.send_message(
            chat_id=CHAT_HUB_ID,
            message_thread_id=topic.message_thread_id,
            text=(
                f"🎉 Компания «{group_name}» создана!\n"
                "Знакомьтесь и планируйте первую встречу."
            ),
        )
    except TelegramAPIError as e:
        logger.warning("Чатинг: приветствие в топик не ушло (group_id=%s): %s", group_id, e)

    # 4. Зовём участников.
    for user_id in user_ids:
        await invite_user_to_chat(
            bot, user_id=user_id, group_id=group_id, group_name=group_name
        )


async def invite_user_to_chat(
    bot: Bot, *, user_id: int, group_id: int, group_name: str
) -> bool:
    """
    Выпустить одноразовую invite-ссылку в Hub и прислать её участнику в личку.

    member_limit=1 — ссылка сгорает после первого входа; expire_date — TTL.
    Возвращает True, если ссылка отправлена пользователю.

    Импорт notifications — внутри функции, чтобы избежать циклического импорта
    на старте бота (notifications ← keyboards ← config, всё инициализируется лениво).
    """
    if not _hub_configured():
        return False

    telegram_id = await _resolve_telegram_id(user_id)
    if telegram_id is None:
        logger.warning("Чатинг: user_id=%s не найден — не приглашаем", user_id)
        return False

    # Выпускаем ссылку.
    try:
        expire = datetime.now(timezone.utc) + timedelta(minutes=CHAT_INVITE_TTL_MINUTES)
        link = await bot.create_chat_invite_link(
            chat_id=CHAT_HUB_ID,
            name=f"u{user_id}_g{group_id}",  # видно в Telegram-UI для аудита
            expire_date=expire,
            member_limit=1,
        )
    except TelegramAPIError as e:
        logger.error("Чатинг: createChatInviteLink упал (user_id=%s): %s", user_id, e)
        return False

    # Шлём пуш со ссылкой-кнопкой.
    from app.bot.services import notifications

    return await notifications.notify_chat_invite(
        bot,
        user_id=user_id,
        group_name=group_name,
        invite_link=link.invite_link,
    )


async def post_to_group_topic(bot: Bot, *, group_id: int, text: str) -> bool:
    """
    Отправить системное сообщение в топик компании (поздравления, подборки).

    Если топик ещё не создан (message_thread_id is None) — выходим: слать некуда.
    Возвращает True при успешной отправке.
    """
    if not _hub_configured():
        return False

    group = await _get_group(group_id)
    if group is None or group.message_thread_id is None:
        logger.info("Чатинг: топик для group_id=%s не готов — сообщение пропущено", group_id)
        return False

    try:
        await bot.send_message(
            chat_id=group.telegram_chat_id,
            message_thread_id=group.message_thread_id,
            text=text,
        )
        return True
    except TelegramAPIError as e:
        logger.error("Чатинг: post в топик упал (group_id=%s): %s", group_id, e)
        return False
