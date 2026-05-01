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

# `data-has-audio="false"` is required on the <video> element when both <video> and <audio>
# share the same muxed `src`. Without it, HF's timingCompiler.ts:104-106 unconditionally
# injects `data-has-audio="true"`, which combined with `muted` trips StaticGuard's
# `invalid contract` rule (media.ts:274) and audioMixer.ts:55-56 picks the <video> up
# as a second audio source, producing audible doubling/distortion in studio preview.
#
# The attribute is documented in HF CLI docs (`packages/cli/src/docs/data-attributes.md`)
# and recognized by HF lint, but is NOT in agent-facing SKILL.md canon — this is an
# orchestrator extension filling a documented HF lint contract gap.
#
# Upstream tracking: https://github.com/heygen-com/hyperframes/issues/586
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


def _run_init(episode_dir: Path) -> Path:
    """Run `npx hyperframes init hyperframes --yes` from inside episode_dir.

    Returns path to the created hyperframes/ subdirectory.
    """
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

    # Copy transcript
    if final_json.exists():
        shutil.copyfile(final_json, hf / "transcript.json")

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
