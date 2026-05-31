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
