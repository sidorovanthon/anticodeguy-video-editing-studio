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
