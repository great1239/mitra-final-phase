FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY integration_services/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt
COPY integration_services /app/integration_services

RUN useradd --system --create-home --home-dir /home/integration integration \
    && mkdir -p /data \
    && chown -R integration:integration /data /home/integration

USER integration
