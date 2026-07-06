from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def merge_context(*partitions: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for partition in partitions:
        merged.update(partition)
    return merged

