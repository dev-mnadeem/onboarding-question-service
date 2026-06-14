# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Build stage: resolve dependencies from uv.lock into a standalone virtualenv.
# The MySQL headers are only needed here -- the runtime stage keeps the shared
# library and nothing else.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# uv itself is not pinned: uv.lock pins every dependency of the application.
RUN pip install uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra prod

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=backend.settings

RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --uid 10001 app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . .

# Collect the admin assets at build time. WhiteNoise serves them, so the
# container needs nothing in front of gunicorn.
RUN SECRET_KEY=build-only ENVIRONMENT=build DEBUG=False \
    python manage.py collectstatic --noinput \
    && chown -R app:app /app/staticfiles \
    && mkdir -p /app/media && chown app:app /app/media

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz/ || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
