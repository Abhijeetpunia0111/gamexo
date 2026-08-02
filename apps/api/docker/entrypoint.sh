#!/bin/sh
# Local-dev convenience only. In production, migrations are a deploy step that
# runs once — not something every replica races to do on boot.
set -e

if [ "${RUN_MIGRATIONS_ON_START:-false}" = "true" ]; then
    echo "==> alembic upgrade head"
    alembic upgrade head
fi

if [ "${RUN_SEED_ON_START:-false}" = "true" ]; then
    echo "==> seeding tenant #1"
    python -m app.seed.seed
fi

exec "$@"
