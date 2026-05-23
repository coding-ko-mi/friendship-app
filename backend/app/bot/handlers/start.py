"""
Хендлер команды /start — точка входа в бота.

Логика:
  • если пользователь уже зарегистрирован (есть строка User по telegram_id) —
    приветствуем и даём кнопку «Открыть приложение»;
  • если нет — запускаем регистрацию: просим прислать фото и переводим FSM
    в состояние ожидания фото.

Бот ЧИТАЕТ из БД (узнать, есть ли User), но НЕ пишет — запись делает API
(registration_service). Это сохраняет единственного писателя в БД.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from app.bot import keyboards, texts
from app.bot.states import Registration
from app.database import async_session_factory
from app.models.user import User

router = Router(name="start")


async def _is_registered(telegram_id: int) -> bool:
    """
    Есть ли уже анкета у этого telegram_id.

    Открываем короткую сессию через общую фабрику проекта (ту же, что у API).
    Только чтение — ничего не коммитим.
    """
    async with async_session_factory() as session:
        result = await session.execute(
            select(User.id).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none() is not None


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    """Обработать /start: развилка «уже зарегистрирован / новый»."""
    # message.from_user гарантированно есть для команды от пользователя,
    # но проверяем явно — Telegram допускает сообщения без from_user (каналы).
    if message.from_user is None:
        return

    telegram_id = message.from_user.id

    if await _is_registered(telegram_id):
        # На всякий случай очищаем возможный «висящий» FSM-стейт.
        await state.clear()
        await message.answer(
            texts.START_REGISTERED,
            reply_markup=keyboards.open_app_keyboard(register=False),
        )
        return

    # Новый пользователь — начинаем регистрацию с шага фото.
    await state.set_state(Registration.waiting_for_photo)
    await message.answer(texts.START_NEW_USER)
