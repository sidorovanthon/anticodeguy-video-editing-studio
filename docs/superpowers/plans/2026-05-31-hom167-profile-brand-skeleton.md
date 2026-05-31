# HOM-167 — Profile + Brand Layer Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lay down the version-controlled filesystem skeleton + Pydantic loaders for the four-layer brief composition (skill_canon + profile + brand + episode_intent), with two profiles (`canonical`, `talking-head-portrait`) and one brand (`anticodeguy`).

**Architecture:** Brand/profile canon is operator-authored config that lives **in the repo** (resolved via `repo_root()`, not the TrueNAS data root) so one-config brand changes are version-tracked and ship with the deploy. This ticket ships (1) committed YAML/MD skeleton files, (2) `edit_episode_graph.brief` package with Pydantic schema models + **path-injectable** loader functions, (3) parse/shape tests across both test roots. The **precedence-resolution engine + `resolve_episode_brief` graph node + `brief.resolved.yaml` + `state.brief` + caching + graph wiring are explicitly OUT OF SCOPE — they belong to HOM-166** (the ticket DoD defers the node: "when wired by HOM-XXX brief-substrate ticket"). Loaders are pure functions taking a directory `Path`, so the path-resolution policy decision stays in HOM-166's node.

**Tech Stack:** Python 3, Pydantic v2 (`BaseModel`, `ConfigDict(extra="forbid")` — mirrors `graph/src/edit_episode_graph/schemas/*.py`), PyYAML (`yaml.safe_load` — mirrors `config.py`), pytest. Run graph suite with `graph/.venv/Scripts/python.exe -m pytest graph/tests`.

---

## Scope boundary (read before coding)

| Concern | This ticket (HOM-167) | HOM-166 (brief substrate) |
|---|---|---|
| Committed `profiles/` + `brand/anticodeguy/` skeleton | ✅ | — |
| Pydantic schema models (`brief/schemas.py`) | ✅ | extends if node needs more |
| Per-layer loaders (`brief/loaders.py`, path-injectable) | ✅ | consumes |
| Parse / shape / no-broken-ref tests | ✅ | — |
| Precedence merge (CLI>intent>profile>brand>canon) | ❌ | ✅ §6 |
| `resolve_episode_brief` graph node + wiring | ❌ | ✅ §6 |
| `brief.resolved.yaml` serialization + `state.brief` | ❌ | ✅ §5/§6 |
| Caching / fingerprint / fail-loud validation | ❌ | ✅ §6 |
| `music/` track files + `music/defaults.yaml` | ❌ (dir only, `.gitkeep`) | §15.9 ticket |

**No version pins.** Per operator decision (memory `feedback_no_version_pins_evolve_with_skills`), do **not** add any `hyperframes_version`/skill-version field to profile or brand schema. The system floats `latest`.

**Disk-I/O lint:** the loaders read files (`.read_text`, `.exists`) but live in `graph/src/edit_episode_graph/brief/`, which is **outside** the `nodes/`+`gates/` scope of `tests/test_disk_io_allowlist.py`. No allowlist entry or prewarm needed here. HOM-166's node (in `nodes/`) will owe that compliance.

---

## File Structure

**Committed canon (repo root — version-controlled, sibling to `episodes/` in spec §4):**
- `profiles/canonical/profile.yaml` — empty/regression override (only skill_canon).
- `profiles/talking-head-portrait/profile.yaml` — full example (spec §4).
- `profiles/talking-head-portrait/house-style.md` — video-class guidance; H2 anchors `## Pacing`, `## Structural archetype`, `## Rhythm template`, `## Edit rules` (referenced by spec §9 anchor lists).
- `brand/anticodeguy/brand.md` — voice + the layer-composition doc note; H2 anchors `## Voice`, `## Visual identity`, `## Layer composition`.
- `brand/anticodeguy/palette.yaml` — colors, typography, contrast pairs.
- `brand/anticodeguy/defaults.yaml` — motion_language, captions, cta, grade, transitions.
- `brand/anticodeguy/assets/logo.svg`, `symbol-lime.svg` — placeholder SVGs.
- `brand/anticodeguy/templates/cta_scene.html` — placeholder static HTML (referenced by `defaults.yaml.cta.template`).
- `brand/anticodeguy/music/.gitkeep` — empty; populated by §15.9 ticket.

**Code (`graph/src/edit_episode_graph/brief/`):**
- `__init__.py` — package marker + public exports.
- `schemas.py` — `ProfileConfig` (+ `OutputCfg`, `CaptionsCfg`, `MusicProfileCfg`, `CtaCfg`, `EditCfg`, `PaddingCfg`), `BrandPalette` (+ `ContrastPair`), `BrandDefaults`, `BrandKit`, `EpisodeIntent` (+ `IntentMusic`).
- `loaders.py` — `load_profile`, `load_brand`, `load_brand_palette`, `load_brand_defaults`, `load_intent`.

**Tests (`graph/tests/`):**
- `test_brief_schemas.py` — schema validation against synthetic dicts.
- `test_brief_loaders.py` — loaders against `tmp_path` YAML + empty/missing intent.
- `test_brief_skeleton.py` — loads the REAL committed files, asserts shapes, no broken refs, four-layer shape snapshot.

---

### Task 1: Pydantic schema models

**Files:**
- Create: `graph/src/edit_episode_graph/brief/__init__.py`
- Create: `graph/src/edit_episode_graph/brief/schemas.py`
- Test: `graph/tests/test_brief_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `graph/tests/test_brief_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from edit_episode_graph.brief.schemas import (
    BrandDefaults,
    BrandPalette,
    EpisodeIntent,
    ProfileConfig,
)


def test_canonical_profile_minimal_shape():
    p = ProfileConfig.model_validate(
        {
            "profile_id": "canonical",
            "human_label": "Canonical (regression)",
            "pacing": "skill_default",
            "structural_archetype": "skill_default",
            "rhythm_template": "skill_default",
            "captions": {"enabled": False},
            "animation_density": "skill_default",
            "music": {"enabled": False},
            "cta": {"enabled": False},
        }
    )
    assert p.output is None
    assert p.edit is None
    assert p.captions.enabled is False
    assert p.captions.mode is None
    assert p.music.enabled is False
    assert p.pacing == "skill_default"


def test_full_profile_shape():
    p = ProfileConfig.model_validate(
        {
            "profile_id": "talking-head-portrait",
            "human_label": "Talking head — portrait short",
            "output": {"width": 1080, "height": 1920, "fps": 60},
            "pacing": "tight_conversational",
            "structural_archetype": "hook_problem_solution_cta",
            "rhythm_template": "hook-build-PEAK-breathe-CTA",
            "captions": {"enabled": True, "mode": "karaoke", "safe_zone": "lower_third_avoid_face"},
            "animation_density": "medium",
            "music": {"enabled": True, "default_mix_db": -18},
            "cta": {"enabled": True, "placement": "final_scene"},
            "edit": {
                "remove": ["false_starts", "cross_range_semantic_duplicates"],
                "padding": {"head_ms": 50, "tail_ms": 80},
            },
        }
    )
    assert p.output.width == 1080 and p.output.fps == 60
    assert p.captions.mode == "karaoke"
    assert p.music.default_mix_db == -18
    assert p.edit.padding.head_ms == 50
    assert "cross_range_semantic_duplicates" in p.edit.remove


def test_profile_rejects_unknown_top_key():
    with pytest.raises(ValidationError):
        ProfileConfig.model_validate(
            {
                "profile_id": "x",
                "human_label": "x",
                "captions": {"enabled": False},
                "music": {"enabled": False},
                "cta": {"enabled": False},
                "typo_field": 1,
            }
        )


def test_brand_palette_and_defaults_shape():
    pal = BrandPalette.model_validate(
        {
            "colors": {"ink": "#0E0E0E", "lime": "#C8FF3D"},
            "typography": {"display": "Clash Display", "body": "Inter"},
            "contrast_pairs": [{"fg": "ink", "bg": "paper"}],
        }
    )
    assert pal.colors["lime"] == "#C8FF3D"
    assert pal.contrast_pairs[0].fg == "ink"

    d = BrandDefaults.model_validate(
        {
            "motion_language": {"easing_default": "power2.out"},
            "captions": {"style": "karaoke"},
            "cta": {"template": "cta_scene.html"},
            "grade": {"warmth": 0},
            "transitions": {"primary": "blur crossfade"},
        }
    )
    assert d.cta["template"] == "cta_scene.html"
    assert d.transitions["primary"] == "blur crossfade"


def test_empty_intent_is_all_optional():
    intent = EpisodeIntent.model_validate({})
    assert intent.profile_id is None
    assert intent.brand_id is None
    assert intent.must_cuts == []
    assert intent.grade_overrides == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `graph/.venv/Scripts/python.exe -m pytest graph/tests/test_brief_schemas.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'edit_episode_graph.brief'`

- [ ] **Step 3: Write minimal implementation**

Create `graph/src/edit_episode_graph/brief/__init__.py`:

```python
"""Brief substrate: profile + brand + episode-intent context layers.

This package holds the schema models and path-injectable loaders for the
four-layer brief composition (spec
`docs/superpowers/specs/2026-05-07-resolved-brief-profiles-brand-architecture.md`
§3-§5). HOM-167 ships the skeleton + loaders only; the
`resolve_episode_brief` graph node, precedence engine, `brief.resolved.yaml`
serialization and caching are HOM-166.
"""
from __future__ import annotations

from .loaders import (
    load_brand,
    load_brand_defaults,
    load_brand_palette,
    load_intent,
    load_profile,
)
from .schemas import (
    BrandDefaults,
    BrandKit,
    BrandPalette,
    EpisodeIntent,
    ProfileConfig,
)

__all__ = [
    "BrandDefaults",
    "BrandKit",
    "BrandPalette",
    "EpisodeIntent",
    "ProfileConfig",
    "load_brand",
    "load_brand_defaults",
    "load_brand_palette",
    "load_intent",
    "load_profile",
]
```

Create `graph/src/edit_episode_graph/brief/schemas.py`:

```python
"""Pydantic schemas for the profile + brand + episode-intent context layers.

Mirrors the YAML shapes in spec
`docs/superpowers/specs/2026-05-07-resolved-brief-profiles-brand-architecture.md`
§4. Profiles use a tight `extra="forbid"` schema (operator-authored, must fail
loud on a typo before reaching any LLM node). Brand `defaults` sub-sections are
permissive `dict` values — the operator iterates motion/grade/transition tuning
freely — but the top-level brand keys are still `extra="forbid"` to catch
section typos.

`skill_default` is the sentinel meaning "inherit the skill-canon default"; it is
NOT a hyperframes/skill version pin (memory
`feedback_no_version_pins_evolve_with_skills` — the system never pins versions).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SKILL_DEFAULT = "skill_default"


class OutputCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: int = Field(gt=0)


class CaptionsCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    mode: str | None = None
    safe_zone: str | None = None


class MusicProfileCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    default_mix_db: float | None = None


class CtaCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    placement: str | None = None


class PaddingCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    head_ms: int = Field(ge=0)
    tail_ms: int = Field(ge=0)


class EditCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remove: list[str] = Field(default_factory=list)
    padding: PaddingCfg | None = None


class ProfileConfig(BaseModel):
    """A video-class profile (spec §3 — first-class abstraction, not a bool flag)."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    human_label: str = Field(min_length=1)
    output: OutputCfg | None = None
    pacing: str = SKILL_DEFAULT
    structural_archetype: str = SKILL_DEFAULT
    rhythm_template: str = SKILL_DEFAULT
    captions: CaptionsCfg
    animation_density: str = SKILL_DEFAULT
    music: MusicProfileCfg
    cta: CtaCfg
    edit: EditCfg | None = None


class ContrastPair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fg: str = Field(min_length=1)
    bg: str = Field(min_length=1)


class BrandPalette(BaseModel):
    model_config = ConfigDict(extra="forbid")
    colors: dict[str, str] = Field(default_factory=dict)
    typography: dict[str, str] = Field(default_factory=dict)
    contrast_pairs: list[ContrastPair] = Field(default_factory=list)


class BrandDefaults(BaseModel):
    """Brand-layer defaults laid OVER skill canon (spec §3 — brand wins on conflict).

    Sub-sections are permissive dicts so the operator can iterate; section keys
    are fixed (`extra="forbid"`) to catch typos. Anchors referenced by spec §9:
    `defaults.yaml.motion_language`, `.captions`, `.transitions`.
    """

    model_config = ConfigDict(extra="forbid")

    motion_language: dict[str, Any] = Field(default_factory=dict)
    captions: dict[str, Any] = Field(default_factory=dict)
    cta: dict[str, Any] = Field(default_factory=dict)
    grade: dict[str, Any] = Field(default_factory=dict)
    transitions: dict[str, Any] = Field(default_factory=dict)


class BrandKit(BaseModel):
    """Convenience bundle of the file-backed brand layers for one brand id."""

    model_config = ConfigDict(extra="forbid")

    brand_id: str = Field(min_length=1)
    palette: BrandPalette
    defaults: BrandDefaults


class IntentMusic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: str | None = None
    volume_db: float | None = None


class EpisodeIntent(BaseModel):
    """Per-episode override layer (spec §4 — all fields optional)."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str | None = None
    brand_id: str | None = None
    narrative_context: str | None = None
    target_runtime_s: float | None = None
    must_preserves: list[str] = Field(default_factory=list)
    must_cuts: list[str] = Field(default_factory=list)
    music: IntentMusic | None = None
    animation_wishes: str | None = None
    grade_overrides: dict[str, Any] = Field(default_factory=dict)
    beat_overrides: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `graph/.venv/Scripts/python.exe -m pytest graph/tests/test_brief_schemas.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add graph/src/edit_episode_graph/brief/__init__.py graph/src/edit_episode_graph/brief/schemas.py graph/tests/test_brief_schemas.py
git commit -m "feat(brief): profile/brand/intent Pydantic schemas (HOM-167)"
```

---

### Task 2: Path-injectable loaders

**Files:**
- Create: `graph/src/edit_episode_graph/brief/loaders.py`
- Test: `graph/tests/test_brief_loaders.py`

- [ ] **Step 1: Write the failing test**

Create `graph/tests/test_brief_loaders.py`:

```python
from edit_episode_graph.brief.loaders import (
    load_brand,
    load_intent,
    load_profile,
)
from edit_episode_graph.brief.schemas import EpisodeIntent

PROFILE_YAML = """\
profile_id: talking-head-portrait
human_label: "Talking head — portrait short"
output: {width: 1080, height: 1920, fps: 60}
pacing: tight_conversational
structural_archetype: hook_problem_solution_cta
rhythm_template: "hook-build-PEAK-breathe-CTA"
captions: {enabled: true, mode: karaoke, safe_zone: lower_third_avoid_face}
animation_density: medium
music: {enabled: true, default_mix_db: -18}
cta: {enabled: true, placement: final_scene}
edit:
  remove: [false_starts, cross_range_semantic_duplicates]
  padding: {head_ms: 50, tail_ms: 80}
"""

PALETTE_YAML = """\
colors: {ink: "#0E0E0E", lime: "#C8FF3D"}
typography: {display: "Clash Display", body: "Inter"}
contrast_pairs:
  - {fg: ink, bg: paper}
"""

DEFAULTS_YAML = """\
motion_language: {easing_default: "power2.out"}
captions: {style: karaoke}
cta: {template: cta_scene.html}
grade: {warmth: 0}
transitions: {primary: "blur crossfade"}
"""


def test_load_profile_from_dir(tmp_path):
    pdir = tmp_path / "talking-head-portrait"
    pdir.mkdir()
    (pdir / "profile.yaml").write_text(PROFILE_YAML, encoding="utf-8")
    p = load_profile(pdir)
    assert p.profile_id == "talking-head-portrait"
    assert p.output.height == 1920


def test_load_brand_bundles_palette_and_defaults(tmp_path):
    bdir = tmp_path / "anticodeguy"
    bdir.mkdir()
    (bdir / "palette.yaml").write_text(PALETTE_YAML, encoding="utf-8")
    (bdir / "defaults.yaml").write_text(DEFAULTS_YAML, encoding="utf-8")
    kit = load_brand(bdir)
    assert kit.brand_id == "anticodeguy"
    assert kit.palette.colors["lime"] == "#C8FF3D"
    assert kit.defaults.cta["template"] == "cta_scene.html"


def test_load_intent_missing_file_returns_empty(tmp_path):
    intent = load_intent(tmp_path / "nope.yaml")
    assert intent == EpisodeIntent()


def test_load_intent_empty_file_falls_through(tmp_path):
    f = tmp_path / "intent.yaml"
    f.write_text("", encoding="utf-8")
    assert load_intent(f) == EpisodeIntent()


def test_load_intent_with_overrides(tmp_path):
    f = tmp_path / "intent.yaml"
    f.write_text("profile_id: explainer\nmusic: {track_id: tutorial-clean-2}\n", encoding="utf-8")
    intent = load_intent(f)
    assert intent.profile_id == "explainer"
    assert intent.music.track_id == "tutorial-clean-2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `graph/.venv/Scripts/python.exe -m pytest graph/tests/test_brief_loaders.py -q`
Expected: FAIL — `ImportError: cannot import name 'load_profile' from ...brief.loaders` (module not found / not defined)

- [ ] **Step 3: Write minimal implementation**

Create `graph/src/edit_episode_graph/brief/loaders.py`:

```python
"""Path-injectable loaders for the file-backed context layers.

Pure functions: each takes a directory/file ``Path`` and returns a validated
model. They do NOT decide WHERE ``profiles/`` or ``brand/`` live on disk — that
path-resolution policy (repo_root vs project_root, CLI/intent/default selection)
is the ``resolve_episode_brief`` node's job in HOM-166. Keeping these pure makes
the skeleton trivially testable with a ``tmp_path`` fixture and keeps HOM-167
free of the resolution-priority engine.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schemas import (
    BrandDefaults,
    BrandKit,
    BrandPalette,
    EpisodeIntent,
    ProfileConfig,
)


def _read_yaml(path: Path) -> dict[str, Any]:
    """``yaml.safe_load`` a file to a dict; empty file -> ``{}``."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_profile(profile_dir: Path) -> ProfileConfig:
    """Load ``<profile_dir>/profile.yaml`` into a validated ``ProfileConfig``."""
    return ProfileConfig.model_validate(_read_yaml(profile_dir / "profile.yaml"))


def load_brand_palette(brand_dir: Path) -> BrandPalette:
    return BrandPalette.model_validate(_read_yaml(brand_dir / "palette.yaml"))


def load_brand_defaults(brand_dir: Path) -> BrandDefaults:
    return BrandDefaults.model_validate(_read_yaml(brand_dir / "defaults.yaml"))


def load_brand(brand_dir: Path) -> BrandKit:
    """Bundle palette + defaults for the brand at ``brand_dir`` (id == dir name)."""
    return BrandKit(
        brand_id=brand_dir.name,
        palette=load_brand_palette(brand_dir),
        defaults=load_brand_defaults(brand_dir),
    )


def load_intent(intent_path: Path) -> EpisodeIntent:
    """Load an optional ``intent.yaml``.

    Missing file OR empty file -> an all-default ``EpisodeIntent`` (spec §4:
    "Пустой intent.yaml → дефолты профиля → дефолты бренда → канон").
    """
    if not intent_path.exists():
        return EpisodeIntent()
    return EpisodeIntent.model_validate(_read_yaml(intent_path))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `graph/.venv/Scripts/python.exe -m pytest graph/tests/test_brief_loaders.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add graph/src/edit_episode_graph/brief/loaders.py graph/src/edit_episode_graph/brief/__init__.py graph/tests/test_brief_loaders.py
git commit -m "feat(brief): path-injectable profile/brand/intent loaders (HOM-167)"
```

---

### Task 3: Committed profile + brand skeleton files

**Files:**
- Create: `profiles/canonical/profile.yaml`
- Create: `profiles/talking-head-portrait/profile.yaml`
- Create: `profiles/talking-head-portrait/house-style.md`
- Create: `brand/anticodeguy/brand.md`
- Create: `brand/anticodeguy/palette.yaml`
- Create: `brand/anticodeguy/defaults.yaml`
- Create: `brand/anticodeguy/assets/logo.svg`
- Create: `brand/anticodeguy/assets/symbol-lime.svg`
- Create: `brand/anticodeguy/templates/cta_scene.html`
- Create: `brand/anticodeguy/music/.gitkeep`

- [ ] **Step 1: Create `profiles/canonical/profile.yaml`**

```yaml
# Canonical (regression) profile — empty override.
# Every field is `skill_default` / disabled so the pipeline runs pure skill
# canon with no brand or video-class opinions. Used for regression baselines.
profile_id: canonical
human_label: "Canonical (regression)"
pacing: skill_default
structural_archetype: skill_default
rhythm_template: skill_default
captions:
  enabled: false
animation_density: skill_default
music:
  enabled: false
cta:
  enabled: false
```

- [ ] **Step 2: Create `profiles/talking-head-portrait/profile.yaml`**

```yaml
# Talking-head portrait short (1080x1920@60). Verbatim from spec §4.
profile_id: talking-head-portrait
human_label: "Talking head — portrait short"
output:
  width: 1080
  height: 1920
  fps: 60
pacing: tight_conversational
structural_archetype: hook_problem_solution_cta
rhythm_template: "hook-build-PEAK-breathe-CTA"
captions:
  enabled: true
  mode: karaoke
  safe_zone: lower_third_avoid_face
animation_density: medium
music:
  enabled: true
  default_mix_db: -18           # fixed mix vs voice; canonical mix without sidechain
cta:
  enabled: true
  placement: final_scene
edit:
  remove:
    - false_starts
    - corrected_phrases
    - dead_air
    - cross_range_semantic_duplicates
  padding:
    head_ms: 50
    tail_ms: 80
```

- [ ] **Step 3: Create `profiles/talking-head-portrait/house-style.md`**

H2 anchors below are load-bearing — spec §9 anchor lists pull `## Pacing`,
`## Structural archetype`, `## Rhythm template`, `## Edit rules` verbatim into
node briefs via the canon loader. Do not rename them.

```markdown
# House style — Talking head (portrait short)

Video-class guidance for `talking-head-portrait`. The brand layer
(`brand/<id>/`) sits ON TOP of this; skill canon sits underneath. This file
captures what the skill canon leaves to conversation/style for this class.

## Pacing

Tight and conversational. Cut hard on the beat of each idea; no dead air
between sentences. Favor momentum over breathing room — a portrait short loses
the viewer in the first 2 seconds if the hook drags.

## Structural archetype

`hook → problem → solution → CTA`. Open on the single most arresting line,
state the tension, deliver the payoff, end on a subscribe/follow CTA scene.

## Rhythm template

`hook-build-PEAK-breathe-CTA`. One peak per short; the breathe beat right before
the CTA gives the payoff room to land. Vary scene motion so adjacent beats don't
repeat the same ambient pattern.

## Edit rules

Remove false starts, corrected phrases, dead air, and cross-range semantic
duplicates (the same idea delivered twice across non-adjacent ranges — the
clean-session brief-author would never leave both). Pad cuts head 50ms /
tail 80ms to avoid clipping plosives.
```

- [ ] **Step 4: Create `brand/anticodeguy/palette.yaml`**

```yaml
# anticodeguy brand palette. Minimal real values — operator iterates.
colors:
  ink: "#0E0E0E"        # near-black foreground / text
  paper: "#FAFAF7"      # off-white background
  lime: "#C8FF3D"       # signature accent
  slate: "#3A3F45"      # secondary text / muted
typography:
  display: "Clash Display"
  body: "Inter"
contrast_pairs:
  - fg: ink
    bg: paper
  - fg: paper
    bg: ink
  - fg: ink
    bg: lime
```

- [ ] **Step 5: Create `brand/anticodeguy/defaults.yaml`**

```yaml
# anticodeguy brand defaults laid OVER skill canon. Sub-sections are free-form
# (operator iterates); section keys are fixed. `cta.template` references a file
# under templates/ — keep it in sync (the skeleton test asserts it resolves).
motion_language:
  easing_default: "power2.out"
  intensity: balanced
  signature: "lime accent sweep on emphasis words"
captions:
  style: karaoke
  font: "Inter"
  highlight_color: lime
cta:
  template: cta_scene.html
  text: "Subscribe for more"
grade:
  warmth: 0
  contrast: 0
  saturation: 0
transitions:
  primary: "blur crossfade"
  accents:
    - "cinematic zoom"
    - "fade-to-black"
```

- [ ] **Step 6: Create `brand/anticodeguy/brand.md`**

H2 anchors `## Voice` and `## Visual identity` are pulled by spec §9
(`p3_strategy`, `p4_design_system`). `## Layer composition` satisfies DoD item 4.

```markdown
# anticodeguy — brand canon

The brand layer for the `anticodeguy` channel. Adds invariants ON TOP of skill
canon; it never forks or overrides skill-canon production-correctness rules.

## Voice

Direct, dry, builder-to-builder. No hype words, no "game-changer". Short
declarative sentences. Confident but self-aware. Speaks to people who ship.

## Visual identity

High-contrast editorial: near-black ink on off-white paper, one signature lime
accent used sparingly for emphasis. Clash Display for titles, Inter for body.
Generous negative space; motion is purposeful, never decorative for its own sake.

## Layer composition

The resolved brief composes four context layers, lowest precedence first:

`skill_canon  <  profile  <  brand  <  episode_intent`

- **skill_canon** — read-only upstream rules (video-use / hyperframes SKILL.md).
- **profile** — the video-class defaults (pacing, archetype, rhythm, captions).
- **brand** — these files (voice, palette, motion language, CTA, grade).
- **episode_intent** — optional per-episode `intent.yaml` overrides.

On a formal conflict the higher layer wins **except** skill-canon production-
correctness hard rules: the brand layer may NOT disable or override a canonical
hard rule (e.g. audio-pop fades, caption exit guarantees). Brand opinions live
only in the space the skill canon leaves to conversation/style. The precedence
engine that enforces this is the `resolve_episode_brief` node (HOM-166).
```

- [ ] **Step 7: Create placeholder assets + template + music keep-file**

`brand/anticodeguy/assets/logo.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 64" role="img" aria-label="anticodeguy logo (placeholder)">
  <rect width="240" height="64" fill="#0E0E0E"/>
  <text x="16" y="42" font-family="monospace" font-size="28" fill="#C8FF3D">anticodeguy</text>
</svg>
```

`brand/anticodeguy/assets/symbol-lime.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="anticodeguy symbol (placeholder)">
  <rect width="64" height="64" rx="12" fill="#C8FF3D"/>
  <path d="M20 40 L32 20 L44 40 Z" fill="#0E0E0E"/>
</svg>
```

`brand/anticodeguy/templates/cta_scene.html` (placeholder static HTML — NOT a hyperframes-registry component):

```html
<!-- anticodeguy CTA scene — placeholder static template (HOM-167).
     Real composition content lands with the CTA-gate ticket. -->
<section class="cta-scene" data-brand="anticodeguy">
  <h2>Subscribe for more</h2>
  <img src="../assets/symbol-lime.svg" alt="anticodeguy" width="64" height="64" />
</section>
```

`brand/anticodeguy/music/.gitkeep`:

```
# Music tracks + music/defaults.yaml are populated by the §15.9 music-library ticket.
```

- [ ] **Step 8: Commit**

```bash
git add profiles brand
git commit -m "feat(brief): commit canonical + talking-head profiles and anticodeguy brand skeleton (HOM-167)"
```

---

### Task 4: Skeleton parse + shape + no-broken-ref test

**Files:**
- Test: `graph/tests/test_brief_skeleton.py`

- [ ] **Step 1: Write the failing test**

Create `graph/tests/test_brief_skeleton.py`:

```python
"""Loads the REAL committed profiles/ + brand/ skeleton and asserts shape.

Resolution PRECEDENCE (CLI>intent>profile>brand>canon) + brief.resolved.yaml
serialization is HOM-166's `resolve_episode_brief` node — this test proves the
committed skeleton is loadable, shape-stable, and has no broken asset refs.
"""
from pathlib import Path

from edit_episode_graph._paths import repo_root
from edit_episode_graph.brief.loaders import load_brand, load_intent, load_profile

PROFILES = repo_root() / "profiles"
BRAND = repo_root() / "brand"


def test_canonical_profile_committed():
    p = load_profile(PROFILES / "canonical")
    assert p.profile_id == "canonical"
    assert p.captions.enabled is False
    assert p.music.enabled is False
    assert p.cta.enabled is False
    assert p.output is None


def test_talking_head_profile_committed():
    p = load_profile(PROFILES / "talking-head-portrait")
    assert p.profile_id == "talking-head-portrait"
    assert (p.output.width, p.output.height, p.output.fps) == (1080, 1920, 60)
    assert p.captions.mode == "karaoke"
    assert p.music.default_mix_db == -18
    assert "cross_range_semantic_duplicates" in p.edit.remove
    assert (p.edit.padding.head_ms, p.edit.padding.tail_ms) == (50, 80)


def test_talking_head_house_style_anchors_present():
    text = (PROFILES / "talking-head-portrait" / "house-style.md").read_text(encoding="utf-8")
    for anchor in ("## Pacing", "## Structural archetype", "## Rhythm template", "## Edit rules"):
        assert anchor in text


def test_anticodeguy_brand_committed():
    kit = load_brand(BRAND / "anticodeguy")
    assert kit.brand_id == "anticodeguy"
    assert kit.palette.colors["lime"] == "#C8FF3D"
    assert kit.palette.typography["display"] == "Clash Display"
    assert kit.defaults.transitions["primary"] == "blur crossfade"


def test_anticodeguy_brand_md_anchors_present():
    text = (BRAND / "anticodeguy" / "brand.md").read_text(encoding="utf-8")
    for anchor in ("## Voice", "## Visual identity", "## Layer composition"):
        assert anchor in text


def test_cta_template_ref_resolves_on_disk():
    kit = load_brand(BRAND / "anticodeguy")
    template_name = kit.defaults.cta["template"]
    assert (BRAND / "anticodeguy" / "templates" / template_name).is_file()


def test_brand_assets_exist():
    assets = BRAND / "anticodeguy" / "assets"
    assert (assets / "logo.svg").is_file()
    assert (assets / "symbol-lime.svg").is_file()


def test_music_dir_scaffolded_empty():
    music = BRAND / "anticodeguy" / "music"
    assert music.is_dir()
    # No track files yet — populated by §15.9. Only the keep-file is present.
    assert [p.name for p in music.iterdir()] == [".gitkeep"]


def test_four_layer_shape_snapshot():
    profile = load_profile(PROFILES / "talking-head-portrait")
    brand = load_brand(BRAND / "anticodeguy")
    intent = load_intent(Path("does-not-exist.yaml"))  # empty intent layer

    composed = {
        "profile_id": profile.profile_id,
        "brand_id": brand.brand_id,
        "captions_enabled": profile.captions.enabled,
        "music_enabled": profile.music.enabled,
        "palette_colors": sorted(brand.palette.colors.keys()),
        "intent_has_overrides": intent != type(intent)(),
    }
    assert composed == {
        "profile_id": "talking-head-portrait",
        "brand_id": "anticodeguy",
        "captions_enabled": True,
        "music_enabled": True,
        "palette_colors": ["ink", "lime", "paper", "slate"],
        "intent_has_overrides": False,
    }
```

- [ ] **Step 2: Run test to verify it fails, then passes**

Run: `graph/.venv/Scripts/python.exe -m pytest graph/tests/test_brief_skeleton.py -q`
Expected: PASS (9 passed) — the committed files from Task 3 already satisfy it. If any FAIL, fix the committed file to match (e.g. a palette color name mismatch), not the test's expected shape.

- [ ] **Step 3: Run the FULL graph suite (regression)**

Run: `graph/.venv/Scripts/python.exe -m pytest graph/tests -q`
Expected: PASS — previous green baseline (803 passed) + the new brief tests, zero failures.

- [ ] **Step 4: Run the outer test root (regression — disk-io lint etc.)**

Run: `python -m pytest tests -q` (uses the outer venv per `tests/README.md`)
Expected: PASS — 258 passed, 14 skipped (unchanged). Confirms the new `brief/` package did NOT trip `test_disk_io_allowlist.py` (loaders are outside `nodes/`+`gates/`).

- [ ] **Step 5: Commit**

```bash
git add graph/tests/test_brief_skeleton.py
git commit -m "test(brief): skeleton parse/shape/no-broken-ref + four-layer shape snapshot (HOM-167)"
```

---

## Self-Review

**1. Spec coverage (DoD items):**
- "Directories created, all schema files parse with PyYAML / pydantic loaders" → Tasks 1-4 (`load_profile`/`load_brand` validate every committed file).
- "resolve_episode_brief … successfully reads …" → **deferred to HOM-166** (DoD says "when wired by HOM-XXX brief-substrate ticket"); scope table documents this.
- "Empty intent.yaml falls through to defaults without error" → `test_load_intent_empty_file_falls_through` + `test_load_intent_missing_file_returns_empty` (Task 2).
- "Documentation note in brand.md explaining the layer composition rule" → Task 3 Step 6 `## Layer composition` + `test_anticodeguy_brand_md_anchors_present` (Task 4).
- "Brand assets are real / placeholder; no broken refs from defaults.yaml" → `test_cta_template_ref_resolves_on_disk` + `test_brand_assets_exist` (Task 4).
- "Test that resolves all four layers and snapshot-asserts shape" → `test_four_layer_shape_snapshot` (Task 4), scoped to load+shape (precedence is HOM-166).

**2. Placeholder scan:** none — every step has complete file content or an exact command.

**3. Type consistency:** `ProfileConfig`/`BrandKit`/`BrandPalette`/`BrandDefaults`/`EpisodeIntent` and `load_profile`/`load_brand`/`load_intent` names are identical across Tasks 1, 2, 4 and `__init__.py` exports. `defaults.cta["template"]` (dict access — `BrandDefaults.cta` is `dict[str, Any]`) is consistent between `defaults.yaml`, the schema, and the test.

**Out-of-scope reminders for the implementer:** do NOT add a graph node, do NOT add precedence-merge logic, do NOT add a version-pin field, do NOT populate `music/` with tracks or `music/defaults.yaml`.
