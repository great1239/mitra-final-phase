FROM alpine/git:2.49.1 AS source

ARG INSIGHTFLOW_REPOSITORY=https://github.com/VJY123VJY/bhiv.git
ARG INSIGHTFLOW_REF=db763b141a4bb42b0aca956a84f5f73a82c9f518
RUN git clone --filter=blob:none --no-checkout "$INSIGHTFLOW_REPOSITORY" /source \
    && cd /source \
    && git sparse-checkout init --cone \
    && git sparse-checkout set app migrations \
    && git checkout "$INSIGHTFLOW_REF"

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=source /source/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt
COPY --from=source /source/app /app/app
COPY --from=source /source/migrations /app/migrations
COPY --from=source /source/alembic.ini /app/alembic.ini
COPY integration_services/seed_insightflow_key.py /app/seed_insightflow_key.py

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
