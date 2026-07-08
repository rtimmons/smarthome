from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from rich.console import Console


class DeployTimer:
    def __init__(self, console: Console, enabled: bool = True) -> None:
        self.console = console
        self.enabled = enabled
        self.events: list[dict[str, object]] = []

    @contextmanager
    def phase(self, name: str, **fields: object) -> Iterator[None]:
        if not self.enabled:
            yield
            return

        start = time.perf_counter()
        status = "ok"
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            elapsed = time.perf_counter() - start
            event = {
                "name": name,
                "status": status,
                "seconds": round(elapsed, 3),
                **fields,
            }
            self.events.append(event)

    def record(self, name: str, seconds: float, status: str = "ok", **fields: object) -> None:
        if not self.enabled:
            return
        self.events.append({
            "name": name,
            "status": status,
            "seconds": round(seconds, 3),
            **fields,
        })

    def print_summary(self) -> None:
        if not self.enabled or not self.events:
            return

        self.console.print("\n[bold]Deploy timings[/bold]")
        for event in self.events:
            label = str(event["name"])
            addon = event.get("addon")
            if addon:
                label = f"{label} ({addon})"
            status = "" if event.get("status") == "ok" else f" [{event['status']}]"
            self.console.print(f"  {label}: {event['seconds']:.3f}s{status}")

    def write_json(self, path: str | Path | None) -> None:
        if not path:
            return
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"events": self.events}, indent=2) + "\n", encoding="utf-8")
