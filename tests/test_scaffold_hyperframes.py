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
    out = patch_index_html(DEFAULT_INDEX_HTML, width=1080, height=1920, duration=58.8, video_src="final.mp4")
    # canonical pattern: video muted playsinline + separate audio, both class="clip"
    assert '<video id="el-video" class="clip"' in out
    assert 'muted' in out
    assert 'playsinline' in out
    assert '<audio id="el-audio" class="clip"' in out
    assert out.count('src="final.mp4"') == 2  # both elements, sibling-relative path
    # canonical track-indices per HF SKILL.md line 175/184
    assert 'data-track-index="0"' in out  # video on track 0
    assert 'data-track-index="2"' in out  # audio on track 2 (per canon example)
    # example-clip comment removed
    assert "Add your clips here" not in out


def test_patch_index_html_video_has_explicit_data_has_audio_false():
    """Canonical two-element pair would trigger StaticGuard 'invalid contract' on muxed source.

    HF compiler unconditionally injects data-has-audio="true" on every <video> without
    an explicit attribute (timingCompiler.ts:104-106). Combined with `muted`, this trips
    the StaticGuard rule (media.ts:274). Setting data-has-audio="false" blocks the
    auto-injection (compiler condition is `!hasAttr(...)`) and audioMixer's strict
    equality on "true" excludes this <video> from the mix — audio routes only through
    the <audio> element.

    Documented in HF CLI docs (packages/cli/src/docs/data-attributes.md) but not in
    agent-facing SKILL.md canon. Upstream tracking: heygen-com/hyperframes#586.
    """
    out = patch_index_html(DEFAULT_INDEX_HTML, width=1080, height=1920, duration=58.8, video_src="../edit/final.mp4")
    # Explicit on the <video> element, blocking compiler auto-inject:
    assert 'data-has-audio="false"' in out
    # And NOT on the <audio> element (auto-inject only targets <video>, attribute would be meaningless):
    audio_block = out[out.index("<audio"):out.index("</audio>") + len("</audio>") if "</audio>" in out else len(out)]
    assert "data-has-audio" not in audio_block


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


import shutil


def _have_npx() -> bool:
    return shutil.which("npx") is not None


@pytest.mark.skipif(not _have_npx(), reason="npx not on PATH")
def test_scaffold_end_to_end(tmp_path: Path):
    """Calls real `npx hyperframes init`, applies patches, verifies all artifacts."""
    from scripts.scaffold_hyperframes import scaffold

    episode_dir = tmp_path / "ep"
    episode_dir.mkdir()
    # Place a tiny stand-in for final.mp4. ffprobe needs a real file but we'll
    # bypass ffprobe by passing dimensions explicitly.
    (episode_dir / "edit").mkdir()
    (episode_dir / "edit" / "final.mp4").write_bytes(b"")
    # Place a fake remapped transcript.
    (episode_dir / "edit" / "transcripts").mkdir()
    (episode_dir / "edit" / "transcripts" / "final.json").write_text(
        '[{"text":"hi","start":0,"end":0.2}]', encoding="utf-8"
    )

    scaffold(
        episode_dir=episode_dir,
        slug="2026-04-30-test-episode",
        width=1080,
        height=1920,
        duration=10.0,
        hyperframes_version="^0.4.39",
    )

    hf = episode_dir / "hyperframes"
    assert hf.is_dir()
    # init produces these
    assert (hf / "index.html").exists()
    assert (hf / "meta.json").exists()
    assert (hf / "hyperframes.json").exists()
    # we add these
    assert (hf / "package.json").exists()
    assert (hf / "transcript.json").exists()

    # final.mp4 hardlinked from edit/ next to index.html
    assert (hf / "final.mp4").exists()

    # patches applied
    html = (hf / "index.html").read_text(encoding="utf-8")
    assert 'data-width="1080"' in html
    assert 'data-height="1920"' in html
    assert "<video" in html and "<audio" in html
    assert 'src="final.mp4"' in html
    # parent-dir path no longer used — sibling hardlink replaces it
    assert 'src="../edit/final.mp4"' not in html
    assert 'data-has-audio="false"' in html

    meta = json.loads((hf / "meta.json").read_text(encoding="utf-8"))
    assert meta["id"] == "2026-04-30-test-episode"
    assert meta["name"] == "2026-04-30-test-episode"

    pkg = json.loads((hf / "package.json").read_text(encoding="utf-8"))
    assert pkg["devDependencies"]["hyperframes"] == "^0.4.39"

    transcript = json.loads((hf / "transcript.json").read_text(encoding="utf-8"))
    assert transcript == [{"text": "hi", "start": 0, "end": 0.2}]


import os


def test_hardlink_final_mp4_creates_link(tmp_path: Path):
    """`_hardlink_final_mp4` places final.mp4 next to index.html via hardlink (not copy)."""
    from scripts.scaffold_hyperframes import _hardlink_final_mp4

    episode_dir = tmp_path / "ep"
    (episode_dir / "edit").mkdir(parents=True)
    src = episode_dir / "edit" / "final.mp4"
    src.write_bytes(b"hello")
    (episode_dir / "hyperframes").mkdir()

    _hardlink_final_mp4(episode_dir)

    dst = episode_dir / "hyperframes" / "final.mp4"
    assert dst.exists()
    # hardlink semantics: same inode = same content + same st_nlink>=2
    src_stat = src.stat()
    dst_stat = dst.stat()
    if os.name != "nt":
        # st_ino comparison is reliable on POSIX
        assert src_stat.st_ino == dst_stat.st_ino
    # both Windows and Unix: link count >= 2 after hardlink
    assert src_stat.st_nlink >= 2
    # content matches
    assert dst.read_bytes() == b"hello"


def test_hardlink_final_mp4_is_idempotent(tmp_path: Path):
    """Running twice does not raise — second call is a no-op."""
    from scripts.scaffold_hyperframes import _hardlink_final_mp4

    episode_dir = tmp_path / "ep"
    (episode_dir / "edit").mkdir(parents=True)
    (episode_dir / "edit" / "final.mp4").write_bytes(b"hello")
    (episode_dir / "hyperframes").mkdir()

    _hardlink_final_mp4(episode_dir)
    _hardlink_final_mp4(episode_dir)  # must not raise

    assert (episode_dir / "hyperframes" / "final.mp4").exists()
