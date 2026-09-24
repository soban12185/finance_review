"""Alembic environment - database URL comes from DATABASE_URL / .env."""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401  (registers all tables on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
target_metadata = Base.metadata


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        url = os.environ.get("DATABASE_URL")
    if not url:
        url = settings.database_url
    # Apply the same driver normalization used by app settings so provider URLs
    # (Neon/Supabase/Render - all "postgresql://") resolve: the bundled driver is
    # psycopg, so the SQLAlchemy scheme must be "postgresql+psycopg".
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = "postgresql+psycopg" + url[len("postgresql"):]
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_database_url(), poolclass=pool.NullPool, pool_pre_ping=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()