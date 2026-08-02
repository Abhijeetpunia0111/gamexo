# Python 3.13 rather than 3.14: asyncpg ships wheels for 3.13, and on 3.14 it
# falls back to a source build that needs a C toolchain in the image.
FROM python:3.13-slim

# uv, pinned. Copied from the official distroless image so we do not install a
# toolchain just to fetch a binary.
COPY --from=ghcr.io/astral-sh/uv:0.10.3 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

WORKDIR /app

# Dependency layer, cached independently of source. `--no-install-project`
# because [tool.uv] package = false — there is nothing of ours to install.
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev 2>/dev/null \
    || uv sync --no-install-project --no-dev

COPY . .

RUN chmod +x /app/docker/entrypoint.sh
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
