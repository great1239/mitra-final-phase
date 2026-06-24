from __future__ import annotations

import threading

from .constants import RuntimeState
from .ports import LifecycleStorePort


ALLOWED_TRANSITIONS: dict[RuntimeState, set[RuntimeState]] = {
    RuntimeState.INITIALIZING: {
        RuntimeState.READY,
        RuntimeState.DEGRADED,
        RuntimeState.STOPPED,
    },
    RuntimeState.READY: {
        RuntimeState.ACTIVE,
        RuntimeState.DEGRADED,
        RuntimeState.DRAINING,
    },
    RuntimeState.ACTIVE: {
        RuntimeState.READY,
        RuntimeState.DEGRADED,
        RuntimeState.DRAINING,
    },
    RuntimeState.DEGRADED: {
        RuntimeState.READY,
        RuntimeState.ACTIVE,
        RuntimeState.DRAINING,
    },
    RuntimeState.DRAINING: {RuntimeState.STOPPED},
    RuntimeState.STOPPED: {RuntimeState.INITIALIZING},
}


class RuntimeLifecycle:
    def __init__(self, store: LifecycleStorePort):
        self.store = store
        self._lock = threading.RLock()
        self.state = store.current_state()
        if self.state is None or self.state == RuntimeState.STOPPED:
            previous = self.state
            self.state = RuntimeState.INITIALIZING
            self.store.record_transition(
                previous,
                self.state,
                "Companion runtime lifecycle initialized",
            )

    def transition(self, target: RuntimeState, reason: str) -> dict:
        with self._lock:
            if target == self.state:
                return {
                    "from_state": self.state.value,
                    "to_state": target.value,
                    "reason": reason,
                    "unchanged": True,
                }
            if target not in ALLOWED_TRANSITIONS[self.state]:
                raise ValueError(
                    f"Illegal runtime transition: {self.state.value} -> "
                    f"{target.value}"
                )
            record = self.store.record_transition(self.state, target, reason)
            self.state = target
            return record

    def history(self, limit: int = 100) -> list[dict]:
        return self.store.transitions(limit)
