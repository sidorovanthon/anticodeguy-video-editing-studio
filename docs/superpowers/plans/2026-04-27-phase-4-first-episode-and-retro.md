# Phase 4 — First real episode and retro flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a first real talking-head video through the whole pipeline end-to-end, exercise every checkpoint, fill `retro.md` with real observations, run the macro-retro to surface proposed standards changes, and add `tools/scripts/retro-promote.sh` so the user can promote selected proposals into `standards/` with a `retro-changelog.md` entry.

**Architecture:** No new compositor code. The work is operational: drive a real episode through the pipeline, capture friction, codify learnings into long-lived rules. The only new code is `retro-promote.sh`.

**Tech Stack:** Same as Phase 3 plus the user's first real raw footage.

**Prerequisite:** Phase 3 complete. `phase-3-compositor` git tag exists. The user has placed a real `raw.mp4` in `incoming/` and chosen a music track in `library/music/`.

---

## File structure produced by this phase

```
tools/scripts/retro-promote.sh
tools/scripts/test/test-retro-promote.sh
episodes/<YYYY-MM-DD>-<first-real-slug>/...   (the first real episode, all artifacts)
```

Plus updates to: any of `standards/*.md`, and append entries in `standards/retro-changelog.md`.

---

### Task 1: `retro-promote.sh` — failing test

**Files:**
- Create: `tools/scripts/test/test-retro-promote.sh`

The promote script reads selected proposals from a temporary file (or interactively) and applies them: edits the corresponding `standards/*.md` and appends to `standards/retro-changelog.md`. For testability we accept proposals via a file at `episodes/<slug>/promote.txt`.

`promote.txt` format (one proposal per line):

```
PROMOTE captions.md baseline 22%-from-bottom episode=<slug> reason="overlap with TikTok UI"
PROMOTE motion-graphics.md max-consecutive-same-mode 3 episode=<slug> reason="too monotonous in pilot"
```

The script:
1. Validates each line starts with `PROMOTE`.
2. For each proposal, appends a section to the named `standards/*.md` file (idempotent — skip if same key already present).
3. Appends a single block to `standards/retro-changelog.md` with date + change list + source episode + reason.

- [ ] **Step 1: Write the test**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp -r "$REPO_ROOT" "$WORK/repo"
cd "$WORK/repo"
EP="$WORK/repo/episodes/2026-04-27-promote-test"
mkdir -p "$EP"

cat > "$EP/promote.txt" <<EOF
PROMOTE captions.md baseline 22%-from-bottom episode=2026-04-27-promote-test reason="overlap"
EOF

./tools/scripts/retro-promote.sh 2026-04-27-promote-test \
  || { echo "FAIL: retro-promote exited non-zero"; exit 1; }

grep -q "baseline 22%-from-bottom" standards/captions.md || { echo "FAIL: standards/captions.md not updated"; exit 1; }
grep -q "promote-test" standards/retro-changelog.md      || { echo "FAIL: changelog not appended"; exit 1; }
echo "OK"
```

- [ ] **Step 2: Run, expect failure**

```bash
chmod +x tools/scripts/test/test-retro-promote.sh
tools/scripts/test/test-retro-promote.sh
```

Expected: failure (script does not exist yet).

---

### Task 2: Implement `tools/scripts/retro-promote.sh`

**Files:**
- Create: `tools/scripts/retro-promote.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then echo "Usage: $0 <slug>"; exit 1; fi
SLUG="$1"
REPO_ROOT="$(pwd)"
EP="$REPO_ROOT/episodes/$SLUG"
PROMOTE="$EP/promote.txt"
CHANGELOG="$REPO_ROOT/standards/retro-changelog.md"

[ -d "$EP" ]       || { echo "ERROR: $EP not found"; exit 1; }
[ -f "$PROMOTE" ]  || { echo "ERROR: $PROMOTE not found. Write proposals there first."; exit 1; }

DATE="$(date +%Y-%m-%d)"
declare -a touched_files=()
declare -a changelog_lines=()

while IFS= read -r line; do
  [ -z "$line" ] && continue
  case "$line" in
    \#*) continue ;;
  esac

  if [[ "$line" != PROMOTE* ]]; then
    echo "ERROR: line does not start with PROMOTE: $line"
    exit 1
  fi

  # Parse: PROMOTE <file> <key> <value> episode=<slug> reason="..."
  file="$(awk '{print $2}' <<<"$line")"
  key="$(awk '{print $3}'  <<<"$line")"
  value="$(awk '{print $4}' <<<"$line")"
  reason="$(sed -n 's/.*reason="\([^"]*\)".*/\1/p' <<<"$line")"

  target="$REPO_ROOT/standards/$file"
  [ -f "$target" ] || { echo "ERROR: standards/$file not found"; exit 1; }

  if grep -q "^- $key " "$target" 2>/dev/null; then
    echo "skip: $file already has $key"
    continue
  fi

  printf "\n## Promoted %s\n- %s %s (episode %s; %s)\n" \
    "$DATE" "$key" "$value" "$SLUG" "$reason" >> "$target"

  touched_files+=("$file")
  changelog_lines+=("- $file: $key=$value (reason: $reason)")
done < "$PROMOTE"

if [ "${#touched_files[@]}" -eq 0 ]; then
  echo "No proposals applied."
  exit 0
fi

{
  echo
  echo "## $DATE — promoted from $SLUG"
  printf "%s\n" "${changelog_lines[@]}"
} >> "$CHANGELOG"

echo "Promoted ${#touched_files[@]} proposal(s)."
echo "Updated standards: ${touched_files[*]}"
echo "Appended to: $CHANGELOG"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x tools/scripts/retro-promote.sh
```

- [ ] **Step 3: Run test, expect pass**

```bash
tools/scripts/test/test-retro-promote.sh
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add tools/scripts/retro-promote.sh tools/scripts/test/test-retro-promote.sh
git commit -m "feat: retro-promote.sh applies proposals to standards and changelog"
```

---

### Task 3: First real episode — ingest

User has placed a real `raw.mp4` in `incoming/`, optionally a `notes.md`, and selected a music track.

- [ ] **Step 1: Confirm prerequisites**

```bash
test -f incoming/raw.mp4 && echo "raw OK"
ls library/music/*.mp3 2>/dev/null | head && echo "music OK"
```

Expected: both lines, with at least one music file listed.

- [ ] **Step 2: Run new-episode**

```bash
SLUG=<choose-a-slug-now>          # e.g. introducing-claude-skills
tools/scripts/new-episode.sh "$SLUG"
```

Expected: `Created episodes/<DATE>-<SLUG>`. Note the full episode directory name; subsequent commands use it.

- [ ] **Step 3: Fill `meta.yaml`**

Edit `episodes/<DATE>-<SLUG>/meta.yaml` and set:
- `title` — final title for the short
- `tags` — relevant tags
- `music` — `library/music/<filename>.mp3` (relative path)

- [ ] **Step 4: Commit the new episode skeleton**

```bash
git add episodes/<DATE>-<SLUG>/meta.yaml
git commit -m "feat(episode): scaffold <DATE>-<SLUG>"
```

(`raw.mp4` is gitignored, so it does not enter the commit.)

---

### Task 4: First real episode — Stage 1 (CP1, CP2)

- [ ] **Step 1: Run Stage 1**

```bash
tools/scripts/run-stage1.sh <DATE>-<SLUG>
```

Expected: produces `transcript.json`, `cut-list.md`, `master.mp4`. Run time depends on raw length and ElevenLabs latency.

- [ ] **Step 2: CP1 review**

Open `episodes/<DATE>-<SLUG>/stage-1-cut/cut-list.md`. For each proposed cut, decide keep/cut. Edit the file directly; mark removed cuts with `KEEP:` prefix lines. Write deltas to `episodes/<DATE>-<SLUG>/retro.md` under a `## CP1` heading.

- [ ] **Step 3: Re-run Stage 1 if cut-list edited**

If the cut-list was edited, re-run `tools/scripts/run-stage1.sh <DATE>-<SLUG>` so the master reflects the edits. (Adjust `run-stage1.sh` to support a `--replay` mode if it currently always re-transcribes; if so, file a follow-up improvement in `retro.md`.)

- [ ] **Step 4: CP2 review**

Play `episodes/<DATE>-<SLUG>/stage-1-cut/master.mp4`. Verify pacing, color grade, vignette. Note any complaint in `retro.md` under `## CP2`.

- [ ] **Step 5: Tune `tools/compositor/grade.json` and `standards/color.md` if needed**

Adjust values, re-run stage 1, repeat CP2 until master looks right. Capture each adjustment as a delta in `retro.md`.

- [ ] **Step 6: Commit any tuning**

```bash
git add tools/compositor/grade.json standards/color.md
git commit -m "tune(stage1): grade params from first episode CP2"
```

(Skip commit if no changes were needed.)

---

### Task 5: First real episode — Stage 2 (CP2.5, CP3)

- [ ] **Step 1: Run Stage 2**

```bash
tools/scripts/run-stage2.sh <DATE>-<SLUG>
```

Expected: produces `seam-plan.md`, `composition.html`, `preview.mp4`.

- [ ] **Step 2: CP2.5 review — edit seam-plan**

Open `episodes/<DATE>-<SLUG>/stage-2-composite/seam-plan.md`. For each seam, confirm scene mode and graphic content. Edit graphics' `data` lines as needed. Validate that no forbidden transition (`a-a`, `a-d`, `d-a`, `d-d`, same-graphic `b-b`/`c-c`) appears.

Write deltas to `retro.md` under `## CP2.5`.

- [ ] **Step 3: Re-compose after seam-plan edits**

```bash
REPO_ROOT="$(pwd)" npx tsx tools/compositor/src/index.ts compose --episode "episodes/<DATE>-<SLUG>"
```

Re-render preview:

```bash
( cd "episodes/<DATE>-<SLUG>/stage-2-composite" && npx hyperframes render --input composition.html --output preview.mp4 --width 1440 --height 2560 --fps 60 )
```

- [ ] **Step 4: CP3 review**

Play `preview.mp4`. Verify captions are readable, do not wrap to 2 lines, sit above safe zone, are pure typography (no glass behind). Verify motion graphics fire at expected seams. Note any defect in `retro.md` under `## CP3`.

If captions defects are systemic (e.g. baseline too low everywhere), update `standards/captions.md` and `tokens.json` accordingly, re-compose, re-render. Capture as `retro.md` delta.

- [ ] **Step 5: Final render**

```bash
tools/scripts/render-final.sh <DATE>-<SLUG>
```

Expected: produces `final.mp4` at 1440x2560 / 60 fps / Rec.709 / AAC 320 kbps. Validate with:

```bash
ffprobe -v error -show_entries stream=width,height,r_frame_rate,codec_name -of default=nw=1 \
  episodes/<DATE>-<SLUG>/stage-2-composite/final.mp4
```

- [ ] **Step 6: Commit any standards/tokens changes**

```bash
git add standards/ design-system/tokens/tokens.json
git commit -m "tune(stage2): refinements from first episode CP3"
```

(Skip if none.)

---

### Task 6: Macro-retro

- [ ] **Step 1: Read `episodes/<DATE>-<SLUG>/retro.md` end-to-end**

Group similar deltas. For each group, write one proposal in `episodes/<DATE>-<SLUG>/promote.txt`. Tag each with one of:
- `PROMOTE` — apply now (clear improvement, observed in this episode and confidence high)
- `WATCH` — defer; observe one or two more episodes before deciding (record in `retro.md` only, no `promote.txt` line)
- `CONFIRM` — saw it once already; promote on next confirmation (record in `retro.md` only)

Example `promote.txt`:

```
PROMOTE captions.md baseline 24%-from-bottom episode=<DATE>-<SLUG> reason="UI overlap on iPhone 14 Pro"
PROMOTE color.md vignette-intensity 0.20 episode=<DATE>-<SLUG> reason="0.25 too dark in dim source"
```

- [ ] **Step 2: Apply promotions**

```bash
tools/scripts/retro-promote.sh <DATE>-<SLUG>
```

Expected: standards files updated, `standards/retro-changelog.md` appended.

- [ ] **Step 3: Commit promotions**

```bash
git add standards/ episodes/<DATE>-<SLUG>/
git commit -m "retro(<DATE>-<SLUG>): promote rules from first real episode"
```

- [ ] **Step 4: Tag**

```bash
git tag phase-4-first-episode
```

---

### Task 7: Verification of complete pipeline

- [ ] **Step 1: Run full test suite**

```bash
tools/scripts/test/test-check-deps.sh
tools/scripts/test/test-new-episode.sh
tools/scripts/test/test-run-stage1.sh
tools/scripts/test/test-run-stage2.sh
tools/scripts/test/test-render-final.sh
tools/scripts/test/test-retro-promote.sh
( cd tools/compositor && npx vitest run )
```

Expected: all pass.

- [ ] **Step 2: Confirm episode is publishable**

The `final.mp4` should be ready to upload to YouTube Shorts and TikTok directly. The user uploads manually for the first episode (publishing automation is out of scope; revisit later).

- [ ] **Step 3: Confirm clean working tree**

```bash
git status
```

Expected: clean.

---

## Phase 4 done. The pipeline is now operational.

After at least 3 real episodes, revisit `AGENTS.md` to consider switching from checkpoint mode to autonomous mode for stages where the agent has consistently produced acceptable results without human intervention.
