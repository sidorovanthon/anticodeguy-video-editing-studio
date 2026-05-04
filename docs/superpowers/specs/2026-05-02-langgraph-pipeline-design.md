# LangGraph Pipeline Migration — Design

**Date:** 2026-05-02
**Status:** Draft (awaiting user review)
**Scope:** Architectural blueprint for migrating the four-phase video editing pipeline (`/edit-episode`) from a brief-driven Claude Code orchestration to a LangGraph-based deterministic graph with pluggable LLM CLI backends. Covers full target topology (v7) and the immediate v0 deliverable (single-node pickup graph).

---

## 1. Context

The current pipeline is invoked via the `/edit-episode` slash command, defined as a ~300-line verbatim brief in `.claude/commands/edit-episode.md`. The brief mixes orchestration logic (idempotency rules, path layout, conditional skips), canon enforcement (Hard Rules from `video-use` and `hyperframes` SKILL.md, Output Checklist items, gate definitions), and creative direction (style preferences, pacing targets, beat→visual mapping). All of it is shoveled into a single LLM context, which then spawns sub-agents and Skill invocations.

Recent retros document a recurring failure mode: agents skip canon gates because enforcement is textual ("the brief says X must happen") rather than structural. Examples from `retro-2026-05-02-raw-phase4-omissions.md`:

- Skipped bare-repro before defaulting to inline beat assembly (despite explicit brief instruction).
- Skipped deterministic `tl.set` kill-tweens on B5 exit fades (despite canonical motion-principles rule).
- Did not dispatch parallel beat sub-agents (despite Hard Rule 10 mirror in Phase 4 brief).

These are not knowledge gaps. They are enforcement gaps: the brief is the only mechanism, and agents are not perfectly compliant readers of 300 lines.

## 2. Goals

The migration delivers four properties that the current orchestration cannot:

1. **Control.** Each canon rule that a deterministic check can verify becomes a graph gate node. Skipping a gate is structurally impossible — it sits on the edge of the graph between phases.
2. **Visibility.** Pipeline state, current node, past runs, and per-node traces are visible in LangGraph Studio. No more "what did the agent do for the last 40 minutes" questions.
3. **Resumability.** A SQLite checkpointer stores state per-node. A run that fails or is interrupted resumes from the failed node. Re-cuts and re-composes become `update_state(thread, ...)` + replay.
4. **Subscription-only LLM access with multi-CLI failover.** No API keys. All LLM calls go through authorized CLIs (`claude -p`, `codex exec`, `gemini`) using existing user subscriptions. Per-node tier (cheap/smart) and backend preference are configurable.

## 3. Constraints

- **No Anthropic/OpenAI API credits.** All LLM invocations are subprocess calls to authorized CLIs.
- **External skill canon is non-negotiable** (CLAUDE.md). `video-use` and `hyperframes` are read-only upstream products. The graph orchestrates *around* them, never duplicates their logic. Briefs in LLM nodes reference live `SKILL.md` paths; agents read canon themselves via tools.
- **Branching workflow** (CLAUDE.md). Every change ships through a feature branch + PR. This spec doc itself ships via `spec/langgraph-pipeline-design`.
- **Bare-repro before upstream-blame** (CLAUDE.md). Memory entries about upstream bugs (`feedback_hf_subcomp_loader_*`, etc.) require periodic re-verification. The graph automates this via a `preflight_canon` node.
- **Idempotency must be preserved.** Re-running on the same slug skips completed phases. ElevenLabs/Scribe credits are not re-spent.
- **Coexistence during migration.** `/edit-episode` is not modified until v7. v0–v6 add new capability; the slash command remains the user-facing entry point until cutover.

## 4. Long-term graph topology (v7 target)

### 4.1 Phase 1+2 — Pickup and audio isolation

```
START → pickup → idle? → END
              ↓
       skip_phase2?  ──yes──→  preflight_canon
              │ no              (raw container tagged ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1
              ▼                  → ElevenLabs not invoked)
       isolate_audio
              ↓
       preflight_canon          ← bare-repro for known-blocked patterns,
              ↓                   memory staleness check, last-verified updates
       skip_phase3?
```

`skip_phase2?` reads the container tag deterministically; ElevenLabs is dialed only when the tag is absent.

### 4.2 Phase 3 — video-use, decomposed (canon §"The process" 1–8)

**HR 11 (strategy approval) — restored as `strategy_confirmed_interrupt` in v3.1.** The original v3 design deferred HR 11 (canon: *"Strategy confirmation before execution. Never touch the cut until the user has approved the plain-English plan."*) on the grounds that `/edit-episode` did not interrupt either. Empirically that was a wrong call: the slash command was already violating canon, and the graph runs in LangGraph Studio where the operator is in-the-loop by design. v3.1 inserts `strategy_confirmed_interrupt` between `p3_strategy` and `p3_edl_select`. The node calls `langgraph.types.interrupt({...})` with the strategy summary; on `Command(resume=…)` it sets `state.edit.strategy.approved = true` and proceeds to EDL select. Idempotent — re-entry on a subsequent run after `approved=true` short-circuits without re-prompting. (Source: HOM-107 amendment, 2026-05-04.)

**Orchestrator policy: animations and subtitles are produced in Phase 4 (hyperframes), NOT in Phase 3.** Video-use canon makes both opt-in (`## Animations (when requested)` line 195; `subtitles is optional` line 280). Our `p3_strategy` and `p3_edl_select` briefs honor this opt-out: strategy does not propose animations or subtitles; EDL emits `overlays: []` and omits `subtitles` entirely. As a result `p3_render_segments` is purely cuts + grade + concat — Hard Rules 1 (subtitles last) and 4 (overlay PTS-shift) are trivially satisfied because there are no subtitles or overlays to manage.

**Step 1 sampling: timeline_view PNGs (v3.1).** Canon Step 1 calls for *"one or two timeline_view samples for a visual first impression."* The v3 deterministic `p3_inventory` originally produced none (text-only). v3.1 adds best-effort midpoint sampling — one filmstrip+waveform PNG per source written to `<edit>/verify/inventory/<stem>_mid.png`. Failure is non-fatal (notice + empty `timeline_view_samples` list). Per-cut waveform sampling at decision time still belongs to canon Step 7 (`p3_self_eval`).

```
       skip_phase3?  ──yes──→  glue_remap_transcript
              │ no
              ▼
       p3_inventory          deterministic: ffprobe + transcribe_batch (ElevenLabs) + pack_transcripts
              ▼               + best-effort timeline_view PNG per source under <edit>/verify/inventory/
       p3_pre_scan           LLM cheap, has_tools — reads takes_packed.md → list of slips/avoid
              ▼
       p3_strategy           LLM smart — proposes shape, take strategy, grade, pacing, length estimate.
              ▼               Brief explicitly suppresses animation + subtitle planning (Phase 4 territory).
       strategy_confirmed_interrupt   HITL — interrupt() with strategy summary; resumes on Command(resume=...).
              ▼               Idempotent: state.edit.strategy.approved short-circuits re-entry.
       p3_edl_select         LLM smart, has_tools — editor sub-agent brief from canon §"Editor sub-agent brief".
              ▼               Brief mandates `overlays: []` and omits `subtitles` field; HR 7 reminder
              ▼               for trailing edge (never copy a Scribe word-end timestamp as range end).
       gate:edl_ok           validates EDL schema, word-boundary cuts (HR 6), padding 30–200ms (HR 7) on
              ▼               BOTH edges, adaptive final-cut length (see §6.2 — anchored on
              ▼               strategy.length_estimate_s ±20% with a wide fallback when no estimate
              ▼               is available), `overlays == []`, `subtitles` field absent
       p3_render_segments    deterministic: render.py extract per-segment + grade + 30ms fades (HR 3)
              ▼               + concat -c copy (HR 2). No overlays, no subtitles.
       p3_self_eval          LLM cheap, has_tools — timeline_view at cut boundaries ±1.5s,
              ▼               check cuts/waveform/grade alignment
       gate:eval_ok ─┐       fail + iter<3 → loop back to p3_render_segments
              │      │       fail + iter≥3 → interrupt() escalate to user
              ▼ pass
       p3_persist_session    LLM cheap — appends Session block to <edit>/project.md
              ▼               (canon video-use §"Memory")
       glue_remap_transcript deterministic, scripts/remap_transcript.py
              ▼
       skip_phase4?
```

Phase 3 LLM nodes: 5 (`p3_pre_scan`, `p3_strategy`, `p3_edl_select`, `p3_self_eval`, `p3_persist_session`). Plus 2 deterministic (`p3_inventory`, `p3_render_segments`) and 1 HITL interrupt (`strategy_confirmed_interrupt`). Animation fan-out (`p3_animations_plan`, `p3_animations_slot_<n>` Send) is removed entirely — that surface lives in Phase 4 hyperframes scenes.

### 4.3 Phase 4 — hyperframes, decomposed (canon §"Approach" Step 1/2/3 + Quality Checks)

```
       skip_phase4? ──yes──→ studio_launch
              │ no
              ▼
       p4_scaffold              deterministic: scripts/scaffold_hyperframes.py
              ▼
       p4_design_system         LLM smart, has_tools — Step 1 visual identity gate, generates DESIGN.md
              ▼
       gate:design_ok           DESIGN.md substance: ≥2 visual references, ≥1 alternative, ≥3 anti-patterns,
              ▼                  Beat→Visual Mapping populated, visual-styles preset matched if named
       p4_prompt_expansion      LLM cheap, has_tools — Step 2: writes .hyperframes/expanded-prompt.md
              ▼
       p4_plan                  LLM smart, has_tools — Step 3: narrative beats, rhythm, beat→visual
              ▼                  mapping, transition mechanism per boundary
       gate:plan_ok             ≥3 beats, transition mechanism explicit per boundary (CSS / shader / final-fade),
              ▼                  catalog-vs-custom justification per beat
       p4_catalog_scan          deterministic: npx hyperframes catalog --json
              ▼
       Send(beat_n) ─┐          fan-out per beat (HR 10 mirror)
        ┌─────┐     │
        │beat1│────►│           each = sub-graph (v5): layout-before-animation → entrance-only GSAP →
        │beat2│────►│           tl.set kills → per-beat validate. Tier=smart.
        │beatN│────►│
        └─────┘     │
              ▼ reduce
       p4_captions_layer        LLM cheap, has_tools — authors caption HTML/CSS adapted to DESIGN.md
              ▼                  visual identity (orchestrator-house mandatory; canon makes captions
              ▼                  conditional but our pipeline always produces audio-synced text)
       p4_assemble_index        deterministic: assembles root index.html from beats + captions block
              ▼
       gate:lint                npx hyperframes lint
              ▼
       gate:validate            npx hyperframes validate (WCAG; deterministic triage for opacity-0 headless artifact
              ▼                  before routing to retry — see §6.2)
       gate:inspect             npx hyperframes inspect --at <beat_timestamps>
              ▼
       gate:design_adherence    canon §"Design Adherence" — colors/typography/avoidance vs DESIGN.md
              ▼
       gate:animation_map       node animation-map.mjs (bundled path) → JSON, flag check
              ▼                  (v5+: LLM-justify helper for paced-fast accents — nice-to-have)
       gate:snapshot            npx hyperframes snapshot at beat timestamps + interpret vs Beat→Visual Mapping,
              ▼                  allow 0.3s entrance offset
       gate:captions_track      grep transcript.json in index.html ≥ 1
              ▼
       p4_persist_session       LLM cheap — appends Phase 4 Session block to <edit>/project.md
              ▼
       studio_launch            deterministic: npx hyperframes preview --port 3002 + StaticGuard 5s window
              ▼
```

### 4.4 User Review + Final Render (post-studio)

```
       studio_launch
              ▼
       user_review              interrupt() — HITL: user reviews preview in Studio,
              ▼                  returns {approved: bool, feedback: str|None, target_phase: str|None}
       review_router            conditional edge:
        ┌─────┴──────┬─────────┬─────────┐
        │ approved   │ feedback│ feedback│ feedback
        │ = true     │ → p4    │ → p3    │ → p4_design
        ▼            ▼         ▼         ▼
       p4_final_render          ←── feedback injected into state ──┘
       (npx hyperframes render)
              ▼
       END (final.mp4 in episodes/<slug>/hyperframes/render/)
```

`phase_feedback` is a top-level append-only list in state. Each entry: `{phase, notes, iteration, timestamp}`. The targeted node reads it, injects into its task descriptor on retry. Iteration counter ≥ 3 on the same phase triggers an `interrupt()` escalation: user reformulates or aborts.

### 4.5 Topology properties

- **Idempotency through conditional edges, not in-node early returns.** Studio surfaces skip decisions visually.
- **Gates are first-class nodes.** Every canon-rule that a deterministic check can verify is enforced structurally. Skipping is impossible.
- **`Send` for parallelism.** No bespoke parallel-dispatch wiring; LangGraph fan-out + reduce is native. Backend semaphore prevents subscription rate limits.
- **One thread per slug.** `thread_id == slug`. Episode history, time-travel, re-cut all per-thread.
- **`preflight_canon` as a node.** Memory-staleness checks and bare-repros for known-blocked patterns run on the graph, not as agent honor-system.

## 5. State schema strategy

LangGraph state is a `TypedDict` with `Annotated[T, reducer]` fields. Reducers tell the graph how to merge per-node updates.

### 5.1 Principles

1. **Namespaced sub-states per phase.** `state["pickup"]`, `state["audio"]`, `state["transcripts"]`, `state["edit"]`, `state["compose"]`, `state["review"]`. A node is permitted to write only into its phase namespace plus top-level append-only lists (`errors`, `phase_feedback`, `llm_runs`).
2. **Top-level holds identity and control flow only.** `slug` and `episode_dir` are written once during pickup and immutable thereafter.
3. **Reducers by field type.**
   - Identity (`slug`, `episode_dir`): default last-write-wins.
   - Phase namespaces: shallow dict-merge custom reducer. Returning `{"edit": {"final_mp4_path": "..."}}` merges into existing `state["edit"]` without overwriting siblings.
   - Append-only lists (`phase_feedback`, `errors`, `llm_runs`): `operator.add`.
   - Per-phase iteration counters: nested in namespace, last-write-wins.
4. **Pydantic validation at namespace boundaries.** TypedDict for LangGraph runtime; nodes validate via Pydantic models before returning. Schema violation raises before checkpointer write — failure visible in Studio.
5. **`transcripts` is a top-level namespace, not nested under `edit` or `compose`.** It crosses the Phase 3/4 boundary (raw.json from Phase 3 is consumed by Phase 4 captions_layer); honest reflection of pipeline > paspartout nesting.

### 5.2 Growability v0 → v7

Each version adds namespaces and fields without modifying existing ones. `total=False` on every TypedDict means absent keys are legal — old nodes do not break when new namespaces appear.

| Version | New namespaces / fields |
|---------|--------------------------|
| v0 | `pickup` |
| v1 | `audio`, `transcripts` (raw_json_path, final_json_path, edl_hash) |
| v2 | `llm_runs` (append-only per-call telemetry); `edit.pre_scan` |
| v3 | `edit.strategy`, `edit.edl_path`, `edit.final_mp4_path`, `edit.iteration`, `edit.session_persisted`; `canon_check`; `gate_results` |
| v4 | `compose.design_md_path`, `compose.expanded_prompt_path`, `compose.beats: list[BeatState]`, `compose.captions_block_path`, `compose.index_html_path`, `compose.session_persisted` |
| v5 | per-beat sub-graph state (carried via `Send` payload, not top-level) |
| v6 | `review` (HITL approval/feedback), `phase_feedback` activated |
| v7 | `final_render` (output mp4 path, codec spec) |

### 5.3 v0 schema (full)

```python
from typing import TypedDict, Annotated
from operator import add

class PickupState(TypedDict, total=False):
    raw_path: str | None
    script_path: str | None
    resumed: bool
    idle: bool
    warning: str | None

class GraphError(TypedDict):
    node: str
    message: str
    timestamp: str

class GraphState(TypedDict, total=False):
    slug: str
    episode_dir: str
    pickup: PickupState
    errors: Annotated[list[GraphError], add]
```

## 6. Node taxonomy

All nodes belong to one of four classes. Each class has a base pattern and shared infrastructure.

### 6.1 Deterministic node — wraps Python/CLI

Runs an existing script or external CLI via `subprocess`, parses stdout (typically JSON), validates via Pydantic, returns state update. Examples: `pickup`, `isolate_audio`, `glue_remap_transcript`, `p4_scaffold`, `p4_catalog_scan`, `p3_render_segments`, `p4_assemble_index`, `studio_launch`, `p4_final_render`.

Properties: fast, idempotent on identical input state, fully unit-testable without LLM.

```python
def deterministic_node(name, cmd_factory, parser, namespace):
    def node(state):
        result = subprocess.run(cmd_factory(state), capture_output=True, text=True)
        if result.returncode != 0:
            raise NodeError(node=name, stderr=result.stderr)
        parsed = parser(result.stdout)  # Pydantic
        return {namespace: parsed.model_dump()}
    return node
```

### 6.2 Gate node — artifact validation between phases

Verifies invariants on state + on-disk artifacts. Returns `{passed: bool, violations: list[str], iteration: int}`. Conditional edge below routes to retry / interrupt / proceed.

```python
class Gate:
    name: str
    max_iterations: int = 3

    def checks(self, state) -> list[CheckResult]: ...
    def on_fail_route(self, state, violations) -> Literal["retry", "interrupt", "abort"]: ...
    def __call__(self, state) -> dict:
        results = self.checks(state)
        # appends gate_results history; emits decision
        ...
```

Concrete gates:

| Gate | Checks |
|------|--------|
| `gate:edl_ok` | EDL JSON schema; word-boundary cuts (HR 6); padding 30–200ms (HR 7) on BOTH edges; adaptive final-cut length (see below); `overlays == []`; absent `subtitles` field |

**Adaptive length check (v3.1, supersedes original fixed 25–35% pacing).** The original spec hard-coded `cut_total / source_total ∈ [0.25, 0.35]`. Canon does NOT specify a fixed fraction — Step 4 strategy emits `length_estimate_s` derived from the material itself, and the editor sub-agent brief takes a `Target runtime` parameter. The fixed bound failed empirically on a 70-second talking-head explainer where the LLM correctly produced a ~56s cut against a 62s estimate (80% retention) — gate rejected a correct EDL. v3.1 replaces the fixed bound with:

- **Strategy-anchored mode** (default, when `state.edit.strategy.length_estimate_s` is set): cut length must lie within ±20% of the estimate. Tolerance constant `LENGTH_TOLERANCE = 0.20` lives in `gates/edl_ok.py`.
- **Fallback mode** (no estimate available): cut/source ratio must lie in the wide window `[0.10, 0.95]`. Catches degenerate cases (empty EDL, unmodified passthrough) without blocking legitimate explainer cuts.

The `p3_edl_select` brief calls out HR 7 explicitly for the trailing edge — common failure mode was using a Scribe word-end timestamp as the final range's `end`, giving 0ms padding. (Source: HOM-107 retro on episode `2026-05-04-desktop-software-licensing-...`.)
| `gate:eval_ok` | ffprobe duration matches `total_duration_s` ±100ms; iteration < 3 |
| `gate:design_ok` | DESIGN.md substance: ≥2 visual references, ≥1 alternative, ≥3 anti-patterns, populated Beat→Visual Mapping |
| `gate:plan_ok` | ≥3 beats; per-boundary transition mechanism declared; per-beat catalog-vs-custom justification |
| `gate:lint` | `npx hyperframes lint` exit 0 |
| `gate:validate` | `npx hyperframes validate` exit 0; deterministic triage for headless opacity-0 artifact (regex on HTML for opacity:0 entrance + visible CSS color → mark as artifact, do not iterate palette) |
| `gate:inspect` | `npx hyperframes inspect --at <beat_timestamps>` clean or all overflow marked intentional |
| `gate:design_adherence` | hex values in index.html ⊆ DESIGN.md palette; fonts match; avoidance rules not present (best-effort grep) |
| `gate:animation_map` | animation-map.json: no `collision`, no unjustified `paced-fast`, no >1s dead zones (v5+: LLM justify-helper) |
| `gate:snapshot` | snapshot at beat timestamps; expected-visible elements per Beat→Visual Mapping present (allow 0.3s entrance offset) |
| `gate:captions_track` | `grep -c transcript.json index.html` ≥ 1 |
| `gate:static_guard` | `.hyperframes/preview.log` clean of `[StaticGuard]` / `Invalid HyperFrame contract` for 5s post-launch |

All gates pure-functional: state in, decision + state-update out. Skipping is structurally impossible.

### 6.3 LLM node — authorized CLI invocation

Builds a short task descriptor from state + Jinja2 template, dispatches to `LLMBackend`, parses through Pydantic schema, returns state update.

```python
class LLMNode:
    name: str
    tier: Literal["cheap", "smart"]
    needs_tools: bool
    backends: list[str]            # preference order
    task_template: str             # Jinja2 — short, anchors to canon SKILL.md path
    output_schema: type[BaseModel]
```

The task descriptor is intentionally short (15–40 lines): task statement, inputs from state, output schema, one-line reference to canonical `SKILL.md` for taste guidance. **It does not enumerate Hard Rules** — those become gates downstream. Schema absence of forbidden fields (e.g., `subtitles` in EDL) replaces "do not include X" instructions.

LLM nodes by phase:

| Node | tier | needs_tools | output |
|------|------|-------------|--------|
| `p3_pre_scan` | cheap | yes | `PreScanReport(slips: list[Slip])` |
| `p3_strategy` | smart | no | `Strategy(shape, takes, grade, pacing, length_estimate)` — no animations, no subtitles |
| `p3_edl_select` | smart | yes | canonical `EDL` with `overlays: []` and no `subtitles` field |
| `p3_self_eval` | cheap | yes | `EvalReport(issues, pass)` |
| `p3_persist_session` | cheap | yes | appends Session block to `<edit>/project.md` |
| `p4_design_system` | smart | yes | `DesignDoc(palette, typography, refs, alternatives, anti_patterns, beat_visual_mapping)` — amended cheap → smart in HOM-118 (visual identity is brand-defining creative work; cheap models empirically hollow it out — see `feedback_creative_nodes_flagship_tier`) |
| `p4_prompt_expansion` | smart | yes | `ExpandedPrompt(expanded_prompt_path)` — amended cheap → smart in HOM-119. Canon `references/prompt-expansion.md`: *"the quality gap between a single-pass composition and a multi-scene-pipeline composition comes from this step."* Highest-leverage creative node in Phase 4 — see `feedback_creative_nodes_flagship_tier` |
| `p4_plan` | smart | yes | `CompositionPlan(narrative_arc, rhythm, beats, transitions)` — amended cheap → smart in HOM-120. Plan determines pacing, energy peaks, scene rhythm, and per-boundary transition mechanism — all creative direction. See `feedback_creative_nodes_flagship_tier` |
| `p4_beat_<n>` (Send) | smart | yes | `BeatArtifact(html_path, beat_id, duration)` |
| `p4_captions_layer` | cheap | yes | `CaptionsBlock(html, css)` |
| `p4_persist_session` | cheap | yes | appends Phase 4 Session block to `<edit>/project.md` |

### 6.4 Fan-out node — parallel dispatch via `Send`

```python
def dispatch_beats(state) -> list[Send]:
    return [
        Send("p4_beat_one", {"beat": b, "design_md": ..., "expanded_prompt": ...})
        for b in state["compose"]["plan"]["beats"]
    ]

graph.add_conditional_edges("p4_plan_passed_gate", dispatch_beats, ["p4_beat_one"])
```

Wall-time = max(slot/beat times). State per dispatch isolated via payload. Reduce on next node merges results through the `add` reducer on the `compose.beats[]` list.

### 6.5 Where shared code lives

```
graph/src/edit_episode_graph/
  state.py
  graph.py
  nodes/
    _deterministic.py           # class 1 factory
    _llm.py                     # class 3 base + brief rendering
    pickup.py, isolate_audio.py, p3_*.py, p4_*.py, ...
  gates/
    _base.py                    # class 2 base
    edl_ok.py, design_ok.py, ...
  briefs/
    p3_strategy.j2, p4_design_system.j2, ...
  backends/
    _base.py, _router.py, claude.py, codex.py, gemini.py
  config.yaml                   # backend preference + per-node overrides (v2+)
```

## 7. LLM backend abstraction

### 7.1 Interface

```python
class LLMBackend(Protocol):
    name: str                                   # "claude" | "codex" | "gemini"
    capabilities: BackendCapabilities           # has_tools, supports_streaming, max_concurrent

    def supports(self, req: NodeRequirements) -> bool: ...

    def invoke(
        self,
        task: str,
        *,
        tier: Literal["cheap", "smart"],
        cwd: Path,
        timeout_s: int,
        output_schema: type[BaseModel] | None,
        allowed_tools: list[str] | None = None,
    ) -> InvokeResult: ...
```

Nodes declare requirements (`tier`, `needs_tools`, `backends` preference list); they do not name a provider. `BackendRouter.resolve(node)` selects the first backend that satisfies requirements and is available.

### 7.2 Concrete backends

| Backend | CLI | Auth | tier=cheap | tier=smart | has_tools |
|---------|-----|------|-----------|-----------|-----------|
| `claude` | `claude -p "<task>" --output-format stream-json --model <id>` | Claude Code subscription | `claude-sonnet-4-6` | `claude-opus-4-7` | yes (Read/Bash/Grep/Edit) |
| `codex` | `codex exec "<task>" --model <id> --json` | ChatGPT subscription | `gpt-5-mini` | `gpt-5` | yes |
| `gemini` | `gemini -p "<task>"` | Google subscription | `gemini-2.5-flash` | `gemini-2.5-pro` | yes |

Tier IDs are internal to each backend. The graph only knows `cheap`/`smart`. Switching providers does not require node changes.

### 7.3 `InvokeResult`

```python
class InvokeResult:
    raw_text: str                  # final assistant message
    structured: dict | None         # parsed via output_schema if provided
    tokens_in: int | None
    tokens_out: int | None
    wall_time_s: float
    model_used: str                 # exact ID for traceability
    backend_used: str
    tool_calls: list[ToolCall]      # for Studio observability
```

Tool calls are streamed from the CLI (`--output-format stream-json` for Claude Code, `--json` for Codex) and re-emitted via `dispatch_custom_event()` so Studio shows them as nested steps within the LLM-node trace.

### 7.4 Failover policy (default; per-node overridable)

1. **Auth failure** → next backend; record in `state["errors"]`.
2. **Rate limit** → 30s pause, retry once on same backend; if still rate-limited → next backend.
3. **Schema validation failure** → retry on same backend up to 2 times with feedback message; on third failure → next backend.
4. **Timeout** → next backend.
5. **CLI error** (generic non-zero exit, `BackendCLIError`) → next backend; attempt records `returncode` + `stderr_preview` (first 200 chars) for diagnosis.
6. **Other `BackendError` / `OSError`** → next backend; attempt records `exc_type`.
7. **All backends exhausted** → `interrupt()` with choices: wait / change preference / abort.

Programmer errors (`AttributeError`, `TypeError`, etc. from a parser regression) are **not caught** by the router — they propagate to the calling node so the bug surfaces immediately rather than burning failover attempts under `reason: "other"`.

All attempts logged to `state["llm_runs"][node_name]` (append-only): backend, model, wall_time, success/fail, reason. Visible per-thread in Studio.

### 7.5 Concurrency control

`Send` fan-out (5 beats → 5 parallel `claude` processes) can trip subscription rate limits. Per-backend semaphores (default `claude=2, codex=2, gemini=3`) gate `invoke()`. Excess invocations queue; Studio shows them as `pending`.

### 7.6 Per-node configuration

```yaml
# graph/config.yaml — read by build_graph() at langgraph dev startup
backend_preference: ["claude", "codex"]   # global default failover order

node_overrides:
  p4_design_system:
    tier: smart                            # amended HOM-118 — visual identity is creative
    backend_preference: ["claude"]         # prefer Opus 4.7 for brand-defining work
  "p4_beat_*":                             # glob-pattern for all beat nodes
    tier: smart
    backend_preference: ["claude"]         # creative — prefer Opus
```

Restart of `langgraph dev` picks up changes without code edits.

### 7.7 Windows considerations

`claude.exe` is a `.cmd` shim on Windows. `subprocess.run` with `shell=False` may yield `EINVAL` on `.cmd` shims (same Node.js Windows quirk class as `npm.cmd` documented in `feedback_bundled_helper_path.md`). Implementation must use explicit `claude.exe` path or `shell=True` with proper quoting. Resolved at v2 implementation time, not v0.

## 8. Phased build sequence v0 → v7

Each version is one feature branch + PR. A version is "closed" when it works end-to-end on a real episode and replaces the corresponding part of `/edit-episode`. The slash command is unchanged until v7.

### v0 — Bootstrap

- `graph/` skeleton, `pyproject.toml`, `langgraph.json`, SQLite checkpointer, README
- `state.py`: one namespace `pickup`
- One node `pickup` wrapping `scripts/pickup.py` via subprocess
- `idle?` conditional edge → END
- Skeletons for `backends/` (empty classes), `gates/`, `briefs/` — for forward structure visibility, no code yet
- Run via `langgraph dev`; verify Studio, checkpointer, idempotency on re-run

**Replaces in `/edit-episode`:** nothing. Parallel implementation only.

### v1 — Full LLM-free pipeline coverage

- Nodes: `isolate_audio`, `glue_remap_transcript`, `p4_scaffold`
- Conditional edges: `skip_phase2?`, `skip_phase3?`, `skip_phase4?`
- Namespaces: `audio`, `transcripts`, `compose` (scaffold paths only)
- `preflight_canon` as a passthrough stub (real impl in v3)
- Test on an episode where `final.mp4` already exists: skip Phase 3, run remap, scaffold, halt cleanly before LLM

**Replaces:** Phase 1, 2, glue, scaffold of `/edit-episode` for users with pre-existing `final.mp4`.

### v2 — First LLM node + backend abstraction

- Full `ClaudeCodeBackend` implementation with `--output-format stream-json` parsing and Studio event passthrough
- `CodexBackend` second
- `BackendRouter` with failover policy
- `config.yaml` for per-node tier/backend overrides
- Concurrency semaphore
- First LLM node: `p3_pre_scan` (cheap, narrow output, low-risk entry point)

### v3 — Full Phase 3 + first gates

- LLM nodes: `p3_strategy`, `p3_edl_select`, `p3_self_eval`, `p3_persist_session` (`p3_pre_scan` already shipped in v2)
- Deterministic: `p3_inventory`, `p3_render_segments` (no overlays, no subtitles — those are Phase 4)
- Gates: `gate:edl_ok` (validates `overlays: []` and absent `subtitles` field), `gate:eval_ok` (loop ≤ 3 → escalate)
- `preflight_canon` v1: real memory-staleness check + bare-repro for known-blocked patterns

**Replaces:** Phase 3 of `/edit-episode`. Output (final.mp4 raw cut, no animations or subtitles) — animation/subtitle parity with the legacy pipeline is delegated to Phase 4 hyperframes.

### v4 — Phase 4 sans HITL

- LLM: `p4_design_system`, `p4_prompt_expansion`, `p4_plan`, `p4_captions_layer`, `p4_persist_session`
- Fan-out: `p4_beats_dispatch`
- Deterministic: `p4_catalog_scan`, `p4_assemble_index`, `studio_launch`
- All Quality Check gates (lint, validate, inspect, design_adherence, animation_map, snapshot, captions_track, static_guard)
- No `user_review` loop yet (v6); studio_launch ends the run

**Replaces:** Phase 4 of `/edit-episode` through studio launch.

### v5 — Per-beat sub-graphs + retry-loops

- Each `Send` target expands into a sub-graph: `beat_layout` (LLM, static CSS) → `beat_animate` (LLM, GSAP entrances) → `beat_kills` (deterministic insertion of `tl.set` deterministic kills) → `beat_validate` (sub-gate: track-index uniqueness, no exit-tweens on non-final)
- Per-beat retry loop with sub-gate feedback
- Refinements: `gate:design_adherence` per-beat (faster retry); `gate:animation_map` LLM-justify helper for paced-fast accents (cheap tier)

**Eliminates:** the class of bugs from `retro-2026-05-02` (missing `tl.set` kills).

### v6 — HITL + feedback routing

- `user_review` node via `interrupt()`
- `review_router` conditional edge: approved → `p4_final_render`; feedback → routes to phase with `phase_feedback` injection
- Iteration counter; ≥3 retries on same phase → escalation `interrupt()`

**Replaces:** the `studio launch + done` ending of `/edit-episode`.

### v7 — Cutover

- `/edit-episode` becomes a thin client: posts to `localhost:2024/threads/<slug>/runs`, streams events to chat
- 300-line brief deleted (preserved in git history)
- README updates; deprecate orchestrator-house memory entries that referred to brief contents

### Dependencies

```
v0 → v1 → v2 → v3 → v4 → v5 → v6 → v7
            \    \    \
             \    \    └── requires per-node config from v2
              \    └─────── requires backends from v2
               └─────────── requires state namespaces from v1
```

Linear; no parallelization (would require dual mocking and integration thrash).

### Stop-points if budget is constrained

- **v0 + v1** = useful sandbox for script debugging and idempotency observation. Does not replace `/edit-episode`.
- **v0 + v1 + v2 + v3** = graph edits videos in parallel with `/edit-episode`.
- **v0..v6** = full replacement except slash-command facade. v7 is cosmetic.

## 9. v0 concrete shape

### 9.1 File layout

```
graph/
├── pyproject.toml
├── langgraph.json
├── README.md
├── .gitignore                             # .langgraph_api/, __pycache__/, .venv/
└── src/edit_episode_graph/
    ├── __init__.py
    ├── state.py
    ├── graph.py
    ├── nodes/
    │   ├── __init__.py
    │   ├── _deterministic.py              # factory
    │   └── pickup.py
    ├── gates/
    │   ├── __init__.py
    │   └── _base.py                       # skeleton, populated in v3
    ├── briefs/
    │   └── __init__.py                    # empty, populated in v2
    └── backends/
        ├── __init__.py
        ├── _base.py                       # Protocol skeleton
        ├── _router.py                     # raises NotImplementedError
        ├── claude.py                      # skeleton
        ├── codex.py                       # skeleton
        └── gemini.py                      # skeleton
```

Skeletons for `gates/_base.py`, `briefs/`, `backends/*` are created with `pass`-bodies and module-level docstring describing intended responsibility. They anchor structure and make imports resolve. No functional code in v0.

### 9.2 `pyproject.toml` (full)

```toml
[project]
name = "edit-episode-graph"
version = "0.0.1"
description = "LangGraph orchestrator for the anticodeguy video editing pipeline"
requires-python = ">=3.11"
dependencies = [
    "langgraph>=0.2.60",
    "langgraph-checkpoint-sqlite>=2.0",
    "pydantic>=2.7",
]

[project.optional-dependencies]
dev = [
    "langgraph-cli[inmem]>=0.1.55",   # provides `langgraph dev` + Studio
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/edit_episode_graph"]
```

Notes:
- `langgraph` itself is the runtime. `langgraph-cli[inmem]` is the dev tool that provides the `langgraph dev` command and the Studio UI. We pin it under `[dev]` because production deployment (post-v7) won't need it.
- `langgraph-checkpoint-sqlite` is the SqliteSaver used in §9.5. As of LangGraph 0.2.x it ships in a separate package, not in core.
- Python 3.11+ — LangGraph requires it; this is also our project default.
- Build backend is `hatchling` (lightweight, no extra dependencies). Could swap for `setuptools`; choice is non-load-bearing.

### 9.3 `langgraph.json`

```json
{
  "dependencies": ["."],
  "graphs": {
    "edit_episode": "./src/edit_episode_graph/graph.py:graph"
  },
  "env": ".env"
}
```

A minimal `.env` file (created empty in v0) is referenced — `langgraph dev` reads it to populate process env. Variables that v2+ may need (e.g., `ELEVENLABS_API_KEY` for `isolate_audio`) live there. v0 does not require any.

### 9.4 `state.py` (full)

See §5.3.

### 9.5 `nodes/pickup.py`

```python
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]   # graph/src/.../nodes → repo root

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def pickup_node(state):
    cmd = [sys.executable, "-m", "scripts.pickup", "--inbox", "inbox", "--episodes", "episodes"]
    if state.get("slug"):
        cmd += ["--slug", state["slug"]]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        return {"errors": [{"node": "pickup", "message": result.stderr, "timestamp": _now()}]}

    parsed = json.loads(result.stdout)
    return {
        "slug": parsed["slug"],
        "episode_dir": parsed["episode_dir"],
        "pickup": {
            "raw_path": parsed.get("raw_path"),
            "script_path": parsed.get("script_path"),
            "resumed": parsed.get("resumed", False),
            "idle": parsed.get("idle", False),
            "warning": parsed.get("warning"),
        },
    }
```

### 9.6 `graph.py` (full)

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from .state import GraphState
from .nodes.pickup import pickup_node


def _route_after_pickup(state) -> str:
    if state.get("errors"):
        return END
    if state.get("pickup", {}).get("idle"):
        return END
    # v0: pickup is the only node; v1 will replace this with "isolate_audio".
    return END


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("pickup", pickup_node)
    g.set_entry_point("pickup")
    g.add_conditional_edges("pickup", _route_after_pickup)
    return g.compile(
        checkpointer=SqliteSaver.from_conn_string(
            str(Path(__file__).parent.parent.parent / ".langgraph_api" / "checkpoints.sqlite")
        )
    )


graph = build_graph()
```

Checkpointer location: `graph/.langgraph_api/checkpoints.sqlite` (isolated from repo root). Migrate to repo-root `.langgraph_api/` later only if multiple graphs appear.

### 9.7 Run

```bash
cd graph
python -m venv .venv
# PowerShell: .\.venv\Scripts\Activate.ps1
# Bash: source .venv/Scripts/activate
pip install -e ".[dev]"      # core deps + langgraph-cli[inmem] for `langgraph dev`
langgraph dev                # starts API on :2024 + opens Studio URL in stdout
```

Open the Studio URL printed to stdout. Create a new thread with arbitrary `thread_id` (or use slug). Run with input `{"slug": "<inbox-stem>"}` or `{}` for auto-pick.

### 9.8 Definition of done for v0

1. `langgraph dev` starts cleanly; Studio UI opens.
2. Run on a real `inbox/<slug>.<ext>` produces `episodes/<slug>/raw.<ext>` (and `script.txt` if paired).
3. Run with empty `inbox/` and no slug → `pickup.idle = true`, graph reaches END without error.
4. Re-run with same slug → `pickup.resumed = true`, no file duplication.
5. Failure case (e.g., two videos with same stem) → `errors[]` populated, run terminates, Studio shows error.
6. SQLite checkpoint at `graph/.langgraph_api/checkpoints.sqlite` written; thread history visible in Studio.

### 9.9 Out of scope for v0

- No tests (deferred to v1, when 3+ nodes justify infra investment).
- No real backend implementations (skeletons only).
- No `preflight_canon` (real impl in v3).
- No namespaces beyond `pickup`.
- `/edit-episode` is not modified.

## 10. Explicit non-goals (whole migration)

- **No upstream changes to `video-use` or `hyperframes`.** All glue stays in this orchestrator (CLAUDE.md "External skill canon").
- **No re-implementation of canonical logic.** Every canon-driven step either invokes the canonical helper (`render.py`, `npx hyperframes lint`, etc.) or relies on the LLM reading live `SKILL.md` via tools.
- **No replacement of subprocess CLI with Anthropic/OpenAI Python SDKs.** Subscription-only constraint is permanent, not transitional.
- **No abandonment of `/edit-episode`.** It remains the user-facing entry point. v7 makes it a thin client over the LangGraph API; it is not deleted.
- **No cross-episode shared state.** Each slug is a thread. No global mutable data between runs.

## 11. Open decisions (to revisit when relevant)

- **`gate:design_adherence` avoidance-rule check fidelity.** Strict text-grep is the v4 default. If false-negatives accumulate (avoidance-rule violations passing the gate), an LLM-augmented version (cheap tier) may be added in v5+.
- **`gate:animation_map` LLM-justify helper.** v4 is strict deterministic (any flag → fail). v5+ may add a cheap LLM helper that distinguishes intentional `paced-fast` accents from bugs.
- **Final render storage.** v6 places `final.mp4` at `episodes/<slug>/hyperframes/render/<slug>.mp4`. May need a delivery-format selector (1080p vs 4K, codec) — deferred until concrete request.
- **External-UI front-end.** LangGraph Studio is sufficient for v0–v7. Custom web UI (Next.js, Streamlit, tray app) is post-v7 and out of this spec.

## 12. References

- `CLAUDE.md` — branching workflow, external skill canon rule, bare-repro methodology, bundled helper path rule
- `.claude/commands/edit-episode.md` — current orchestration brief (target of decomposition)
- `~/.claude/skills/video-use/SKILL.md` — Phase 3 canon (§"The process", §"Hard Rules", §"Editor sub-agent brief", §"Animations", §"Memory")
- `~/.agents/skills/hyperframes/SKILL.md` — Phase 4 canon (§"Approach" Step 1/2/3, §"Layout Before Animation", §"Scene Transitions", §"Output Checklist", §"Quality Checks")
- `docs/retros/retro-2026-05-02-raw-phase4-omissions.md` — failure mode that motivates structural enforcement
- `docs/retros/retro-2026-05-01-liquid-glass-subcomp-loader.md` — `<template>` + `data-composition-src` blocker (#589); informs `preflight_canon` and inline-vs-subcomp routing
- `MEMORY.md` entries `feedback_external_skill_canon`, `feedback_branch_pr_workflow`, `feedback_hf_subcomp_loader_*` — operating constraints
- LangGraph docs: state reducers, `Send` API, `interrupt()`, SqliteSaver checkpointer, `langgraph dev` Studio
