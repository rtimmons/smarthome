from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from rich.console import Console


class DeployTimer:
    def __init__(self, console: Console, enabled: bool = True) -> None:
        self.console = console
        self.enabled = enabled
        self.events: list[dict[str, object]] = []
        self.started_at = time.perf_counter()
        self.started_at_utc = datetime.now(timezone.utc).isoformat()
        self._lock = threading.Lock()

    @contextmanager
    def phase(self, name: str, **fields: object) -> Iterator[None]:
        if not self.enabled:
            yield
            return

        start = time.perf_counter()
        status = "ok"
        try:
            yield
        except BaseException:
            status = "error"
            raise
        finally:
            elapsed = time.perf_counter() - start
            event = {
                "name": name,
                "status": status,
                "seconds": round(elapsed, 3),
                "started_offset_seconds": round(start - self.started_at, 3),
                "finished_offset_seconds": round(time.perf_counter() - self.started_at, 3),
                **fields,
            }
            with self._lock:
                self.events.append(event)

    def record(self, name: str, seconds: float, status: str = "ok", **fields: object) -> None:
        if not self.enabled:
            return
        finished_offset = time.perf_counter() - self.started_at
        event = {
            "name": name,
            "status": status,
            "seconds": round(seconds, 3),
            "started_offset_seconds": round(max(0.0, finished_offset - seconds), 3),
            "finished_offset_seconds": round(finished_offset, 3),
            **fields,
        }
        with self._lock:
            self.events.append(event)

    def print_summary(self) -> None:
        if not self.enabled or not self.events:
            return

        self.console.print("\n[bold]Deploy timings[/bold]")
        with self._lock:
            events = sorted(
                self.events,
                key=lambda event: (
                    float(event.get("started_offset_seconds", 0.0)),
                    str(event["name"]),
                ),
            )
        for event in events:
            label = str(event["name"])
            addon = event.get("addon")
            if addon:
                label = f"{label} ({addon})"
            status = "" if event.get("status") == "ok" else f" [{event['status']}]"
            offset = float(event.get("started_offset_seconds", 0.0))
            self.console.print(f"  [+{offset:7.3f}s] {label}: {event['seconds']:.3f}s{status}")

    def write_json(self, path: str | Path | None) -> None:
        if not path:
            return
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            events = list(self.events)
        target.write_text(
            json.dumps(
                {
                    "started_at_utc": self.started_at_utc,
                    "duration_seconds": round(time.perf_counter() - self.started_at, 3),
                    "events": events,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
