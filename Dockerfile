FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MITRA_COMPANION_DATA_ROOT=/data \
    MITRA_COMPANION_ENVIRONMENT=production \
    OTEL_SERVICE_NAME=mitra-companion-runtime

WORKDIR /app
RUN groupadd --system mitra \
    && useradd --system --gid mitra --create-home --home-dir /app mitra

COPY requirements.txt pyproject.toml ./
COPY pratham ./pratham
COPY contracts ./contracts
COPY scripts ./scripts

RUN pip install --no-cache-dir . \
    && mkdir -p /data /tmp/mitra \
    && chown -R mitra:mitra /app /data /tmp/mitra

EXPOSE 8090
VOLUME ["/data"]

USER mitra
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 CMD ["python", "-c", "import os, urllib.request; port=os.getenv('MITRA_COMPANION_PORT', os.getenv('PORT', '8090')); urllib.request.urlopen(f'http://127.0.0.1:{port}/ready')"]
CMD ["mitra-companion", "serve"]
