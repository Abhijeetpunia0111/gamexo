"""Per-request database accounting, exposed as `Server-Timing`.

The thing that makes this API fast or slow is not query cost, it is the number of
sequential round trips: next to the database each one is ~0.1 ms, from another
region ~45 ms, from another continent ~257 ms. Query count is therefore the number
worth watching, and it is invisible without something counting it.

Emitted on every response:

    Server-Timing: db;dur=91.2;desc="4 queries", app;dur=6.3
    X-DB-Queries: 4
    X-DB-Connects: 0

`X-DB-Connects` is new *physical* connections opened while serving the request. It
should be 0 once the pool is warm; anything else means requests are paying TLS
handshakes, which is what `warm_pool` and `DB_POOL_SIZE` exist to prevent.
"""

from __future__ import annotations

import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import event
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.db.session import engine


@dataclass(slots=True)
class DbStats:
    queries: int = 0
    seconds: float = 0.0
    connects: int = 0
    #: Statements in execution order — only collected when explicitly asked for,
    #: since holding every statement of every request is a memory leak with a
    #: friendly face.
    statements: list[str] = field(default_factory=list)


# A mutable object in the ContextVar rather than an immutable value: SQLAlchemy runs
# these events inside its own greenlet, which sees a *copy* of the context. Rebinding
# the var there would be invisible to the request; mutating the object it points at
# is not.
_stats: ContextVar[DbStats | None] = ContextVar("gamexo_db_stats", default=None)

_COLLECT_STATEMENTS = False


def current_stats() -> DbStats | None:
    return _stats.get()


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _before(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
    conn.info["_gamexo_t0"] = time.perf_counter()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _after(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
    stats = _stats.get()
    if stats is None:
        return
    started = conn.info.pop("_gamexo_t0", None)
    stats.queries += 1
    if started is not None:
        stats.seconds += time.perf_counter() - started
    if _COLLECT_STATEMENTS:
        stats.statements.append(" ".join(statement.split())[:200])


@event.listens_for(engine.sync_engine, "connect")
def _connect(*args: Any) -> None:
    stats = _stats.get()
    if stats is not None:
        stats.connects += 1


class DbTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        stats = DbStats()
        token = _stats.set(stats)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            _stats.reset(token)

        total_ms = (time.perf_counter() - started) * 1000
        db_ms = stats.seconds * 1000
        response.headers["Server-Timing"] = (
            f'db;dur={db_ms:.1f};desc="{stats.queries} queries", '
            f"app;dur={max(0.0, total_ms - db_ms):.1f}"
        )
        response.headers["X-DB-Queries"] = str(stats.queries)
        response.headers["X-DB-Connects"] = str(stats.connects)
        return response
