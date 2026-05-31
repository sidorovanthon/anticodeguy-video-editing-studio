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
