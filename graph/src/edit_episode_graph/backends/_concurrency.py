"""Per-backend concurrency caps, enforced by `threading.Semaphore`.

Subscription CLIs rate-limit aggressively; `Send`-fan-out can spawn 5+ parallel
invocations. Acquiring before subprocess.run gates the dispatch without
needing CLI-side coordination.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator


class BackendSemaphores:
    def __init__(self, caps: dict[str, int]):
        self._sems: dict[str, threading.Semaphore] = {
            name: threading.Semaphore(n) for name, n in caps.items()
        }

    @contextmanager
    def acquire(self, backend_name: str) -> Iterator[None]:
        sem = self._sems.get(backend_name)
        if sem is None:
            yield
            return
        sem.acquire()
        try:
            yield
        finally:
            sem.release()
