from __future__ import annotations

from enum import StrEnum


SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "1.0.0"
RUNTIME_VERSION = "1.0.0"
COMPATIBILITY_VERSION = "mitra-companion-1"


class RuntimeState(StrEnum):
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"


class SessionState(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class AttachmentState(StrEnum):
    ATTACHED = "ATTACHED"
    DEGRADED = "DEGRADED"
    DETACHED = "DETACHED"


class DispatchStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ContextScope(StrEnum):
    SESSION = "session"
    WORKSPACE = "workspace"
    PRODUCT = "product"
    HANDOFF = "handoff"

