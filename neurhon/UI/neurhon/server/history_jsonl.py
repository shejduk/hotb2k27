"""Listening history stored as a JSON Lines file (one JSON object per line)."""

import json
import threading
from dataclasses import asdict
from pathlib import Path

from neurhon.server.interfaces import HistoryEntry, HistoryStore, Mood, Track


class JsonlHistoryStore(HistoryStore):
    """Prowizoryczna implementacja HistoryStore"""

    def __init__(self, path: str | Path = "history.jsonl"):
        self._path = Path(path)
        self._lock = threading.Lock()

    def append(self, entry: HistoryEntry) -> None:
        line = json.dumps(asdict(entry), ensure_ascii=False) # spłaszcza wartości ze słownika i zapisuje jako json
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def get_entries(self, limit: int = 100, since: float | None = None) -> list[HistoryEntry]:
        if not self._path.exists():
            return []

        entries = []
        with self._lock:
            lines = self._path.read_text(encoding="utf-8").splitlines()

        for line in lines:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                entry = HistoryEntry(
                    timestamp=data["timestamp"],
                    track=Track(**data["track"]),
                    mood=Mood(**data["mood"]),
                    reason=data.get("reason", "auto"),
                )
            except (ValueError, KeyError, TypeError):
                continue  # jak wywali błąd to żeby nie było kichy
            if since is None or entry.timestamp >= since:
                entries.append(entry)

        entries.reverse()  # file is oldest-first, we return newest-first
        return entries[:limit]
