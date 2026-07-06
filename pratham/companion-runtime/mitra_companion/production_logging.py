from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import RuntimeSettings


class JsonRuntimeFormatter(logging.Formatter):
    """JSONL formatter for process-level production logs."""

    def format(self, record: logging.LogRecord) -> str:
        fields = getattr(record, "fields", {})
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "event_type": getattr(record, "event_type", record.getMessage()),
        }
        if isinstance(fields, dict):
            payload.update(_redact(fields))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def configure_production_logging(
    settings: RuntimeSettings,
) -> logging.Logger:
    logger = logging.getLogger(
        f"mitra_companion.production.{settings.runtime_instance_id}"
    )
    logger.setLevel(getattr(logging, settings.production_log_level, logging.INFO))
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = JsonRuntimeFormatter()
    if settings.production_log_to_stdout:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if settings.production_log_path is not None:
        log_path = Path(settings.production_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def production_log(
    logger: logging.Logger,
    event_type: str,
    **fields: Any,
) -> None:
    logger.info(
        event_type,
        extra={
            "event_type": event_type,
            "fields": fields,
        },
    )


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("secret", "token", "key")):
                redacted[key] = "<redacted>"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
