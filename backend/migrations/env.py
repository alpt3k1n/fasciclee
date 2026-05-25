import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, MetaData
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override URL from DATABASE_URL env var (strip async driver prefix)
db_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "+psycopg2")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Import only the metadata, not the async engine
from sqlalchemy import MetaData as _M
import sqlalchemy as sa

# Build metadata by importing models without triggering async engine creation
def _get_metadata() -> _M:
    # Temporarily patch create_async_engine to a no-op so database.py loads cleanly
    import unittest.mock as mock
    dummy_engine = mock.MagicMock()
    dummy_engine.dialect = mock.MagicMock()

    with mock.patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=dummy_engine):
        from app.database import Base
        import app.models  # noqa: F401 — registers all tables on Base.metadata
        return Base.metadata


target_metadata = _get_metadata()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
