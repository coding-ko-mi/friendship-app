"""
Точка входа Telegram-бота (aiogram 3.x, режим webhook).

Переключён с polling на webhook в модуле «Деплой» (handoff_7).
Причина: HTTPS всё равно нужен для Mini App → webhook бесплатен,
и это правильный подход для продакшна.

Что делает:
  1. Создаёт Bot с дефолтным parse_mode=HTML.
  2. FSM-сторадж — RedisStorage (общий Redis проекта).
  3. Подключает роутеры (/start, приём фото).
  4. Регистрирует webhook URL у Telegram.
  5. Запускает aiohttp-сервер на WEBHOOK_PORT для приёма апдейтов.
  6. Параллельно запускает consumer событий из Redis.

Webhook URL (из env): https://твой-домен/webhook
nginx пробрасывает /webhook → этот aiohttp-сервер внутри Docker-сети.

Возврат к polling для локальной разработки:
  Закомментируй блок webhook и раскомментируй polling-блок внизу.
"""
from __future__ import annotations

import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.bot.events_consumer import run_events_consumer
from app.bot.handlers import registration, start
from app.config import REDIS_URL, TELEGRAM_BOT_TOKEN, WEBHOOK_SECRET
from app.redis_client import redis_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Webhook настройки из env (задаются в .env, пробрасываются через compose).
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")   # https://домен/webhook
WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8080"))


def build_dispatcher() -> Dispatcher:
    """
    Собрать Dispatcher с FSM-стораджем на Redis и подключёнными роутерами.

    Порядок роутеров: start первым (команда /start), затем registration
    (приём фото в состоянии waiting_for_photo).
    """
    storage = RedisStorage.from_url(REDIS_URL)
    dp = Dispatcher(storage=storage)
    dp.include_router(start.router)
    dp.include_router(registration.router)
    return dp


async def on_startup(bot: Bot) -> None:
    """Зарегистрировать webhook URL у Telegram при старте."""
    if not WEBHOOK_URL:
        raise RuntimeError(
            "WEBHOOK_URL не задан в .env. "
            "Формат: https://твой-домен/webhook"
        )
    # secret_token защищает /webhook от чужих POST'ов: Telegram эхом шлёт его
    # в X-Telegram-Bot-Api-Secret-Token, aiogram сверяет — несовпадение → 401.
    await bot.set_webhook(WEBHOOK_URL, secret_token=WEBHOOK_SECRET or None)
    logger.info(
        "Webhook зарегистрирован: %s (secret_token=%s)",
        WEBHOOK_URL,
        "set" if WEBHOOK_SECRET else "DISABLED — опасно для прода",
    )


async def on_shutdown(bot: Bot) -> None:
    """Снять webhook при остановке (чтобы Telegram перестал слать апдейты)."""
    await bot.delete_webhook()
    logger.info("Webhook снят")


def main() -> None:
    """Запустить бота в webhook-режиме + consumer событий."""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN не задан. Укажите его в .env "
            "(получить у @BotFather)."
        )

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()

    # Регистрируем startup/shutdown хуки.
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # aiohttp-приложение для приёма webhook-запросов от Telegram.
    app = web.Application()

    # SimpleRequestHandler связывает маршрут WEBHOOK_PATH с Dispatcher.
    # Каждый POST от Telegram на /webhook → aiogram обрабатывает как Update.
    # secret_token: aiogram сверит заголовок входящего POST с этой строкой.
    # Если строка пустая — проверка отключена (так что в локалке/без WEBHOOK_SECRET
    # всё работает). На проде WEBHOOK_SECRET обязателен — см. .env.example.
    handler = SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET or None
    )
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Consumer событий из Redis запускается как фоновая задача aiohttp.
    # Он стартует вместе с aiohttp-сервером через on_startup.
    async def start_consumer(app: web.Application) -> None:
        app["consumer_task"] = asyncio.create_task(
            run_events_consumer(bot, redis_client)
        )

    async def stop_consumer(app: web.Application) -> None:
        task = app.get("consumer_task")
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app.on_startup.append(start_consumer)
    app.on_cleanup.append(stop_consumer)

    logger.info(
        "Бот запускается (webhook mode: %s, port %s)...",
        WEBHOOK_PATH,
        WEBHOOK_PORT,
    )
    web.run_app(app, host=WEBHOOK_HOST, port=WEBHOOK_PORT)


# ---------------------------------------------------------------------------
# ЛОКАЛЬНАЯ РАЗРАБОТКА: polling-режим
# Раскомментируй этот блок и закомментируй main() выше для разработки без HTTPS.
# ---------------------------------------------------------------------------
# async def _main_polling() -> None:
#     bot = Bot(token=TELEGRAM_BOT_TOKEN,
#               default=DefaultBotProperties(parse_mode=ParseMode.HTML))
#     dp = build_dispatcher()
#     consumer_task = asyncio.create_task(run_events_consumer(bot, redis_client))
#     try:
#         await dp.start_polling(bot, drop_pending_updates=True)
#     finally:
#         consumer_task.cancel()
#         try:
#             await consumer_task
#         except asyncio.CancelledError:
#             pass
#         await bot.session.close()
#
# if __name__ == "__main__":
#     try:
#         asyncio.run(_main_polling())
#     except (KeyboardInterrupt, SystemExit):
#         logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
