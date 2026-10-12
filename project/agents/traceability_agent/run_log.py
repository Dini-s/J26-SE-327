"""Append-only JSONL event log of a pipeline run, read live by the dashboard."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RunLogger:
    """Writes one JSON object per line to ``<root>/<run_id>/events.jsonl``.

    Every line has ``type`` and ``ts`` plus event-specific fields. Lines are flushed
    immediately so a reader polling the file sees events as they happen.
    """

    def __init__(self, path: Path) -> None:
        """Open (and create) the event file.

        Args:
            path: The ``events.jsonl`` file to append to.
        """
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def new(cls, root: Path, label: str = "run") -> "RunLogger":
        """Create a logger for a fresh run directory named by timestamp and label."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return cls(Path(root) / f"{stamp}-{label}" / "events.jsonl")

    def emit(self, type: str, **data: Any) -> None:
        """Append one event.

        Args:
            type: Event name, e.g. ``run_start``, ``shortlist``, ``verdict``, ``run_end``.
            **data: JSON-serialisable fields.
        """
        record = {"type": type, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **data}
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
