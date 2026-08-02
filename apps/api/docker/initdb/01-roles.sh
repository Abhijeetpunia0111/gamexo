#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Bootstraps the two-role setup that makes Row-Level Security actually enforce.
#
#   gamexo_migrator — owns the database and schema. Alembic connects as this.
#   gamexo_app      — the API connects as this. NOSUPERUSER, NOBYPASSRLS, DML only.
#
# The split is not ceremony. Postgres exempts a table's OWNER from its own RLS
# policies unless FORCE ROW LEVEL SECURITY is set, and exempts superusers and
# BYPASSRLS roles unconditionally. Migrations must own the tables to alter them,
# so the API has to be someone else. tests/test_tenant_isolation.py asserts these
# role properties directly, because they are invisible until they fail.
#
# Runs once, on first initialisation of an empty data volume.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE "${DB_MIGRATOR_USER}" LOGIN PASSWORD '${DB_MIGRATOR_PASSWORD}'
        NOSUPERUSER NOCREATEROLE NOBYPASSRLS;
    CREATE ROLE "${DB_APP_USER}" LOGIN PASSWORD '${DB_APP_PASSWORD}'
        NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

    ALTER DATABASE "${POSTGRES_DB}" OWNER TO "${DB_MIGRATOR_USER}";

    CREATE DATABASE "${DB_TEST_DATABASE}" OWNER "${DB_MIGRATOR_USER}";
EOSQL

# Per-database setup. Applied identically to the dev and test databases so the
# isolation tests run against the same privilege model as production.
for db in "$POSTGRES_DB" "$DB_TEST_DATABASE"; do
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" <<-EOSQL
        ALTER SCHEMA public OWNER TO "${DB_MIGRATOR_USER}";

        -- Required by the booking exclusion constraint in Phase 2:
        -- EXCLUDE USING gist (tenant_id WITH =, court_id WITH =, time_range WITH &&)
        -- needs btree_gist to put a plain-equality UUID column into a GiST index.
        -- Created here because CREATE EXTENSION needs privileges the migrator lacks.
        CREATE EXTENSION IF NOT EXISTS btree_gist;

        GRANT CONNECT ON DATABASE "${db}" TO "${DB_APP_USER}";
        GRANT USAGE ON SCHEMA public TO "${DB_APP_USER}";

        -- Future tables created by the migrator are automatically readable/writable
        -- by the app role, so every later migration does not need to remember to GRANT.
        -- Tables needing narrower rights (audit_log is INSERT/SELECT only) REVOKE
        -- explicitly in their own migration.
        ALTER DEFAULT PRIVILEGES FOR ROLE "${DB_MIGRATOR_USER}" IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "${DB_APP_USER}";
        ALTER DEFAULT PRIVILEGES FOR ROLE "${DB_MIGRATOR_USER}" IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO "${DB_APP_USER}";
EOSQL
done
