from alembic import context
from sqlalchemy import create_engine, pool
from logging.config import fileConfig
from app.core.db import Base  # Подключаем метаданные моделей
from app.models.user import User  # Импортируем все модели
from app.models.group import Group
from app.models.post import Post
from app.core.config import DATABASE_URL

# Настраиваем Alembic
config = context.config
fileConfig(config.config_file_name)

# ✅ Указываем метаданные моделей
target_metadata = Base.metadata

# ✅ Устанавливаем URL БД
config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_online():
    """Запускаем миграции в онлайн-режиме"""
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise NotImplementedError("Offline migrations are not supported.")
else:
    run_migrations_online()
