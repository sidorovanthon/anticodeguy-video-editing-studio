# `/edit-episode` Second-Retro Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land all 14 findings from `retro-2026-04-30-desktop-software-licensing-it-turns-out-is.md` into `.claude/commands/edit-episode.md`, `scripts/scaffold_hyperframes.py`, and `docs/cheatsheets/hyperframes.md` — closing the meta-issue that the first retro's pacing-policy never reached the brief.

**Architecture:** Three artifacts get mechanical edits, all canon-verified against `~/.claude/skills/video-use/SKILL.md` and `~/.agents/skills/hyperframes/SKILL.md`:

1. **`.claude/commands/edit-episode.md`** — Phase 3 brief gains pacing+retake+no-subtitles policy; Phase 4 brief becomes multi-scene-mandatory with substantive DESIGN.md gate; new Visual Verification step uses canonical `npx hyperframes inspect --at` and `snapshot --at`.
2. **`scripts/scaffold_hyperframes.py`** — `VIDEO_AUDIO_PAIR_TEMPLATE` gains `class="clip"` and canonical `data-track-index="2"` for audio; new hardlink helper places `final.mp4` alongside `index.html` so `lint`/`validate` resolve paths; studio launch redirects logs to `.hyperframes/preview.log`.
3. **`docs/cheatsheets/hyperframes.md`** — gotcha block warning future scaffold authors to follow the cheatsheet's `<video>`/`<audio>` example, not `SKILL.md`'s incomplete one.

**Tech Stack:** Python 3.13 + `subprocess` + `os.link`/`mklink /H` (cross-platform hardlink). Pytest. Markdown for command/brief/cheatsheet edits. No new dependencies.

**Source spec:** `docs/superpowers/specs/2026-04-30-edit-episode-second-retro-fixes-design.md`.

**Branch workflow (CLAUDE.md mandate):** Work in a worktree. Suggested branch name: `retro-fixes-2026-04-30`. Open PR `--base main` once all tasks pass; merge with `gh pr merge --squash --delete-branch`.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `scripts/scaffold_hyperframes.py` | Modify | Template + hardlink + video_src change |
| `tests/test_scaffold_hyperframes.py` | Modify | Update existing assertions + new hardlink test |
| `.claude/commands/edit-episode.md` | Modify | Phase 3 brief, Phase 4 brief, Visual Verification gate, studio-launch log redirect |
| `docs/cheatsheets/hyperframes.md` | Modify | Append gotcha block |
| `docs/superpowers/specs/2026-04-30-edit-episode-second-retro-fixes-design.md` | (read-only) | Source of truth for every change below |

No new files are created.

---

## Pre-flight

- [ ] **P1: Create worktree per CLAUDE.md branch+PR workflow**

```bash
git worktree add .worktrees/retro-fixes-2026-04-30 -b retro-fixes-2026-04-30
cd .worktrees/retro-fixes-2026-04-30
```

Expected: new branch `retro-fixes-2026-04-30` checked out in `.worktrees/retro-fixes-2026-04-30/`. All subsequent paths in this plan are relative to that worktree root.

- [ ] **P2: Verify baseline tests pass before any change**

```bash
pytest tests/test_scaffold_hyperframes.py -v
```

Expected: all tests pass (some may be skipped if `npx` is missing — that's OK).

---

## Task 1: Add `class="clip"` and canonical `data-track-index` to scaffold template

**Why:** Per per-project HF `CLAUDE.md` Key Rule 2, every timed element needs `class="clip"` for the framework to register it as a managed clip. Without it, `muted` is a passive HTML attribute the studio media controller may ignore → phantom audio doubling. Canon `SKILL.md` line 184 places audio at `data-track-index="2"`; we currently use `1`. Same-track clips cannot overlap (canon line 122) — track 2 is convention to leave room for overlays on track 1.

**Files:**
- Modify: `scripts/scaffold_hyperframes.py:15-18` (template constant)
- Modify: `tests/test_scaffold_hyperframes.py:80-95` (update assertions in `test_patch_index_html_injects_video_audio_pair`)

- [ ] **Step 1: Update tests first — make existing test assert canonical attributes**

Replace the body of `test_patch_index_html_injects_video_audio_pair` in `tests/test_scaffold_hyperframes.py` (lines 80-89) with:

```python
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
```

Note: also changes `video_src` from `../edit/final.mp4` to `final.mp4` (Task 3 will add the hardlink that makes this resolvable). Sequential tests will fail on this until Task 3 lands — that's expected.

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_scaffold_hyperframes.py::test_patch_index_html_injects_video_audio_pair -v
```

Expected: FAIL with assertion errors on `class="clip"` and `data-track-index="2"`.

- [ ] **Step 3: Update `VIDEO_AUDIO_PAIR_TEMPLATE` to add `class="clip"` and canon track-indices**

In `scripts/scaffold_hyperframes.py`, replace lines 15-18:

```python
VIDEO_AUDIO_PAIR_TEMPLATE = """      <video id="el-video" class="clip" data-start="0" data-track-index="0"
             src="{src}" muted playsinline></video>
      <audio id="el-audio" class="clip" data-start="0" data-track-index="2"
             src="{src}" data-volume="1"></audio>"""
```

- [ ] **Step 4: Run the test again**

```bash
pytest tests/test_scaffold_hyperframes.py::test_patch_index_html_injects_video_audio_pair -v
```

Expected: PASS.

- [ ] **Step 5: Run the full scaffold test file — no other regressions**

```bash
pytest tests/test_scaffold_hyperframes.py -v
```

Expected: previously passing tests still pass; `test_scaffold_end_to_end` (npx-dependent) may now fail because we still pass `video_src="../edit/final.mp4"` from `scaffold()` itself — that's expected and Task 3 fixes it.

- [ ] **Step 6: Commit**

```bash
git add scripts/scaffold_hyperframes.py tests/test_scaffold_hyperframes.py
git commit -m "fix(scaffold): add class=\"clip\" and canon track-index to media pair

Per per-project HF CLAUDE.md Key Rule 2, timed elements MUST have
class=\"clip\" for framework clip registration. Without it, the studio
media controller may ignore <video muted> and play both tracks. Canon
SKILL.md line 184 places audio at data-track-index=2; we previously used
1. Closes retro 1.4 root cause (no workaround needed)."
```

---

## Task 2: Hardlink `final.mp4` into `hyperframes/` and update `video_src` to sibling path

**Why:** `<video src="../edit/final.mp4">` resolves at runtime but trips HF `lint`/`validate`'s path checker (parent-directory traversal). User's manual workaround last episode was `mklink /H hyperframes/final.mp4 ../edit/final.mp4`. Hardlink costs zero extra disk vs. copy (~30-100 MB saved per episode). Cross-platform: Windows `mklink /H` via `cmd`, Unix `os.link`.

**Files:**
- Modify: `scripts/scaffold_hyperframes.py` (add `_hardlink_final_mp4` helper; change `video_src` in `scaffold()`)
- Modify: `tests/test_scaffold_hyperframes.py` (add hardlink test)

- [ ] **Step 1: Write a failing test for the hardlink helper**

Append to `tests/test_scaffold_hyperframes.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_scaffold_hyperframes.py::test_hardlink_final_mp4_creates_link -v
```

Expected: FAIL with `ImportError: cannot import name '_hardlink_final_mp4'`.

- [ ] **Step 3: Add the `_hardlink_final_mp4` helper to `scripts/scaffold_hyperframes.py`**

Add this helper function after `_ffprobe_dimensions_and_duration` (around line 107):

```python
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
```

Add `import os` to the top of the file (after `import json`):

```python
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
```

- [ ] **Step 4: Run hardlink tests — must pass**

```bash
pytest tests/test_scaffold_hyperframes.py::test_hardlink_final_mp4_creates_link tests/test_scaffold_hyperframes.py::test_hardlink_final_mp4_is_idempotent -v
```

Expected: both PASS.

- [ ] **Step 5: Update `scaffold()` to call hardlink helper and pass `video_src="final.mp4"`**

In `scripts/scaffold_hyperframes.py` `scaffold()` function, change two things:

1. The `patch_index_html` call (around line 139-142) — change `video_src` from `"../edit/final.mp4"` to `"final.mp4"`:

```python
    html = patch_index_html(
        html, width=width, height=height, duration=duration,
        video_src="final.mp4",
    )
```

2. After `index_path.write_text(...)` (around line 149) and before `# Patch meta.json` (line 151), insert:

```python
    # Hardlink final.mp4 next to index.html (canon path resolution)
    _hardlink_final_mp4(episode_dir)
```

- [ ] **Step 6: Update `test_scaffold_end_to_end` assertions for the new path**

In `tests/test_scaffold_hyperframes.py`, update the `test_scaffold_end_to_end` test:

- The line `assert not (hf / "final.mp4").exists()` (around line 158) needs to flip — we DO now create a sibling `final.mp4`. Replace it with:

```python
    # final.mp4 hardlinked from edit/ next to index.html
    assert (hf / "final.mp4").exists()
```

- The line `assert 'src="../edit/final.mp4"' in html` (around line 165) needs updating to:

```python
    assert 'src="final.mp4"' in html
    # parent-dir path no longer used — sibling hardlink replaces it
    assert 'src="../edit/final.mp4"' not in html
```

- [ ] **Step 7: Run end-to-end test**

```bash
pytest tests/test_scaffold_hyperframes.py::test_scaffold_end_to_end -v
```

Expected: PASS (or SKIP if `npx` missing — both acceptable).

- [ ] **Step 8: Run the full file**

```bash
pytest tests/test_scaffold_hyperframes.py -v
```

Expected: all pass / skipped.

- [ ] **Step 9: Commit**

```bash
git add scripts/scaffold_hyperframes.py tests/test_scaffold_hyperframes.py
git commit -m "fix(scaffold): hardlink final.mp4 next to index.html

HF lint/validate trip on parent-directory paths in src=. Hardlink
costs 0 extra disk vs copy (~30-100 MB per episode). Cross-platform
via mklink /H on Windows and os.link on Unix. Closes retro 2.1."
```

---

## Task 3: Phase 3 brief — pacing + no-subtitles + retake selection

**Why:** Retro 1.1, 1.2 + retake addendum. The first retro produced a pacing formula that never made it to the brief. Subtitles must be omitted from `final.mp4` so HF owns captions. Retake tie-breaker prevents agent paralysis.

**Files:**
- Modify: `.claude/commands/edit-episode.md` — replace the `> **Pacing:**` line in the Phase 3 brief; add a new `> **Subtitles:**` block; add a `> **Retake selection:**` block; update `> **Required outputs:**` to drop `subtitles`.

- [ ] **Step 1: Replace the Phase 3 pacing line**

In `.claude/commands/edit-episode.md`, line 93 currently reads:

```
> **Pacing:** follow the "Cut craft (techniques)" section of the canon — silences ≥400ms cleanest cuts, 150–400ms usable with visual check, <150ms unsafe. Padding stays in 30–200ms (Hard Rule 7). Per Principle 5, the canon's launch-video example values (50ms / 80ms) are a worked example, not a mandate. Default lean for our content: tight end of the window, eliminate retakes/false starts.
```

Replace it with:

```
> **Pacing target.** Aim for **25–35% runtime reduction** from source. Treat any inter-phrase silence > 300ms as a cut candidate (canon: silences ≥ 400ms are cleanest cut targets, 150–400ms usable with visual check, < 150ms unsafe — mid-phrase). Cut padding stays in 30–200ms (Hard Rule 7 — absorbs Scribe's 50–100ms drift; this rule is about cut-edge padding, NOT inter-phrase silence). Remove all retakes and false starts. If final runtime > 75% of source, append a one-line note in `project.md` explaining why tighter cuts were not possible.
```

- [ ] **Step 2: Insert a `> **Subtitles:**` block right after the new pacing block**

Add immediately after the pacing line (so before `> **Required outputs:**`):

```
>
> **Subtitles.** Do NOT burn subtitles into `final.mp4`. Omit the `subtitles` field from EDL **and** pass `--no-subtitles` to `helpers/render.py` (defense in depth — canon §8 of `docs/cheatsheets/video-use.md`). Do not pass `--build-subtitles`. Captions are produced downstream by Phase 4 (HyperFrames `references/captions.md`).
>
> **Retake selection.** When the same beat is recorded multiple times (false-starts, retakes within a single take or across takes), pick the cleanest delivery — fewer slips, better energy, completed thought. If two takes are roughly equal, prefer the **later** one (the speaker is usually warmed up). Note the choice briefly in EDL `reason`, e.g. `"Last take, first had stutter"` (canon EDL example uses this `reason` shape).
```

- [ ] **Step 3: Update the `> **Required outputs:**` block to drop `subtitles` from the recommended list**

Currently line 98:

```
> - `edl.json` — final EDL per the canon's "EDL format". Functionally required: `ranges`, `sources`. Recommended: `total_duration_s`, `grade`, `subtitles`, `overlays`.
```

Replace with:

```
> - `edl.json` — final EDL per the canon's "EDL format". Functionally required: `ranges`, `sources`. Recommended: `total_duration_s`, `grade`, `overlays`. **Do NOT** include `subtitles` — HF owns captions (see Subtitles block above).
```

- [ ] **Step 4: Verify the brief reads coherently**

```bash
sed -n '79,115p' .claude/commands/edit-episode.md
```

Expected: pacing/subtitles/retake blocks read in order; no `master.srt` mention remains as a required output.

- [ ] **Step 5: Verify `master.srt` is no longer mentioned anywhere as required**

```bash
grep -n "master.srt" .claude/commands/edit-episode.md
```

Expected: zero matches (or only inside an unrelated context — visual review confirms).

- [ ] **Step 6: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "feat(edit-episode): tighten Phase 3 brief — pacing/no-subs/retake policy

- Pacing target: 25-35% reduction, 300ms cut-candidate threshold,
  escape hatch via project.md note.
- Subtitles: omit from EDL and pass --no-subtitles. HF owns captions.
- Retake selection: cleanest delivery wins; tie-breaker is later take.

Closes retro 1.1, 1.2, and retake addendum. Closes the meta-issue
(prior retro's pacing formula never reached the brief)."
```

---

## Task 4: Phase 4 brief — multi-scene mandate + DESIGN.md substance + WCAG canon + registry

**Why:** Retro 1.3, 2.2, 2.3, 2.5, 3.4. Single-scene caption-only compositions are out. DESIGN.md must be substantive (≥2 references, ≥1 alternative). WCAG fails are resolved by adjusting hue, not retreating from color. Registry blocks become mandatory consideration.

**Files:**
- Modify: `.claude/commands/edit-episode.md` — Phase 4 brief (lines 145-165 area).

- [ ] **Step 1: Replace the Multi-scene transitions line**

Currently line 151:

```
> **Multi-scene transitions:** if the composition has multiple scenes, the canon's "Scene Transitions (Non-Negotiable)" rules apply: always use transitions, every scene gets entrance animations, never exit animations except on the final scene.
```

Replace with:

```
> **Multi-scene narrative composition (mandatory).** Read `<EPISODE_DIR>/script.txt` and identify ≥ 3 narrative beats. Compositions MUST be multi-scene with ≥ 3 beat-derived scenes. Apply Scene Transitions canon (HF SKILL.md §"Scene Transitions" — non-negotiable: always use transitions, every scene gets entrance animations, never exit animations except on the final scene). For each beat, choose either (a) a registry block (run `npx hyperframes catalog` to browse before authoring custom HTML; install via `npx hyperframes add <name>`) or (b) custom motion / overlay justified by the script content. Single-scene caption-only compositions are not acceptable. Document the beat→visual mapping in `DESIGN.md` alongside palette and typography decisions.
```

- [ ] **Step 2: Replace the Visual Identity Gate paragraph with a substantive-DESIGN.md mandate**

Currently line 149:

```
> **Visual Identity Gate (canonical `<HARD-GATE>`):** before writing any composition HTML, follow the canon's gate order in SKILL.md §"Visual Identity Gate". The user's named style is **"Liquid Glass / iOS frosted glass"** — start at gate step 3: read `~/.agents/skills/hyperframes/visual-styles.md` for a matching named preset and apply it. If no matching preset exists, generate a minimal `DESIGN.md` per the canon's structure. Do not hardcode `#333` / `#3b82f6` / `Roboto`.
```

Replace with:

```
> **Visual Identity Gate (canonical `<HARD-GATE>`).** Before writing any composition HTML, follow the canon's gate order in SKILL.md §"Visual Identity Gate". The user's named style is **"Liquid Glass / iOS frosted glass"** — start at gate step 3: read `~/.agents/skills/hyperframes/visual-styles.md` for a matching named preset and apply it. If no matching preset exists, generate a `DESIGN.md` per the canon's structure. Do not hardcode `#333` / `#3b82f6` / `Roboto`.
>
> **DESIGN.md substance.** The generated `DESIGN.md` must contain — not as a template, but as real authored content:
> - **Style Prompt** — one-paragraph mood statement.
> - **Colors** — 3–5 hex values with named roles.
> - **Typography** — 1–2 font families.
> - **Visual References** — name ≥ 2 specific real-world references (e.g., "iOS 17 Control Center frosted panels", "Vision Pro spatial UI"). Generic references like "modern minimalist" do not count.
> - **Alternatives Considered** — describe ≥ 1 alternative direction and why it was rejected.
> - **What NOT to Do** — 3–5 anti-patterns specific to this episode.
> - **Beat→Visual Mapping** — from the multi-scene block above.
>
> **WCAG fail handling.** WCAG fails are resolved by adjusting hue within the palette family (HF SKILL.md §"Contrast": "On dark backgrounds: brighten until clears 4.5:1 ... Stay within palette family — don't invent a new color, adjust the existing one"). Try ≥ 2 darker/brighter variants of the same hue before considering structural changes. Removing color in favor of weight-only emphasis is a last resort and requires a one-line justification in `DESIGN.md`.
```

- [ ] **Step 3: Verify the brief**

```bash
sed -n '143,180p' .claude/commands/edit-episode.md
```

Expected: Visual Identity Gate → DESIGN.md substance → multi-scene narrative → WCAG handling read in coherent order.

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "feat(edit-episode): Phase 4 brief — multi-scene + DESIGN.md substance + WCAG canon

- Multi-scene mandatory (>=3 beat-derived scenes from script.txt).
- DESIGN.md must have >=2 visual references and >=1 alternative considered.
- WCAG fails resolved by adjusting hue (canon), not retreating from color.
- Registry catalog browse step is now part of every beat decision.

Closes retro 1.3, 2.2, 2.3, 2.5, 3.4."
```

---

## Task 5: Visual Verification gate

**Why:** Retro 1.5. Canonical Output Checklist (`lint`/`validate`/`inspect`/animation-map) covers layout/contrast/choreography but not narrative coherence. The new gate uses `inspect --at` (canonical layout audit on narrative timestamps) plus `snapshot --at` (canonical PNG screenshots — no full render, no ffmpeg shell-out) plus three explicit per-frame questions.

**Files:**
- Modify: `.claude/commands/edit-episode.md` — insert a new block in the Phase 4 brief between the existing "Output Checklist" (and orchestrator extra-check) and "Project memory" / "Studio launch".

- [ ] **Step 1: Insert the Visual Verification block**

Find the line (around 161):

```
> **Project memory:** append a session block to `<EPISODE_DIR>/edit/project.md` with Strategy / Decisions / Outstanding for this composition.
```

Insert immediately BEFORE that line:

```
> **Visual verification (mandatory before announcing Done).** Use canonical HF tools — no ffmpeg shell-out.
>
> 1. **Canonical layout audit at beat boundaries.** Run `npx hyperframes inspect --at <beat_timestamps>` from `<EPISODE_DIR>/hyperframes/`, where `<beat_timestamps>` are the comma-separated start times of each beat from the §"Beat→Visual Mapping" of `DESIGN.md`. Re-uses the canonical layout/overflow audit on the timestamps that matter narratively.
> 2. **Canonical screenshots at beat boundaries.** Run `npx hyperframes snapshot --at <beat_timestamps>` (canonical PNG screenshots without full render — see `docs/cheatsheets/hyperframes.md` §"snapshot"). Include `1`, every beat boundary, and `<duration - 1>` in the timestamp list.
> 3. **Three explicit questions per snapshot** — answer in writing in your final report, before the studio launch:
>    a. Is the expected beat element visible (registry block / scene card / overlay from §"Multi-scene narrative composition")?
>    b. Any unintended z-overlap (caption covering a key element, scene exit leaving residue)?
>    c. Is the A-roll video accidentally occluded by a semi-transparent overlay?
> 4. Only after this list is in your report, proceed to the studio launch.
>
```

- [ ] **Step 2: Verify**

```bash
sed -n '155,180p' .claude/commands/edit-episode.md
```

Expected: Visual verification block sits between the Output Checklist + extra check and Project memory; no broken markdown.

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "feat(edit-episode): add Visual Verification gate to Phase 4

Uses canonical \`hyperframes inspect --at\` and \`snapshot --at\` on
beat-boundary timestamps from DESIGN.md beat-mapping. Three explicit
questions per snapshot guard against caption overlap, scene-exit
residue, and accidental video occlusion. No ffmpeg shell-out.

Closes retro 1.5."
```

---

## Task 6: Studio-launch — redirect log to `.hyperframes/preview.log`

**Why:** Retro 3.1. Background `npx hyperframes preview` currently dumps log into the episode root or `hyperframes/preview.log`. `.hyperframes/` is the canonical scratch directory (cheatsheet §"Внутренние ресурсы скилла" uses it for tooling output) and is conventionally gitignored.

**Files:**
- Modify: `.claude/commands/edit-episode.md` — studio launch commands in the Phase 4 brief (around line 163-165) AND in the skip-build path (around line 173).

- [ ] **Step 1: Update the Phase 4 brief studio-launch commands**

Currently (lines 163-167):

```
> **Studio launch:** after gates pass, launch the preview server in the background. Run from `<EPISODE_DIR>/hyperframes/`:
> - PowerShell: `Start-Process npx -ArgumentList 'hyperframes','preview','--port','3002' -WindowStyle Hidden`
> - Bash: `npx hyperframes preview --port 3002 &`
>
> Report `http://localhost:3002` to the user.
```

Replace with:

```
> **Studio launch:** after gates pass, launch the preview server in the background. Run from `<EPISODE_DIR>/hyperframes/`. Logs go to `.hyperframes/preview.log` (canonical scratch dir):
> - Bash: `mkdir -p .hyperframes && npx hyperframes preview --port 3002 > .hyperframes/preview.log 2>&1 &`
> - PowerShell: `New-Item -ItemType Directory -Force -Path .hyperframes | Out-Null; Start-Process npx -ArgumentList 'hyperframes','preview','--port','3002' -RedirectStandardOutput .hyperframes\preview.log -RedirectStandardError .hyperframes\preview.err.log -WindowStyle Hidden`
>
> Report `http://localhost:3002` to the user.
```

- [ ] **Step 2: Verify the skip-build studio-launch path inherits the change**

Currently line 173:

```
If Phase 4 was skipped because `index.html` already existed, run the studio launch above directly (use `--list` first to detect an already-running server and skip if found).
```

This already references "the studio launch above" — no edit needed; it inherits the redirect automatically.

- [ ] **Step 3: Confirm `.hyperframes/` is already gitignored**

`.gitignore` already has `episodes/` (covers the entire episodes tree, including `episodes/**/hyperframes/.hyperframes/` transitively). No edit needed.

```bash
grep -n "^episodes/$" .gitignore
```

Expected: at least one match. If missing, the orchestrator's `episodes/` ignore is broken — fix that separately, not in this PR.

- [ ] **Step 4: Verify the brief reads cleanly**

```bash
sed -n '163,175p' .claude/commands/edit-episode.md
```

Expected: both bash and PowerShell launch commands include the redirect to `.hyperframes/preview.log`.

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "chore(edit-episode): redirect studio preview log to .hyperframes/

Stops preview.log from landing in the episode root or hyperframes/
root. .hyperframes/ is the canonical scratch dir (cheatsheet shows
it as the standard output dir for tooling). Closes retro 3.1."
```

---

## Task 7: Cheatsheet gotchas

**Why:** Retro 3.2 root cause + retro 1.4 root cause documentation. The cheatsheet was already correct on `class="clip"`; the manual scaffold drifted from it by porting from `SKILL.md`'s incomplete video example. Future scaffold authors need a sign that says "trust the cheatsheet, not SKILL.md's `<video>`/`<audio>` example".

**Files:**
- Modify: `docs/cheatsheets/hyperframes.md` — append a "Scaffolding gotchas" subsection near the §"Setup / окружение" section (or wherever feels coherent — `tail` the file to find the right spot).

- [ ] **Step 1: Find the right insertion point**

```bash
grep -n "^## " docs/cheatsheets/hyperframes.md | tail -20
```

Pick a location: either right before §"Setup / окружение" or as a new top-level §"Scaffolding gotchas". Use whichever flows better — `## Setup / окружение` is on line ~944 currently, so insert before it.

- [ ] **Step 2: Insert the gotchas block**

Insert this block immediately before the `## Setup / окружение` heading:

```markdown
## Scaffolding gotchas

Drift between `SKILL.md` examples and what the runtime actually requires has bitten this orchestrator twice. Future scaffold authors:

- **Prefer this cheatsheet's `<video>`/`<audio>` example over `SKILL.md`'s.** The main `SKILL.md` `Video and Audio` example (canon line 171–188) omits `class="clip"`. The runtime's per-project `CLAUDE.md` Key Rule 2 requires `class="clip"` on every timed element, and `npx hyperframes lint` enforces it. The §"Видео и аудио" examples on this cheatsheet include `class="clip"` correctly — that is the source of truth for media-element scaffolding.
- **Parent-directory paths (`../`) in `src` attributes break `lint`/`validate`.** All media referenced from `index.html` must live alongside it (or in subdirectories). When the file's logical home is a sibling directory (e.g., `<episode>/edit/final.mp4` for an HF project at `<episode>/hyperframes/`), use a hardlink (`mklink /H` on Windows, `os.link` on Unix) — zero additional disk vs. a copy.

---

```

- [ ] **Step 3: Verify**

```bash
grep -n "Scaffolding gotchas\|class=\"clip\"\|mklink /H" docs/cheatsheets/hyperframes.md | head -10
```

Expected: at least three matches — the new section heading, the `class="clip"` mention, and the `mklink /H` mention.

- [ ] **Step 4: Commit**

```bash
git add docs/cheatsheets/hyperframes.md
git commit -m "docs(cheatsheet): document scaffolding gotchas (class=clip, ../ paths)

Future authors should trust the cheatsheet's media-pair example over
SKILL.md's, which omits class=\"clip\". And the parent-dir gotcha
explains why hardlinks are the right answer for sibling-directory
assets. Closes retro meta-issue (drift from canon during manual
scaffold work)."
```

---

## Task 8: Investigation — `animation-map.mjs` / `contrast-report.mjs` bootstrap

**Why:** Retro 2.4. Scripts in `~/.agents/skills/hyperframes/scripts/*.mjs` use ancestor-chain `package.json` lookup; globally-installed `hyperframes` does not appear in that chain. We must investigate before deciding a fix.

**Files:**
- This task produces a short investigation note (no code change yet) and either a follow-up commit if a clean fix is found, or a TODO commit + upstream issue link if not.

- [ ] **Step 1: Try `npm install hyperframes --save-dev` in repo root and re-run `animation-map.mjs`**

```bash
# At repo root (the worktree, NOT inside an episode):
npm init -y > /dev/null 2>&1
npm install hyperframes --save-dev
node ~/.agents/skills/hyperframes/scripts/animation-map.mjs episodes/2026-04-30-desktop-software-licensing-it-turns-out-is/hyperframes \
  --out episodes/2026-04-30-desktop-software-licensing-it-turns-out-is/hyperframes/.hyperframes/anim-map 2>&1 | head -30
```

- [ ] **Step 2: Record the outcome**

If the script ran successfully — the ancestor-chain found `node_modules/hyperframes` in the repo root. Proceed to Step 3a.

If it still failed — try the speculative env-var `HYPERFRAMES_SKILL_NODE_MODULES` (mentioned in retro 2.4; **NOT** documented in canon or cheatsheet — this is a guess at a possible knob, may not exist):

```bash
HYPERFRAMES_SKILL_NODE_MODULES=$(npm root -g) node ~/.agents/skills/hyperframes/scripts/animation-map.mjs episodes/.../hyperframes 2>&1 | head -30
```

If that worked, proceed to Step 3b. If both failed (likely, given the env-var is speculative), proceed to Step 3c.

- [ ] **Step 3a: If repo-root `npm install hyperframes` worked — keep `package.json` and document**

Edit `.claude/commands/edit-episode.md` Phase 4 brief: replace the existing animation-map step (line 157) with a version that confirms repo-root `node_modules/hyperframes` is the canonical bootstrap path:

```
> 4. `node ~/.agents/skills/hyperframes/scripts/animation-map.mjs <hyperframes-dir> --out <hyperframes-dir>/.hyperframes/anim-map` — required for new compositions per canon. The script bootstraps from `<repo-root>/node_modules/hyperframes` (installed via `npm install hyperframes --save-dev` at the orchestrator repo root). Read the JSON; check every flag (`offscreen`, `collision`, `invisible`, `paced-fast`, `paced-slow`); fix or justify.
```

Commit with both the `package.json`/`package-lock.json` and the brief edit:

```bash
git add package.json package-lock.json .claude/commands/edit-episode.md
git commit -m "chore: install hyperframes in repo root for skill scripts bootstrap

The ancestor-chain package-loader in animation-map.mjs / contrast-report.mjs
finds <repo-root>/node_modules/hyperframes from any episode subdirectory.
Closes retro 2.4."
```

- [ ] **Step 3b: If the speculative env-var worked — wire it into the brief AND verify upstream**

Before relying on it, search the upstream skill source for any reference (the env-var is not in canon — if it works, it may be undocumented and could disappear):

```bash
grep -rn "HYPERFRAMES_SKILL_NODE_MODULES" ~/.agents/skills/hyperframes/ 2>/dev/null
```

If a match exists, the var IS a real (if undocumented) knob — use it. If no match but the script still resolved the global install, the success was likely coincidental (e.g., your shell's `NODE_PATH` was set elsewhere). In that case, prefer Step 3a (repo-root install) for stability.

If proceeding with the env-var, edit `.claude/commands/edit-episode.md` Phase 4 brief (line 157):

```
> 4. `HYPERFRAMES_SKILL_NODE_MODULES=$(npm root -g) node ~/.agents/skills/hyperframes/scripts/animation-map.mjs <hyperframes-dir> --out <hyperframes-dir>/.hyperframes/anim-map` — required for new compositions per canon. The env var points the package-loader at the global install (undocumented in canon — may break in future skill updates). Read the JSON; check every flag (`offscreen`, `collision`, `invisible`, `paced-fast`, `paced-slow`); fix or justify.
```

Commit:

```bash
git add .claude/commands/edit-episode.md
git commit -m "fix(edit-episode): wire HYPERFRAMES_SKILL_NODE_MODULES for animation-map

Closes retro 2.4 — global hyperframes install resolves via the env-var.
Note: env-var is undocumented in HF skill canon; may break in future
upstream changes. Re-evaluate if animation-map fails after a skill update."
```

- [ ] **Step 3c: If both failed — document with a TODO and a planned upstream issue**

Edit `.claude/commands/edit-episode.md` Phase 4 brief (line 157), keep the canonical command, but add a TODO line:

```
> 4. `node ~/.agents/skills/hyperframes/scripts/animation-map.mjs <hyperframes-dir> --out <hyperframes-dir>/.hyperframes/anim-map` — required for new compositions per canon. **Currently broken when hyperframes is installed globally**: the script's ancestor-chain `package.json` lookup misses the global location. Track upstream fix; until then, mark this step `skipped — blocked by hyperframes-skill upstream issue`. Read the JSON if it ran; check every flag.
```

Commit:

```bash
git add .claude/commands/edit-episode.md
git commit -m "docs(edit-episode): document animation-map bootstrap gap (retro 2.4)

Both repo-root install and HYPERFRAMES_SKILL_NODE_MODULES failed to
resolve the global hyperframes install. Marking the canonical
animation-map step as 'skipped — blocked by upstream' until upstream
fixes the package-loader. Open issue is a follow-up action."
```

Then immediately open an upstream issue:

```bash
# Spell out the repro in the issue body
gh issue create \
  --repo heygen-com/hyperframes \
  --title "scripts/animation-map.mjs ancestor-chain misses globally-installed hyperframes" \
  --body "Repro: install hyperframes globally (\`npm i -g hyperframes\`), run \`node ~/.agents/skills/hyperframes/scripts/animation-map.mjs <comp-dir>\`. The package-loader's ancestor-chain walk from the script's own location does not reach the global node_modules. Setting HYPERFRAMES_SKILL_NODE_MODULES=\$(npm root -g) does not help. See repro details at <link to this commit>."
```

(If `gh` is not authenticated for the upstream repo, document the issue text in `docs/superpowers/specs/2026-04-30-edit-episode-second-retro-fixes-design.md` Section 6 as a paste-ready block and ask the user to file it.)

---

## Task 9: Final spec/plan housekeeping + PR

**Why:** Wrap the branch, push, open the PR per CLAUDE.md mandate.

- [ ] **Step 1: Run the full test suite once more**

```bash
pytest -v
```

Expected: all pass / skipped. If anything fails, investigate before proceeding.

- [ ] **Step 2: Push the branch**

```bash
git push -u origin retro-fixes-2026-04-30
```

- [ ] **Step 3: Open the PR**

```bash
gh pr create --base main --title "retro-2026-04-30: tighten Phase 3/4 briefs, fix scaffold media pair, hardlink final.mp4" --body "$(cat <<'EOF'
## Summary

Lands all 14 findings from `retro-2026-04-30-desktop-software-licensing-it-turns-out-is.md`:

- **Phase 3 brief** — explicit pacing target (25-35% reduction, 300ms cut threshold), no-burned-in-subtitles policy, retake selection tie-breaker.
- **Phase 4 brief** — multi-scene mandatory (≥3 beat-derived scenes), DESIGN.md substance gate, WCAG hue-adjust canon, registry catalog browse step.
- **Visual Verification gate** — canonical `inspect --at` + `snapshot --at` at beat boundaries, three explicit per-frame questions before announcing Done.
- **Scaffold** — `class="clip"` and canon `data-track-index="2"` for the audio element (root cause of phantom audio doubling), hardlink `final.mp4` next to `index.html` (closes the parent-dir-path validator failure).
- **Studio launch** — log redirect to `.hyperframes/preview.log`.
- **Cheatsheet gotchas** — sign for future scaffold authors: trust the cheatsheet over SKILL.md's `<video>` example.
- **Investigation outcome** — animation-map bootstrap (see commit log).

Spec: `docs/superpowers/specs/2026-04-30-edit-episode-second-retro-fixes-design.md`.
Plan: `docs/superpowers/plans/2026-04-30-edit-episode-second-retro-fixes.md`.

## Test plan

- [x] `pytest tests/test_scaffold_hyperframes.py -v` — all pass / skipped
- [ ] Manual: re-run `/edit-episode 2026-04-30-desktop-software-licensing-it-turns-out-is` after deleting `final.mp4` + `master.srt` + `hyperframes/` (idempotency contract — Scribe and ElevenLabs caches are NOT invalidated). Verify:
  - `final.mp4` lacks burned-in subtitles
  - inter-phrase silences tightened (final runtime within 65-75% of source)
  - HF composition has ≥ 3 scenes with transitions
  - `DESIGN.md` has ≥ 2 visual references and ≥ 1 alternative
  - Visual Verification block produces inspect + snapshot output before studio launches
  - Studio plays a single audio track (no phantom dub)

EOF
)"
```

- [ ] **Step 4: Wait for tests, then merge**

```bash
gh pr checks --watch
gh pr merge --squash --delete-branch
```

- [ ] **Step 5: Clean up the worktree**

```bash
cd ../..
git worktree remove .worktrees/retro-fixes-2026-04-30
git checkout main
git pull
```

---

## Verification after merge (not part of this PR)

These are post-merge checks the user runs against the affected episode. Only open follow-up issues if any FAIL.

- [ ] **V1: Phantom audio dub gone (retro 1.4 verification)**

After re-running `/edit-episode <slug>` and launching studio, confirm there is exactly one audio track, no ~50–100 ms shifted dub. If still present after `class="clip"` is applied → minimally reproduce in a clean HF project (canon-correct `<video>`/`<audio>` pair with `class="clip"`) and file an upstream HF studio issue.

- [ ] **V2: `data-has-audio` warning (retro 3.3 verification)**

Run `npx hyperframes validate` in the regenerated `hyperframes/` dir. If StaticGuard still emits the `data-has-audio=true but also muted` warning, diagnose separately — that is a different issue than retro 1.4.

- [ ] **V3: Idempotency contract holds**

After re-run:
- `transcripts/raw.json` survives (no Scribe re-spend).
- `ANTICODEGUY_AUDIO_CLEANED` tag on `raw.<ext>` survives (no ElevenLabs Audio Isolation re-spend).
- Phase 1 + Phase 2 announced as skipped; Phase 3 + Phase 4 re-run.
