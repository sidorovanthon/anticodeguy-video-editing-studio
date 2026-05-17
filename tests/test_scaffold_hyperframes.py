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


def test_patch_index_html_canonicalizes_root_composition_id_to_root():
    """HOM-142: scaffold's default `data-composition-id="main"` and
    `__timelines["main"]` are renamed to "root" so the assembled
    `index.html`'s shim/captions references resolve and HF lint's
    `timeline_id_mismatch` rule stays green."""
    out = patch_index_html(
        DEFAULT_INDEX_HTML, width=1080, height=1920, duration=58.8, video_src="final.mp4"
    )
    assert 'data-composition-id="main"' not in out
    assert 'data-composition-id="root"' in out
    assert '__timelines["main"]' not in out
    assert '__timelines["root"]' in out


def test_patch_index_html_defers_body_background_to_css_variable():
    """HOM-191: body background must be a `var(--bg, …)` placeholder so
    `p4_design_system` palette tokens land via `p4_assemble_index`'s
    `:root { … }` block rather than a literal hex that
    `gate:design_adherence` flags as out-of-palette.
    """
    out = patch_index_html(
        DEFAULT_INDEX_HTML, width=1080, height=1920, duration=58.8, video_src="final.mp4"
    )
    # Literal `#000` (or any short/long hex) is gone from the body block.
    # Sliced to the inline <style> block so we don't false-match elsewhere.
    style_open = out.index("<style>")
    style_close = out.index("</style>", style_open)
    style_block = out[style_open:style_close]
    assert "background: #000" not in style_block
    # Custom property placeholder with a generic CSS fallback is in place.
    assert "background: var(--bg, transparent);" in style_block
    # Sanity: no literal hex survived in the scaffold's body declarations.
    import re as _re

    assert not _re.search(
        r"background\s*:\s*#[0-9a-fA-F]{3,8}", style_block
    ), f"literal hex background survived: {style_block!r}"


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
@pytest.mark.parametrize(
    "final_json_content,case_id",
    [
        # Legacy bare-array shape (pre-PR #12). Exercises the
        # `isinstance(envelope, dict)` backward-compat fallback at
        # scripts/scaffold_hyperframes.py:211.
        ('[{"text":"hi","start":0,"end":0.2}]', "legacy_bare_array"),
        # Envelope shape (post-PR #12). Exercises the canonical
        # `envelope["words"]` unwrap path. Without this case, the dict branch
        # has no test coverage and could be silently broken by a future
        # refactor that removes the `isinstance` guard as "dead code".
        (
            '{"edl_hash":"abc123def456","words":[{"text":"hi","start":0,"end":0.2}]}',
            "envelope",
        ),
    ],
    ids=lambda v: v if isinstance(v, str) and len(v) < 30 else None,
)
def test_scaffold_end_to_end(tmp_path: Path, final_json_content: str, case_id: str):
    """Calls real `npx hyperframes init`, applies patches, verifies all artifacts.

    Parametrized over both transcript shapes: legacy bare-array (back-compat
    fallback) and envelope (canonical post-PR #12 shape). Both must unwrap to
    the same bare-array `transcript.json` for the HF caption pipeline.
    """
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
        final_json_content, encoding="utf-8"
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


def test_run_init_skips_when_index_html_exists(tmp_path: Path):
    """HOM-194: `_run_init` must skip `npx hyperframes init` if hyperframes/index.html
    already exists, so a `_CACHE_VERSION` bump on `p4_scaffold` can re-execute on top
    of the prior on-disk artifact (e.g. canonical fixture tree) without tripping HF
    CLI's "Directory already exists and is not empty" guard.

    Asserts via sentinel content survival: if init had run, it would have wiped/refused
    the existing file; the sentinel proves the existing file was preserved.
    """
    from scripts.scaffold_hyperframes import _run_init

    episode_dir = tmp_path / "ep"
    hf = episode_dir / "hyperframes"
    hf.mkdir(parents=True)
    sentinel = "<!-- HOM-194-SENTINEL: this file existed before _run_init -->"
    (hf / "index.html").write_text(
        f"<!doctype html><html><body>{sentinel}</body></html>",
        encoding="utf-8",
    )

    out = _run_init(episode_dir)
    assert out == hf
    # File untouched — npx was NOT invoked.
    assert sentinel in (hf / "index.html").read_text(encoding="utf-8")


def test_scaffold_repatches_existing_hyperframes_dir(tmp_path: Path):
    """HOM-194: `scaffold` on a populated hyperframes/ skips init but still applies
    patches. Simulates the HOM-191 re-record scenario: an unpatched `index.html`
    (literal `background: #000;`) sits in the fixture; re-running scaffold must
    rewrite it to `var(--bg, transparent)` without re-invoking init.
    """
    from scripts.scaffold_hyperframes import scaffold

    episode_dir = tmp_path / "ep"
    (episode_dir / "edit").mkdir(parents=True)
    (episode_dir / "edit" / "final.mp4").write_bytes(b"placeholder")

    hf = episode_dir / "hyperframes"
    hf.mkdir()
    sentinel = "HOM-194-PRE-EXISTING-SENTINEL"
    # Stub an unpatched index.html (literal #000 + sentinel comment).
    (hf / "index.html").write_text(
        DEFAULT_INDEX_HTML.replace(
            "<!doctype html>",
            f"<!doctype html>\n<!-- {sentinel} -->",
        ),
        encoding="utf-8",
    )
    # Stub the sibling artifacts that scaffold reads/writes after init.
    (hf / "meta.json").write_text(
        json.dumps({"id": "old", "name": "old", "createdAt": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    (hf / "hyperframes.json").write_text("{}", encoding="utf-8")

    scaffold(
        episode_dir=episode_dir,
        slug="2026-05-09-test-episode",
        width=1080,
        height=1920,
        duration=10.0,
        hyperframes_version="^0.4.39",
    )

    html = (hf / "index.html").read_text(encoding="utf-8")
    # Sentinel survived: existing file was patched in-place, not regenerated.
    assert sentinel in html
    # HOM-191 patch applied on re-run.
    assert "background: var(--bg, transparent);" in html
    assert "background: #000" not in html
    # Other patches applied as well.
    assert 'data-width="1080"' in html
    assert 'data-composition-id="root"' in html
    # Sibling artifacts overwritten with new slug.
    meta = json.loads((hf / "meta.json").read_text(encoding="utf-8"))
    assert meta["id"] == "2026-05-09-test-episode"
    assert meta["createdAt"] == "2026-01-01T00:00:00Z"  # preserved
    pkg = json.loads((hf / "package.json").read_text(encoding="utf-8"))
    assert pkg["devDependencies"]["hyperframes"] == "^0.4.39"


def test_scaffold_second_call_is_no_op_on_index_html(tmp_path: Path):
    """HOM-194: a second `scaffold` invocation on an already-scaffolded dir must
    converge — the resulting `index.html` is byte-identical to the first run's
    output, proving `patch_index_html` is idempotent on re-application.

    Simulates the cache-bump replay path without invoking npx by pre-staging a
    fully-patched `index.html` from `patch_index_html` itself.
    """
    from scripts.scaffold_hyperframes import scaffold, patch_index_html

    episode_dir = tmp_path / "ep"
    (episode_dir / "edit").mkdir(parents=True)
    (episode_dir / "edit" / "final.mp4").write_bytes(b"placeholder")

    hf = episode_dir / "hyperframes"
    hf.mkdir()

    # First "run" output — produced by patch_index_html on the canonical template.
    first_html = patch_index_html(
        DEFAULT_INDEX_HTML, width=1080, height=1920, duration=10.0,
        video_src="final.mp4",
    )
    (hf / "index.html").write_text(first_html, encoding="utf-8")
    (hf / "meta.json").write_text(
        json.dumps({"id": "x", "name": "x", "createdAt": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    (hf / "hyperframes.json").write_text("{}", encoding="utf-8")

    scaffold(
        episode_dir=episode_dir,
        slug="2026-05-09-test-episode",
        width=1080,
        height=1920,
        duration=10.0,
        hyperframes_version="^0.4.39",
    )

    second_html = (hf / "index.html").read_text(encoding="utf-8")
    assert second_html == first_html, (
        "patch_index_html is not idempotent — re-running scaffold mutated index.html"
    )


def test_is_already_scaffolded_index_html_only(tmp_path: Path):
    """HOM-287 regression guard: index.html-only dir is recognized as scaffolded.

    The classic HOM-194 path — fixture or prior-run dir with index.html
    present — must still short-circuit init regardless of whether
    `hyperframes.json` / `package.json` exist.
    """
    from scripts.scaffold_hyperframes import _is_already_scaffolded

    hf = tmp_path / "hyperframes"
    hf.mkdir()
    (hf / "index.html").write_text("<html></html>", encoding="utf-8")
    assert _is_already_scaffolded(hf) is True


def test_is_already_scaffolded_partial_cleanup_state(tmp_path: Path):
    """HOM-287: hyperframes.json + package.json without index.html → scaffolded.

    This is the post-HOM-283 fixture-cleanup shape. Without recognizing
    it, `npx hyperframes init` halts on "Directory already exists and is
    not empty" and a fresh-tier prewarm cannot make forward progress.
    """
    from scripts.scaffold_hyperframes import _is_already_scaffolded

    hf = tmp_path / "hyperframes"
    hf.mkdir()
    (hf / "hyperframes.json").write_text("{}", encoding="utf-8")
    (hf / "package.json").write_text("{}", encoding="utf-8")
    assert _is_already_scaffolded(hf) is True


def test_is_already_scaffolded_empty_dir(tmp_path: Path):
    """HOM-287 regression guard: empty dir is NOT scaffolded, init must run."""
    from scripts.scaffold_hyperframes import _is_already_scaffolded

    hf = tmp_path / "hyperframes"
    hf.mkdir()
    assert _is_already_scaffolded(hf) is False


def test_is_already_scaffolded_partial_single_marker(tmp_path: Path):
    """HOM-287: a single marker alone is insufficient — both required.

    `hyperframes.json` alone could be a stray write; `package.json` alone
    is generic JS metadata. Requires both to narrow the signal to
    "previously scaffolded".
    """
    from scripts.scaffold_hyperframes import _is_already_scaffolded

    hf = tmp_path / "hyperframes"
    hf.mkdir()
    (hf / "hyperframes.json").write_text("{}", encoding="utf-8")
    assert _is_already_scaffolded(hf) is False

    (hf / "hyperframes.json").unlink()
    (hf / "package.json").write_text("{}", encoding="utf-8")
    assert _is_already_scaffolded(hf) is False


def test_run_init_skips_when_partial_cleanup_markers_present(tmp_path: Path, monkeypatch):
    """HOM-287: `_run_init` must skip the subprocess when the widened
    probe matches the partial-cleanup shape, even without `index.html`.

    Verified by monkey-patching ``subprocess.run`` so any invocation
    raises — if init were called, the test would fail.
    """
    from scripts import scaffold_hyperframes as sh

    episode_dir = tmp_path / "ep"
    hf = episode_dir / "hyperframes"
    hf.mkdir(parents=True)
    (hf / "hyperframes.json").write_text("{}", encoding="utf-8")
    (hf / "package.json").write_text("{}", encoding="utf-8")

    def fail_run(*args, **kwargs):
        raise AssertionError(
            "subprocess.run must not be invoked when partial-cleanup markers exist"
        )

    monkeypatch.setattr(sh.subprocess, "run", fail_run)

    out = sh._run_init(episode_dir)
    assert out == hf
    # Files preserved — probe is read-only.
    assert (hf / "hyperframes.json").exists()
    assert (hf / "package.json").exists()


def test_run_init_invokes_subprocess_on_empty_dir(tmp_path: Path, monkeypatch):
    """HOM-287 regression guard: empty `hyperframes/` (or missing entirely) → init runs."""
    from scripts import scaffold_hyperframes as sh

    episode_dir = tmp_path / "ep"
    episode_dir.mkdir()

    calls: list[tuple] = []

    class FakeResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append((tuple(cmd), kwargs.get("cwd")))
        # Simulate init creating the hyperframes/ dir
        (episode_dir / "hyperframes").mkdir(exist_ok=True)
        return FakeResult()

    monkeypatch.setattr(sh.subprocess, "run", fake_run)

    out = sh._run_init(episode_dir)
    assert out == episode_dir / "hyperframes"
    assert len(calls) == 1, f"expected exactly one subprocess.run call, got {len(calls)}"
    cmd, cwd = calls[0]
    assert cmd[0] == "npx" and "init" in cmd
    assert cwd == episode_dir


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
