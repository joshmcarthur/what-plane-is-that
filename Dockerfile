FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=1320 \
    CACHE_TTL_SECONDS=8 \
    OBSERVER_LAT=-41.29 \
    OBSERVER_LNG=174.78 \
    NEAREST_RADIUS_KM=15 \
    NEAREST_MAX_ALT_FT=15000 \
    NEAREST_MAX_SEEN_POS_S=20 \
    AIRCRAFT_DB_PREFIXES=ZK \
    AIRCRAFT_DB_CACHE_DIR=/var/cache/what-plane \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /var/cache/what-plane

COPY pyproject.toml uv.lock README.md ./
COPY what_plane ./what_plane
RUN uv sync --frozen --no-dev

VOLUME ["/var/cache/what-plane"]

EXPOSE 1320

CMD ["uvicorn", "what_plane.main:app", "--host", "0.0.0.0", "--port", "1320"]
