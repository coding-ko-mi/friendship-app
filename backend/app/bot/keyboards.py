"""
Клавиатуры бота.

На MVP боту нужна по сути одна кнопка — открыть Mini App (web_app).
Кнопка web_app работает только по HTTPS-ссылке (требование Telegram),
поэтому MINI_APP_URL на проде обязан быть https-доменом фронтенда.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.bot import texts
from app.config import MINI_APP_URL


def open_app_keyboard(*, register: bool) -> InlineKeyboardMarkup:
    """
    Кнопка открытия Mini App.

    register=True  — текст «Заполнить анкету» (поток регистрации после фото).
    register=False — текст «Открыть приложение» (для уже зарегистрированных).

    Технически кнопка одна и та же (web_app по MINI_APP_URL); меняется только
    подпись, чтобы пользователю было понятно, что произойдёт по нажатию.
    """
    label = texts.BTN_OPEN_APP_REGISTER if register else texts.BTN_OPEN_APP
    button = InlineKeyboardButton(
        text=label,
        web_app=WebAppInfo(url=MINI_APP_URL),
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])
