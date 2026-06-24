FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MITRA_COMPANION_DATA_ROOT=/data

WORKDIR /app

COPY requirements.txt pyproject.toml ./
COPY pratham ./pratham
COPY contracts ./contracts
COPY scripts ./scripts

RUN pip install --no-cache-dir .

EXPOSE 8090
VOLUME ["/data"]

CMD ["mitra-companion", "serve", "--host", "0.0.0.0", "--port", "8090"]

