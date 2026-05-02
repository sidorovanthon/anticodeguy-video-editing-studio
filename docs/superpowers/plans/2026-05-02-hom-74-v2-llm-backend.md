# HOM-74 v2 — First LLM Node + Backend Abstraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce subprocess-CLI LLM invocation into the LangGraph pipeline via an `LLMBackend` abstraction (Claude Code + Codex), a `BackendRouter` with failover/concurrency policy, YAML config, and the first production LLM node `p3_pre_scan`.

**Architecture:** Backends are subprocess wrappers around authorized CLIs (`claude -p --output-format stream-json`, `codex exec --json`). They share a `LLMBackend` Protocol returning `InvokeResult`. A `BackendRouter` walks an ordered preference list, applying failover rules (auth → next; rate limit → 30s pause + retry once → next; schema fail → ≤2 retries with feedback → next; timeout → next; exhausted → `interrupt()`). Per-backend `threading.Semaphore` instances cap concurrency. Per-node tier/preference overrides come from `graph/config.yaml` (glob-aware). LLM nodes are built from a small `LLMNode` base that renders a Jinja2 task descriptor, dispatches via the router, validates against a Pydantic schema, re-emits CLI tool-call events through `dispatch_custom_event()`, and appends per-call telemetry to `state["llm_runs"]`. `p3_pre_scan` slots into the v1 graph between `preflight_canon` and `halt_llm_boundary`: if `takes_packed.md` exists (and `final.mp4` does not), pre-scan runs and writes `state["edit"]["pre_scan"]["slips"]`; otherwise it is bypassed. Tests run end-to-end via subprocess-mocking — no real CLI calls in CI.

**Tech Stack:** Python 3.11+, LangGraph 0.2.x, Pydantic 2, Jinja2, PyYAML, pytest. Subprocess CLIs: `claude` (Claude Code), `codex` (ChatGPT). No API SDKs.

---

## File Structure

**New files (all paths relative to `graph/`):**
- `src/edit_episode_graph/backends/_types.py` — shared dataclasses/typed dicts: `BackendCapabilities`, `NodeRequirements`, `InvokeResult`, `ToolCall`, exception taxonomy (`AuthError`, `RateLimitError`, `SchemaValidationError`, `BackendTimeout`, `AllBackendsExhausted`).
- `src/edit_episode_graph/backends/_concurrency.py` — `BackendSemaphores` (one `threading.Semaphore` per backend name).
- `src/edit_episode_graph/backends/_stream_parsers.py` — `parse_claude_stream_json(stdout) -> (assistant_text, tool_calls)`; `parse_codex_json(stdout) -> (assistant_text, tool_calls)`. Pure functions; the only place stdout-shape knowledge lives.
- `src/edit_episode_graph/backends/_schema_extract.py` — `extract_structured(raw_text, schema)` — strips markdown fences and `json` blocks, returns parsed Pydantic instance or raises `SchemaValidationError`.
- `src/edit_episode_graph/config.py` — `load_config(path) -> RouterConfig` (PyYAML); `RouterConfig.resolve_node(node_name) -> NodeConfig` with glob-pattern matching (`fnmatch`).
- `src/edit_episode_graph/nodes/_llm.py` — `LLMNode` callable wrapping Jinja2 brief render → router → schema validate → state-update with `llm_runs` append.
- `src/edit_episode_graph/nodes/p3_pre_scan.py` — concrete first LLM node.
- `src/edit_episode_graph/briefs/p3_pre_scan.j2` — Jinja2 task descriptor (≤25 lines; refs `~/.claude/skills/video-use/SKILL.md` §"The process" Step 2).
- `src/edit_episode_graph/schemas/__init__.py` — package marker.
- `src/edit_episode_graph/schemas/p3_pre_scan.py` — Pydantic models `Slip`, `PreScanReport`.
- `graph/config.yaml` — global preference + per-node overrides (initially `p3_pre_scan: cheap, ["claude","codex"]`).
- `graph/tests/__init__.py`, `graph/tests/conftest.py` — pytest scaffolding.
- `graph/tests/test_stream_parsers.py`
- `graph/tests/test_schema_extract.py`
- `graph/tests/test_config.py`
- `graph/tests/test_concurrency.py`
- `graph/tests/test_router.py`
- `graph/tests/test_llm_node.py`
- `graph/tests/test_p3_pre_scan_routing.py`
- `graph/tests/fixtures/claude_stream_ok.jsonl` — recorded `--output-format stream-json` lines for one tool-call + final assistant message.
- `graph/tests/fixtures/codex_json_ok.json` — recorded `codex exec --json` envelope.

**Modified files:**
- `src/edit_episode_graph/state.py` — add `EditState`, `PreScanState`, `LLMRunRecord`, `llm_runs` (append-only), `edit` namespace.
- `src/edit_episode_graph/backends/_base.py` — populate `LLMBackend` Protocol + import re-exports.
- `src/edit_episode_graph/backends/_router.py` — implement `BackendRouter` (failover policy).
- `src/edit_episode_graph/backends/claude.py` — full `ClaudeCodeBackend`.
- `src/edit_episode_graph/backends/codex.py` — full `CodexBackend`.
- `src/edit_episode_graph/backends/gemini.py` — left as skeleton (out of v2 scope per spec §8 v2; only `claude` + `codex` are required).
- `src/edit_episode_graph/nodes/_routing.py` — extend `route_after_preflight` with a `p3_pre_scan` branch.
- `src/edit_episode_graph/graph.py` — add `p3_pre_scan` node + edge to `halt_llm_boundary`.
- `src/edit_episode_graph/nodes/halt_llm_boundary.py` — adjust notice copy to reflect that pre-scan may have run.
- `graph/pyproject.toml` — add `jinja2`, `pyyaml`, `pytest`, `pytest-asyncio` (dev).

---

### Task 1: Test scaffolding + new dependencies

**Files:**
- Modify: `graph/pyproject.toml`
- Create: `graph/tests/__init__.py`
- Create: `graph/tests/conftest.py`

- [ ] **Step 1: Update `pyproject.toml`**

Add to `[project] dependencies`:

```toml
dependencies = [
    "langgraph>=0.2.60",
    "langgraph-checkpoint-sqlite>=2.0",
    "pydantic>=2.7",
    "jinja2>=3.1",
    "pyyaml>=6.0",
]
```

Add to `[project.optional-dependencies]`:

```toml
dev = [
    "langgraph-cli[inmem]>=0.1.55",
    "pytest>=8.0",
]
```

- [ ] **Step 2: Create empty `graph/tests/__init__.py`**

```python
```

- [ ] **Step 3: Create `graph/tests/conftest.py`**

```python
"""Shared pytest fixtures for the edit-episode-graph tests."""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
```

- [ ] **Step 4: Reinstall in editable mode + verify pytest collects**

Run: `cd graph && .venv/Scripts/pip install -e ".[dev]" && .venv/Scripts/pytest --collect-only -q`
Expected: exit 0; "no tests ran" (no test files yet).

- [ ] **Step 5: Commit**

```bash
git add graph/pyproject.toml graph/tests/__init__.py graph/tests/conftest.py
git commit -m "v2(graph): add pytest scaffolding + jinja2/pyyaml deps (HOM-74)"
```

---

### Task 2: Backend type primitives + exception taxonomy

**Files:**
- Create: `graph/src/edit_episode_graph/backends/_types.py`
- Create: `graph/tests/test_types.py`

- [ ] **Step 1: Write the failing test**

```python
# graph/tests/test_types.py
from edit_episode_graph.backends._types import (
    AllBackendsExhausted,
    AuthError,
    BackendCapabilities,
    BackendTimeout,
    InvokeResult,
    NodeRequirements,
    RateLimitError,
    SchemaValidationError,
    ToolCall,
)


def test_capabilities_defaults():
    caps = BackendCapabilities(name="claude", has_tools=True, supports_streaming=True, max_concurrent=2)
    assert caps.name == "claude" and caps.max_concurrent == 2


def test_node_requirements_supports():
    req = NodeRequirements(tier="cheap", needs_tools=True, backends=["claude", "codex"])
    caps = BackendCapabilities(name="claude", has_tools=True, supports_streaming=True, max_concurrent=2)
    assert req.satisfied_by(caps) is True
    no_tools = BackendCapabilities(name="x", has_tools=False, supports_streaming=False, max_concurrent=1)
    assert req.satisfied_by(no_tools) is False


def test_invoke_result_round_trip():
    r = InvokeResult(
        raw_text="hi",
        structured=None,
        tokens_in=10,
        tokens_out=2,
        wall_time_s=0.5,
        model_used="claude-sonnet-4-6",
        backend_used="claude",
        tool_calls=[ToolCall(name="Read", input={"path": "/x"}, output_preview="...")],
    )
    assert r.tool_calls[0].name == "Read"


def test_exception_hierarchy():
    assert issubclass(AuthError, Exception)
    assert issubclass(RateLimitError, Exception)
    assert issubclass(SchemaValidationError, Exception)
    assert issubclass(BackendTimeout, Exception)
    assert issubclass(AllBackendsExhausted, Exception)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd graph && .venv/Scripts/pytest tests/test_types.py -v`
Expected: ImportError (`_types` does not exist).

- [ ] **Step 3: Implement `_types.py`**

```python
# graph/src/edit_episode_graph/backends/_types.py
"""Backend-layer shared types and exception taxonomy.

All backends speak the same language to nodes via these primitives. Adding a
new field here is a breaking change for every backend implementation — keep
the surface narrow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Tier = Literal["cheap", "smart"]


@dataclass(frozen=True)
class BackendCapabilities:
    name: str
    has_tools: bool
    supports_streaming: bool
    max_concurrent: int


@dataclass(frozen=True)
class NodeRequirements:
    tier: Tier
    needs_tools: bool
    backends: list[str]   # preference order; empty = router default

    def satisfied_by(self, caps: BackendCapabilities) -> bool:
        if self.needs_tools and not caps.has_tools:
            return False
        return True


@dataclass(frozen=True)
class ToolCall:
    name: str
    input: dict[str, Any]
    output_preview: str   # truncated; full output is in stream log


@dataclass
class InvokeResult:
    raw_text: str
    structured: Any | None
    tokens_in: int | None
    tokens_out: int | None
    wall_time_s: float
    model_used: str
    backend_used: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class BackendError(Exception):
    """Base for all backend-layer errors."""


class AuthError(BackendError):
    """CLI reports unauthenticated / expired session."""


class RateLimitError(BackendError):
    """CLI reports rate-limit / quota exhausted."""


class BackendTimeout(BackendError):
    """Subprocess exceeded `timeout_s`."""


class SchemaValidationError(BackendError):
    """Final assistant text could not be parsed into the requested Pydantic schema."""

    def __init__(self, message: str, raw_text: str):
        super().__init__(message)
        self.raw_text = raw_text


class AllBackendsExhausted(BackendError):
    """Router tried every backend in the preference list and none succeeded."""

    def __init__(self, attempts: list[dict[str, Any]]):
        super().__init__(f"All backends exhausted across {len(attempts)} attempt(s).")
        self.attempts = attempts
```

- [ ] **Step 4: Verify tests pass**

Run: `cd graph && .venv/Scripts/pytest tests/test_types.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add graph/src/edit_episode_graph/backends/_types.py graph/tests/test_types.py
git commit -m "v2(graph): backend type primitives + exception taxonomy (HOM-74)"
```

---

### Task 3: Stream-JSON parsers (Claude + Codex)

**Files:**
- Create: `graph/src/edit_episode_graph/backends/_stream_parsers.py`
- Create: `graph/tests/fixtures/claude_stream_ok.jsonl`
- Create: `graph/tests/fixtures/codex_json_ok.json`
- Create: `graph/tests/test_stream_parsers.py`

- [ ] **Step 1: Create `claude_stream_ok.jsonl` fixture**

The Claude Code `-p --output-format stream-json` emits one JSON object per line. Minimal realistic shape (verified against Claude Code 2.0+ output):

```jsonl
{"type":"system","subtype":"init","session_id":"abc","model":"claude-sonnet-4-6","tools":["Read","Grep"]}
{"type":"assistant","message":{"content":[{"type":"text","text":"Reading the file."},{"type":"tool_use","id":"t1","name":"Read","input":{"file_path":"/tmp/takes_packed.md"}}]}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"# Take 1\nHello world."}]}}
{"type":"assistant","message":{"content":[{"type":"text","text":"```json\n{\"slips\": [{\"quote\": \"hello world\", \"take_index\": 1, \"reason\": \"placeholder\"}]}\n```"}]}}
{"type":"result","subtype":"success","session_id":"abc","total_cost_usd":0.001,"usage":{"input_tokens":120,"output_tokens":40},"result":"```json\n{\"slips\": [{\"quote\": \"hello world\", \"take_index\": 1, \"reason\": \"placeholder\"}]}\n```"}
```

- [ ] **Step 2: Create `codex_json_ok.json` fixture**

The `codex exec --json` envelope is a single JSON object (not stream). Minimal shape:

```json
{
  "model": "gpt-5-mini",
  "messages": [
    {"role": "assistant", "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "Read", "arguments": "{\"file_path\": \"/tmp/takes_packed.md\"}"}}]},
    {"role": "tool", "tool_call_id": "t1", "content": "# Take 1\nHello world."},
    {"role": "assistant", "content": "```json\n{\"slips\": [{\"quote\": \"hello world\", \"take_index\": 1, \"reason\": \"placeholder\"}]}\n```"}
  ],
  "usage": {"input_tokens": 100, "output_tokens": 30}
}
```

- [ ] **Step 3: Write the failing test**

```python
# graph/tests/test_stream_parsers.py
from edit_episode_graph.backends._stream_parsers import (
    parse_claude_stream_json,
    parse_codex_json,
)


def test_parse_claude_stream_json(fixtures_dir):
    raw = (fixtures_dir / "claude_stream_ok.jsonl").read_text(encoding="utf-8")
    parsed = parse_claude_stream_json(raw)
    assert "slips" in parsed.assistant_text
    assert parsed.tokens_in == 120
    assert parsed.tokens_out == 40
    assert parsed.model_used == "claude-sonnet-4-6"
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].name == "Read"
    assert parsed.tool_calls[0].input == {"file_path": "/tmp/takes_packed.md"}


def test_parse_codex_json(fixtures_dir):
    raw = (fixtures_dir / "codex_json_ok.json").read_text(encoding="utf-8")
    parsed = parse_codex_json(raw)
    assert "slips" in parsed.assistant_text
    assert parsed.tokens_in == 100
    assert parsed.tokens_out == 30
    assert parsed.model_used == "gpt-5-mini"
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].name == "Read"


def test_claude_stream_garbage_lines_skipped():
    raw = "not-json\n" + '{"type":"result","subtype":"success","session_id":"x","model":"claude-sonnet-4-6","usage":{"input_tokens":1,"output_tokens":1},"result":"hi"}\n'
    parsed = parse_claude_stream_json(raw)
    assert parsed.assistant_text == "hi"
```

- [ ] **Step 4: Run to verify failure**

Run: `cd graph && .venv/Scripts/pytest tests/test_stream_parsers.py -v`
Expected: ImportError.

- [ ] **Step 5: Implement `_stream_parsers.py`**

```python
# graph/src/edit_episode_graph/backends/_stream_parsers.py
"""Pure parsers for CLI stdout shapes.

These are the ONLY place that knows the exact wire format of each CLI's JSON
output. Backends call them and treat the result uniformly. Garbage / partial
lines are skipped silently — CLIs occasionally emit progress noise that isn't
load-bearing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ._types import ToolCall


@dataclass
class ParsedStream:
    assistant_text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int | None = None
    tokens_out: int | None = None
    model_used: str = ""


def parse_claude_stream_json(stdout: str) -> ParsedStream:
    """Parse `claude -p --output-format stream-json` stdout."""
    out = ParsedStream(assistant_text="")
    pending_tools: dict[str, ToolCall] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        otype = obj.get("type")
        if otype == "system" and obj.get("subtype") == "init":
            out.model_used = obj.get("model", out.model_used)
        elif otype == "assistant":
            for block in (obj.get("message") or {}).get("content") or []:
                if block.get("type") == "tool_use":
                    tc = ToolCall(
                        name=block.get("name", ""),
                        input=block.get("input") or {},
                        output_preview="",
                    )
                    pending_tools[block.get("id", "")] = tc
                    out.tool_calls.append(tc)
        elif otype == "user":
            for block in (obj.get("message") or {}).get("content") or []:
                if block.get("type") == "tool_result":
                    tc = pending_tools.get(block.get("tool_use_id", ""))
                    if tc is not None:
                        content = block.get("content") or ""
                        if isinstance(content, list):
                            content = " ".join(str(c) for c in content)
                        idx = out.tool_calls.index(tc)
                        out.tool_calls[idx] = ToolCall(
                            name=tc.name,
                            input=tc.input,
                            output_preview=str(content)[:200],
                        )
        elif otype == "result":
            out.assistant_text = obj.get("result", out.assistant_text) or ""
            usage = obj.get("usage") or {}
            out.tokens_in = usage.get("input_tokens")
            out.tokens_out = usage.get("output_tokens")
            if "model" in obj:
                out.model_used = obj["model"]
    return out


def parse_codex_json(stdout: str) -> ParsedStream:
    """Parse `codex exec --json` stdout (single JSON envelope)."""
    obj = json.loads(stdout)
    out = ParsedStream(
        assistant_text="",
        model_used=obj.get("model", ""),
    )
    usage = obj.get("usage") or {}
    out.tokens_in = usage.get("input_tokens")
    out.tokens_out = usage.get("output_tokens")
    pending_tools: dict[str, ToolCall] = {}
    for msg in obj.get("messages") or []:
        role = msg.get("role")
        if role == "assistant":
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                try:
                    inp = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    inp = {"_raw": fn.get("arguments", "")}
                call = ToolCall(name=fn.get("name", ""), input=inp, output_preview="")
                pending_tools[tc.get("id", "")] = call
                out.tool_calls.append(call)
            content = msg.get("content")
            if isinstance(content, str) and content:
                out.assistant_text = content
        elif role == "tool":
            tc = pending_tools.get(msg.get("tool_call_id", ""))
            if tc is not None:
                idx = out.tool_calls.index(tc)
                out.tool_calls[idx] = ToolCall(
                    name=tc.name,
                    input=tc.input,
                    output_preview=str(msg.get("content", ""))[:200],
                )
    return out
```

- [ ] **Step 6: Verify tests pass**

Run: `cd graph && .venv/Scripts/pytest tests/test_stream_parsers.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add graph/src/edit_episode_graph/backends/_stream_parsers.py graph/tests/fixtures graph/tests/test_stream_parsers.py
git commit -m "v2(graph): pure stream-json parsers for claude + codex (HOM-74)"
```

---

### Task 4: Schema-extractor (markdown-fence stripping + Pydantic validate)

**Files:**
- Create: `graph/src/edit_episode_graph/backends/_schema_extract.py`
- Create: `graph/tests/test_schema_extract.py`

- [ ] **Step 1: Write the failing test**

```python
# graph/tests/test_schema_extract.py
import pytest
from pydantic import BaseModel

from edit_episode_graph.backends._schema_extract import extract_structured
from edit_episode_graph.backends._types import SchemaValidationError


class _Demo(BaseModel):
    n: int
    label: str


def test_extracts_from_fenced_block():
    raw = "Here is the result:\n```json\n{\"n\": 7, \"label\": \"ok\"}\n```\nDone."
    out = extract_structured(raw, _Demo)
    assert out.n == 7 and out.label == "ok"


def test_extracts_bare_json():
    raw = '{"n": 1, "label": "bare"}'
    out = extract_structured(raw, _Demo)
    assert out.label == "bare"


def test_validation_error_includes_raw():
    raw = '```json\n{"n": "not-a-number", "label": 1}\n```'
    with pytest.raises(SchemaValidationError) as exc:
        extract_structured(raw, _Demo)
    assert exc.value.raw_text == raw


def test_no_json_at_all_raises():
    with pytest.raises(SchemaValidationError):
        extract_structured("just prose", _Demo)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd graph && .venv/Scripts/pytest tests/test_schema_extract.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `_schema_extract.py`**

```python
# graph/src/edit_episode_graph/backends/_schema_extract.py
"""Extract a Pydantic model from free-form LLM assistant text.

Handles the common shapes: (a) a ```json ... ``` fenced block, (b) a ``` ... ```
unfenced block, (c) bare JSON. Raises SchemaValidationError on any failure
with the raw text attached so the router can surface it as feedback on retry.
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ._types import SchemaValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
_BARE_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


def extract_structured(raw_text: str, schema: type[T]) -> T:
    candidates: list[str] = []
    candidates.extend(m.group(1) for m in _FENCE_RE.finditer(raw_text))
    if not candidates:
        m = _BARE_RE.search(raw_text)
        if m:
            candidates.append(m.group(1))

    if not candidates:
        raise SchemaValidationError("no JSON object/array found in assistant text", raw_text)

    last_err: Exception | None = None
    for cand in candidates:
        try:
            data = json.loads(cand)
        except json.JSONDecodeError as e:
            last_err = e
            continue
        try:
            return schema.model_validate(data)
        except ValidationError as e:
            last_err = e
            continue
    raise SchemaValidationError(f"schema validation failed: {last_err}", raw_text)
```

- [ ] **Step 4: Verify tests pass**

Run: `cd graph && .venv/Scripts/pytest tests/test_schema_extract.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add graph/src/edit_episode_graph/backends/_schema_extract.py graph/tests/test_schema_extract.py
git commit -m "v2(graph): schema extractor with fence-stripping + validation error (HOM-74)"
```

---

### Task 5: LLMBackend Protocol + populate `_base.py`

**Files:**
- Modify: `graph/src/edit_episode_graph/backends/_base.py`

- [ ] **Step 1: Replace `_base.py` with the Protocol**

```python
# graph/src/edit_episode_graph/backends/_base.py
"""LLMBackend Protocol — the single contract every backend implements.

Spec §7.1. Nodes never import a concrete backend; they go through
`BackendRouter.invoke(node_requirements, task, ...)`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from ._types import (
    BackendCapabilities,
    InvokeResult,
    NodeRequirements,
    Tier,
)


@runtime_checkable
class LLMBackend(Protocol):
    name: str
    capabilities: BackendCapabilities

    def supports(self, req: NodeRequirements) -> bool: ...

    def invoke(
        self,
        task: str,
        *,
        tier: Tier,
        cwd: Path,
        timeout_s: int,
        output_schema: type[BaseModel] | None,
        allowed_tools: list[str] | None = None,
        model_override: str | None = None,
    ) -> InvokeResult: ...


__all__ = ["LLMBackend"]
```

- [ ] **Step 2: Smoke-import**

Run: `cd graph && .venv/Scripts/python -c "from edit_episode_graph.backends._base import LLMBackend; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add graph/src/edit_episode_graph/backends/_base.py
git commit -m "v2(graph): LLMBackend Protocol (HOM-74)"
```

---

### Task 6: Concurrency semaphores

**Files:**
- Create: `graph/src/edit_episode_graph/backends/_concurrency.py`
- Create: `graph/tests/test_concurrency.py`

- [ ] **Step 1: Write the failing test**

```python
# graph/tests/test_concurrency.py
import threading
import time

from edit_episode_graph.backends._concurrency import BackendSemaphores


def test_caps_concurrency():
    sems = BackendSemaphores({"claude": 2})
    active = []
    peak = [0]
    lock = threading.Lock()

    def worker():
        with sems.acquire("claude"):
            with lock:
                active.append(1)
                peak[0] = max(peak[0], len(active))
            time.sleep(0.05)
            with lock:
                active.pop()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak[0] == 2


def test_unknown_backend_unbounded():
    sems = BackendSemaphores({"claude": 2})
    with sems.acquire("never-heard-of-it"):
        pass  # no error
```

- [ ] **Step 2: Run to verify failure**

Run: `cd graph && .venv/Scripts/pytest tests/test_concurrency.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `_concurrency.py`**

```python
# graph/src/edit_episode_graph/backends/_concurrency.py
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
```

- [ ] **Step 4: Verify tests pass**

Run: `cd graph && .venv/Scripts/pytest tests/test_concurrency.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add graph/src/edit_episode_graph/backends/_concurrency.py graph/tests/test_concurrency.py
git commit -m "v2(graph): per-backend concurrency semaphores (HOM-74)"
```

---

### Task 7: Config loader (`config.yaml` + glob overrides)

**Files:**
- Create: `graph/src/edit_episode_graph/config.py`
- Create: `graph/config.yaml`
- Create: `graph/tests/test_config.py`

- [ ] **Step 1: Create `graph/config.yaml`**

```yaml
# graph/config.yaml — read by build_graph() at startup. Restart `langgraph dev`
# to pick up changes. Glob patterns supported in node_overrides keys (fnmatch).

backend_preference: ["claude", "codex"]

concurrency:
  claude: 2
  codex: 2
  gemini: 3

defaults:
  timeout_s: 120

node_overrides:
  p3_pre_scan:
    tier: cheap
    backend_preference: ["claude", "codex"]
    timeout_s: 90
    # Real-CLI smoke test (Task 18) routes through Haiku for minimal subscription
    # spend. Remove or change to a Sonnet/Opus ID for production use.
    model: claude-haiku-4-5-20251001
```

- [ ] **Step 2: Write the failing test**

```python
# graph/tests/test_config.py
from pathlib import Path

from edit_episode_graph.config import load_config


def test_loads_yaml(tmp_path):
    cfg_text = """
backend_preference: ["claude", "codex"]
concurrency: {claude: 2, codex: 2, gemini: 3}
defaults: {timeout_s: 120}
node_overrides:
  p3_pre_scan: {tier: cheap, backend_preference: [claude], timeout_s: 90}
  "p4_beat_*": {tier: smart, backend_preference: [claude]}
"""
    p = tmp_path / "c.yaml"
    p.write_text(cfg_text, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.backend_preference == ["claude", "codex"]
    assert cfg.concurrency == {"claude": 2, "codex": 2, "gemini": 3}


def test_node_resolve_explicit():
    from edit_episode_graph.config import RouterConfig
    cfg = RouterConfig(
        backend_preference=["claude"],
        concurrency={"claude": 2},
        defaults={"timeout_s": 100},
        node_overrides={"p3_pre_scan": {"tier": "cheap", "backend_preference": ["codex"], "timeout_s": 30}},
    )
    n = cfg.resolve_node("p3_pre_scan")
    assert n.tier == "cheap"
    assert n.backend_preference == ["codex"]
    assert n.timeout_s == 30


def test_node_resolve_glob_match():
    from edit_episode_graph.config import RouterConfig
    cfg = RouterConfig(
        backend_preference=["claude"],
        concurrency={},
        defaults={"timeout_s": 100},
        node_overrides={"p4_beat_*": {"tier": "smart", "backend_preference": ["claude"]}},
    )
    n = cfg.resolve_node("p4_beat_one")
    assert n.tier == "smart"


def test_node_resolve_falls_back_to_defaults():
    from edit_episode_graph.config import RouterConfig
    cfg = RouterConfig(
        backend_preference=["claude", "codex"],
        concurrency={},
        defaults={"timeout_s": 99},
        node_overrides={},
    )
    n = cfg.resolve_node("anything")
    assert n.tier == "cheap"
    assert n.backend_preference == ["claude", "codex"]
    assert n.timeout_s == 99
    assert n.model is None


def test_node_resolve_model_override():
    from edit_episode_graph.config import RouterConfig
    cfg = RouterConfig(
        backend_preference=["claude"], concurrency={}, defaults={"timeout_s": 60},
        node_overrides={"p3_pre_scan": {"model": "claude-haiku-4-5-20251001"}},
    )
    assert cfg.resolve_node("p3_pre_scan").model == "claude-haiku-4-5-20251001"
```

- [ ] **Step 3: Run to verify failure**

Run: `cd graph && .venv/Scripts/pytest tests/test_config.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `config.py`**

```python
# graph/src/edit_episode_graph/config.py
"""YAML config loader for backend preferences + per-node overrides.

Schema is intentionally permissive (plain dicts, no Pydantic) so tweaking the
file is low-friction. `RouterConfig.resolve_node(name)` returns the merged
NodeConfig for a given node name, applying explicit-key match first, then the
first matching glob.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml


@dataclass
class NodeConfig:
    tier: str
    backend_preference: list[str]
    timeout_s: int
    model: str | None = None   # optional override; bypasses backend's tier→model map


@dataclass
class RouterConfig:
    backend_preference: list[str]
    concurrency: dict[str, int]
    defaults: dict[str, Any]
    node_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    def resolve_node(self, name: str) -> NodeConfig:
        override = self.node_overrides.get(name)
        if override is None:
            for pat, val in self.node_overrides.items():
                if fnmatch(name, pat):
                    override = val
                    break
        override = override or {}
        return NodeConfig(
            tier=override.get("tier", "cheap"),
            backend_preference=override.get("backend_preference", self.backend_preference),
            timeout_s=int(override.get("timeout_s", self.defaults.get("timeout_s", 120))),
            model=override.get("model"),
        )


def load_config(path: Path) -> RouterConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return RouterConfig(
        backend_preference=list(raw.get("backend_preference") or []),
        concurrency=dict(raw.get("concurrency") or {}),
        defaults=dict(raw.get("defaults") or {}),
        node_overrides=dict(raw.get("node_overrides") or {}),
    )


_REPO_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def load_default_config() -> RouterConfig:
    """Loads `graph/config.yaml`. Returns a permissive default if file is absent."""
    if _REPO_CONFIG_PATH.exists():
        return load_config(_REPO_CONFIG_PATH)
    return RouterConfig(
        backend_preference=["claude", "codex"],
        concurrency={"claude": 2, "codex": 2, "gemini": 3},
        defaults={"timeout_s": 120},
        node_overrides={},
    )
```

- [ ] **Step 5: Verify tests pass**

Run: `cd graph && .venv/Scripts/pytest tests/test_config.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add graph/src/edit_episode_graph/config.py graph/config.yaml graph/tests/test_config.py
git commit -m "v2(graph): YAML config loader with glob-aware per-node overrides (HOM-74)"
```

---

### Task 8: ClaudeCodeBackend (full implementation)

**Files:**
- Modify: `graph/src/edit_episode_graph/backends/claude.py`
- Create: `graph/tests/test_claude_backend.py`

- [ ] **Step 1: Write the failing test**

```python
# graph/tests/test_claude_backend.py
"""ClaudeCodeBackend tests — subprocess is monkey-patched.

We verify: command shape, stdout parsing, schema extraction, exception
mapping for stderr signals (auth, rate limit, timeout). No real CLI is
invoked.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from edit_episode_graph.backends._types import (
    AuthError,
    BackendTimeout,
    NodeRequirements,
    RateLimitError,
    SchemaValidationError,
)
from edit_episode_graph.backends.claude import ClaudeCodeBackend


class _Slip(BaseModel):
    quote: str
    take_index: int | None = None
    reason: str


class _Report(BaseModel):
    slips: list[_Slip]


def _make_subprocess_run(stdout: str = "", stderr: str = "", returncode: int = 0):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)
    return fake_run


def test_invoke_parses_structured(monkeypatch, fixtures_dir):
    raw = (fixtures_dir / "claude_stream_ok.jsonl").read_text(encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", _make_subprocess_run(stdout=raw))
    b = ClaudeCodeBackend()
    res = b.invoke(
        "do thing",
        tier="cheap",
        cwd=Path.cwd(),
        timeout_s=60,
        output_schema=_Report,
    )
    assert res.backend_used == "claude"
    assert res.model_used == "claude-sonnet-4-6"
    assert isinstance(res.structured, _Report)
    assert res.structured.slips[0].quote == "hello world"
    assert len(res.tool_calls) == 1


def test_invoke_command_shape(monkeypatch, fixtures_dir):
    raw = (fixtures_dir / "claude_stream_ok.jsonl").read_text(encoding="utf-8")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(stdout=raw, stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    b = ClaudeCodeBackend()
    b.invoke("hello", tier="smart", cwd=Path.cwd(), timeout_s=30, output_schema=None)

    cmd = captured["cmd"]
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
    assert "-p" in cmd_str
    assert "stream-json" in cmd_str
    assert "claude-opus-4-7" in cmd_str   # smart tier
    assert captured["kwargs"]["timeout"] == 30


def test_auth_failure_raises(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        _make_subprocess_run(stderr="Error: not authenticated. Run `claude login`.", returncode=1),
    )
    b = ClaudeCodeBackend()
    with pytest.raises(AuthError):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=10, output_schema=None)


def test_rate_limit_raises(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        _make_subprocess_run(stderr="Error: rate limit reached, retry in 60s.", returncode=1),
    )
    b = ClaudeCodeBackend()
    with pytest.raises(RateLimitError):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=10, output_schema=None)


def test_timeout_raises(monkeypatch):
    def boom(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 0))
    monkeypatch.setattr(subprocess, "run", boom)
    b = ClaudeCodeBackend()
    with pytest.raises(BackendTimeout):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=1, output_schema=None)


def test_schema_failure_raises(monkeypatch):
    bad = '{"type":"result","subtype":"success","model":"claude-sonnet-4-6","usage":{"input_tokens":1,"output_tokens":1},"result":"no json here"}\n'
    monkeypatch.setattr(subprocess, "run", _make_subprocess_run(stdout=bad))
    b = ClaudeCodeBackend()
    with pytest.raises(SchemaValidationError):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=10, output_schema=_Report)


def test_supports_requires_tools_capability():
    b = ClaudeCodeBackend()
    assert b.supports(NodeRequirements(tier="cheap", needs_tools=True, backends=["claude"]))
    assert b.supports(NodeRequirements(tier="cheap", needs_tools=False, backends=[]))
```

- [ ] **Step 2: Run to verify failure**

Run: `cd graph && .venv/Scripts/pytest tests/test_claude_backend.py -v`
Expected: ImportError / NotImplementedError.

- [ ] **Step 3: Implement `claude.py`**

```python
# graph/src/edit_episode_graph/backends/claude.py
"""ClaudeCodeBackend — `claude -p "<task>" --output-format stream-json --model <id>`.

Spec §7.2. Subscription auth only.

Windows note (§7.7 + memory `feedback_bundled_helper_path.md`): `claude.exe`
on Windows is a `.cmd` shim. We resolve it via `shutil.which("claude")` which
returns the absolute path the OS will actually exec; Python's subprocess can
launch a `.cmd` from an absolute path without `shell=True` on modern Windows
Python (3.11+).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel

from ._schema_extract import extract_structured
from ._stream_parsers import parse_claude_stream_json
from ._types import (
    AuthError,
    BackendCapabilities,
    BackendTimeout,
    InvokeResult,
    NodeRequirements,
    RateLimitError,
    Tier,
)

_MODEL_BY_TIER: dict[str, str] = {
    "cheap": "claude-sonnet-4-6",
    "smart": "claude-opus-4-7",
}

_AUTH_SIGNALS = ("not authenticated", "claude login", "unauthorized", "auth", "session expired")
_RATE_SIGNALS = ("rate limit", "quota", "too many requests")


class ClaudeCodeBackend:
    name = "claude"
    capabilities = BackendCapabilities(
        name="claude", has_tools=True, supports_streaming=True, max_concurrent=2,
    )

    def __init__(self, executable: str | None = None):
        self._executable = executable or shutil.which("claude") or "claude"

    def supports(self, req: NodeRequirements) -> bool:
        return self.capabilities.has_tools or not req.needs_tools

    def invoke(
        self,
        task: str,
        *,
        tier: Tier,
        cwd: Path,
        timeout_s: int,
        output_schema: type[BaseModel] | None,
        allowed_tools: list[str] | None = None,
        model_override: str | None = None,
    ) -> InvokeResult:
        model = model_override or _MODEL_BY_TIER[tier]
        cmd = [
            self._executable,
            "-p", task,
            "--output-format", "stream-json",
            "--verbose",
            "--model", model,
        ]
        if allowed_tools:
            cmd += ["--allowed-tools", ",".join(allowed_tools)]

        t0 = time.monotonic()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(cwd), timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            raise BackendTimeout(f"claude exceeded {timeout_s}s") from e
        wall = time.monotonic() - t0

        stderr_lc = (result.stderr or "").lower()
        if result.returncode != 0:
            if any(sig in stderr_lc for sig in _AUTH_SIGNALS):
                raise AuthError(result.stderr.strip() or "claude auth failed")
            if any(sig in stderr_lc for sig in _RATE_SIGNALS):
                raise RateLimitError(result.stderr.strip() or "claude rate limited")
            # generic non-zero — surface as auth-or-other; let router retry
            raise RuntimeError(f"claude exit {result.returncode}: {result.stderr.strip()}")

        parsed = parse_claude_stream_json(result.stdout)
        structured = None
        if output_schema is not None:
            structured = extract_structured(parsed.assistant_text, output_schema)

        return InvokeResult(
            raw_text=parsed.assistant_text,
            structured=structured,
            tokens_in=parsed.tokens_in,
            tokens_out=parsed.tokens_out,
            wall_time_s=wall,
            model_used=parsed.model_used or model,
            backend_used=self.name,
            tool_calls=parsed.tool_calls,
        )
```

- [ ] **Step 4: Verify tests pass**

Run: `cd graph && .venv/Scripts/pytest tests/test_claude_backend.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add graph/src/edit_episode_graph/backends/claude.py graph/tests/test_claude_backend.py
git commit -m "v2(graph): ClaudeCodeBackend with stream-json parse + error mapping (HOM-74)"
```

---

### Task 9: CodexBackend (full implementation)

**Files:**
- Modify: `graph/src/edit_episode_graph/backends/codex.py`
- Create: `graph/tests/test_codex_backend.py`

- [ ] **Step 1: Write the failing test**

```python
# graph/tests/test_codex_backend.py
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from edit_episode_graph.backends._types import AuthError, NodeRequirements, RateLimitError
from edit_episode_graph.backends.codex import CodexBackend


class _R(BaseModel):
    slips: list[dict]


def _fake(stdout="", stderr="", rc=0):
    return lambda cmd, **kw: SimpleNamespace(stdout=stdout, stderr=stderr, returncode=rc)


def test_invoke_parses(fixtures_dir, monkeypatch):
    raw = (fixtures_dir / "codex_json_ok.json").read_text(encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", _fake(stdout=raw))
    b = CodexBackend()
    res = b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=30, output_schema=_R)
    assert res.backend_used == "codex"
    assert res.model_used == "gpt-5-mini"
    assert res.structured is not None


def test_command_shape(monkeypatch, fixtures_dir):
    raw = (fixtures_dir / "codex_json_ok.json").read_text(encoding="utf-8")
    captured = {}

    def fake(cmd, **kw):
        captured["cmd"] = cmd
        return SimpleNamespace(stdout=raw, stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake)
    b = CodexBackend()
    b.invoke("hi", tier="smart", cwd=Path.cwd(), timeout_s=30, output_schema=None)
    cmd_str = " ".join(captured["cmd"])
    assert "exec" in cmd_str
    assert "--json" in cmd_str
    assert "gpt-5" in cmd_str


def test_auth_error(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake(stderr="please run `codex login`", rc=1))
    b = CodexBackend()
    with pytest.raises(AuthError):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=10, output_schema=None)


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake(stderr="rate limit hit", rc=1))
    b = CodexBackend()
    with pytest.raises(RateLimitError):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=10, output_schema=None)


def test_supports():
    assert CodexBackend().supports(NodeRequirements(tier="cheap", needs_tools=True, backends=["codex"]))
```

- [ ] **Step 2: Run to verify failure**

Run: `cd graph && .venv/Scripts/pytest tests/test_codex_backend.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `codex.py`**

```python
# graph/src/edit_episode_graph/backends/codex.py
"""CodexBackend — `codex exec "<task>" --model <id> --json`.

Spec §7.2. ChatGPT subscription auth.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel

from ._schema_extract import extract_structured
from ._stream_parsers import parse_codex_json
from ._types import (
    AuthError,
    BackendCapabilities,
    BackendTimeout,
    InvokeResult,
    NodeRequirements,
    RateLimitError,
    Tier,
)

_MODEL_BY_TIER: dict[str, str] = {
    "cheap": "gpt-5-mini",
    "smart": "gpt-5",
}

_AUTH_SIGNALS = ("not authenticated", "codex login", "unauthorized", "session expired")
_RATE_SIGNALS = ("rate limit", "quota", "too many requests")


class CodexBackend:
    name = "codex"
    capabilities = BackendCapabilities(
        name="codex", has_tools=True, supports_streaming=False, max_concurrent=2,
    )

    def __init__(self, executable: str | None = None):
        self._executable = executable or shutil.which("codex") or "codex"

    def supports(self, req: NodeRequirements) -> bool:
        return self.capabilities.has_tools or not req.needs_tools

    def invoke(
        self,
        task: str,
        *,
        tier: Tier,
        cwd: Path,
        timeout_s: int,
        output_schema: type[BaseModel] | None,
        allowed_tools: list[str] | None = None,
        model_override: str | None = None,
    ) -> InvokeResult:
        model = model_override or _MODEL_BY_TIER[tier]
        cmd = [self._executable, "exec", task, "--model", model, "--json"]
        t0 = time.monotonic()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(cwd), timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            raise BackendTimeout(f"codex exceeded {timeout_s}s") from e
        wall = time.monotonic() - t0
        stderr_lc = (result.stderr or "").lower()
        if result.returncode != 0:
            if any(sig in stderr_lc for sig in _AUTH_SIGNALS):
                raise AuthError(result.stderr.strip() or "codex auth failed")
            if any(sig in stderr_lc for sig in _RATE_SIGNALS):
                raise RateLimitError(result.stderr.strip() or "codex rate limited")
            raise RuntimeError(f"codex exit {result.returncode}: {result.stderr.strip()}")

        parsed = parse_codex_json(result.stdout)
        structured = None
        if output_schema is not None:
            structured = extract_structured(parsed.assistant_text, output_schema)

        return InvokeResult(
            raw_text=parsed.assistant_text,
            structured=structured,
            tokens_in=parsed.tokens_in,
            tokens_out=parsed.tokens_out,
            wall_time_s=wall,
            model_used=parsed.model_used or model,
            backend_used=self.name,
            tool_calls=parsed.tool_calls,
        )
```

- [ ] **Step 4: Verify tests pass**

Run: `cd graph && .venv/Scripts/pytest tests/test_codex_backend.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add graph/src/edit_episode_graph/backends/codex.py graph/tests/test_codex_backend.py
git commit -m "v2(graph): CodexBackend with json envelope parse (HOM-74)"
```

---

### Task 10: BackendRouter (failover policy + telemetry)

**Files:**
- Modify: `graph/src/edit_episode_graph/backends/_router.py`
- Create: `graph/tests/test_router.py`

- [ ] **Step 1: Write the failing test**

```python
# graph/tests/test_router.py
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends._types import (
    AllBackendsExhausted,
    AuthError,
    BackendCapabilities,
    BackendTimeout,
    InvokeResult,
    NodeRequirements,
    RateLimitError,
    SchemaValidationError,
)


class _Schema(BaseModel):
    n: int


class _StubBackend:
    def __init__(self, name: str, behavior):
        self.name = name
        self.capabilities = BackendCapabilities(name, has_tools=True, supports_streaming=True, max_concurrent=2)
        self._behavior = behavior     # callable(call_idx) -> raises or returns InvokeResult
        self.calls = 0

    def supports(self, req): return True

    def invoke(self, task, *, tier, cwd, timeout_s, output_schema, allowed_tools=None):
        self.calls += 1
        return self._behavior(self.calls)


def _ok():
    return InvokeResult(raw_text="{\"n\":1}", structured=_Schema(n=1), tokens_in=1,
                        tokens_out=1, wall_time_s=0.01, model_used="m", backend_used="x", tool_calls=[])


def test_first_backend_succeeds():
    a = _StubBackend("a", lambda i: _ok())
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "task", cwd=Path.cwd(), timeout_s=10, output_schema=_Schema)
    assert res.backend_used in ("x",)
    assert a.calls == 1 and b.calls == 0
    assert len(attempts) == 1 and attempts[0]["success"] is True


def test_auth_fail_advances_to_next_backend():
    def auth_fail(_): raise AuthError("nope")
    a = _StubBackend("a", auth_fail)
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 1 and b.calls == 1
    assert attempts[0]["reason"] == "auth"
    assert attempts[1]["success"] is True


def test_schema_validation_retries_same_backend(monkeypatch):
    states = iter([
        SchemaValidationError("bad", "raw1"),
        SchemaValidationError("bad", "raw2"),
        _ok(),
    ])

    def behavior(_):
        nxt = next(states)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    a = _StubBackend("a", behavior)
    r = BackendRouter([a], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 3
    assert sum(1 for at in attempts if at["reason"] == "schema") == 2


def test_schema_validation_exhausts_to_next(monkeypatch):
    a = _StubBackend("a", lambda i: (_ for _ in ()).throw(SchemaValidationError("bad", "r")))
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, _ = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                      "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 3 and b.calls == 1


def test_rate_limit_retries_once_then_advances(monkeypatch):
    sleeps = []
    monkeypatch.setattr("edit_episode_graph.backends._router.time.sleep", lambda s: sleeps.append(s))

    states = iter([RateLimitError("nope"), RateLimitError("still"), _ok()])

    def behavior(_):
        nxt = next(states)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    a = _StubBackend("a", behavior)
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 2  # initial + one retry after sleep
    assert b.calls == 1
    assert sleeps == [30]


def test_timeout_advances():
    def boom(_): raise BackendTimeout("slow")
    a = _StubBackend("a", boom)
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert attempts[0]["reason"] == "timeout"


def test_all_exhausted_raises():
    def boom(_): raise AuthError("x")
    a = _StubBackend("a", boom)
    b = _StubBackend("b", boom)
    r = BackendRouter([a, b], BackendSemaphores({}))
    with pytest.raises(AllBackendsExhausted):
        r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                 "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)


def test_unsupported_backend_skipped():
    class _NoTools(_StubBackend):
        def __init__(self):
            super().__init__("a", lambda i: _ok())
            self.capabilities = BackendCapabilities("a", has_tools=False, supports_streaming=True, max_concurrent=1)
        def supports(self, req): return not req.needs_tools

    a = _NoTools()
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 0 and b.calls == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `cd graph && .venv/Scripts/pytest tests/test_router.py -v`
Expected: 8 failures (NotImplementedError or signature mismatch).

- [ ] **Step 3: Implement `_router.py`**

```python
# graph/src/edit_episode_graph/backends/_router.py
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
```

- [ ] **Step 4: Verify tests pass**

Run: `cd graph && .venv/Scripts/pytest tests/test_router.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add graph/src/edit_episode_graph/backends/_router.py graph/tests/test_router.py
git commit -m "v2(graph): BackendRouter with failover policy + telemetry (HOM-74)"
```

---

### Task 11: State extension — `edit.pre_scan` + `llm_runs` namespace

**Files:**
- Modify: `graph/src/edit_episode_graph/state.py`

- [ ] **Step 1: Update `state.py`**

Add to the imports / classes (preserving existing entries):

```python
class PreScanState(TypedDict, total=False):
    slips: list[dict]
    source_path: str | None
    skipped: bool
    skip_reason: str | None


class EditState(TypedDict, total=False):
    pre_scan: PreScanState


class LLMRunRecord(TypedDict, total=False):
    node: str
    backend: str
    model: str
    tier: str
    success: bool
    reason: str | None
    wall_time_s: float | None
    tokens_in: int | None
    tokens_out: int | None
    timestamp: str
```

And extend `GraphState` to include `edit` (dict-merge) and `llm_runs` (append-only):

```python
class GraphState(TypedDict, total=False):
    slug: str
    episode_dir: str
    pickup: Annotated[PickupState, dict_merge]
    audio: Annotated[AudioState, dict_merge]
    transcripts: Annotated[TranscriptsState, dict_merge]
    compose: Annotated[ComposeState, dict_merge]
    edit: Annotated[EditState, dict_merge]
    errors: Annotated[list[GraphError], add]
    notices: Annotated[list[str], add]
    llm_runs: Annotated[list[LLMRunRecord], add]
```

- [ ] **Step 2: Smoke-import**

Run: `cd graph && .venv/Scripts/python -c "from edit_episode_graph.state import GraphState, EditState, LLMRunRecord; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add graph/src/edit_episode_graph/state.py
git commit -m "v2(graph): state — add edit.pre_scan + llm_runs (HOM-74)"
```

---

### Task 12: Pydantic schema for PreScanReport

**Files:**
- Create: `graph/src/edit_episode_graph/schemas/__init__.py`
- Create: `graph/src/edit_episode_graph/schemas/p3_pre_scan.py`

- [ ] **Step 1: Create empty `schemas/__init__.py`**

```python
```

- [ ] **Step 2: Create `schemas/p3_pre_scan.py`**

```python
# graph/src/edit_episode_graph/schemas/p3_pre_scan.py
"""Schema for p3_pre_scan output.

Mirrors video-use SKILL.md §"The process" Step 2: "verbal slips, obvious
mis-speaks, or phrasings to avoid". A slip is a single phrase the editor
should skip; `take_index` is optional because some slips span multiple takes
or are not anchored to a specific `## Take N` header.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Slip(BaseModel):
    quote: str = Field(min_length=1, description="Exact phrase from takes_packed.md to avoid in the cut.")
    take_index: int | None = Field(default=None, description="Take number where the slip occurs, if anchored.")
    reason: str = Field(min_length=1, description="Why the editor should skip this — slip, mis-speak, off-topic, etc.")


class PreScanReport(BaseModel):
    slips: list[Slip] = Field(default_factory=list)
```

- [ ] **Step 3: Smoke-import**

Run: `cd graph && .venv/Scripts/python -c "from edit_episode_graph.schemas.p3_pre_scan import PreScanReport; print(PreScanReport(slips=[]).model_dump())"`
Expected: `{'slips': []}`.

- [ ] **Step 4: Commit**

```bash
git add graph/src/edit_episode_graph/schemas/
git commit -m "v2(graph): PreScanReport schema (HOM-74)"
```

---

### Task 13: Brief template for p3_pre_scan

**Files:**
- Create: `graph/src/edit_episode_graph/briefs/p3_pre_scan.j2`

- [ ] **Step 1: Create the template**

```jinja
{# Pre-scan task descriptor — mirrors video-use SKILL.md §"The process" Step 2.
   Kept short (≤25 lines): tells the executor where the input lives, what to
   look for, and what shape to return. Hard Rules and forbidden-field
   guarantees live in the schema (see schemas/p3_pre_scan.py), not in prose. #}
You are running the **pre-scan** pass for an anticodeguy episode (`{{ slug }}`).

Canon: `~/.claude/skills/video-use/SKILL.md` §"The process" — Step 2 ("Pre-scan
for problems"). Read it once if you have not.

Input: `{{ takes_packed_path }}` (a `takes_packed.md` produced by the inventory
step). Read it via the `Read` tool. Walk through the takes once. Note:

  - Verbal slips, mis-starts, false starts, words the speaker corrected.
  - Obvious mis-speaks (wrong word, wrong number, swapped name).
  - Phrasings the editor should avoid even if they parse cleanly (filler,
    off-topic asides, things the speaker explicitly retracted).

Return ONLY a JSON document matching this schema:

```json
{
  "slips": [
    {"quote": "<exact phrase>", "take_index": <int|null>, "reason": "<why>"}
  ]
}
```

If there are no slips worth flagging, return `{"slips": []}`. Do not include
prose outside the JSON block. Do not invent slips — only flag what is in the
file.
```

- [ ] **Step 2: Verify Jinja2 can render**

Run: `cd graph && .venv/Scripts/python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('src/edit_episode_graph/briefs')); print(env.get_template('p3_pre_scan.j2').render(slug='demo', takes_packed_path='/x/y.md')[:80])"`
Expected: First ~80 chars of the rendered brief.

- [ ] **Step 3: Commit**

```bash
git add graph/src/edit_episode_graph/briefs/p3_pre_scan.j2
git commit -m "v2(graph): brief — p3_pre_scan task descriptor (HOM-74)"
```

---

### Task 14: `LLMNode` base + per-call telemetry

**Files:**
- Create: `graph/src/edit_episode_graph/nodes/_llm.py`
- Create: `graph/tests/test_llm_node.py`

- [ ] **Step 1: Write the failing test**

```python
# graph/tests/test_llm_node.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from pydantic import BaseModel

from edit_episode_graph.backends._types import InvokeResult, NodeRequirements
from edit_episode_graph.nodes._llm import LLMNode


class _Out(BaseModel):
    n: int


def _fake_router(structured):
    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(raw_text='{"n":1}', structured=structured, tokens_in=10,
                     tokens_out=2, wall_time_s=0.5, model_used="m", backend_used="claude", tool_calls=[]),
        [{"backend": "claude", "success": True, "model": "m", "tokens_in": 10, "tokens_out": 2,
          "wall_time_s": 0.5, "ts": datetime.now(timezone.utc).isoformat()}],
    )
    return router


def test_llm_node_returns_state_update():
    node = LLMNode(
        name="demo",
        requirements=NodeRequirements("cheap", needs_tools=False, backends=["claude"]),
        brief_template="hello {{ slug }}",
        output_schema=_Out,
        result_namespace="edit",
        result_key="demo",
        timeout_s=10,
    )
    state = {"slug": "abc", "episode_dir": str(Path.cwd())}
    update = node._invoke_with(_fake_router(_Out(n=1)), state, render_ctx={"slug": "abc"})
    assert update["edit"]["demo"] == {"n": 1}
    assert update["llm_runs"][0]["node"] == "demo"
    assert update["llm_runs"][0]["success"] is True


def test_llm_node_records_failure(monkeypatch):
    from edit_episode_graph.backends._types import AllBackendsExhausted
    router = MagicMock()
    router.invoke.side_effect = AllBackendsExhausted([
        {"backend": "claude", "success": False, "reason": "auth", "ts": "t"},
    ])
    node = LLMNode(
        name="demo", requirements=NodeRequirements("cheap", False, ["claude"]),
        brief_template="hi", output_schema=_Out, result_namespace="edit",
        result_key="demo", timeout_s=5,
    )
    update = node._invoke_with(router, {"slug": "x", "episode_dir": str(Path.cwd())}, render_ctx={})
    assert "errors" in update
    assert update["llm_runs"][0]["success"] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `cd graph && .venv/Scripts/pytest tests/test_llm_node.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `_llm.py`**

```python
# graph/src/edit_episode_graph/nodes/_llm.py
"""LLMNode — minimal base for nodes that dispatch through BackendRouter.

Subclass or instantiate to build a callable that LangGraph treats as a node.
The base handles: brief rendering (Jinja2 string), router invocation,
telemetry append to `state["llm_runs"]`, error → `state["errors"]` + notice
on terminal failure (AllBackendsExhausted).

Tool-call observability: if a `dispatch_custom_event` is available
(LangGraph runtime), each `ToolCall` from the InvokeResult is re-emitted as
a `tool_call` custom event so Studio renders nested steps. Outside the
runtime (unit tests), the dispatch is a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jinja2 import Template
from pydantic import BaseModel

from ..backends._router import BackendRouter
from ..backends._types import (
    AllBackendsExhausted,
    InvokeResult,
    NodeRequirements,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dispatch_event(name: str, payload: dict) -> None:
    try:
        from langgraph.config import get_stream_writer  # type: ignore
        writer = get_stream_writer()
        writer({"event": name, "payload": payload})
    except Exception:
        return


@dataclass
class LLMNode:
    name: str
    requirements: NodeRequirements
    brief_template: str
    output_schema: type[BaseModel] | None
    result_namespace: str
    result_key: str
    timeout_s: int = 120
    allowed_tools: list[str] | None = None
    extra_render_ctx: Callable[[dict], dict] = field(default=lambda s: {})

    def __call__(self, state: dict, *, router: BackendRouter | None = None) -> dict:
        # In production, the router is bound in graph.py at compile time via
        # functools.partial; tests pass it explicitly.
        from ..config import load_default_config
        if router is None:
            from .._runtime import get_router   # late import; defined in next task
            router = get_router()
        ctx = {"slug": state.get("slug"), "episode_dir": state.get("episode_dir")}
        ctx.update(self.extra_render_ctx(state))
        node_cfg = load_default_config().resolve_node(self.name)
        # Per-node config overrides defaults baked into the LLMNode dataclass.
        effective_req = NodeRequirements(
            tier=node_cfg.tier or self.requirements.tier,
            needs_tools=self.requirements.needs_tools,
            backends=node_cfg.backend_preference or self.requirements.backends,
        )
        return self._invoke_with(
            router, state, render_ctx=ctx,
            requirements=effective_req,
            timeout_s=node_cfg.timeout_s or self.timeout_s,
            model_override=node_cfg.model,
        )

    def _invoke_with(
        self, router: BackendRouter, state: dict, render_ctx: dict,
        *, requirements: NodeRequirements | None = None,
        timeout_s: int | None = None,
        model_override: str | None = None,
    ) -> dict:
        req = requirements or self.requirements
        timeout_s = timeout_s or self.timeout_s
        task = Template(self.brief_template).render(**render_ctx)
        cwd = Path(state.get("episode_dir") or ".")
        try:
            result, attempts = router.invoke(
                req,
                task,
                cwd=cwd,
                timeout_s=timeout_s,
                output_schema=self.output_schema,
                allowed_tools=self.allowed_tools,
                model_override=model_override,
            )
        except AllBackendsExhausted as e:
            runs = [self._record(at) for at in e.attempts]
            return {
                "errors": [{"node": self.name, "message": str(e), "timestamp": _now()}],
                "llm_runs": runs,
                "notices": [f"{self.name}: all backends exhausted; see llm_runs"],
            }

        for tc in result.tool_calls:
            _safe_dispatch_event("tool_call", {
                "node": self.name, "tool": tc.name,
                "input": tc.input, "output_preview": tc.output_preview,
            })

        runs = [self._record(at) for at in attempts]
        update: dict[str, Any] = {"llm_runs": runs}
        if self.output_schema is not None and isinstance(result.structured, BaseModel):
            update[self.result_namespace] = {self.result_key: result.structured.model_dump()}
        else:
            update[self.result_namespace] = {self.result_key: {"raw_text": result.raw_text}}
        return update

    def _record(self, attempt: dict) -> dict:
        return {
            "node": self.name,
            "backend": attempt.get("backend"),
            "model": attempt.get("model"),
            "tier": self.requirements.tier,
            "success": attempt.get("success", False),
            "reason": attempt.get("reason"),
            "wall_time_s": attempt.get("wall_time_s"),
            "tokens_in": attempt.get("tokens_in"),
            "tokens_out": attempt.get("tokens_out"),
            "timestamp": attempt.get("ts", _now()),
        }
```

- [ ] **Step 4: Verify tests pass**

Run: `cd graph && .venv/Scripts/pytest tests/test_llm_node.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add graph/src/edit_episode_graph/nodes/_llm.py graph/tests/test_llm_node.py
git commit -m "v2(graph): LLMNode base with telemetry + tool-call passthrough (HOM-74)"
```

---

### Task 15: Runtime singleton (router builder + module-level cache)

**Files:**
- Create: `graph/src/edit_episode_graph/_runtime.py`

- [ ] **Step 1: Implement `_runtime.py`**

```python
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
```

- [ ] **Step 2: Smoke-import**

Run: `cd graph && .venv/Scripts/python -c "from edit_episode_graph._runtime import get_router; r = get_router(); print(type(r).__name__)"`
Expected: `BackendRouter`.

- [ ] **Step 3: Commit**

```bash
git add graph/src/edit_episode_graph/_runtime.py
git commit -m "v2(graph): process-level router singleton (HOM-74)"
```

---

### Task 16: `p3_pre_scan` node + skip-when-no-takes guard

**Files:**
- Create: `graph/src/edit_episode_graph/nodes/p3_pre_scan.py`
- Create: `graph/tests/test_p3_pre_scan_node.py`

- [ ] **Step 1: Write the failing test**

```python
# graph/tests/test_p3_pre_scan_node.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes.p3_pre_scan import p3_pre_scan_node
from edit_episode_graph.schemas.p3_pre_scan import PreScanReport, Slip


def test_skips_when_takes_packed_missing(tmp_path):
    state = {"slug": "demo", "episode_dir": str(tmp_path)}
    update = p3_pre_scan_node(state, router=MagicMock())
    assert update["edit"]["pre_scan"]["skipped"] is True
    assert "takes_packed.md" in (update["edit"]["pre_scan"].get("skip_reason") or "")
    assert "llm_runs" not in update or update["llm_runs"] == []


def test_runs_when_takes_packed_present(tmp_path):
    edit_dir = tmp_path / "edit"
    edit_dir.mkdir()
    (edit_dir / "takes_packed.md").write_text("# Take 1\nHello.\n", encoding="utf-8")

    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text='{"slips":[{"quote":"hello","take_index":1,"reason":"placeholder"}]}',
            structured=PreScanReport(slips=[Slip(quote="hello", take_index=1, reason="placeholder")]),
            tokens_in=50, tokens_out=20, wall_time_s=1.0,
            model_used="claude-sonnet-4-6", backend_used="claude", tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-sonnet-4-6",
          "tokens_in": 50, "tokens_out": 20, "wall_time_s": 1.0, "ts": "now"}],
    )

    state = {"slug": "demo", "episode_dir": str(tmp_path)}
    update = p3_pre_scan_node(state, router=router)
    assert update["edit"]["pre_scan"]["slips"] == [
        {"quote": "hello", "take_index": 1, "reason": "placeholder"},
    ]
    assert update["edit"]["pre_scan"]["source_path"].endswith("takes_packed.md")
    assert update["llm_runs"][0]["node"] == "p3_pre_scan"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd graph && .venv/Scripts/pytest tests/test_p3_pre_scan_node.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `p3_pre_scan.py`**

```python
# graph/src/edit_episode_graph/nodes/p3_pre_scan.py
"""p3_pre_scan — first production LLM node.

Reads `episodes/<slug>/edit/takes_packed.md` (produced by the v3-future
`p3_inventory` node, but already present on episodes that ran video-use
manually) and emits `PreScanReport`.

If `takes_packed.md` does not exist yet, the node returns a "skipped" marker
without calling any backend — this is the v2 path during the LLM-boundary
halt where the inventory step has not yet run. v3 will remove the skip.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Template

from ..backends._router import BackendRouter
from ..backends._types import AllBackendsExhausted, NodeRequirements
from ..schemas.p3_pre_scan import PreScanReport
from ._llm import LLMNode

_BRIEF_PATH = Path(__file__).resolve().parent.parent / "briefs" / "p3_pre_scan.j2"


def _build_node() -> LLMNode:
    return LLMNode(
        name="p3_pre_scan",
        requirements=NodeRequirements(tier="cheap", needs_tools=True, backends=["claude", "codex"]),
        brief_template=_BRIEF_PATH.read_text(encoding="utf-8"),
        output_schema=PreScanReport,
        result_namespace="edit",
        result_key="pre_scan",
        timeout_s=90,
        allowed_tools=["Read"],
        extra_render_ctx=lambda state: {
            "takes_packed_path": str(Path(state["episode_dir"]) / "edit" / "takes_packed.md"),
        },
    )


def p3_pre_scan_node(state, *, router: BackendRouter | None = None):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return {"edit": {"pre_scan": {"skipped": True, "skip_reason": "no episode_dir in state"}}}
    takes = Path(episode_dir) / "edit" / "takes_packed.md"
    if not takes.exists():
        return {"edit": {"pre_scan": {"skipped": True, "skip_reason": f"takes_packed.md missing at {takes}"}}}

    node = _build_node()
    update = node(state, router=router)
    # Ensure the "slips" key is present even when the brief returned an empty list,
    # and tag the source path for traceability.
    pre_scan = (update.get("edit") or {}).get("pre_scan") or {}
    if "slips" not in pre_scan and "skipped" not in pre_scan:
        pre_scan["slips"] = []
    pre_scan["source_path"] = str(takes)
    update.setdefault("edit", {})["pre_scan"] = pre_scan
    return update
```

- [ ] **Step 4: Verify tests pass**

Run: `cd graph && .venv/Scripts/pytest tests/test_p3_pre_scan_node.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add graph/src/edit_episode_graph/nodes/p3_pre_scan.py graph/tests/test_p3_pre_scan_node.py
git commit -m "v2(graph): p3_pre_scan node with skip-when-no-takes guard (HOM-74)"
```

---

### Task 17: Wire p3_pre_scan into v1 graph topology

**Files:**
- Modify: `graph/src/edit_episode_graph/nodes/_routing.py`
- Modify: `graph/src/edit_episode_graph/graph.py`
- Modify: `graph/src/edit_episode_graph/nodes/halt_llm_boundary.py`
- Create: `graph/tests/test_p3_pre_scan_routing.py`

- [ ] **Step 1: Write the failing test**

```python
# graph/tests/test_p3_pre_scan_routing.py
from pathlib import Path

from langgraph.graph import END

from edit_episode_graph.nodes._routing import route_after_preflight


def test_routes_to_pre_scan_when_takes_packed_exists(tmp_path):
    edit = tmp_path / "edit"
    edit.mkdir()
    (edit / "takes_packed.md").write_text("# t\n", encoding="utf-8")
    state = {"episode_dir": str(tmp_path)}
    assert route_after_preflight(state) == "p3_pre_scan"


def test_routes_to_glue_when_final_exists(tmp_path):
    edit = tmp_path / "edit"
    edit.mkdir()
    (edit / "final.mp4").write_bytes(b"x")
    (edit / "takes_packed.md").write_text("# t\n", encoding="utf-8")
    state = {"episode_dir": str(tmp_path)}
    assert route_after_preflight(state) == "glue_remap_transcript"


def test_routes_to_halt_when_neither_exists(tmp_path):
    state = {"episode_dir": str(tmp_path)}
    assert route_after_preflight(state) == "halt_llm_boundary"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd graph && .venv/Scripts/pytest tests/test_p3_pre_scan_routing.py -v`
Expected: 1 of 3 fails (the `p3_pre_scan` branch is not yet present).

- [ ] **Step 3: Update `route_after_preflight` in `_routing.py`**

Replace the function body:

```python
def route_after_preflight(state) -> str:
    """preflight_canon → glue_remap_transcript | p3_pre_scan | halt_llm_boundary (skip_phase3)."""
    if state.get("errors"):
        return END
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return END
    edit_dir = Path(episode_dir) / "edit"
    if (edit_dir / "final.mp4").exists():
        return "glue_remap_transcript"
    if (edit_dir / "takes_packed.md").exists():
        return "p3_pre_scan"
    return "halt_llm_boundary"
```

- [ ] **Step 4: Update `graph.py`**

Add the import:

```python
from .nodes.p3_pre_scan import p3_pre_scan_node
```

Add node registration in `build_graph_uncompiled` (after `p4_scaffold` registration):

```python
    g.add_node("p3_pre_scan", p3_pre_scan_node)
```

Update the `route_after_preflight` conditional-edge mapping to include the new branch:

```python
    g.add_conditional_edges(
        "preflight_canon",
        route_after_preflight,
        {
            END: END,
            "glue_remap_transcript": "glue_remap_transcript",
            "p3_pre_scan": "p3_pre_scan",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
```

Add the post-pre-scan edge (route to halt_llm_boundary so the run terminates with a clean notice — Phase 3 EDL/render is v3+):

```python
    g.add_edge("p3_pre_scan", "halt_llm_boundary")
```

Update the docstring's ASCII topology to reflect the new branch (one extra line under `skip_phase3?`).

- [ ] **Step 5: Update `halt_llm_boundary.py` notice copy**

```python
def halt_llm_boundary_node(state):
    pre_scan_state = (state.get("edit") or {}).get("pre_scan") or {}
    if pre_scan_state.get("slips") is not None and not pre_scan_state.get("skipped"):
        msg = (
            "v2 halt: pre_scan ran ({n} slip(s) recorded); EDL + render require v3 LLM nodes"
            .format(n=len(pre_scan_state.get("slips") or []))
        )
    else:
        msg = "v1 halt: `final.mp4` missing; Phase 3 (`p3_inventory`+) requires LLM nodes (v3+)"
    return {"notices": [msg]}
```

- [ ] **Step 6: Verify tests pass**

Run: `cd graph && .venv/Scripts/pytest tests/test_p3_pre_scan_routing.py tests/test_p3_pre_scan_node.py -v`
Expected: all pass.

- [ ] **Step 7: Smoke-build the graph**

Run: `cd graph && .venv/Scripts/python -c "from edit_episode_graph.graph import build_graph; g = build_graph(); print(sorted(g.get_graph().nodes))"`
Expected: list includes `p3_pre_scan`.

- [ ] **Step 8: Commit**

```bash
git add graph/src/edit_episode_graph/nodes/_routing.py graph/src/edit_episode_graph/graph.py graph/src/edit_episode_graph/nodes/halt_llm_boundary.py graph/tests/test_p3_pre_scan_routing.py
git commit -m "v2(graph): wire p3_pre_scan into topology (HOM-74)"
```

---

### Task 18: Full test suite + Studio smoke run

**Files:**
- None (verification + ad-hoc).

- [ ] **Step 1: Run the full test suite**

Run: `cd graph && .venv/Scripts/pytest -v`
Expected: all green; no skips.

- [ ] **Step 2: Bring up Studio and smoke-run on a real episode (REAL CLI CALL)**

This step makes a real `claude -p` invocation against the Anthropic subscription. `graph/config.yaml` must have `node_overrides.p3_pre_scan.model: claude-haiku-4-5-20251001` (set in Task 7) so the spend is minimal.

Pick a slug whose `episodes/<slug>/edit/takes_packed.md` exists but `final.mp4` does not. Confirm via `ls episodes/desktop-licensing-story/edit/`. If `final.mp4` is present, pick a different episode (e.g., `2026-05-01-...`).

Run (PowerShell):

```powershell
cd graph
.\.venv\Scripts\langgraph.exe dev
```

In Studio:
1. New thread, `thread_id = <slug>`.
2. Run with input `{"slug": "<slug>"}`.
3. Observe trace: `pickup → preflight_canon → p3_pre_scan → halt_llm_boundary → END`.
4. Open the `p3_pre_scan` node in the right pane. Confirm:
   - `tool_call` custom events appear (one per Read).
   - `state.edit.pre_scan.slips` is populated (or `[]` if no slips).
   - `state.llm_runs[0]` has `success: true`, `node: p3_pre_scan`, `backend: claude`, `model: claude-haiku-4-5-20251001`, populated `tokens_in/out` and `wall_time_s`.
5. Re-run the same thread → `pre_scan` is re-issued (idempotency for LLM nodes is a v3+ topic; for now re-run = re-call).

- [ ] **Step 3: Failover demo (optional but in DoD)**

Temporarily edit `graph/config.yaml`:

```yaml
node_overrides:
  p3_pre_scan:
    tier: cheap
    backend_preference: ["nonexistent", "claude", "codex"]
```

Restart `langgraph dev`. Re-run. Studio should show one attempt with `reason: unsupported`, then a successful claude attempt. Revert the config change.

- [ ] **Step 4: Commit any incidental fixes**

If Studio surfaces an issue (likely candidates: `--verbose` flag absent on installed Claude CLI version, codex JSON shape mismatch, etc.), fix in-place, add a regression test if the bug had a deterministic surface, and commit:

```bash
git add -A
git commit -m "v2(graph): smoke-run fixes from Studio shakedown (HOM-74)"
```

If everything passes cleanly, no commit.

---

### Task 19: Open the PR

**Files:**
- None.

- [ ] **Step 1: Push the branch**

```bash
git push -u origin a/hom-74-v2-llm-backend
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --base main --title "v2(graph): first LLM node + backend abstraction (HOM-74)" --body "$(cat <<'EOF'
## Summary

- LLMBackend Protocol + ClaudeCodeBackend (stream-json) + CodexBackend (json envelope)
- BackendRouter with failover policy (auth → next; rate limit → 30s + retry once → next; schema → 2 retries → next; timeout → next; exhausted → AllBackendsExhausted)
- Per-backend concurrency semaphores (default claude=2, codex=2, gemini=3)
- YAML config (`graph/config.yaml`) with glob-aware per-node overrides
- LLMNode base with brief rendering, telemetry append (`state["llm_runs"]`), and `tool_call` custom-event passthrough for Studio
- First production LLM node: `p3_pre_scan` (cheap tier, has_tools, reads `takes_packed.md`, outputs `PreScanReport`)
- State extended: `edit.pre_scan` namespace + `llm_runs` append-only top-level list
- Routing: `preflight_canon` now branches to `p3_pre_scan` when `takes_packed.md` exists (and `final.mp4` does not)

Linear: HOM-74

## Test plan

- [x] `pytest -v` green (router failover, schema retry, concurrency cap, parsers, config glob, llm node, routing)
- [ ] Studio smoke run on a real episode with existing `takes_packed.md` — pre_scan emits slips, tool calls visible in trace, llm_runs populated
- [ ] Failover demo: prepend `nonexistent` to `backend_preference` in config.yaml → router skips it and lands on claude
- [ ] Concurrency demo (manual): drive 5 parallel invokes via a one-off script; Studio shows 2 active + 3 pending

EOF
)"
```

- [ ] **Step 3: Add the PR link to the Linear issue + flip status to In Review**

Use `mcp__linear-hb__save_comment` with `issue: HOM-74` and the PR URL, then `mcp__linear-hb__save_issue` with `id: HOM-74, state: "In Review"`.

- [ ] **Step 4: Stop here**

Wait for CI (no CI configured beyond local pytest, so this is essentially "wait for user". The merge step lives in HOM-74's closing handoff, not in this plan).

---

## Self-Review

**1. Spec coverage:**
- §7.1 Protocol → Task 5 ✓
- §7.2 Claude + Codex backends → Tasks 8, 9 ✓
- §7.3 InvokeResult → Task 2 ✓
- §7.4 Failover policy → Task 10 ✓ (auth, rate-limit + 30s, schema ≤2 retries, timeout, exhausted)
- §7.5 Concurrency semaphores → Task 6 ✓
- §7.6 config.yaml + glob-pattern overrides → Task 7 ✓
- §7.7 Windows `.cmd` shim → addressed via `shutil.which` returning the absolute `.cmd` path; documented in Task 8 docstring. (If the smoke run in Task 18 surfaces EINVAL, the fallback is `shell=True` — flagged as smoke-run fix candidate.)
- §6.3 LLMNode base + p3_pre_scan row → Tasks 14, 16 ✓
- DoD: tool calls in trace (LLMNode dispatches `tool_call` events) ✓; pre_scan in state.edit ✓; schema retry (router test) ✓; failover demoable (Task 18 step 3) ✓; semaphore observable (concurrency test demonstrates cap; Task 18 step 3 manual demo).
- Memory: `feedback_bundled_helper_path.md` Windows note → docstring in `claude.py`.

**2. Placeholder scan:** No "TBD" / "implement later" / "similar to N" / "add appropriate handling" found. Each step has full code.

**3. Type consistency:**
- `NodeRequirements.backends` (list[str]) — used consistently in router preference walk.
- `InvokeResult.structured` is `Any | None`; `LLMNode` checks `isinstance(result.structured, BaseModel)` before `model_dump()`. Consistent with router test fixtures returning `_Schema(n=1)`.
- `BackendCapabilities.max_concurrent` exists but is not consumed by `BackendSemaphores` (which reads from `config.yaml` via `RouterConfig.concurrency`). That is intentional: the cap is operator-tunable, not backend-declared. No code references the field, but it is part of spec §7.1 and useful as a default hint for new operators reading the code.
- Router telemetry dicts use `reason` ∈ {"auth", "rate_limit", "timeout", "schema", "other", "unsupported"}. `LLMNode._record` passes through verbatim. `LLMRunRecord` TypedDict marks `reason` as `str | None`. Consistent.
- `result_namespace="edit"` + `result_key="pre_scan"` in p3_pre_scan node lines up with `EditState.pre_scan: PreScanState` in state.py.
