#!/bin/sh
# Entrypoint for every Python service.
#
# Runs pending database migrations before the app starts, so a fresh
# `docker compose up` creates the schema from the migration files instead of
# relying on SQLAlchemy create_all(). Migrations are the single source of
# truth for the schema.
#
# ALEMBIC_CONFIG points at the service alembic.ini copied into the image,
# for example /workspace/services/auth/alembic.ini.
set -e

if [ -n "$ALEMBIC_CONFIG" ] && [ -f "$ALEMBIC_CONFIG" ]; then
    echo "[entrypoint] running migrations with $ALEMBIC_CONFIG"
    alembic -c "$ALEMBIC_CONFIG" upgrade head
fi

exec "$@"
