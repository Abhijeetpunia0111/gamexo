# Source this for one-off CLI work (alembic, seed, python -c) when apps/api/.env
# is absent. Values mirror .env.example; local dev only, no secrets.
export DATABASE_URL="postgresql+asyncpg://gamexo_app:gamexo_app_pw@localhost:5433/gamexo"
export MIGRATION_DATABASE_URL="postgresql+asyncpg://gamexo_migrator:gamexo_migrator_pw@localhost:5433/gamexo"
export JWT_SECRET_KEY="dev-only-insecure-secret-change-me-before-anything-real"
export DB_APP_USER=gamexo_app
export ALLOW_TENANT_HEADER=true
export ENVIRONMENT=local
