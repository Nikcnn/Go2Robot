from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

EventLevel = Literal["info", "warn", "error"]
EventCategory = Literal[
    "state_transition",
    "action_accepted",
    "action_rejected",
    "movement_blocked",
    "fault",
    "mission",
    "connection",
]


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


class PersistentEventLog:
    """Cross-mission append-only JSON-lines log with in-memory cache for history queries."""

    def __init__(self, log_path: Path, cache_limit: int = 1000) -> None:
        self._path = log_path
        self._cache_limit = cache_limit
        self._lock = threading.Lock()
        self._cache: list[dict] = []
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load_recent()

    def _load_recent(self) -> None:
        if not self._path.exists():
            return
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
            for line in lines[-self._cache_limit:]:
                line = line.strip()
                if line:
                    try:
                        self._cache.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass  # skip corrupt lines
        except Exception:
            pass  # don't crash on corrupt log; start fresh

    def append(
        self,
        level: EventLevel,
        category: EventCategory,
        event: str,
        message: str,
        details: dict | None = None,
    ) -> dict:
        record: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "category": category,
            "event": event,
            "message": message,
            "details": details or {},
        }
        with self._lock:
            self._cache.append(record)
            if len(self._cache) > self._cache_limit:
                self._cache = self._cache[-self._cache_limit:]
            try:
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, default=_json_default) + "\n")
            except Exception:
                pass  # disk errors must not crash the server
        return record

    def query(
        self,
        level: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return entries in reverse-chronological order (newest first)."""
        with self._lock:
            records = list(self._cache)
        if level:
            records = [r for r in records if r.get("level") == level]
        if category:
            records = [r for r in records if r.get("category") == category]
        return records[-limit:][::-1]
