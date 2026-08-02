"""Dump the OpenAPI schema to a file, without starting a server.

    uv run python scripts/export_openapi.py ../web/src/api/openapi.json

Used by the client generator so the schema comes straight from the FastAPI app —
no running server, no drift between what is generated and what is deployed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Runnable from anywhere, including a package.json script in apps/web.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Placeholders so the settings model validates: this script never opens a
# connection, it only walks the route table.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost:5432/x")
os.environ.setdefault("MIGRATION_DATABASE_URL", "postgresql+asyncpg://x:x@localhost:5432/x")
os.environ.setdefault("JWT_SECRET_KEY", "openapi-export-placeholder-not-a-real-secret")

from app.main import app  # noqa: E402


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json").resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    schema = app.openapi()
    # Stable key order and a trailing newline, so regenerating produces a clean
    # diff instead of reordering the whole file.
    target.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")

    paths = len(schema.get("paths", {}))
    schemas = len(schema.get("components", {}).get("schemas", {}))
    print(f"Wrote {target} — {paths} paths, {schemas} schemas")


if __name__ == "__main__":
    main()
