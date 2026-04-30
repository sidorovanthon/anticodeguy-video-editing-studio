"""Unit tests for scaffold_hyperframes pure-functional helpers."""
import json
from pathlib import Path

import pytest

from scripts.scaffold_hyperframes import (
    patch_index_html,
    patch_meta_json,
    build_package_json,
)

DEFAULT_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }
      html,
      body {
        margin: 0;
        width: 1920px;
        height: 1080px;
        overflow: hidden;
        background: #000;
      }
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="10"
      data-width="1920"
      data-height="1080"
    >



      <!--
        Add your clips here. Example:
        <div id="title" class="clip" data-start="0" data-duration="5" data-track-index="1"
             style="font-size: 64px; color: #fff; padding: 40px">
          Hello World
        </div>
      -->
    </div>

    <script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      // Example: tl.from("#title", { opacity: 0, y: -50, duration: 1 }, 0);
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


def test_patch_index_html_replaces_dimensions_and_duration():
    out = patch_index_html(DEFAULT_INDEX_HTML, width=1080, height=1920, duration=58.8, video_src="../edit/final.mp4")
    assert 'content="width=1080, height=1920"' in out
    assert "width: 1080px" in out
    assert "height: 1920px" in out
    assert 'data-width="1080"' in out
    assert 'data-height="1920"' in out
    assert 'data-duration="58.8"' in out
    # 1920×1080 defaults are gone
    assert "1920, height=1080" not in out
    assert "data-width=\"1920\"" not in out


def test_patch_index_html_injects_video_audio_pair():
    out = patch_index_html(DEFAULT_INDEX_HTML, width=1080, height=1920, duration=58.8, video_src="../edit/final.mp4")
    # canonical pattern: video muted playsinline + separate audio
    assert '<video id="el-video"' in out
    assert 'muted' in out
    assert 'playsinline' in out
    assert '<audio id="el-audio"' in out
    assert out.count('src="../edit/final.mp4"') == 2  # both elements
    # example-clip comment removed
    assert "Add your clips here" not in out


def test_patch_index_html_no_data_has_audio():
    """Canonical pattern uses two-element pair, NOT data-has-audio."""
    out = patch_index_html(DEFAULT_INDEX_HTML, width=1080, height=1920, duration=58.8, video_src="../edit/final.mp4")
    assert "data-has-audio" not in out


def test_patch_meta_json_overwrites_id_and_name():
    src = {"id": "hyperframes", "name": "hyperframes", "createdAt": "2026-04-30T07:58:27.115Z"}
    out = patch_meta_json(src, slug="2026-04-30-hello-world")
    assert out["id"] == "2026-04-30-hello-world"
    assert out["name"] == "2026-04-30-hello-world"
    assert out["createdAt"] == "2026-04-30T07:58:27.115Z"  # preserved


def test_build_package_json_declares_hyperframes_devdep():
    pkg = build_package_json(slug="2026-04-30-hello-world", hyperframes_version="^0.4.39")
    assert pkg["name"] == "2026-04-30-hello-world"
    assert "hyperframes" in pkg["devDependencies"]
    assert pkg["devDependencies"]["hyperframes"] == "^0.4.39"
    assert "private" in pkg and pkg["private"] is True
