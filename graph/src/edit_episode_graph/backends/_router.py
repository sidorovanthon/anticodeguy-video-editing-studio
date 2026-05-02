"""BackendRouter — failover policy across an ordered backend list.

Spec §7.4 failover rules:
  1. Auth failure       → next backend.
  2. Rate limit         → 30s pause, retry once on same backend; if still
                          rate-limited → next backend.
  3. Schema validation  → retry on same backend up to 2 times (3 attempts
                          total); on third failure → next backend.
  4. Timeout            → next backend.
  5. All exhausted      → raise AllBackendsExhausted.

Telemetry (per-attempt dict) is returned alongside the InvokeResult so the
calling LLMNode can append it to `state["llm_runs"][node_name]`.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ._concurrency import BackendSemaphores
from ._types import (
    AllBackendsExhausted,
    AuthError,
    BackendTimeout,
    InvokeResult,
    NodeRequirements,
    RateLimitError,
    SchemaValidationError,
)

_RATE_LIMIT_BACKOFF_S = 30
_SCHEMA_RETRIES_PER_BACKEND = 2   # → 3 attempts total per backend


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BackendRouter:
    def __init__(self, backends, semaphores: BackendSemaphores):
        self._by_name = {b.name: b for b in backends}
        self._sems = semaphores

    def invoke(
        self,
        req: NodeRequirements,
        task: str,
        *,
        cwd: Path,
        timeout_s: int,
        output_schema: type[BaseModel] | None,
        allowed_tools: list[str] | None = None,
        model_override: str | None = None,
    ) -> tuple[InvokeResult, list[dict[str, Any]]]:
        attempts: list[dict[str, Any]] = []
        preference = req.backends or list(self._by_name.keys())

        for name in preference:
            backend = self._by_name.get(name)
            if backend is None or not backend.supports(req):
                attempts.append({"backend": name, "success": False, "reason": "unsupported", "ts": _now()})
                continue

            schema_failures = 0
            rate_retried = False
            while True:
                t0 = time.monotonic()
                try:
                    with self._sems.acquire(name):
                        res = backend.invoke(
                            task,
                            tier=req.tier,
                            cwd=cwd,
                            timeout_s=timeout_s,
                            output_schema=output_schema,
                            allowed_tools=allowed_tools,
                            model_override=model_override,
                        )
                except AuthError as e:
                    attempts.append({"backend": name, "success": False, "reason": "auth",
                                     "wall_time_s": time.monotonic() - t0, "message": str(e), "ts": _now()})
                    break  # next backend
                except RateLimitError as e:
                    attempts.append({"backend": name, "success": False, "reason": "rate_limit",
                                     "wall_time_s": time.monotonic() - t0, "message": str(e), "ts": _now()})
                    if not rate_retried:
                        rate_retried = True
                        time.sleep(_RATE_LIMIT_BACKOFF_S)
                        continue
                    break
                except BackendTimeout as e:
                    attempts.append({"backend": name, "success": False, "reason": "timeout",
                                     "wall_time_s": time.monotonic() - t0, "message": str(e), "ts": _now()})
                    break
                except SchemaValidationError as e:
                    schema_failures += 1
                    attempts.append({"backend": name, "success": False, "reason": "schema",
                                     "wall_time_s": time.monotonic() - t0, "message": str(e),
                                     "raw_preview": e.raw_text[:200], "ts": _now()})
                    if schema_failures <= _SCHEMA_RETRIES_PER_BACKEND:
                        continue
                    break
                except Exception as e:
                    attempts.append({"backend": name, "success": False, "reason": "other",
                                     "wall_time_s": time.monotonic() - t0, "message": str(e), "ts": _now()})
                    break
                else:
                    attempts.append({"backend": name, "success": True, "model": res.model_used,
                                     "tokens_in": res.tokens_in, "tokens_out": res.tokens_out,
                                     "wall_time_s": res.wall_time_s, "ts": _now()})
                    return res, attempts

        raise AllBackendsExhausted(attempts)
