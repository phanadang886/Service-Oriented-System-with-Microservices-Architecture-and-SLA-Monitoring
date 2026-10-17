#!/bin/bash
# Create one database per service.
# The postgres image only creates POSTGRES_DB on first start, so the other
# three must be created explicitly or "alembic upgrade head" fails.

set -e

for db in auth_db catalog_db booking_db notification_db; do
    echo "  creating database: $db"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        SELECT 'CREATE DATABASE $db'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
done