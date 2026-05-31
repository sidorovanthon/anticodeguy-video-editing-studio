"""Runtime canon-section loader (HOM-377, spec §9).

Pulls **verbatim** canon sections out of the live `hyperframes` / `video-use`
skills **by section anchor** (never line number) and splats them into LLM-node
briefs at render time. This is the durable fix for the line-pin rot class
(F1/F4, audit `docs/retros/retro-2026-05-31-langgraph-architecture-audit.md`):
the skills auto-update via Task Scheduler, line numbers drift on every pull,
section names do not.

Three contracts make float-latest skills safe for the graph:

1. **Anchor, never index.** `load_skill_section` matches an H2/H3 heading by
   ``str.startswith`` on the heading text; index/line extraction is forbidden
   (fragile to renumbering). Sub-list-item extraction matches a markdown list
   item by its leading text (``item="Converse"`` etc.), again never by index.
2. **Fail loud.** A heading / list-item that does not resolve (renamed, moved,
   file deleted) raises :class:`CanonAnchorMissing` — never a silent-empty
   block smuggled into an LLM brief. :func:`verify_anchors` walks every
   registered anchor once at graph build (import time, via
   ``build_graph_uncompiled``) so an upstream rename is a startup hard-fail
   before any LLM dispatch.
3. **Cache-correct.** :func:`canon_fingerprint` hashes the resolved blocks for
   a node; consuming nodes fold it into ``make_llm_key`` extras, so a canon
   edit upstream invalidates exactly the nodes that pull the changed section —
   "go to the skill every run" becomes "every cache-miss". The
   :data:`NODE_CANON_ANCHORS` manifest is the single source of truth for which
   anchors a node consumes; the same manifest drives render-context injection
   (:func:`load_canon_blocks`), the fingerprint, and `verify_anchors`, so the
   rendered brief and the cache key can never drift apart.

Skill roots resolve to the live auto-updated copies
(``~/.agents/skills/hyperframes``, ``~/.claude/skills/video-use``); tests
override via the ``HOMESTUDIO_CANON_ROOT_*`` env vars to point at a fixture
tree (hermetic loader unit tests + the canon-invalidation fingerprint test).

Profile / brand sections (spec §9.1 ``assemble_brief_context``) are NOT handled
here — that three-source assembler is the HOM-166 / M6 deliverable. This module
is skill-canon only.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------- #
# Skill-root resolution
# --------------------------------------------------------------------------- #

# Short name → live skill root. hyperframes lives under ``~/.agents`` (the
# functional fallback in ``gates/animation_map.py`` resolves there); video-use
# under ``~/.claude``. Tests override per-skill via the env vars below.
_DEFAULT_ROOTS: dict[str, Path] = {
    "hyperframes": Path.home() / ".agents" / "skills" / "hyperframes",
    "video-use": Path.home() / ".claude" / "skills" / "video-use",
}

_ROOT_ENV: dict[str, str] = {
    "hyperframes": "HOMESTUDIO_CANON_ROOT_HYPERFRAMES",
    "video-use": "HOMESTUDIO_CANON_ROOT_VIDEO_USE",
}


def skill_root(skill: str) -> Path:
    """Resolve a skill short-name to its root dir (env override wins).

    Resolved on every call (no caching) so a test that flips
    ``HOMESTUDIO_CANON_ROOT_*`` mid-session takes effect immediately.
    """
    if skill not in _DEFAULT_ROOTS:
        raise KeyError(
            f"unknown canon skill {skill!r}; known: {sorted(_DEFAULT_ROOTS)}"
        )
    override = os.environ.get(_ROOT_ENV[skill])
    return Path(override) if override else _DEFAULT_ROOTS[skill]


# --------------------------------------------------------------------------- #
# Errors + the per-node anchor descriptor
# --------------------------------------------------------------------------- #


class CanonAnchorMissing(RuntimeError):
    """Raised when a canon anchor (heading or list-item) does not resolve.

    Carries the locating fields so :func:`verify_anchors` and node dispatch
    surface a single actionable line: which skill / file / anchor failed and
    that the live skill almost certainly changed upstream.
    """

    def __init__(
        self,
        skill: str,
        rel_path: str,
        anchor: str,
        *,
        item: str | None = None,
        reason: str = "did not resolve",
    ) -> None:
        self.skill = skill
        self.rel_path = rel_path
        self.anchor = anchor
        self.item = item
        loc = f"{skill}:{rel_path} §{anchor!r}"
        if item is not None:
            loc += f" → list item {item!r}"
        super().__init__(
            f"canon anchor {loc} {reason}. The live skill likely changed "
            "upstream (skills auto-update via Task Scheduler). Check the "
            "skill's current headings/list and update NODE_CANON_ANCHORS + the "
            "brief — cite by section name, never line number (HOM-376/HOM-377)."
        )


@dataclass(frozen=True)
class CanonRef:
    """One verbatim canon block a node depends on.

    * ``key`` — stable name the brief references as ``{{ canon.<key> }}`` and
      the fingerprint/verify machinery iterate over.
    * ``skill`` — ``"hyperframes"`` | ``"video-use"``.
    * ``rel_path`` — path under the skill root (``"SKILL.md"``,
      ``"references/motion-principles.md"``).
    * ``anchor`` — the H2/H3 heading prefix, including its ``##``/``###``
      marker (matched via ``startswith``).
    * ``item`` — optional leading text of a markdown list item to extract from
      within the section (``"Converse"``, ``"Self-eval"``). ``None`` pulls the
      whole section.
    """

    key: str
    skill: str
    rel_path: str
    anchor: str
    item: str | None = None


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #

_HEADING_RE = re.compile(r"^(#{1,6})\s")
_LIST_ITEM_RE = re.compile(r"^(\s*)(?:\d+\.|[-*+])\s+(.*)$")
# Minimum heading-text length (excluding the ``#`` marker + its space): a floor
# against trivially-short anchors that could prefix-match several headings.
# Spec §9.3 suggests ~10; 8 keeps margin below the shortest real anchor
# (``## EDL format`` = 10) without rejecting borderline-valid short headings.
# The >1-match ambiguity check in ``load_skill_section`` is the PRIMARY guard;
# this length floor only catches an obviously-too-short developer mistake early.
_MIN_ANCHOR_TEXT = 8


def _heading_level(line: str) -> int:
    """ATX heading level (number of leading ``#``), or 0 if not a heading."""
    m = _HEADING_RE.match(line)
    return len(m.group(1)) if m else 0


def _read_skill_file(skill: str, rel_path: str) -> str:
    path = skill_root(skill) / rel_path
    if not path.is_file():
        raise CanonAnchorMissing(
            skill, rel_path, "(file)", reason=f"file not found at {path}"
        )
    return path.read_text(encoding="utf-8")


def _extract_list_item(
    section_lines: list[str], item: str, *, skill: str, rel_path: str, anchor: str
) -> str:
    """Return the verbatim markdown list item (plus indented continuation).

    Matches a list item whose text — after stripping its ``-``/``N.`` marker
    and leading ``*`` emphasis — ``startswith(item)``. Continuation lines (more
    indented, or blank) are captured until the next list item at the same or
    lower indent. Index-based selection is intentionally NOT supported.
    """
    matches: list[tuple[int, int]] = []  # (line_index, indent_width)
    for idx in range(1, len(section_lines)):  # skip the heading at [0]
        m = _LIST_ITEM_RE.match(section_lines[idx])
        if not m:
            continue
        normalized = m.group(2).lstrip("*").strip()
        if normalized.startswith(item):
            matches.append((idx, len(m.group(1))))

    if not matches:
        raise CanonAnchorMissing(
            skill, rel_path, anchor, item=item, reason="list item not found"
        )
    if len(matches) > 1:
        raise CanonAnchorMissing(
            skill, rel_path, anchor, item=item,
            reason=f"ambiguous — {len(matches)} list items match leading text",
        )

    start_idx, start_indent = matches[0]
    end_idx = len(section_lines)
    for j in range(start_idx + 1, len(section_lines)):
        line = section_lines[j]
        if not line.strip():
            continue  # blank lines are part of the item's continuation
        if _heading_level(line) > 0:
            end_idx = j
            break
        m2 = _LIST_ITEM_RE.match(line)
        if m2 and len(m2.group(1)) <= start_indent:
            end_idx = j
            break

    block = "\n".join(section_lines[start_idx:end_idx]).rstrip()
    if not block.strip():
        raise CanonAnchorMissing(
            skill, rel_path, anchor, item=item, reason="empty extraction"
        )
    return block + "\n"


def _extract_section_block(
    text: str,
    anchor: str,
    *,
    item: str | None,
    min_anchor_text: int,
    skill: str,
    rel_path: str,
) -> str:
    """Extract one verbatim section (optionally one list item) from ``text``.

    Shared core for :func:`load_skill_section` (skill-root resolved) and
    :func:`load_section` (direct path). ``skill``/``rel_path`` only flavour the
    actionable :class:`CanonAnchorMissing` messages.
    """
    anchor = anchor.strip()
    level = _heading_level(anchor + " ")
    if level == 0:
        raise ValueError(
            f"anchor must start with a markdown heading marker (## / ###): {anchor!r}"
        )
    if len(anchor) - level - 1 < min_anchor_text:
        raise ValueError(
            f"anchor text too short to match safely: {anchor!r} "
            f"(need >= {min_anchor_text} chars after the heading marker)"
        )

    lines = text.splitlines()
    heading_idxs = [
        i for i, line in enumerate(lines)
        if _heading_level(line) > 0 and line.strip().startswith(anchor)
    ]
    if not heading_idxs:
        raise CanonAnchorMissing(skill, rel_path, anchor, item=item, reason="heading not found")
    if len(heading_idxs) > 1:
        raise CanonAnchorMissing(
            skill, rel_path, anchor, item=item,
            reason=f"ambiguous — {len(heading_idxs)} headings match prefix",
        )

    start = heading_idxs[0]
    end = len(lines)
    for j in range(start + 1, len(lines)):
        lv = _heading_level(lines[j])
        if 0 < lv <= level:
            end = j
            break
    section_lines = lines[start:end]

    if item is not None:
        return _extract_list_item(
            section_lines, item, skill=skill, rel_path=rel_path, anchor=anchor
        )

    block = "\n".join(section_lines).rstrip()
    if not block.strip():
        raise CanonAnchorMissing(skill, rel_path, anchor, reason="empty extraction")
    return block + "\n"


def load_skill_section(
    skill: str, rel_path: str, anchor: str, *, item: str | None = None
) -> str:
    """Return the verbatim canon block for ``anchor`` (optionally one list item).

    Skill-canon flavour: resolves ``skill`` + ``rel_path`` to the live skill file
    and extracts with the strict skill-canon anchor floor (``_MIN_ANCHOR_TEXT``).
    Raises :class:`CanonAnchorMissing` on missing file / zero-or-many heading
    match / unresolved list item / empty block.
    """
    text = _read_skill_file(skill, rel_path)
    return _extract_section_block(
        text, anchor, item=item, min_anchor_text=_MIN_ANCHOR_TEXT,
        skill=skill, rel_path=rel_path,
    )


# Relaxed floor for profile/brand: our own operator-authored files may have
# short legit headings (`## Voice` = 5, `## Pacing` = 6). The >1-match ambiguity
# check in `_extract_section_block` is the primary guard; 3 still catches an
# obviously-too-short developer mistake without rejecting real headings.
_MIN_SECTION_ANCHOR_TEXT = 3


def load_section(
    path: Path,
    anchor: str,
    *,
    item: str | None = None,
    min_anchor_text: int = _MIN_ANCHOR_TEXT,
    source_label: str = "(file)",
) -> str:
    """Return the verbatim section for ``anchor`` from the markdown file at ``path``.

    Path-based generalization of :func:`load_skill_section` (HOM-114). Used for
    profile/brand layers whose roots are resolved per-episode. ``source_label``
    flavours the error message. Raises :class:`CanonAnchorMissing` on a missing
    file (a deleted/renamed file is loud, never silent-empty).
    """
    if not path.is_file():
        raise CanonAnchorMissing(
            source_label, path.name, "(file)", reason=f"file not found at {path}"
        )
    text = path.read_text(encoding="utf-8")
    return _extract_section_block(
        text, anchor, item=item, min_anchor_text=min_anchor_text,
        skill=source_label, rel_path=path.name,
    )


# --------------------------------------------------------------------------- #
# Per-node anchor manifest (spec §9 per-node anchor list — skill-canon only)
# --------------------------------------------------------------------------- #
#
# Curated NON-NEGOTIABLE / load-bearing sections per node — NOT every section a
# brief cites. On-demand references (typography, beat-direction, techniques,
# transcript-guide, dynamic-techniques) stay as Read citations: canon's own
# ``## References (loaded on demand)`` model treats them as load-on-demand, and
# splatting them verbatim would bloat every brief. profile/brand sections from
# spec §9 (house-style/brand/palette/defaults) are HOM-166/M6 scope.

_VIDEO_USE_PROCESS = "## The process"
_VIDEO_USE_CUT_CRAFT = "## Cut craft (techniques)"
_VIDEO_USE_HARD_RULES = "## Hard Rules (production correctness — non-negotiable)"

_HF_LAYOUT = "## Layout Before Animation"
_HF_RULES = "## Rules (Non-Negotiable)"
_HF_SCENE_TRANSITIONS = "## Scene Transitions (Non-Negotiable)"
_HF_ANIMATION_GUARDRAILS = "## Animation Guardrails"
_MOTION_PRINCIPLES = "references/motion-principles.md"
_LOAD_BEARING_GSAP = "## Load-Bearing GSAP Rules"

# p4_beat / p4_redispatch_beat share the same authoring canon (redispatch is the
# retry-flavoured variant of the same per-scene Pattern A task).
_BEAT_ANCHORS: tuple[CanonRef, ...] = (
    CanonRef("layout_before_animation", "hyperframes", "SKILL.md", _HF_LAYOUT),
    CanonRef("rules_non_negotiable", "hyperframes", "SKILL.md", _HF_RULES),
    CanonRef("scene_transitions", "hyperframes", "SKILL.md", _HF_SCENE_TRANSITIONS),
    CanonRef("animation_guardrails", "hyperframes", "SKILL.md", _HF_ANIMATION_GUARDRAILS),
    CanonRef("load_bearing_gsap", "hyperframes", _MOTION_PRINCIPLES, _LOAD_BEARING_GSAP),
)

NODE_CANON_ANCHORS: dict[str, tuple[CanonRef, ...]] = {
    "p3_pre_scan": (
        CanonRef("process_inventory", "video-use", "SKILL.md", _VIDEO_USE_PROCESS, item="Inventory"),
        CanonRef("process_pre_scan", "video-use", "SKILL.md", _VIDEO_USE_PROCESS, item="Pre-scan"),
        CanonRef("cut_craft", "video-use", "SKILL.md", _VIDEO_USE_CUT_CRAFT),
    ),
    "p3_strategy": (
        CanonRef("process_propose_strategy", "video-use", "SKILL.md", _VIDEO_USE_PROCESS, item="Propose strategy"),
        CanonRef("cut_craft", "video-use", "SKILL.md", _VIDEO_USE_CUT_CRAFT),
        CanonRef("color_grade", "video-use", "SKILL.md", "## Color grade (when requested)"),
    ),
    "p3_edl_select": (
        CanonRef("editor_sub_agent_brief", "video-use", "SKILL.md", "## Editor sub-agent brief (for multi-take selection)"),
        CanonRef("edl_format", "video-use", "SKILL.md", "## EDL format"),
        CanonRef("hard_rules", "video-use", "SKILL.md", _VIDEO_USE_HARD_RULES),
        CanonRef("cut_craft", "video-use", "SKILL.md", _VIDEO_USE_CUT_CRAFT),
    ),
    "p3_self_eval": (
        CanonRef("process_self_eval", "video-use", "SKILL.md", _VIDEO_USE_PROCESS, item="Self-eval"),
        CanonRef("hard_rules", "video-use", "SKILL.md", _VIDEO_USE_HARD_RULES),
    ),
    "p4_beat": _BEAT_ANCHORS,
    "p4_redispatch_beat": _BEAT_ANCHORS,
    "p4_captions_layer": (
        CanonRef("caption_exit_guarantee", "hyperframes", "references/captions.md", "## Caption Exit Guarantee"),
        CanonRef("text_overflow_prevention", "hyperframes", "references/captions.md", "## Text Overflow Prevention"),
        CanonRef("positioning", "hyperframes", "references/captions.md", "## Positioning"),
        CanonRef("constraints", "hyperframes", "references/captions.md", "## Constraints"),
    ),
}


# --------------------------------------------------------------------------- #
# Profile / brand markdown-section manifest (HOM-114, spec §9)
# --------------------------------------------------------------------------- #
#
# MARKDOWN sections only — `house-style.md` / `brand.md`. The YAML brand config
# (`defaults.yaml.transitions/.motion_language/.captions`, `palette.yaml`) is
# loaded by HOM-167's pydantic models and composed + fingerprinted by HOM-166's
# `resolve_episode_brief` (`brief.fingerprint`), NOT here. Refs are RELATIVE to a
# per-episode resolved profile/brand dir (HOM-166 supplies the dir at call time);
# the `canonical` profile ships no `house-style.md` and resolves to `{}`.

_PROFILE_FILE = "house-style.md"
_BRAND_FILE = "brand.md"


@dataclass(frozen=True)
class SectionRef:
    """One verbatim markdown section a node depends on, relative to a layer dir.

    Distinct from :class:`CanonRef` (which carries a global ``skill`` short-name);
    profile/brand roots are per-episode, so only ``rel_path`` + ``anchor`` are
    fixed here and the dir is supplied at load time.
    """

    key: str
    rel_path: str
    anchor: str
    item: str | None = None


_HS_PACING = SectionRef("pacing", _PROFILE_FILE, "## Pacing")
_HS_ARCHETYPE = SectionRef("structural_archetype", _PROFILE_FILE, "## Structural archetype")
_HS_RHYTHM = SectionRef("rhythm_template", _PROFILE_FILE, "## Rhythm template")
_HS_EDIT_RULES = SectionRef("edit_rules", _PROFILE_FILE, "## Edit rules")

NODE_PROFILE_ANCHORS: dict[str, tuple[SectionRef, ...]] = {
    "p3_strategy": (_HS_PACING, _HS_ARCHETYPE),
    "p3_edl_select": (_HS_EDIT_RULES,),
    # "full house-style.md" per §9 — all four authored sections, verbatim.
    "p4_design_system": (_HS_PACING, _HS_ARCHETYPE, _HS_RHYTHM, _HS_EDIT_RULES),
    "p4_prompt_expansion": (_HS_RHYTHM,),
}

NODE_BRAND_ANCHORS: dict[str, tuple[SectionRef, ...]] = {
    "p3_strategy": (SectionRef("voice", _BRAND_FILE, "## Voice"),),
    "p4_design_system": (SectionRef("visual_identity", _BRAND_FILE, "## Visual identity"),),
}


def _load_layer_blocks(
    refs: tuple[SectionRef, ...], layer_dir: Path, source_label: str
) -> dict[str, str]:
    """Resolve ``refs`` against ``layer_dir`` → ``{key: verbatim_block}``.

    Two-tier contract (spec §9 fail-loud, reconciled with the canonical baseline):
      * referenced file ABSENT → that ref is skipped (the layer legitimately omits
        prose — e.g. the ``canonical`` profile has no ``house-style.md``);
      * referenced file PRESENT but anchor missing → :class:`CanonAnchorMissing`
        (loud — a renamed/deleted section must never become a silent-empty brief).
    Accidental deletion of a *reference* layer's file is caught earlier by
    :func:`verify_anchors` at graph build.
    """
    out: dict[str, str] = {}
    for ref in refs:
        path = layer_dir / ref.rel_path
        if not path.is_file():
            continue
        out[ref.key] = load_section(
            path, ref.anchor, item=ref.item,
            min_anchor_text=_MIN_SECTION_ANCHOR_TEXT,
            source_label=f"{source_label}:{layer_dir.name}",
        )
    return out


def load_profile_blocks(node: str, profile_dir: Path) -> dict[str, str]:
    """Verbatim profile (`house-style.md`) blocks registered on ``node``."""
    return _load_layer_blocks(NODE_PROFILE_ANCHORS.get(node, ()), profile_dir, "profile")


def load_brand_blocks(node: str, brand_dir: Path) -> dict[str, str]:
    """Verbatim brand (`brand.md`) blocks registered on ``node``."""
    return _load_layer_blocks(NODE_BRAND_ANCHORS.get(node, ()), brand_dir, "brand")


# --------------------------------------------------------------------------- #
# Node-facing API: render-context blocks, cache fingerprint, startup verify
# --------------------------------------------------------------------------- #


def load_canon_blocks(node: str) -> dict[str, str]:
    """Return ``{ref.key: verbatim_block}`` for every anchor registered on ``node``.

    Splatted into the node's Jinja render context as ``canon`` so the brief
    references ``{{ canon.<key> }}``. Raises :class:`CanonAnchorMissing` if any
    anchor fails (fail-loud — never a silent-empty block in the brief).
    """
    return {
        ref.key: load_skill_section(ref.skill, ref.rel_path, ref.anchor, item=ref.item)
        for ref in NODE_CANON_ANCHORS.get(node, ())
    }


def canon_fingerprint(
    node: str,
    profile_dir: Path | None = None,
    brand_dir: Path | None = None,
) -> str:
    """Stable sha256 over the verbatim blocks ``node`` pulls.

    Folded into the node's ``make_llm_key`` extras so an upstream edit to any
    section the node pulls invalidates exactly that node. Manifest order is
    deterministic, so the digest is stable across runs.

    **Back-compat:** with no dirs, the digest is byte-identical to the HOM-377
    skill-only digest — the committed fixture ``cache.db`` and the existing node
    cache keys must not drift. ``profile_dir``/``brand_dir`` (supplied by HOM-166's
    ``resolve_episode_brief`` per episode) append the profile/brand block hashes so
    a `house-style.md`/`brand.md` edit invalidates the consuming nodes too.
    """
    h = hashlib.sha256()
    for ref in NODE_CANON_ANCHORS.get(node, ()):
        block = load_skill_section(ref.skill, ref.rel_path, ref.anchor, item=ref.item)
        h.update(ref.key.encode("utf-8"))
        h.update(b"\x00")
        h.update(block.encode("utf-8"))
        h.update(b"\x00")
    if profile_dir is not None:
        for key, block in sorted(load_profile_blocks(node, profile_dir).items()):
            h.update(b"profile:")
            h.update(key.encode("utf-8"))
            h.update(b"\x00")
            h.update(block.encode("utf-8"))
            h.update(b"\x00")
    if brand_dir is not None:
        for key, block in sorted(load_brand_blocks(node, brand_dir).items()):
            h.update(b"brand:")
            h.update(key.encode("utf-8"))
            h.update(b"\x00")
            h.update(block.encode("utf-8"))
            h.update(b"\x00")
    return h.hexdigest()


# Memoize the default (full-manifest) verify per *resolved skill-root signature*
# — NOT a bare bool. A bare flag would let a build against live canon suppress a
# later verify against a test fixture root (HOMESTUDIO_CANON_ROOT_* override), or
# vice versa. Keying on the resolved roots re-verifies when the roots change.
_VERIFIED_SIGNATURES: set[tuple[tuple[str, str], ...]] = set()


def _roots_signature() -> tuple[tuple[str, str], ...]:
    return tuple(sorted((skill, str(skill_root(skill))) for skill in _DEFAULT_ROOTS))


def all_refs() -> list[CanonRef]:
    """Flatten every registered ``(node, CanonRef)`` into a de-duplicated list.

    Dedup is by the locating identity ``(skill, rel_path, anchor, item)`` so the
    shared ``_BEAT_ANCHORS`` (p4_beat + p4_redispatch_beat) and the repeated
    ``cut_craft`` / ``hard_rules`` refs are each verified once.
    """
    seen: set[tuple[str, str, str, str | None]] = set()
    out: list[CanonRef] = []
    for refs in NODE_CANON_ANCHORS.values():
        for ref in refs:
            ident = (ref.skill, ref.rel_path, ref.anchor, ref.item)
            if ident in seen:
                continue
            seen.add(ident)
            out.append(ref)
    return out


def verify_anchors(refs: list[CanonRef] | None = None, *, force: bool = False) -> None:
    """Resolve every registered canon anchor once; raise on the first failure.

    Called at graph build (``build_graph_uncompiled`` → import time) so an
    upstream rename is a startup hard-fail before any LLM dispatch (spec §9.6).
    Memoized once per process for the default (full-manifest) path so repeated
    ``build_graph`` calls in a test session don't re-read every skill file.

    Pass an explicit ``refs`` list (or ``force=True``) to bypass memoization —
    used by the fail-loud rename test against a fixture skill tree.
    """
    if refs is None:
        sig = _roots_signature()
        if not force and sig in _VERIFIED_SIGNATURES:
            return
        for ref in all_refs():
            load_skill_section(ref.skill, ref.rel_path, ref.anchor, item=ref.item)
        _VERIFIED_SIGNATURES.add(sig)
        return
    for ref in refs:
        load_skill_section(ref.skill, ref.rel_path, ref.anchor, item=ref.item)
