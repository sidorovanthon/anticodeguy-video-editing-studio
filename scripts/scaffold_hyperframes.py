"""Scaffold hyperframes/ project: wrap `npx hyperframes init` and patch outputs.

Per docs/superpowers/specs/2026-04-30-pipeline-enforcement-design.md §4.2.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# `data-has-audio="false"` on the muted <video> explicitly declares it carries no playable
# audio — the soundtrack is played from the sibling <audio> element (both reference the same
# muxed `src`). The attribute is documented in HF CLI docs
# (`packages/cli/src/docs/data-attributes.md`) and recognized by HF lint.
#
# On HF 0.4.x this was ALSO a required workaround for upstream #586 (the compiler defaulted
# muted same-src videos to has-audio=true → StaticGuard "invalid contract" + audio doubling
# in studio preview). #586 was bare-repro'd FIXED on 0.6.63 (HOM-379:
# docs/bare-repro-verdicts/2026-05-31-hom-379-hf-0663-revalidation.md) — bare same-src renders
# clean with audioCount:1 and no StaticGuard. The attribute is retained here as a correct,
# canon-compatible explicit declaration, no longer as a bug workaround.
VIDEO_AUDIO_PAIR_TEMPLATE = """      <video id="el-video" class="clip" data-start="0" data-track-index="0"
             src="{src}" data-has-audio="false" muted playsinline></video>
      <audio id="el-audio" class="clip" data-start="0" data-track-index="2"
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
    # 3a. Defer body palette to p4_design_system via CSS custom property.
    # `npx hyperframes init`'s template emits `background: #000;` in the inline
    # `<style>` block. Without this rewrite the literal hex survives into the
    # final index.html and `gate:design_adherence` flags it as out-of-palette
    # (HOM-191). p4_assemble_index later writes a `:root { --bg: …; }` block
    # consuming `compose.design.palette`; the fallback `transparent` keeps a
    # bare scaffold render-safe before design tokens are bound.
    html = re.sub(
        r'background:\s*#[0-9a-fA-F]{3,8}\s*;',
        'background: var(--bg, transparent);',
        html,
        count=1,
    )
    # 4. inject video+audio pair, replace example-clip comment
    pair_html = VIDEO_AUDIO_PAIR_TEMPLATE.format(src=video_src)
    html = re.sub(
        r"(\s*\n\s*\n\s*<!--\s*\n\s*Add your clips here\..*?-->\s*)",
        f"\n      {pair_html.strip()}\n    ",
        html,
        flags=re.DOTALL,
    )
    # 5. canonicalize root composition id from `npx hyperframes init`'s default
    # ("main") to "root" so it matches `p4_assemble_index`'s shim and
    # `p4_captions_layer`'s nesting (both reference `__timelines["root"]`).
    # Without this, HF lint trips `timeline_id_mismatch` because the registered
    # id ("main") and the id our injected scripts read ("root") diverge.
    # See HOM-142.
    html = re.sub(
        r'data-composition-id="main"',
        'data-composition-id="root"',
        html,
        count=1,
    )
    # Narrow to the assignment form so a future template that mentions
    # `__timelines["main"]` in a comment / instructional string isn't
    # silently rewritten — only the actual registration is renamed.
    html = re.sub(
        r'__timelines\["main"\]\s*=',
        '__timelines["root"] =',
        html,
        count=1,
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


def _is_already_scaffolded(hf: Path) -> bool:
    """Return True iff ``hf/`` is already populated enough that `npx hyperframes init` would fail.

    HOM-287: the probe must recognize BOTH shapes that block init's
    "directory already exists and is not empty" guard:

    1. The classic case — `index.html` is present (a prior scaffold run, or
       the legacy fixture shape that committed index.html). Skipping here
       avoids the cache-bump replay hazard (HOM-194).

    2. The partial-cleanup case — `hyperframes.json` AND `package.json` are
       present but `index.html` is missing. This is what HOM-283's fixture
       cleanup leaves behind: it removes the state-first text artifacts
       (index.html, compositions/*) but keeps source-asset markers
       (hyperframes.json, package.json, meta.json, transcript.json,
       hardlinked final.mp4). The directory is non-empty, so init refuses
       to run, but the markers prove an init was performed previously —
       re-running it would just re-emit identical scaffolding. Skip init
       and let the caller bootstrap a fresh `index.html` template via
       ``_bootstrap_index_html_from_tmp``.

    Why both markers, not either? `hyperframes.json` alone is suspicious
    (could be a stray write), `package.json` alone is generic JS metadata.
    Requiring both narrows the signal to "this dir was previously scaffolded".
    """
    if (hf / "index.html").exists():
        return True
    if (hf / "hyperframes.json").exists() and (hf / "package.json").exists():
        return True
    return False


def _run_init(episode_dir: Path) -> Path:
    """Run `npx hyperframes init hyperframes --yes` from inside episode_dir.

    Returns path to the created hyperframes/ subdirectory.

    Idempotent: if `<episode_dir>/hyperframes/` is already scaffolded (see
    ``_is_already_scaffolded`` for the widened HOM-287 probe), `npx hyperframes init`
    is skipped entirely — upstream HF CLI hard-aborts on non-empty target dirs
    (`Directory already exists and is not empty: hyperframes`), which would
    block any re-execution after a `_CACHE_VERSION` bump on `p4_scaffold`
    (HOM-194) or after a partial fixture cleanup (HOM-283 → HOM-287). The
    caller (`scaffold`) still re-applies `patch_index_html` on whatever
    `index.html` is present — bootstrapping a fresh template into the dir
    via ``_bootstrap_index_html_from_tmp`` when the partial-cleanup case
    left no `index.html` behind. The patches are themselves idempotent so
    the final artifact converges to the same shape regardless of starting
    state.
    """
    hf = episode_dir / "hyperframes"
    if _is_already_scaffolded(hf):
        print(
            f"[scaffold] {hf}/ already populated — skipping init, applying patches only",
            file=sys.stderr,
        )
        hf.mkdir(parents=True, exist_ok=True)
        return hf
    cmd = ["npx", "hyperframes", "init", "hyperframes", "--yes"]
    result = subprocess.run(
        cmd,
        cwd=episode_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=(sys.platform == "win32"),  # npx on Windows resolves via cmd.exe
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"npx hyperframes init failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    hf = episode_dir / "hyperframes"
    if not hf.is_dir():
        raise RuntimeError(f"npx hyperframes init reported success but {hf} does not exist")
    return hf


def _bootstrap_index_html_from_tmp(hf: Path) -> None:
    """Run `npx hyperframes init` in a scratch tmp dir to extract a fresh `index.html` template.

    HOM-287: when ``_is_already_scaffolded`` skipped init because the
    partial-cleanup shape was detected (hyperframes.json + package.json
    present, index.html absent), the rest of ``scaffold()`` still needs a
    canonical `index.html` template to patch. We get one by running init
    in a brand-new tmp dir (where the "non-empty dir" guard cannot trip),
    copying just the `index.html` file into ``hf``, and discarding the
    rest. The orchestrator-house patches in ``patch_index_html`` then
    overlay on top.

    No-op if ``hf/index.html`` already exists (post-HOM-194 skip path).
    """
    if (hf / "index.html").exists():
        return
    import tempfile

    with tempfile.TemporaryDirectory(prefix="hf-init-bootstrap-") as tmp:
        tmp_path = Path(tmp)
        cmd = ["npx", "hyperframes", "init", "hyperframes", "--yes"]
        result = subprocess.run(
            cmd,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            shell=(sys.platform == "win32"),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"npx hyperframes init (tmp bootstrap) failed (exit {result.returncode}):\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        src = tmp_path / "hyperframes" / "index.html"
        if not src.exists():
            raise RuntimeError(
                f"npx hyperframes init (tmp bootstrap) reported success but {src} is missing"
            )
        shutil.copyfile(src, hf / "index.html")


def _ffprobe_dimensions_and_duration(video: Path) -> tuple[int, int, float]:
    """Read width, height, duration from a video via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration",
        "-of", "json",
        str(video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    data = json.loads(result.stdout)
    width = int(data["streams"][0]["width"])
    height = int(data["streams"][0]["height"])
    duration = float(data["format"]["duration"])
    return width, height, duration


def _hardlink_final_mp4(episode_dir: Path) -> None:
    """Place a hardlink to edit/final.mp4 alongside hyperframes/index.html.

    Without this, <video src="../edit/final.mp4"> trips HF lint/validate's
    parent-directory path check. Hardlink is zero additional disk; both
    Windows and Unix are supported.

    Idempotent: returns silently if hyperframes/final.mp4 already exists.
    """
    src = episode_dir / "edit" / "final.mp4"
    dst = episode_dir / "hyperframes" / "final.mp4"
    if dst.exists():
        return
    if not src.exists():
        raise FileNotFoundError(f"cannot hardlink {dst}: {src} does not exist")
    if sys.platform == "win32":
        # Windows: mklink /H requires cmd.exe
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/H", str(dst), str(src)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"mklink /H failed (exit {result.returncode}): {result.stderr or result.stdout}"
            )
    else:
        os.link(src, dst)


def scaffold(
    *,
    episode_dir: Path,
    slug: str,
    width: int | None = None,
    height: int | None = None,
    duration: float | None = None,
    hyperframes_version: str = "^0.4.39",
) -> Path:
    """End-to-end scaffold per design spec §4.2.

    Steps 1-6 in order. If width/height/duration are not provided, ffprobe the
    final.mp4 to get them. Returns the hyperframes/ directory path.

    Idempotent under re-runs (HOM-194): if `<episode_dir>/hyperframes/index.html`
    already exists from a prior run (or from a tracked fixture artifact),
    `_run_init` is skipped and `patch_index_html` is re-applied to the existing
    file. Patches are themselves idempotent — re-applying on already-patched
    output is a no-op — so a `_CACHE_VERSION` bump on `p4_scaffold` (e.g.
    HOM-191's body-bg → CSS variable rewrite) re-executes safely on top of the
    prior on-disk artifact instead of aborting on HF CLI's "Directory already
    exists and is not empty" guard.
    """
    final_mp4 = episode_dir / "edit" / "final.mp4"
    final_json = episode_dir / "edit" / "transcripts" / "final.json"

    if width is None or height is None or duration is None:
        if not final_mp4.exists() or final_mp4.stat().st_size == 0:
            raise FileNotFoundError(
                f"need final.mp4 to ffprobe for dimensions, but {final_mp4} is missing or empty. "
                f"Pass width/height/duration explicitly to bypass."
            )
        width, height, duration = _ffprobe_dimensions_and_duration(final_mp4)

    hf = _run_init(episode_dir)

    # HOM-287: if init was skipped because of the widened partial-cleanup
    # probe (hyperframes.json + package.json present but no index.html),
    # bootstrap a fresh template from a scratch tmp dir so the patch step
    # below has something to overlay onto. No-op when index.html already
    # exists (the classic HOM-194 skip path).
    _bootstrap_index_html_from_tmp(hf)

    # Patch index.html
    index_path = hf / "index.html"
    html = index_path.read_text(encoding="utf-8")
    html = patch_index_html(
        html, width=width, height=height, duration=duration,
        video_src="final.mp4",
    )
    if '<video id="el-video"' not in html:
        raise RuntimeError(
            "patch_index_html: video/audio injection failed — the upstream "
            "`npx hyperframes init` template likely changed shape. Inspect "
            f"{index_path} and update the example-clip regex in patch_index_html."
        )
    index_path.write_text(html, encoding="utf-8")

    # Hardlink final.mp4 next to index.html (canon path resolution)
    _hardlink_final_mp4(episode_dir)

    # Patch meta.json
    meta_path = hf / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta = patch_meta_json(meta, slug=slug)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Add package.json
    pkg = build_package_json(slug=slug, hyperframes_version=hyperframes_version)
    (hf / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")

    # Copy transcript: final.json is an envelope ({edl_hash, words}); HF consumes a
    # word-level array of {text, start, end} entries (per `references/transcript-guide.md`
    # — the canonical caption transcript shape, sometimes called "Normalized word array").
    if final_json.exists():
        envelope = json.loads(final_json.read_text(encoding="utf-8"))
        words = envelope["words"] if isinstance(envelope, dict) else envelope
        (hf / "transcript.json").write_text(
            json.dumps(words, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return hf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold hyperframes/ project for an episode.")
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument("--slug", type=str, required=True)
    parser.add_argument("--hyperframes-version", type=str, default="^0.4.39")
    args = parser.parse_args(argv)
    hf = scaffold(
        episode_dir=args.episode_dir,
        slug=args.slug,
        hyperframes_version=args.hyperframes_version,
    )
    print(json.dumps({"hyperframes_dir": str(hf)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
