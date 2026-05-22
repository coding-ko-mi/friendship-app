"""
Окружение Alembic (async).

Берёт строку подключения и метаданные моделей из приложения,
поэтому миграции всегда сверяются с актуальной схемой в коде.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import DATABASE_URL
from app.models import Base  # импорт регистрирует все таблицы в Base.metadata

# Объект конфигурации Alembic (доступ к значениям из alembic.ini).
config = context.config

# Подставляем строку подключения из приложения (а не из alembic.ini).
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Настройка логирования из alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные, по которым autogenerate сравнивает код и БД.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Режим offline: генерация SQL без подключения к БД."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # отслеживать изменения типов столбцов
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Запуск миграций на установленном соединении."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Режим online: подключаемся к БД async-движком и применяем миграции."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = DATABASE_URL
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
