"""Alembic environment for booking_db.

Run from the repository root:
    alembic -c services/booking/alembic.ini upgrade head

The container entrypoint runs the same file on startup, so the schema is
always created from migrations.
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def database_url() -> str:
    url = os.getenv("BOOKING_DATABASE_URL") or os.getenv("BOOKING_DB_URL")
    if not url:
        raise RuntimeError("BOOKING_DATABASE_URL (or BOOKING_DB_URL) is not set")

    url = url.replace("+asyncpg", "+psycopg")

    in_container = Path("/.dockerenv").exists()
    host = os.getenv("ALEMBIC_DB_HOST") or ("postgres" if in_container else "localhost")

    parts = urlsplit(url)
    port = parts.port or 5432
    userinfo = parts.netloc.rsplit("@", 1)[0] if "@" in parts.netloc else ""
    new_netloc = f"{userinfo}@{host}:{port}" if userinfo else f"{host}:{port}"
    return urlunsplit((parts.scheme, new_netloc, parts.path, parts.query, parts.fragment))


config.set_main_option("sqlalchemy.url", database_url())

# No ORM models yet: migrations in this service are written by hand.
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
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
