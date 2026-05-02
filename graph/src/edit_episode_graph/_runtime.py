# graph/src/edit_episode_graph/_runtime.py
"""Process-level singleton for the router.

LangGraph's `langgraph dev` rebuilds the graph on code changes; we want a
single router (with its semaphores and backend instances) per process so the
concurrency caps are honored across all node invocations within that
process. The first call to `get_router()` builds it from `config.yaml`;
subsequent calls return the cache.
"""

from __future__ import annotations

from functools import lru_cache

from .backends._concurrency import BackendSemaphores
from .backends._router import BackendRouter
from .backends.claude import ClaudeCodeBackend
from .backends.codex import CodexBackend
from .config import load_default_config


@lru_cache(maxsize=1)
def get_router() -> BackendRouter:
    cfg = load_default_config()
    backends = [ClaudeCodeBackend(), CodexBackend()]
    sems = BackendSemaphores(cfg.concurrency)
    return BackendRouter(backends, sems)
