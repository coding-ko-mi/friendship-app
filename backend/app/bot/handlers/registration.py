"""
Хендлер приёма фото — единственный интерактивный шаг регистрации в боте.

Срабатывает ТОЛЬКО в состоянии Registration.waiting_for_photo, чтобы не реагировать
на случайные фото вне регистрации. Что делает:
  1. Берёт file_id самого большого варианта присланного фото.
  2. Кладёт его в Redis (pending_photo:{telegram_id}) — оттуда заберёт API.
  3. Очищает FSM и даёт кнопку открытия Mini App для остальной анкеты.

Если в этом состоянии пришло НЕ фото — мягко просим прислать именно фотографию.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot import keyboards, texts
from app.bot.services.pending_photo import save_pending_photo
from app.bot.states import Registration
from app.redis_client import redis_client

router = Router(name="registration")


@router.message(Registration.waiting_for_photo, F.photo)
async def handle_photo(message: Message, state: FSMContext) -> None:
    """Принять фото, сохранить file_id в Redis, перевести в Mini App."""
    if message.from_user is None or not message.photo:
        return

    # message.photo — список вариантов одного фото в разных разрешениях,
    # отсортированных по возрастанию. Берём последний (самый качественный).
    file_id = message.photo[-1].file_id

    await save_pending_photo(
        redis_client,
        telegram_id=message.from_user.id,
        file_id=file_id,
    )

    # Фото сохранено — в боте регистрация закончена, остальное в Mini App.
    await state.clear()
    await message.answer(
        texts.PHOTO_SAVED,
        reply_markup=keyboards.open_app_keyboard(register=True),
    )


@router.message(Registration.waiting_for_photo)
async def handle_not_a_photo(message: Message) -> None:
    """
    В состоянии ожидания фото пришло что-то кроме фото (текст, файл, стикер).

    Не меняем состояние — остаёмся ждать фото, просто подсказываем формат.
    """
    await message.answer(texts.PHOTO_NOT_A_PHOTO)
