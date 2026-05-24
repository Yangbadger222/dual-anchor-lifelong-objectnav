from __future__ import annotations

from objectnav_core.memory.sqlite_store import SQLiteMemoryStore
from objectnav_core.models import TrialEvent


class TrialLogger:
    def __init__(self, store: SQLiteMemoryStore, trial_id: str) -> None:
        self.store = store
        self.trial_id = trial_id
        self.events: list[TrialEvent] = []

    def record(
        self,
        event_type: str,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        event = TrialEvent(
            trial_id=self.trial_id,
            event_type=event_type,
            message=message,
            payload=payload or {},
        )
        self.events.append(event)
        self.store.record_trial_event(self.trial_id, event_type, message, payload)
