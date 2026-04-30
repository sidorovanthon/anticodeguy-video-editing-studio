"""Scaffold hyperframes/ project: wrap `npx hyperframes init` and patch outputs.

Per docs/superpowers/specs/2026-04-30-pipeline-enforcement-design.md §4.2.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_AUDIO_PAIR_TEMPLATE = """      <video id="el-video" data-start="0" data-track-index="0"
             src="{src}" muted playsinline></video>
      <audio id="el-audio" data-start="0" data-track-index="1"
             src="{src}" data-volume="1"></audio>"""


def patch_index_html(html: str, *, width: int, height: int, duration: float, video_src: str) -> str:
    """Apply the four known-wrong-location patches to init's index.html."""
    # 1. <meta name="viewport">
    html = re.sub(
        r'<meta name="viewport" content="width=\d+, height=\d+"\s*/>',
        f'<meta name="viewport" content="width={width}, height={height}" />',
        html,
    )
    # 2. body width/height in inline <style>
    html = re.sub(r"width:\s*\d+px;", f"width: {width}px;", html, count=1)
    html = re.sub(r"height:\s*\d+px;", f"height: {height}px;", html, count=1)
    # 3. root div data-* attrs
    html = re.sub(r'data-width="\d+"', f'data-width="{width}"', html)
    html = re.sub(r'data-height="\d+"', f'data-height="{height}"', html)
    html = re.sub(r'data-duration="[\d.]+"', f'data-duration="{duration}"', html)
    # 4. inject video+audio pair, replace example-clip comment
    pair_html = VIDEO_AUDIO_PAIR_TEMPLATE.format(src=video_src)
    html = re.sub(
        r"(\s*\n\s*\n\s*<!--\s*\n\s*Add your clips here\..*?-->\s*)",
        f"\n      {pair_html.strip()}\n    ",
        html,
        flags=re.DOTALL,
    )
    return html


def patch_meta_json(meta: dict, *, slug: str) -> dict:
    """Overwrite id and name with episode slug; preserve other fields."""
    out = dict(meta)
    out["id"] = slug
    out["name"] = slug
    return out


def build_package_json(*, slug: str, hyperframes_version: str) -> dict:
    """Construct a minimal package.json that pins hyperframes as devDep."""
    return {
        "name": slug,
        "version": "0.1.0",
        "private": True,
        "devDependencies": {"hyperframes": hyperframes_version},
    }
