# HOM-166 Brief Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the `state.brief` namespace, a deterministic `resolve_episode_brief` node that composes profile + brand + episode-intent into a per-episode `brief.resolved.yaml` (+ `brief.fingerprint`), loosen the three creative schemas to carry prose rationale, fold `brief.fingerprint` into every creative-node cache key, and wire the per-episode `{{ profile.* }}` / `{{ brand.* }}` blocks into the four nodes that register profile/brand anchors.

**Architecture:** `resolve_episode_brief` is a Class-1 deterministic in-process node (like `rehydrate_skip_phase3`), placed on the common path between pickup/isolate_audio and `preflight_canon` so it runs before any creative node on **every** path (Phase 3 and the Phase-3-skip → Phase 4 path). It reuses HOM-167's path-injectable `brief.loaders` (profile/brand pydantic models) and HOM-114's `_canon_loader.{load_profile_blocks,load_brand_blocks,canon_fingerprint}`. Two complementary invalidation channels: (1) `brief.fingerprint` — a global per-episode sha256 over the resolved YAML config (profile.yaml + palette.yaml + defaults.yaml + intent selection), folded into creative cache-key `extras`; (2) `canon_fingerprint(node, profile_dir, brand_dir)` — per-node digest of the verbatim `house-style.md` / `brand.md` markdown sections, already shipped by HOM-114, now fed the resolved per-episode dirs.

**Tech Stack:** Python 3, LangGraph (`StateGraph`, `CachePolicy`), Pydantic v2, Jinja2 briefs, PyYAML, pytest. Two test roots: `graph/tests` (run via `graph/.venv/Scripts/python.exe -m pytest graph/tests`) and repo-level `tests/` (run via `python -m pytest tests`).

**Spec:** `docs/superpowers/specs/2026-05-07-resolved-brief-profiles-brand-architecture.md` §5 + §6 + §7 (+ §9 amendment for the `{{ profile.* }}` / `{{ brand.* }}` render-context wiring).

**Scope note — deferred to later M6 tickets (do NOT build here):**
- Music selection / `brief.music` population (§11) → HOM-174. `brief.music` is `None` in HOM-166; the schema slot exists for forward-compat. `brand/anticodeguy/music/` is empty, so no track resolution / LUFS / license validation runs.
- CLI `--profile/--brand/--music-track` overrides (§16) → HOM-79. HOM-166 reads an optional `state["brief_overrides"]` dict as the forward-compat override channel; the priority chain is testable without a CLI.
- Converse interrupt / narrative_context capture (§8) → HOM-168. HOM-166 only passes `intent.yaml.narrative_context` straight through.

---

## File Structure

**Created:**
- `graph/src/edit_episode_graph/nodes/resolve_episode_brief.py` — the deterministic resolver node, its `CACHE_POLICY`, and the `profile_dir_for` / `brand_dir_for` state→dir helpers' callers.
- `graph/tests/test_resolve_episode_brief_node.py` — unit tests for resolution priority, canonical forcing, fail-loud validation, fingerprint, brief.resolved.yaml shape.
- `tests/test_brief_fingerprint_invalidation.py` — palette-change-invalidates / brand.md-change-stable fingerprint tests + canonical-mode smoke.

**Modified:**
- `graph/src/edit_episode_graph/state.py` — add `BriefMusicState`, `BriefState`; add `brief` channel to `GraphState`.
- `graph/src/edit_episode_graph/_caching.py` — add `brief_fingerprint(state)` helper.
- `graph/src/edit_episode_graph/_paths.py` — add `profile_dir_for(state)` / `brand_dir_for(state)` pure path helpers.
- `graph/src/edit_episode_graph/config.py` — add `default_profile_id` / `default_brand_id` to `RouterConfig` + loader.
- `graph/src/edit_episode_graph/graph.py` — wire `resolve_episode_brief` between pickup/isolate_audio and preflight_canon.
- `graph/src/edit_episode_graph/nodes/_routing.py` — `route_after_pickup` retargets non-END outcome to `resolve_episode_brief`.
- `graph/src/edit_episode_graph/schemas/p3_strategy.py` — drop `extra="forbid"`, add `rationale` + `taste_notes`.
- `graph/src/edit_episode_graph/schemas/p4_design_system.py` — add `rationale` + `cross_scene_logic`.
- `graph/src/edit_episode_graph/schemas/p4_plan.py` — add `rationale` + `cross_scene_logic`.
- 9 creative node `_cache_key`s (fold `brief.fingerprint`): `p3_pre_scan.py`, `p3_self_eval.py`, `p3_strategy.py`, `p3_edl_select.py`, `p4_design_system.py`, `p4_prompt_expansion.py`, `p4_plan.py`, `p4_beat.py`, `p4_captions_layer.py` (each + `_CACHE_VERSION` bump).
- 4 profile/brand-consuming nodes (render ctx + dir-fed `canon_fingerprint`): `p3_strategy.py`, `p3_edl_select.py`, `p4_design_system.py`, `p4_prompt_expansion.py`.
- 5 briefs: `briefs/p3_strategy.j2`, `briefs/p3_edl_select.j2`, `briefs/p4_design_system.j2`, `briefs/p4_prompt_expansion.j2`, `briefs/p4_plan.j2`.
- `briefs/_macros.j2` — add a `profile_brand_section` macro.
- `graph/tests/test_p4_topology.py` — add node + edges.
- `tests/_helpers/brief_render_contexts.py` — profile/brand placeholders + new schema-field context.
- `tests/snapshots/briefs/{p3_strategy,p3_edl_select,p4_design_system,p4_prompt_expansion,p4_plan}.txt` — regenerated.
- `tests/test_disk_io_allowlist.py` — allowlist `resolve_episode_brief.py`.
- `graph/src/edit_episode_graph/nodes/halt_llm_boundary.py` — mention `brief.resolved.yaml` if it enumerates pipeline artifacts (verify during Task 12).

---

## Task 1: `state.brief` namespace

**Files:**
- Modify: `graph/src/edit_episode_graph/state.py`
- Test: `graph/tests/test_state.py`

- [ ] **Step 1: Add the TypedDicts and channel.** In `state.py`, add before `class GraphState` (e.g. after `SessionState`):

```python
class BriefMusicState(TypedDict, total=False):
    """Resolved music selection (spec §5). HOM-166 always leaves this ``None`` —
    music selection + library substrate land in HOM-174/HOM-175 (§11). The slot
    exists so the schema is forward-compatible and creative nodes can read
    ``brief.music`` unconditionally."""
    track_id: str
    asset_path: str
    volume_db: float
    fade_in_s: float
    fade_out_s: float
    license_note: str
    lufs_integrated: float


class BriefState(TypedDict, total=False):
    """Per-episode resolved context (spec §5). Written once by
    ``resolve_episode_brief`` before any creative node. ``fingerprint`` is a
    sha256 over the canonicalized resolved YAML config (profile.yaml +
    palette.yaml + defaults.yaml + intent selection + narrative_context +
    music); it is folded into every creative node's ``make_llm_key`` extras so
    a brand/profile/intent edit invalidates exactly the creative nodes (and
    nothing deterministic). ``brand_id`` is ``None`` for the ``canonical``
    regression profile (brand layer disabled)."""
    profile_id: str
    brand_id: str | None
    resolved_brief_path: str
    narrative_context: str | None
    music: BriefMusicState | None
    fingerprint: str
```

Then add to `GraphState` (after the `session` channel):

```python
    # HOM-166: per-episode resolved context (profile + brand + intent) composed
    # by `resolve_episode_brief` before Phase 3. dict_merge so a future
    # narrative_context update (HOM-168 Converse) merges without clobbering the
    # initial resolution. Pre-HOM-166 checkpoints carry no `brief` field —
    # total=False keeps them parsing.
    brief: Annotated[BriefState, dict_merge]
```

- [ ] **Step 2: Write the migration/parse test.** Append to `graph/tests/test_state.py`:

```python
def test_brief_channel_optional_and_merges():
    from edit_episode_graph.state import GraphState, dict_merge
    # absent brief parses (forward-compat with pre-HOM-166 checkpoints)
    assert "brief" not in {}  # trivially: total=False, no brief required
    left = {"profile_id": "talking-head-portrait", "brand_id": "anticodeguy"}
    right = {"narrative_context": "ep about X"}
    merged = dict_merge(left, right)
    assert merged["profile_id"] == "talking-head-portrait"
    assert merged["narrative_context"] == "ep about X"
```

- [ ] **Step 3: Run.** `graph/.venv/Scripts/python.exe -m pytest graph/tests/test_state.py -q` → PASS.

- [ ] **Step 4: Commit.**

```bash
git add graph/src/edit_episode_graph/state.py graph/tests/test_state.py
git commit -m "HOM-166: add state.brief namespace (BriefState + BriefMusicState)"
```

---

## Task 2: `brief_fingerprint` helper + project-default config

**Files:**
- Modify: `graph/src/edit_episode_graph/_caching.py`
- Modify: `graph/src/edit_episode_graph/config.py`
- Modify: `graph/config.yaml`
- Test: `graph/tests/test_config.py`

- [ ] **Step 1: Add the fingerprint helper.** Append to `_caching.py`:

```python
def brief_fingerprint(state: Any) -> str:
    """Return ``state.brief.fingerprint`` or a stable nonce when no brief is set.

    Folded into every creative node's ``make_llm_key`` extras (HOM-166). During
    LangGraph graph introspection (``compiled.get_graph()``) the key_func runs
    against the channel default — no ``brief`` — so we emit ``"no-brief"``; a
    real run always carries a resolved fingerprint from ``resolve_episode_brief``.
    """
    if not isinstance(state, dict):
        return "no-brief"
    return ((state.get("brief") or {}).get("fingerprint")) or "no-brief"
```

- [ ] **Step 2: Add project-default fields to config.** In `config.py`, add to `RouterConfig` dataclass:

```python
    # HOM-166: project-default profile/brand selection (spec §6). Resolution
    # priority is CLI/override > intent.yaml > THESE defaults. canonical profile
    # forces brand_id=None regardless.
    default_profile_id: str = "talking-head-portrait"
    default_brand_id: str = "anticodeguy"
```

In `load_config`, add to the `RouterConfig(...)` construction:

```python
        default_profile_id=str(raw.get("default_profile_id") or "talking-head-portrait"),
        default_brand_id=str(raw.get("default_brand_id") or "anticodeguy"),
```

And in the permissive fallback `RouterConfig(...)` inside `load_default_config` (no file case), the dataclass defaults already cover it — no change needed there.

- [ ] **Step 3: Document defaults in config.yaml.** Add near the top of `graph/config.yaml` (after `backend_preference:`):

```yaml
# HOM-166: project-default profile/brand for resolve_episode_brief (spec §6).
# Priority: state.brief_overrides > episodes/<slug>/intent.yaml > these.
default_profile_id: talking-head-portrait
default_brand_id: anticodeguy
```

- [ ] **Step 4: Test config defaults.** Append to `graph/tests/test_config.py`:

```python
def test_brief_defaults_present(tmp_path):
    from edit_episode_graph.config import load_config
    p = tmp_path / "c.yaml"
    p.write_text("backend_preference: [claude]\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.default_profile_id == "talking-head-portrait"
    assert cfg.default_brand_id == "anticodeguy"
    p.write_text("default_profile_id: explainer\ndefault_brand_id: acme\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.default_profile_id == "explainer"
    assert cfg.default_brand_id == "acme"
```

- [ ] **Step 5: Run + commit.**

```bash
graph/.venv/Scripts/python.exe -m pytest graph/tests/test_config.py -q
git add graph/src/edit_episode_graph/_caching.py graph/src/edit_episode_graph/config.py graph/config.yaml graph/tests/test_config.py
git commit -m "HOM-166: brief_fingerprint helper + default_profile_id/brand_id config"
```

---

## Task 3: `_paths` profile/brand dir helpers

**Files:**
- Modify: `graph/src/edit_episode_graph/_paths.py`
- Test: `graph/tests/test_paths.py`

- [ ] **Step 1: Add the helpers.** Append to `_paths.py` (module level, after `scripts_root`):

```python
def profile_dir_for(state: dict) -> Path | None:
    """Resolve ``state.brief.profile_id`` to ``<repo>/profiles/<id>`` or ``None``.

    Used by creative nodes for ``load_profile_blocks`` + dir-fed
    ``canon_fingerprint`` (HOM-166). ``None`` when no brief is bound (graph
    introspection / pre-resolve) so ``canon_fingerprint(node, None, ...)`` keeps
    the HOM-377 skill-only back-compat digest. Pure path build — no I/O."""
    pid = (state.get("brief") or {}).get("profile_id") if isinstance(state, dict) else None
    return (repo_root() / "profiles" / pid) if pid else None


def brand_dir_for(state: dict) -> Path | None:
    """Resolve ``state.brief.brand_id`` to ``<repo>/brand/<id>`` or ``None``
    (``None`` for the canonical profile or pre-resolve introspection)."""
    bid = (state.get("brief") or {}).get("brand_id") if isinstance(state, dict) else None
    return (repo_root() / "brand" / bid) if bid else None
```

- [ ] **Step 2: Test.** Append to `graph/tests/test_paths.py`:

```python
def test_profile_brand_dir_for():
    from edit_episode_graph._paths import profile_dir_for, brand_dir_for, repo_root
    assert profile_dir_for({}) is None
    assert brand_dir_for({}) is None
    st = {"brief": {"profile_id": "talking-head-portrait", "brand_id": "anticodeguy"}}
    assert profile_dir_for(st) == repo_root() / "profiles" / "talking-head-portrait"
    assert brand_dir_for(st) == repo_root() / "brand" / "anticodeguy"
    assert brand_dir_for({"brief": {"profile_id": "canonical", "brand_id": None}}) is None
```

- [ ] **Step 3: Run + commit.**

```bash
graph/.venv/Scripts/python.exe -m pytest graph/tests/test_paths.py -q
git add graph/src/edit_episode_graph/_paths.py graph/tests/test_paths.py
git commit -m "HOM-166: _paths.profile_dir_for / brand_dir_for state helpers"
```

---

## Task 4: `resolve_episode_brief` node (TDD)

**Files:**
- Create: `graph/src/edit_episode_graph/nodes/resolve_episode_brief.py`
- Create: `graph/tests/test_resolve_episode_brief_node.py`
- Modify: `tests/test_disk_io_allowlist.py`

This node is deterministic and in-process (NOT a subprocess wrapper). It reads `episodes/<slug>/intent.yaml`, the resolved `profiles/<id>/` and `brand/<id>/` dirs via HOM-167's loaders, composes the resolved brief, computes the fingerprint, writes `episodes/<slug>/brief.resolved.yaml`, and returns `{"brief": {...}, "notices": [...]}`. It **raises** `BriefResolutionError` on operator misconfiguration (missing profile dir, unparseable YAML) — fail-loud per spec §6.

- [ ] **Step 1: Write the failing tests.** Create `graph/tests/test_resolve_episode_brief_node.py`:

```python
"""Unit tests for resolve_episode_brief (HOM-166, spec §6)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from edit_episode_graph.nodes.resolve_episode_brief import (
    BriefResolutionError,
    resolve_episode_brief_node,
    _resolve_selection,
)


def _seed_repo(tmp_path: Path) -> None:
    """Minimal profiles/ + brand/ tree under an HOMESTUDIO_REPO_ROOT override."""
    prof = tmp_path / "profiles" / "talking-head-portrait"
    prof.mkdir(parents=True)
    (prof / "profile.yaml").write_text(
        "profile_id: talking-head-portrait\n"
        "human_label: TH\n"
        "captions: {enabled: true}\n"
        "music: {enabled: true}\n"
        "cta: {enabled: true}\n",
        encoding="utf-8",
    )
    canon = tmp_path / "profiles" / "canonical"
    canon.mkdir(parents=True)
    (canon / "profile.yaml").write_text(
        "profile_id: canonical\nhuman_label: Canon\n"
        "captions: {enabled: false}\nmusic: {enabled: false}\ncta: {enabled: false}\n",
        encoding="utf-8",
    )
    brand = tmp_path / "brand" / "anticodeguy"
    brand.mkdir(parents=True)
    (brand / "palette.yaml").write_text("colors: {bg: '#000000', fg: '#ffffff'}\n", encoding="utf-8")
    (brand / "defaults.yaml").write_text("motion_language: {}\ncaptions: {}\n", encoding="utf-8")


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    _seed_repo(tmp_path)
    monkeypatch.setenv("HOMESTUDIO_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    (tmp_path / "episodes" / "ep1").mkdir(parents=True)
    return tmp_path


def test_default_selection(repo):
    pid, bid = _resolve_selection({"slug": "ep1"})
    assert pid == "talking-head-portrait"
    assert bid == "anticodeguy"


def test_intent_overrides_default(repo):
    (repo / "episodes" / "ep1" / "intent.yaml").write_text(
        "profile_id: canonical\n", encoding="utf-8"
    )
    pid, bid = _resolve_selection({"slug": "ep1"})
    assert pid == "canonical"
    assert bid is None  # canonical forces brand off


def test_state_override_beats_intent(repo):
    (repo / "episodes" / "ep1" / "intent.yaml").write_text(
        "profile_id: canonical\n", encoding="utf-8"
    )
    pid, _ = _resolve_selection({"slug": "ep1", "brief_overrides": {"profile_id": "talking-head-portrait"}})
    assert pid == "talking-head-portrait"


def test_node_writes_resolved_yaml_and_state(repo):
    out = resolve_episode_brief_node({"slug": "ep1"})
    brief = out["brief"]
    assert brief["profile_id"] == "talking-head-portrait"
    assert brief["brand_id"] == "anticodeguy"
    assert brief["music"] is None
    assert len(brief["fingerprint"]) == 64
    resolved_path = Path(brief["resolved_brief_path"])
    assert resolved_path.exists()
    doc = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    assert doc["profile_id"] == "talking-head-portrait"
    assert doc["fingerprint"] == brief["fingerprint"]


def test_fingerprint_changes_on_palette_edit(repo):
    fp1 = resolve_episode_brief_node({"slug": "ep1"})["brief"]["fingerprint"]
    (repo / "brand" / "anticodeguy" / "palette.yaml").write_text(
        "colors: {bg: '#111111', fg: '#ffffff'}\n", encoding="utf-8"
    )
    fp2 = resolve_episode_brief_node({"slug": "ep1"})["brief"]["fingerprint"]
    assert fp1 != fp2


def test_canonical_resolves_without_brand(repo):
    (repo / "episodes" / "ep1" / "intent.yaml").write_text("profile_id: canonical\n", encoding="utf-8")
    brief = resolve_episode_brief_node({"slug": "ep1"})["brief"]
    assert brief["brand_id"] is None


def test_missing_profile_dir_raises(repo):
    with pytest.raises(BriefResolutionError):
        resolve_episode_brief_node({"slug": "ep1", "brief_overrides": {"profile_id": "nonexistent"}})


def test_narrative_context_passthrough(repo):
    (repo / "episodes" / "ep1" / "intent.yaml").write_text(
        "narrative_context: |\n  Episode about X.\n", encoding="utf-8"
    )
    brief = resolve_episode_brief_node({"slug": "ep1"})["brief"]
    assert "Episode about X." in brief["narrative_context"]
```

- [ ] **Step 2: Run to confirm failure.** `graph/.venv/Scripts/python.exe -m pytest graph/tests/test_resolve_episode_brief_node.py -q` → FAIL (module not found).

- [ ] **Step 3: Implement the node.** Create `graph/src/edit_episode_graph/nodes/resolve_episode_brief.py`:

```python
"""resolve_episode_brief — deterministic per-episode context resolver (HOM-166).

Spec: docs/superpowers/specs/2026-05-07-resolved-brief-profiles-brand-architecture.md
§5 (state.brief) + §6 (this node) + §9 (per-episode profile_dir/brand_dir).

Sits between pickup/isolate_audio and preflight_canon so it runs before any
creative node on EVERY path — Phase 3 and the Phase-3-skip → Phase 4 path.
Composes the four-layer context (skill canon is pulled per-node elsewhere;
this node composes profile + brand YAML + episode intent) into a canonically
serialized `episodes/<slug>/brief.resolved.yaml` and a `brief.fingerprint`
that creative-node cache keys fold in.

Resolution priority (high→low): state.brief_overrides > intent.yaml >
config.default_*. The `canonical` profile forces `brand_id=None` (brand layer
disabled, regression mode). Music selection is deferred to HOM-174 — `music`
is always `None` here.

Fail-loud (spec §6): a missing profile/brand dir or unparseable YAML raises
`BriefResolutionError` rather than smuggling an empty context into an LLM.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from langgraph.types import CachePolicy

from .._caching import make_key, stable_fingerprint
from .._paths import EpisodePaths, repo_root
from ..brief.loaders import load_brand, load_intent, load_profile
from ..config import load_default_config

# Bump on resolution-logic / resolved-shape change (changes brief.fingerprint
# inputs and therefore the resolved.yaml contract).
_CACHE_VERSION = 1


class BriefResolutionError(RuntimeError):
    """Operator misconfiguration in profile/brand/intent — fail loud (spec §6)."""


def _profiles_root() -> Path:
    return repo_root() / "profiles"


def _brand_root() -> Path:
    return repo_root() / "brand"


def _intent_path(slug: str) -> Path:
    return EpisodePaths(slug).episode_dir / "intent.yaml"


def _resolve_selection(state: dict) -> tuple[str, str | None]:
    """Resolve (profile_id, brand_id) by priority. Pure-ish: reads intent.yaml.

    Used by both the node body and the cache key_func so they never drift.
    """
    overrides = state.get("brief_overrides") or {}
    cfg = load_default_config()
    slug = state.get("slug")
    intent = load_intent(_intent_path(slug)) if slug else None

    profile_id = (
        overrides.get("profile_id")
        or (intent.profile_id if intent else None)
        or cfg.default_profile_id
    )
    if profile_id == "canonical":
        return profile_id, None
    brand_id = (
        overrides.get("brand_id")
        or (intent.brand_id if intent else None)
        or cfg.default_brand_id
    )
    return profile_id, brand_id


def _selected_files(state: dict) -> list[str | None]:
    """The on-disk files whose content drives the resolution — content-hashed
    into the cache key. Tolerant of unbound state (introspection)."""
    slug = state.get("slug")
    if not slug:
        return [None]
    profile_id, brand_id = _resolve_selection(state)
    files: list[str | None] = [str(_intent_path(slug))]
    files.append(str(_profiles_root() / profile_id / "profile.yaml"))
    if brand_id:
        files.append(str(_brand_root() / brand_id / "palette.yaml"))
        files.append(str(_brand_root() / brand_id / "defaults.yaml"))
    return files


def _cache_key(state, *_args, **_kwargs):
    slug = state.get("slug") or "__unbound__"
    overrides = state.get("brief_overrides") or {}
    return make_key(
        node="resolve_episode_brief",
        version=_CACHE_VERSION,
        slug=slug,
        files=_selected_files(state),
        extras=(stable_fingerprint(overrides),),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _resolved_dict(state: dict) -> tuple[dict, str, str | None, str | None]:
    """Build the canonical resolved-brief dict + (narrative_context, profile_id,
    brand_id). Raises BriefResolutionError on misconfiguration."""
    slug = state.get("slug")
    profile_id, brand_id = _resolve_selection(state)

    profile_dir = _profiles_root() / profile_id
    if not (profile_dir / "profile.yaml").is_file():
        raise BriefResolutionError(
            f"profile {profile_id!r}: profile.yaml not found under {profile_dir} "
            "(check intent.yaml.profile_id / brief_overrides / default_profile_id)"
        )
    try:
        profile = load_profile(profile_dir)
    except Exception as exc:  # pydantic/yaml errors → actionable wrapper
        raise BriefResolutionError(f"profile {profile_id!r} failed to parse: {exc}") from exc

    brand_dump = None
    if brand_id is not None:
        brand_dir = _brand_root() / brand_id
        if not brand_dir.is_dir():
            raise BriefResolutionError(
                f"brand {brand_id!r}: directory not found at {brand_dir}"
            )
        try:
            brand = load_brand(brand_dir)
        except Exception as exc:
            raise BriefResolutionError(f"brand {brand_id!r} failed to parse: {exc}") from exc
        brand_dump = {
            "palette": brand.palette.model_dump(mode="json"),
            "defaults": brand.defaults.model_dump(mode="json"),
        }

    intent = load_intent(_intent_path(slug)) if slug else None
    narrative_context = intent.narrative_context if intent else None

    resolved = {
        "profile_id": profile_id,
        "brand_id": brand_id,
        "narrative_context": narrative_context,
        "music": None,  # HOM-174 populates; None here keeps canonical+TH smokes green
        "profile": profile.model_dump(mode="json"),
        "brand": brand_dump,
    }
    return resolved, narrative_context, profile_id, brand_id


def resolve_episode_brief_node(state: dict) -> dict:
    slug = state.get("slug")
    if not slug:
        # Upstream pickup idle/error — nothing to resolve; routing handles END.
        return {}

    resolved, narrative_context, profile_id, brand_id = _resolved_dict(state)
    fingerprint = stable_fingerprint(resolved)

    resolved_path = EpisodePaths(slug).episode_dir / "brief.resolved.yaml"
    resolved_path.parent.mkdir(parents=True, exist_ok=True)  # disk-io-allow: resolver owns the resolved-brief artifact
    doc = {**resolved, "fingerprint": fingerprint, "resolved_brief_path": str(resolved_path)}
    resolved_path.write_text(  # disk-io-allow: resolver owns the resolved-brief artifact
        yaml.safe_dump(doc, sort_keys=True, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )

    return {
        "brief": {
            "profile_id": profile_id,
            "brand_id": brand_id,
            "resolved_brief_path": str(resolved_path),
            "narrative_context": narrative_context,
            "music": None,
            "fingerprint": fingerprint,
        },
        "notices": [
            f"resolve_episode_brief: profile={profile_id} brand={brand_id} "
            f"fingerprint={fingerprint[:12]}…"
        ],
    }
```

> Note: `mkdir`/`write_text` carry `# disk-io-allow:` because the file write is the node's *purpose*; the whole-file allowlist (Step 5) covers re-scans, and the per-line comment documents intent at the call site.

- [ ] **Step 4: Allowlist the module.** In `tests/test_disk_io_allowlist.py`, add to `ALLOWLIST_NODES`:

```python
    # HOM-166: deterministic config resolver — reading profile/brand/intent and
    # writing brief.resolved.yaml is its entire purpose (like pickup / preflight).
    "resolve_episode_brief.py",
```

- [ ] **Step 5: Run.** `graph/.venv/Scripts/python.exe -m pytest graph/tests/test_resolve_episode_brief_node.py -q` → PASS. Then `python -m pytest tests/test_disk_io_allowlist.py -q` → PASS.

- [ ] **Step 6: Commit.**

```bash
git add graph/src/edit_episode_graph/nodes/resolve_episode_brief.py graph/tests/test_resolve_episode_brief_node.py tests/test_disk_io_allowlist.py
git commit -m "HOM-166: resolve_episode_brief deterministic node + disk-io allowlist"
```

---

## Task 5: Wire `resolve_episode_brief` into the graph topology

**Files:**
- Modify: `graph/src/edit_episode_graph/nodes/_routing.py`
- Modify: `graph/src/edit_episode_graph/graph.py`
- Modify: `graph/tests/test_p4_topology.py`
- Test: `graph/tests/test_p3_pre_scan_routing.py` (route_after_pickup coverage — verify)

Placement: `pickup --(route_after_pickup)--> {END, resolve_episode_brief}`, `isolate_audio --> resolve_episode_brief`, `resolve_episode_brief --> preflight_canon`. The skip_phase2 distinction (tagged → straight to resolve; untagged → isolate_audio → resolve) is preserved; only the post-isolate / tagged-skip target changes from `preflight_canon` to `resolve_episode_brief`.

- [ ] **Step 1: Retarget `route_after_pickup`.** In `_routing.py`, change the tagged-clean branch return value:

```python
    raw = _find_raw_video(Path(episode_dir))
    if raw is not None and _container_has_clean_tag(raw):
        return "resolve_episode_brief"
    return "isolate_audio"
```

Update the docstring first line to `"""pickup → END | isolate_audio | resolve_episode_brief (skip_phase2 baked in)."""`.

- [ ] **Step 2: Wire in graph.py.** Add the import near the other node imports:

```python
from .nodes.resolve_episode_brief import (
    CACHE_POLICY as resolve_episode_brief_cache_policy,
    resolve_episode_brief_node,
)
```

Add the node registration (next to `rehydrate_skip_phase3`):

```python
    # HOM-166: deterministic per-episode brief resolver. Runs before any
    # creative node on EVERY path (Phase 3 and the Phase-3-skip → Phase 4
    # path) — placed on the common edge into preflight_canon.
    g.add_node(
        "resolve_episode_brief",
        resolve_episode_brief_node,
        cache_policy=resolve_episode_brief_cache_policy,
    )
```

Change the `route_after_pickup` conditional-edge mapping (the `pickup` block) to:

```python
    g.add_conditional_edges(
        "pickup",
        route_after_pickup,
        {
            END: END,
            "isolate_audio": "isolate_audio",
            "resolve_episode_brief": "resolve_episode_brief",
        },
    )
    g.add_edge("isolate_audio", "resolve_episode_brief")
    g.add_edge("resolve_episode_brief", "preflight_canon")
```

(Remove the old `g.add_edge("isolate_audio", "preflight_canon")` and the `"preflight_canon": "preflight_canon"` entry from the pickup mapping.)

- [ ] **Step 3: Update topology test.** In `graph/tests/test_p4_topology.py::test_phase4_nodes_present_in_compiled_graph`, add `"resolve_episode_brief"` to the `expected` set. In `test_phase4_chain_edges_wired`, add to `expected_edges`:

```python
        # HOM-166: resolver on the common pre-Phase-3 path.
        ("pickup", "resolve_episode_brief"),
        ("isolate_audio", "resolve_episode_brief"),
        ("resolve_episode_brief", "preflight_canon"),
```

- [ ] **Step 4: Run.**

```bash
graph/.venv/Scripts/python.exe -m pytest graph/tests/test_p4_topology.py graph/tests/test_p3_pre_scan_routing.py -q
```
Expected: PASS. If `route_after_pickup` has a dedicated routing test asserting `"preflight_canon"`, update that assertion to `"resolve_episode_brief"`.

- [ ] **Step 5: Commit.**

```bash
git add graph/src/edit_episode_graph/nodes/_routing.py graph/src/edit_episode_graph/graph.py graph/tests/test_p4_topology.py
git commit -m "HOM-166: wire resolve_episode_brief between pickup/isolate_audio and preflight"
```

---

## Task 6: Schema loosening — p3_strategy

**Files:**
- Modify: `graph/src/edit_episode_graph/schemas/p3_strategy.py`
- Test: `graph/tests/test_state_schema_migration.py` (or a new `graph/tests/test_strategy_schema.py`)

- [ ] **Step 1: Write the failing migration test.** Append to `graph/tests/test_state_schema_migration.py`:

```python
def test_strategy_accepts_old_shape_and_new_prose():
    from edit_episode_graph.schemas.p3_strategy import Strategy
    # Old 5-field recording still validates (forward-compat).
    old = {"shape": "x", "takes": ["t1"], "grade": "neutral", "pacing": "fast", "length_estimate_s": 30.0}
    s = Strategy.model_validate(old)
    assert s.rationale == "" and s.taste_notes == ""
    # New prose fields accepted.
    new = {**old, "rationale": "because", "taste_notes": "free md"}
    s2 = Strategy.model_validate(new)
    assert s2.rationale == "because"
```

- [ ] **Step 2: Run → FAIL** (`rationale` not a field / extra forbidden).

- [ ] **Step 3: Loosen the schema.** Replace the `Strategy` class body in `schemas/p3_strategy.py`:

```python
class Strategy(BaseModel):
    # HOM-166 (spec §7): extra="allow" + prose fields. The strategist agent
    # produces prose the narrow 5-field shape dropped; `rationale` /
    # `taste_notes` carry it downstream alongside the structural fields. Both
    # optional (default "") so pre-HOM-166 recordings still validate.
    model_config = ConfigDict(extra="allow")

    shape: str = Field(min_length=1, description="Plain-English narrative shape for the cut.")
    takes: list[str] = Field(default_factory=list, description="Take-selection guidance, by take or phrase.")
    grade: str = Field(min_length=1, description="Color/grade direction for the deterministic render step.")
    pacing: str = Field(min_length=1, description="Pacing guidance and target density.")
    length_estimate_s: float = Field(gt=0, description="Estimated final cut length in seconds.")
    rationale: str = Field(default="", description="3-6 sentences of prose justifying the strategy.")
    taste_notes: str = Field(default="", description="Free-form markdown taste notes (tone, brand fit).")
```

- [ ] **Step 4: Run → PASS.** `graph/.venv/Scripts/python.exe -m pytest graph/tests/test_state_schema_migration.py -q`

- [ ] **Step 5: Commit.**

```bash
git add graph/src/edit_episode_graph/schemas/p3_strategy.py graph/tests/test_state_schema_migration.py
git commit -m "HOM-166: loosen Strategy schema — extra=allow + rationale/taste_notes"
```

---

## Task 7: Schema loosening — p4_design_system + p4_plan

**Files:**
- Modify: `graph/src/edit_episode_graph/schemas/p4_design_system.py`
- Modify: `graph/src/edit_episode_graph/schemas/p4_plan.py`
- Test: `graph/tests/test_state_schema_migration.py`

- [ ] **Step 1: Add failing tests.** Append to `graph/tests/test_state_schema_migration.py`:

```python
def test_design_doc_adds_optional_prose():
    from edit_episode_graph.schemas.p4_design_system import DesignDoc
    base = {
        "style_name": "Editorial", "palette": [{"role": "bg", "hex": "#000"}, {"role": "fg", "hex": "#fff"}],
        "typography": [{"role": "headline", "family": "Inter"}],
        "refs": [{"label": "Stripe", "description": "typography"}, {"label": "Pentagram", "description": "grid"}],
        "alternatives": [{"name": "Folk", "rejected_because": "too warm"}],
        "anti_patterns": ["no neon", "no drop shadows", "no center-everything"],
        "beat_visual_mapping": [{"beat": "HOOK", "treatment": "stat slam"}],
        "design_md_path": "/x/DESIGN.md", "design_md": "# DESIGN\n",
    }
    d = DesignDoc.model_validate(base)
    assert d.rationale == "" and d.cross_scene_logic == ""
    d2 = DesignDoc.model_validate({**base, "rationale": "r", "cross_scene_logic": "c"})
    assert d2.rationale == "r" and d2.cross_scene_logic == "c"


def test_plan_adds_optional_prose():
    from edit_episode_graph.schemas.p4_plan import CompositionPlan
    base = {
        "narrative_arc": "hook→payoff", "rhythm": "fast-SLOW-fast",
        "beats": [{"beat": "HOOK", "concept": "c1c1", "mood": "m", "energy": "high",
                   "duration_s": 6.9, "catalog_or_custom": "custom", "justification": "off-axis"}],
        "transitions": [],
    }
    p = CompositionPlan.model_validate(base)
    assert p.rationale == "" and p.cross_scene_logic == ""
    p2 = CompositionPlan.model_validate({**base, "rationale": "r", "cross_scene_logic": "c"})
    assert p2.cross_scene_logic == "c"
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Add fields to `DesignDoc`** (after `design_md`, keep `extra="forbid"`):

```python
    rationale: str = Field(
        default="",
        description="3-6 sentences on WHY this visual identity fits the brand + content "
                    "(HOM-166 §7). Prose alongside the structured fields, not instead of.",
    )
    cross_scene_logic: str = Field(
        default="",
        description="How the design holds together across scenes — recurring motifs, palette "
                    "rhythm, what stays constant vs varies (HOM-166 §7).",
    )
```

- [ ] **Step 4: Add fields to `CompositionPlan`** (after `transitions`, keep `extra="forbid"`):

```python
    rationale: str = Field(
        default="",
        description="3-6 sentences on WHY this beat/rhythm/transition plan serves the narrative "
                    "(HOM-166 §7).",
    )
    cross_scene_logic: str = Field(
        default="",
        description="Cross-scene reasoning — rhythm arc, transition budget, motion variation "
                    "across beats (HOM-166 §7).",
    )
```

- [ ] **Step 5: Run → PASS, then commit.**

```bash
graph/.venv/Scripts/python.exe -m pytest graph/tests/test_state_schema_migration.py -q
git add graph/src/edit_episode_graph/schemas/p4_design_system.py graph/src/edit_episode_graph/schemas/p4_plan.py graph/tests/test_state_schema_migration.py
git commit -m "HOM-166: add rationale/cross_scene_logic to DesignDoc + CompositionPlan"
```

---

## Task 8: Fold `brief.fingerprint` into all creative-node cache keys

**Files (each: bump `_CACHE_VERSION`, add `brief_fingerprint` import + extras entry):**
- `nodes/p3_pre_scan.py`, `nodes/p3_self_eval.py`, `nodes/p3_strategy.py`, `nodes/p3_edl_select.py`, `nodes/p4_design_system.py`, `nodes/p4_prompt_expansion.py`, `nodes/p4_plan.py`, `nodes/p4_beat.py`, `nodes/p4_captions_layer.py`
- Test: `tests/test_fingerprint_invalidation.py` (repo-level — extend `_NODE_REGISTRY` if present) and a focused new test.

**Pattern (apply to each node's `_cache_key`):**

1. Add import: `from .._caching import ... , brief_fingerprint` (merge into the existing `_caching` import line).
2. In the `extras=(...)` tuple, add as the LAST entry: `f"brief:{brief_fingerprint(state)}"`.
3. Bump the node's `_CACHE_VERSION` by 1 and add a one-line comment: `# vN (HOM-166): brief.fingerprint folded into cache key (state.brief resolution).`

- [ ] **Step 1: Apply the pattern to all 9 nodes.** Exact current versions to bump: `p3_pre_scan` 3→4, `p3_self_eval` 3→4, `p3_strategy` 4→5, `p3_edl_select` 5→6, `p4_design_system` 5→6, `p4_prompt_expansion` 7→8, `p4_plan` 5→6, `p4_beat` (current value — read the constant, bump +1), `p4_captions_layer` 10→11.

  Example for `p3_strategy.py` `_cache_key` `extras`:

```python
        extras=(
            stable_fingerprint(slips),
            stable_fingerprint(revisions),
            f"canon:{canon_fingerprint('p3_strategy')}",   # replaced in Task 9 with dir-fed call
            f"brief:{brief_fingerprint(state)}",
        ),
```

  Example for `p4_plan.py` (no canon line today) `extras`:

```python
        extras=(
            stable_fingerprint(self._strategy(state)) if False else strategy_fingerprint(strategy),
            # ... keep existing extras entries verbatim ...
            f"brief:{brief_fingerprint(state)}",
        ),
```
  (Do NOT restructure existing extras — only append the `brief:` entry. The line above is illustrative of "append, don't rewrite".)

- [ ] **Step 2: Add a focused invalidation test.** Create `tests/test_brief_fingerprint_in_cache_keys.py`:

```python
"""brief.fingerprint must change every creative node's cache key (HOM-166)."""
from __future__ import annotations

import importlib

import pytest

CREATIVE_NODES = [
    ("p3_pre_scan", "p3_pre_scan"),
    ("p3_self_eval", "p3_self_eval"),
    ("p3_strategy", "p3_strategy"),
    ("p3_edl_select", "p3_edl_select"),
    ("p4_design_system", "p4_design_system"),
    ("p4_prompt_expansion", "p4_prompt_expansion"),
    ("p4_plan", "p4_plan"),
    ("p4_beat", "p4_beat"),
    ("p4_captions_layer", "p4_captions_layer"),
]


@pytest.mark.parametrize("module,_name", CREATIVE_NODES)
def test_brief_fingerprint_changes_cache_key(module, _name, monkeypatch, tmp_path):
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("HOMESTUDIO_REPO_ROOT", str(tmp_path))
    mod = importlib.import_module(f"edit_episode_graph.nodes.{module}")
    base = {"slug": "ep1", "edit": {}, "compose": {}, "transcripts": {}}
    k1 = mod._cache_key({**base, "brief": {"fingerprint": "AAA"}})
    k2 = mod._cache_key({**base, "brief": {"fingerprint": "BBB"}})
    assert k1 != k2, f"{module} cache key ignores brief.fingerprint"
```

- [ ] **Step 3: Run.**

```bash
python -m pytest tests/test_brief_fingerprint_in_cache_keys.py -q
graph/.venv/Scripts/python.exe -m pytest graph/tests -q -k "cache or caching"
```
Expected: PASS. (Some node `_cache_key`s require minimal state shape — the `base` dict above is intentionally minimal; if a node raises on missing keys, extend `base` with the empty namespace it reads.)

- [ ] **Step 4: Commit.**

```bash
git add graph/src/edit_episode_graph/nodes/p3_pre_scan.py graph/src/edit_episode_graph/nodes/p3_self_eval.py graph/src/edit_episode_graph/nodes/p3_strategy.py graph/src/edit_episode_graph/nodes/p3_edl_select.py graph/src/edit_episode_graph/nodes/p4_design_system.py graph/src/edit_episode_graph/nodes/p4_prompt_expansion.py graph/src/edit_episode_graph/nodes/p4_plan.py graph/src/edit_episode_graph/nodes/p4_beat.py graph/src/edit_episode_graph/nodes/p4_captions_layer.py tests/test_brief_fingerprint_in_cache_keys.py
git commit -m "HOM-166: fold brief.fingerprint into all creative-node cache keys"
```

---

## Task 9: Wire `{{ profile.* }}` / `{{ brand.* }}` into the four registered nodes

The four nodes registered in `_canon_loader.NODE_PROFILE_ANCHORS` / `NODE_BRAND_ANCHORS`: `p3_strategy`, `p3_edl_select`, `p4_design_system`, `p4_prompt_expansion`. For each: feed the resolved `profile_dir` / `brand_dir` into `canon_fingerprint` and add `profile` / `brand` render-context blocks.

**Files:**
- Modify the 4 node modules + their 4 `.j2` briefs.
- Modify: `graph/src/edit_episode_graph/briefs/_macros.j2`

- [ ] **Step 1: Add the brief macro.** Append to `briefs/_macros.j2`:

```jinja
{% macro profile_brand_section(profile, brand) -%}
{% if (profile and profile|length) or (brand and brand|length) %}
Profile & brand context (operator-authored overlay ON TOP of canon — brand
wins on conflict; honor canonical opt-outs, never replace canon):
{% for key, block in (profile or {}).items() %}
{{ block }}
{% endfor %}
{% for key, block in (brand or {}).items() %}
{{ block }}
{% endfor %}
{% endif %}
{%- endmacro %}
```

(The `canonical` profile + brand-less runs render this as empty — preserving the "clean canonical run passes as before" wave-1 acceptance.)

- [ ] **Step 2: Per node — render ctx + cache.** For each of the 4 nodes:
  - Add imports: `from .._paths import EpisodePaths, profile_dir_for, brand_dir_for` (merge with existing `_paths` import) and ensure `from .._canon_loader import canon_fingerprint, load_profile_blocks, load_brand_blocks` (add the two `load_*_blocks`; `p4_design_system` / `p4_prompt_expansion` must add `canon_fingerprint` + the loaders fresh).
  - In `_cache_key`, replace `canon_fingerprint('<node>')` with `canon_fingerprint('<node>', profile_dir_for(state), brand_dir_for(state))`. For `p4_design_system` / `p4_prompt_expansion` (no canon line today) ADD a new extras entry `f"canon:{canon_fingerprint('<node>', profile_dir_for(state), brand_dir_for(state))}"`.
  - In `_render_ctx`, add:

```python
        "profile": load_profile_blocks("<node>", profile_dir_for(state)) if profile_dir_for(state) else {},
        "brand": load_brand_blocks("<node>", brand_dir_for(state)) if brand_dir_for(state) else {},
```

  (`load_profile_blocks`/`load_brand_blocks` require a real dir; guard the `None` case to `{}`.)

  - Note: the `_CACHE_VERSION` was already bumped in Task 8; bump it again by 1 here with a comment `# vN+1 (HOM-166): profile/brand blocks + dir-fed canon_fingerprint.` — OR combine Task 8 + Task 9 edits per node into a single version bump if executing both at once. (If combined, document both reasons on one bump.)

- [ ] **Step 3: Per brief — render the section.** In each of `briefs/p3_strategy.j2`, `briefs/p3_edl_select.j2`, `briefs/p4_design_system.j2`, `briefs/p4_prompt_expansion.j2`: add near the top `{% from "_macros.j2" import profile_brand_section %}` (if not already importing macros — p3_strategy already imports `canon_section`; add to that line) and insert the call after the canon section, e.g. for `p3_strategy.j2` after line 11:

```jinja
{{ profile_brand_section(profile, brand) }}
```

- [ ] **Step 4: Run unit tests for the 4 nodes** to confirm no render/cache regressions:

```bash
graph/.venv/Scripts/python.exe -m pytest graph/tests/test_p3_strategy_node.py graph/tests/test_p4_design_system_node.py graph/tests/test_p4_prompt_expansion_node.py graph/tests/test_profile_brand_sections.py -q
```
Expected: PASS (node bodies tolerate `brief` absent → `profile_dir_for` None → `{}` blocks).

- [ ] **Step 5: Commit.**

```bash
git add graph/src/edit_episode_graph/nodes/p3_strategy.py graph/src/edit_episode_graph/nodes/p3_edl_select.py graph/src/edit_episode_graph/nodes/p4_design_system.py graph/src/edit_episode_graph/nodes/p4_prompt_expansion.py graph/src/edit_episode_graph/briefs/_macros.j2 graph/src/edit_episode_graph/briefs/p3_strategy.j2 graph/src/edit_episode_graph/briefs/p3_edl_select.j2 graph/src/edit_episode_graph/briefs/p4_design_system.j2 graph/src/edit_episode_graph/briefs/p4_prompt_expansion.j2
git commit -m "HOM-166: wire {{profile.*}}/{{brand.*}} blocks + dir-fed canon_fingerprint into 4 nodes"
```

---

## Task 10: Update brief snapshots + render-context fixtures

**Files:**
- Modify: `tests/_helpers/brief_render_contexts.py`
- Regenerate: `tests/snapshots/briefs/{p3_strategy,p3_edl_select,p4_design_system,p4_prompt_expansion,p4_plan}.txt`

- [ ] **Step 1: Add profile/brand placeholders.** In `tests/_helpers/brief_render_contexts.py`, add after `_placeholder_canon`:

```python
from edit_episode_graph._canon_loader import (
    NODE_CANON_ANCHORS, NODE_PROFILE_ANCHORS, NODE_BRAND_ANCHORS,
)


def _placeholder_profile(node: str) -> dict[str, str]:
    return {
        ref.key: f"## PROFILE PLACEHOLDER — {ref.anchor}\n(snapshot fixture)\n"
        for ref in NODE_PROFILE_ANCHORS.get(node, ())
    }


def _placeholder_brand(node: str) -> dict[str, str]:
    return {
        ref.key: f"## BRAND PLACEHOLDER — {ref.anchor}\n(snapshot fixture)\n"
        for ref in NODE_BRAND_ANCHORS.get(node, ())
    }
```

  Then in `p3_strategy_ctx`, `p3_edl_select_ctx`, `p4_design_system_ctx`, `p4_prompt_expansion_ctx` add:

```python
        "profile": _placeholder_profile("<node>"),
        "brand": _placeholder_brand("<node>"),
```

  For the schema-loosened briefs, no context change is needed unless the brief renders the new fields (Task 11 may add request text — if so, no new context vars are introduced; the schema fields are model output, not render inputs).

- [ ] **Step 2: Regenerate snapshots.**

```bash
python -m pytest tests/test_brief_snapshots.py --update-snapshots -q
```

- [ ] **Step 3: Review the diff** to confirm: profile/brand placeholder blocks appear in the 4 briefs; the canonical-citation contract is intact (no embedded canon); p4_plan / p3_strategy / p4_design_system show any new schema-request prose from Task 11. Run again WITHOUT `--update-snapshots` → PASS.

- [ ] **Step 4: Commit.**

```bash
git add tests/_helpers/brief_render_contexts.py tests/snapshots/briefs/
git commit -m "HOM-166: brief snapshots — profile/brand blocks + loosened-schema prose"
```

---

## Task 11: Brief request text for the new prose fields

Update the three loosened-schema briefs so the sub-agent actually emits `rationale` / `taste_notes` / `cross_scene_logic`. Keep additive and canon-referencing (no embedded canon).

**Files:**
- `briefs/p3_strategy.j2`, `briefs/p4_design_system.j2`, `briefs/p4_plan.j2`

- [ ] **Step 1: p3_strategy.j2** — update the JSON example + add a request line. Change the example block to include the new keys and add a sentence:

```jinja
Return ONLY JSON matching:

```json
{"shape":"...","takes":["..."],"grade":"...","pacing":"...","length_estimate_s":30.0,"rationale":"...","taste_notes":"..."}
```

`rationale`: 3-6 sentences justifying the cut shape, take selection, and pacing
against the material. `taste_notes`: free-form notes on tone / brand fit (use
the Profile & brand context above when present).
```

- [ ] **Step 2: p4_design_system.j2** — add to the output instructions a request for `rationale` (why this identity fits) and `cross_scene_logic` (recurring motifs / palette rhythm across scenes). Match the brief's existing instruction style (find the "Return … JSON" / DesignDoc section and append the two field descriptions).

- [ ] **Step 3: p4_plan.j2** — add a request for `rationale` (why this beat/rhythm/transition plan serves the narrative) and `cross_scene_logic` (rhythm arc, transition budget, motion variation).

- [ ] **Step 4: Bump `_CACHE_VERSION`** on `p3_strategy`, `p4_design_system`, `p4_plan` by 1 with comment `# vN (HOM-166): brief requests rationale/taste_notes prose.` (If combined with Task 8/9 bumps, fold into one bump with all reasons noted.)

- [ ] **Step 5: Regenerate snapshots + run.**

```bash
python -m pytest tests/test_brief_snapshots.py --update-snapshots -q
python -m pytest tests/test_brief_snapshots.py tests/test_brief_no_line_pins.py -q
```
Expected: PASS. Review diff: new prose-request lines present; no embedded canon.

- [ ] **Step 6: Commit.**

```bash
git add graph/src/edit_episode_graph/briefs/p3_strategy.j2 graph/src/edit_episode_graph/briefs/p4_design_system.j2 graph/src/edit_episode_graph/briefs/p4_plan.j2 graph/src/edit_episode_graph/nodes/p3_strategy.py graph/src/edit_episode_graph/nodes/p4_design_system.py graph/src/edit_episode_graph/nodes/p4_plan.py tests/snapshots/briefs/
git commit -m "HOM-166: briefs request rationale/taste_notes/cross_scene_logic prose"
```

---

## Task 12: halt_llm_boundary notice + fingerprint-invalidation integration test + canonical smoke

**Files:**
- Modify (verify): `graph/src/edit_episode_graph/nodes/halt_llm_boundary.py`
- Create: `tests/test_brief_fingerprint_invalidation.py`

- [ ] **Step 1: Verify the halt notice.** Read `halt_llm_boundary.py`. If it enumerates pipeline artifacts/phases in its notice, add a mention that `brief.resolved.yaml` is resolved before Phase 3 (so the operator sees the new pre-Phase-3 artifact). If the notice is generic (just "LLM boundary reached"), no change — note that in the commit message.

- [ ] **Step 2: Integration test — palette change invalidates p4_design_system, brand.md change does not change brief.fingerprint.** Create `tests/test_brief_fingerprint_invalidation.py`:

```python
"""Wave-1 acceptance (spec §16): palette edit invalidates the brief fingerprint
(→ p4_design_system cache miss); editing brand.md PROSE (a markdown layer,
fingerprinted per-node via canon_fingerprint, NOT part of brief.fingerprint)
leaves brief.fingerprint stable. Canonical-mode resolves with brand_id=None."""
from __future__ import annotations

from pathlib import Path

import pytest


def _seed(tmp_path: Path) -> None:
    prof = tmp_path / "profiles" / "talking-head-portrait"; prof.mkdir(parents=True)
    (prof / "profile.yaml").write_text(
        "profile_id: talking-head-portrait\nhuman_label: TH\n"
        "captions: {enabled: true}\nmusic: {enabled: true}\ncta: {enabled: true}\n", encoding="utf-8")
    (prof / "house-style.md").write_text("## Pacing\nTight.\n## Structural archetype\nHook.\n", encoding="utf-8")
    canon = tmp_path / "profiles" / "canonical"; canon.mkdir(parents=True)
    (canon / "profile.yaml").write_text(
        "profile_id: canonical\nhuman_label: C\n"
        "captions: {enabled: false}\nmusic: {enabled: false}\ncta: {enabled: false}\n", encoding="utf-8")
    brand = tmp_path / "brand" / "anticodeguy"; brand.mkdir(parents=True)
    (brand / "palette.yaml").write_text("colors: {bg: '#000000', fg: '#ffffff'}\n", encoding="utf-8")
    (brand / "defaults.yaml").write_text("motion_language: {}\ncaptions: {}\n", encoding="utf-8")
    (brand / "brand.md").write_text("## Voice\nCalm.\n## Visual identity\nLime.\n", encoding="utf-8")
    (tmp_path / "episodes" / "ep1").mkdir(parents=True)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("HOMESTUDIO_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    return tmp_path


def _resolve(slug="ep1", overrides=None):
    from edit_episode_graph.nodes.resolve_episode_brief import resolve_episode_brief_node
    st = {"slug": slug}
    if overrides:
        st["brief_overrides"] = overrides
    return resolve_episode_brief_node(st)["brief"]


def test_palette_edit_changes_brief_fingerprint(repo):
    fp1 = _resolve()["fingerprint"]
    (repo / "brand" / "anticodeguy" / "palette.yaml").write_text(
        "colors: {bg: '#111111', fg: '#ffffff'}\n", encoding="utf-8")
    assert _resolve()["fingerprint"] != fp1


def test_brand_md_prose_edit_keeps_brief_fingerprint_stable(repo):
    fp1 = _resolve()["fingerprint"]
    (repo / "brand" / "anticodeguy" / "brand.md").write_text(
        "## Voice\nENERGETIC.\n## Visual identity\nLime.\n", encoding="utf-8")
    assert _resolve()["fingerprint"] == fp1  # markdown is per-node canon_fingerprint, not brief.fingerprint


def test_design_system_cache_key_misses_on_palette_change(repo):
    from edit_episode_graph.nodes.p4_design_system import _cache_key
    b1 = _resolve()
    st = {"slug": "ep1", "brief": b1, "edit": {"edl": {"ranges": [{"beat": "HOOK"}]}, "strategy": {}}}
    k1 = _cache_key(st)
    (repo / "brand" / "anticodeguy" / "palette.yaml").write_text(
        "colors: {bg: '#222222', fg: '#ffffff'}\n", encoding="utf-8")
    b2 = _resolve()
    k2 = _cache_key({**st, "brief": b2})
    assert k1 != k2


def test_canonical_mode_no_brand(repo):
    b = _resolve(overrides={"profile_id": "canonical"})
    assert b["brand_id"] is None
    assert b["profile_id"] == "canonical"
```

- [ ] **Step 3: Run.**

```bash
python -m pytest tests/test_brief_fingerprint_invalidation.py -q
```
Expected: PASS.

- [ ] **Step 4: Commit.**

```bash
git add tests/test_brief_fingerprint_invalidation.py graph/src/edit_episode_graph/nodes/halt_llm_boundary.py
git commit -m "HOM-166: wave-1 fingerprint-invalidation tests + halt notice"
```

---

## Task 13: Full suite + spec amendment + PR

- [ ] **Step 1: Run both test roots green.**

```bash
graph/.venv/Scripts/python.exe -m pytest graph/tests -q
python -m pytest tests -q
```
Expected: PASS (replay smokes may SKIP via `requires_fixture_cache` — that is acceptable per CLAUDE.md; HOM-166 invalidates the committed fixture cache.db by design, re-recording is a separate wave-acceptance step).

- [ ] **Step 2: Spec amendment (rides along, separate commit).** Append a dated note under spec §6 (or §9) recording the HOM-166 decisions that differ from the original draft: (a) `brief.music` is `None` in HOM-166 (music deferred to HOM-174); (b) override channel is `state["brief_overrides"]` (CLI is HOM-79); (c) `brief.fingerprint` covers the YAML config layers only — markdown `house-style.md`/`brand.md` invalidation is the per-node `canon_fingerprint` channel (the negative "unrelated brand field → stable" test edits `brand.md` prose).

```bash
git add docs/superpowers/specs/2026-05-07-resolved-brief-profiles-brand-architecture.md
git commit -m "docs(spec): amend §6/§9 with HOM-166 implementation decisions"
```

- [ ] **Step 3: Push + PR.**

```bash
git push -u origin hom-166-brief-substrate
gh pr create --base main --title "HOM-166: brief substrate — state.brief + resolve_episode_brief + schema loosening" --body-file docs/superpowers/plans/2026-05-31-hom-166-brief-substrate.md
```

- [ ] **Step 4: Code review** (dispatch an independent reviewer agent on the diff per `feedback_code_review_before_merge`), address findings, then `gh pr merge --squash --delete-branch`.

---

## Self-Review notes (spec coverage)

- §5 state.brief → Task 1 (schema) + Task 4 (populated). `music` slot present, `None` (scope note).
- §6 resolve_episode_brief → Task 4 (node, priority chain, canonical forcing, fail-loud, brief.resolved.yaml, cache policy) + Task 5 (topology).
- §7 schema loosening → Task 6 (p3_strategy extra=allow + 2 fields) + Task 7 (design_system + plan + 2 fields each).
- §5 fingerprint in make_llm_key for creative nodes → Task 8 (9 nodes).
- §9 per-episode profile_dir/brand_dir + `{{ profile.* }}`/`{{ brand.* }}` → Task 3 (helpers) + Task 9 (4 nodes + briefs) + Task 10 (snapshots).
- DoD topology test → Task 5. DoD schema migration → Tasks 6-7. DoD canonical smoke + palette invalidation → Task 12. DoD halt notice → Task 12. Brief snapshots (HOM-183) → Tasks 10-11. Disk-IO allowlist (HOM-283) → Task 4.
