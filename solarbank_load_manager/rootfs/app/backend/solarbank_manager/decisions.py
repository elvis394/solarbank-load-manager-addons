from __future__ import annotations

from collections import deque

from .models import Decision


class DecisionLog:
    def __init__(self, max_entries: int = 5760) -> None:
        self.entries: deque[Decision] = deque(maxlen=max_entries)

    def append(self, decision: Decision) -> None:
        self.entries.appendleft(decision)

    def latest(self) -> Decision | None:
        return self.entries[0] if self.entries else None

    def list(self, limit: int = 100) -> list[Decision]:
        return list(self.entries)[:limit]
