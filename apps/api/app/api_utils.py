"""Helpers shared by every domain router."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Generic, Sequence, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError

T = TypeVar("T")
M = TypeVar("M")


class Page(BaseModel, Generic[T]):
    """A page of results.

    Total count included because every list screen in the frontend shows one
    ("48 bookings", "5 team members"). Counting is a second query, but at academy
    scale it is trivial and it saves the client from paging just to learn the size.
    """

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=50, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def page_params(
    page: Annotated[int, Query(ge=1, description="1-indexed page number")] = 1,
    size: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
) -> PageParams:
    return PageParams(page=page, size=size)


# Depends() is what makes these query parameters. Without it FastAPI sees a
# BaseModel annotation and treats it as a request body, so every list endpoint
# starts demanding a JSON payload on GET.
Params = Annotated[PageParams, Depends(page_params)]


async def paginate(
    session: AsyncSession, stmt: Select[Any], params: PageParams, schema: type[T]
) -> Page[T]:
    """Run a SELECT as a page of validated schema objects.

    The tenant predicate is added by the session's `do_orm_execute` listener and RLS
    filters underneath it, so `stmt` never mentions tenant_id — including the count,
    which would otherwise report the whole platform's totals.
    """
    total = await session.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    )
    total = int(total or 0)

    rows = await session.execute(stmt.offset(params.offset).limit(params.size))
    items = [schema.model_validate(row) for row in rows.scalars().unique()]

    return Page[schema](  # type: ignore[valid-type]
        items=items,
        total=total,
        page=params.page,
        size=params.size,
        pages=max(1, (total + params.size - 1) // params.size),
    )


async def get_or_404(
    session: AsyncSession, model: type[M], entity_id: uuid.UUID, *, label: str | None = None
) -> M:
    """Fetch one row by id within the current tenant.

    A row belonging to another academy is invisible here — RLS returns nothing — so
    a cross-tenant id is indistinguishable from a nonexistent one. That is the
    correct behaviour: a 404 discloses less than a 403 would.
    """
    entity = await session.get(model, entity_id)
    if entity is None:
        name = label or model.__name__
        raise NotFoundError(f"{name} not found.", details={"id": str(entity_id)})
    return entity


def as_list(rows: Sequence[Any], schema: type[T]) -> list[T]:
    return [schema.model_validate(row) for row in rows]
