"""Alembic environment for auth_db.

Run from the repository root:
    alembic -c services/auth/alembic.ini upgrade head

The container entrypoint runs the same file on startup, so the schema is
always created from migrations.

Connection string comes from the service URL already configured for the app
(AUTH_DATABASE_URL in compose, AUTH_DB_URL in .env), with two adjustments:
  - driver swapped to psycopg 2/3 sync driver (Alembic runs synchronously);
  - host replaced by localhost when running outside Docker, because the
    compose name "postgres" only resolves inside the compose network.
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

# Lets Alembic import "services.auth.app.models" from the repository root.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.auth.app.database import Base  # noqa: E402
import services.auth.app.models  # noqa: E402,F401  (registers the tables)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def database_url() -> str:
    url = os.getenv("AUTH_DATABASE_URL") or os.getenv("AUTH_DB_URL")
    if not url:
        raise RuntimeError("AUTH_DATABASE_URL (or AUTH_DB_URL) is not set")

    url = url.replace("+asyncpg", "+psycopg")

    # Inside a container /.dockerenv exists; outside it does not.
    in_container = Path("/.dockerenv").exists()
    host = os.getenv("ALEMBIC_DB_HOST") or ("postgres" if in_container else "localhost")

    parts = urlsplit(url)
    netloc = parts.netloc.rsplit("@", 1)[-1]
    port = parts.port or 5432
    userinfo = parts.netloc.rsplit("@", 1)[0] if "@" in parts.netloc else ""
    new_netloc = f"{userinfo}@{host}:{port}" if userinfo else f"{host}:{port}"
    return urlunsplit((parts.scheme, new_netloc, parts.path, parts.query, parts.fragment))


config.set_main_option("sqlalchemy.url", database_url())

target_metadata = Base.metadata


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
