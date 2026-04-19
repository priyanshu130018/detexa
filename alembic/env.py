"""
Alembic environment file.
Run migrations with:
    alembic upgrade head
    alembic revision --autogenerate -m "describe change"
"""
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make project importable
sys.path.insert(0, str(Path(__file__).parents[1]))

from core.config import settings
from database.db import Base
from database import models  # noqa – register ORM classes

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
