# syntax=docker/dockerfile:1
FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY mockbox ./mockbox
RUN pip install ".[server,yaml]" \
    && useradd --create-home --uid 10001 mockbox

USER mockbox

# Inside a container the server must listen on all interfaces to be reachable.
ENV MOCKBOX_HOST=0.0.0.0 \
    MOCKBOX_PORT=5000 \
    MOCKBOX_IN_CONTAINER=1
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('MOCKBOX_PORT', '5000'), timeout=2)" || exit 1

# Mount a config file at /app/config.ini, or configure with MOCKBOX_* environment variables.
ENTRYPOINT ["mockbox"]
