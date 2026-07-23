#!/bin/sh
set -eu

alembic upgrade head
python /app/seed_insightflow_key.py
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
