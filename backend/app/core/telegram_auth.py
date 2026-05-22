"""
Валидация Telegram Mini App initData.

Когда пользователь открывает Mini App, Telegram передаёт в window.Telegram.WebApp.initData
строку с данными пользователя и HMAC-подписью. Мы проверяем подпись на сервере —
это и есть «авторизация через Telegram».

Алгоритм проверки (официальная документация Telegram):
1. Разбить initData на пары key=value
2. Убрать пару hash=...
3. Отсортировать оставшиеся пары по ключу
4. Склеить через \n
5. Ключ проверки = HMAC-SHA256("WebAppData", bot_token)
6. Подпись = HMAC-SHA256(data_check_string, secret_key)
7. Сравнить подпись с hash из initData

Если подпись верна — данные пришли от Telegram, telegram_id можно доверять.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from app.config import TELEGRAM_BOT_TOKEN


class TelegramAuthError(Exception):
    """Ошибка валидации initData."""
    pass


def validate_init_data(init_data_raw: str) -> dict:
    """
    Проверить подпись initData и вернуть данные пользователя.

    Args:
        init_data_raw: строка из window.Telegram.WebApp.initData

    Returns:
        Словарь с данными: {"id": 123456, "first_name": "Иван", ...}

    Raises:
        TelegramAuthError: подпись неверна, данные устарели, или токен не настроен
    """
    if not TELEGRAM_BOT_TOKEN:
        raise TelegramAuthError(
            "TELEGRAM_BOT_TOKEN не задан в .env"
        )

    # Разбираем строку в словарь
    params = dict(parse_qsl(init_data_raw, keep_blank_values=True))

    received_hash = params.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("Отсутствует hash в initData")

    # Проверяем свежесть данных (не старше 24 часов)
    auth_date = params.get("auth_date")
    if auth_date:
        age_seconds = int(time.time()) - int(auth_date)
        if age_seconds > 86400:  # 24 часа
            raise TelegramAuthError(
                f"initData устарел ({age_seconds // 3600} ч). Переоткрой Mini App."
            )

    # Собираем строку для проверки: отсортированные key=value через \n
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )

    # Вычисляем ожидаемую подпись
    secret_key = hmac.new(
        b"WebAppData",
        TELEGRAM_BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()

    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramAuthError("Неверная подпись initData")

    # Извлекаем данные пользователя из поля "user"
    user_json = params.get("user")
    if not user_json:
        raise TelegramAuthError("Отсутствует поле user в initData")

    try:
        user_data = json.loads(user_json)
    except json.JSONDecodeError:
        raise TelegramAuthError("Невалидный JSON в поле user")

    if "id" not in user_data:
        raise TelegramAuthError("Отсутствует telegram_id в данных пользователя")

    return user_data
