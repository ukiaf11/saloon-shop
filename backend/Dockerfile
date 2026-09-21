# uv-managed build. Dependencies resolve from uv.lock, so an image build is
# reproducible and does not re-resolve the dependency graph.
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.5 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 curl \
 && rm -rf /var/lib/apt/lists/*

# Dependency layer: cached until the lockfile itself changes.
COPY pyproject.toml uv.lock ./


FROM base AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project
COPY . .
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


FROM base AS prod
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY . .
# /app/media is where a persistent volume mounts in production; creating it
# here gives it the right owner before the volume is attached.
RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /app/media /app/staticfiles \
 && chown -R appuser:appuser /app
USER appuser
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD curl -fsS "http://localhost:${PORT}/healthz" || exit 1
# Shell form so $PORT expands. Platforms (Railway, Render, Fly) inject the port
# they route to; binding a hard-coded 8000 would leave the service unreachable.
# `exec` keeps gunicorn as PID 1 so it receives SIGTERM on redeploy and drains.
CMD exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WEB_CONCURRENCY:-3}" \
    --timeout 60 \
    --access-logfile - --error-logfile -
