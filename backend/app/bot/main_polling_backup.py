"""
Точка входа Telegram-бота (aiogram 3.x, режим polling).

Запуск (из папки backend/, отдельным процессом рядом с uvicorn):
    python -m app.bot.main

Что делает:
  1. Создаёт Bot с дефолтным parse_mode=HTML.
  2. FSM-сторадж — RedisStorage (общий Redis проекта), чтобы стейт регистрации
     переживал перезапуск бота и был отделён от данных приложения по префиксу.
  3. Подключает роутеры (/start, приём фото).
  4. Параллельно запускает polling и consumer событий из Redis.

Почему polling, а не webhook: проще для разработки и MVP, не требует публичного
HTTPS-домена. Переезд на webhook — замена блока запуска ниже, остальной код
(хендлеры, сервисы) не меняется.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.bot.events_consumer import run_events_consumer
from app.bot.handlers import registration, start
from app.config import REDIS_URL, TELEGRAM_BOT_TOKEN
from app.redis_client import redis_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def build_dispatcher() -> Dispatcher:
    """
    Собрать Dispatcher с FSM-стораджем на Redis и подключёнными роутерами.

    Порядок роутеров: start первым (команда /start), затем registration
    (приём фото в состоянии waiting_for_photo). Порядок важен только при
    пересечении фильтров — здесь они не пересекаются, но держим логичным.
    """
    # RedisStorage для FSM. Префикс по умолчанию у aiogram свой ("fsm"),
    # данные приложения (skip-пометки, pending_photo, очередь) лежат под
    # другими ключами — конфликта нет.
    storage = RedisStorage.from_url(REDIS_URL)
    dp = Dispatcher(storage=storage)
    dp.include_router(start.router)
    dp.include_router(registration.router)
    return dp


async def main() -> None:
    """Запустить бота: polling + consumer событий одновременно."""
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

    # Consumer событий — фоновая задача рядом с polling-ом. Обе работают,
    # пока жив процесс; при остановке gather отменит consumer.
    consumer_task = asyncio.create_task(run_events_consumer(bot, redis_client))

    try:
        logger.info("Бот запускается (polling)...")
        # drop_pending_updates=True: при старте игнорируем накопившиеся апдейты,
        # чтобы бот не «отвечал» на старые сообщения после простоя.
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        # Останавливаем consumer и корректно закрываем сессию бота.
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
