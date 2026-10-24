"""Thread-local runtime context: lets the agent's tool call report
progress and results back to the web job that launched it.

Also hosts the DRY_RUN flag used to mock Gemini/Gnani during testing.
"""

from __future__ import annotations

import os
import threading
from typing import Callable

_local = threading.local()


def dry_run() -> bool:
    """True when DRY_RUN is set: mock Gemini + Gnani, skip network media."""
    return os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")


def set_progress(fn: Callable[[str], None] | None) -> None:
    _local.progress = fn


def emit(stage: str) -> None:
    fn = getattr(_local, "progress", None)
    if fn:
        fn(stage)


def set_last_summary(summary: dict | None) -> None:
    _local.last_summary = summary


def get_last_summary() -> dict | None:
    return getattr(_local, "last_summary", None)