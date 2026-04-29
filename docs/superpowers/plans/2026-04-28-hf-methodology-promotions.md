# HyperFrames Methodology Promotions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the standards / AGENTS.md / wrapper changes that codify the HF methodology audit findings (Topic 3 spec): `lint/validate/inspect --strict-all` as required-pass; `≤5 s` scene cap and `scene ≠ seam` separation in `standards/motion-graphics.md`; `scene_mode` and HF transition as orthogonal axes; project-fixed mood with optional override.

**Architecture:** Mostly markdown edits (standards files, AGENTS.md, retro-changelog) plus a small wrapper change (`tools/scripts/run-stage2-compose.sh`) that switches three HF gate invocations from default-mode to `--strict-all`. One new doc (`docs/operations/render-environment.md`) captures the one-shot doctor pre-flight for fresh dev environments. No TS code changes.

**Tech Stack:** Markdown (standards, AGENTS.md, retro-changelog), Bash (compose wrapper).

**Spec:** [`docs/superpowers/specs/2026-04-28-hf-methodology-promotions-design.md`](../specs/2026-04-28-hf-methodology-promotions-design.md)

---

## Pre-flight context

Current `tools/scripts/run-stage2-compose.sh` (lines 64-72) runs:
```bash
"$HF_BIN" lint "$COMPOSITE_DIR"      || { ...; exit 1; }
"$HF_BIN" validate "$COMPOSITE_DIR" || { ...; exit 1; }
"$HF_BIN" inspect "$COMPOSITE_DIR" --json > "$COMPOSITE_DIR/.inspect.json" || { ...; exit 1; }
```

None of these pass `--strict-all`. Per `tools/hyperframes-skills/hyperframes-cli/SKILL.md`:
- `--strict` fails on lint errors (default already does this for `lint`).
- `--strict-all` fails on errors AND warnings.

We promote all three to `--strict-all` to harden the pre-render gate.

`standards/motion-graphics.md` "Scene length" section currently reads "A scene runs from one seam to the next regardless of resulting duration." This needs replacing wholesale per spec P2.

`AGENTS.md` already lists hard rules; add one new bullet under the `## Hard rules` section.

`standards/retro-changelog.md` is append-only; add one dated entry per spec P5.

---

## File Structure

**New files:**
- `docs/operations/render-environment.md` — one-shot doctor pre-flight instructions for fresh dev environments.

**Modified files:**
- `standards/motion-graphics.md` — P2 (scene length / scene ≠ seam), P3 (orthogonal axes section), P4 (mood inheritance section).
- `standards/retro-changelog.md` — P5 dated entry.
- `AGENTS.md` — P1 hard rule about `lint/validate/inspect --strict-all`.
- `tools/scripts/run-stage2-compose.sh` — append `--strict-all` to lint/validate/inspect invocations.
- `tools/scripts/test/test-run-stage2.sh` — assert wrapper aborts on a deliberate warning-level issue (regression test for `--strict-all` enforcement).

---

### Task 1: Update `standards/motion-graphics.md` per P2 (scene length / scene ≠ seam)

**Files:**
- Modify: `standards/motion-graphics.md` (Scene length section, around line 36-38).

- [ ] **Step 1: Locate the existing Scene length section**

```bash
grep -n "^## Scene length" standards/motion-graphics.md
grep -n "Bounded by phrase boundaries" standards/motion-graphics.md
```

Expected: line numbers for the heading and the prose immediately under it.

- [ ] **Step 2: Replace the section in place**

In `standards/motion-graphics.md`, find:

```markdown
## Scene length
Bounded by phrase boundaries, not arbitrary timers. A scene runs from one seam to the next regardless of resulting duration.
```

Replace with:

```markdown
## Scene length and seam mapping

A **scene** is the unit of visual planning. Scenes are derived from script semantics, not from EDL seams.

- **Hard cap: 5 seconds per scene.** No scene exceeds 5 s, regardless of script structure. A 12 s narrative beat is subdivided into 2–3 sub-scenes by the planner. The cap is enforced at planner output, not as a soft preference.
- **Scene boundaries are independent of EDL seams.** EDL seams are structural (where the footage cuts); scene boundaries are semantic (what the viewer should see). A scene may contain 0, 1, or N seams inside it; one seam does not imply a new scene.
- **`max_seams_per_scene` per mode:**
  - `head` — 1 seam max (the visible cut would expose itself on a fullscreen face).
  - `split`, `broll`, `overlay` — N seams allowed (graphic coverage hides the cut).
- **Snap pass.** After semantic segmentation, scene boundaries are snapped to the nearest transcript phrase boundary (silence > ~150 ms between words) within ±300 ms tolerance. Snapping is deterministic and runs as a separate pass between the segmenter and the decorator.

The retired rule "scene runs from one seam to the next regardless of resulting duration" is superseded by this section as of 2026-04-28.
```

- [ ] **Step 3: Verify the file still renders**

Run: `head -80 standards/motion-graphics.md`
Expected: section header `## Scene length and seam mapping` with the new prose; no leftover `## Scene length` header above it.

- [ ] **Step 4: Commit**

```bash
git add standards/motion-graphics.md
git commit -m "standards(motion-graphics): replace scene length rule per Delta 4

Scene length is now ≤5s hard cap, scenes are decoupled from seams,
max_seams_per_scene per mode (head=1, others=N). Supersedes the prior
seam-to-seam rule."
```

---

### Task 2: Update `standards/motion-graphics.md` per P3 (orthogonal axes)

**Files:**
- Modify: `standards/motion-graphics.md` (insert new section near the top, before `## Scenes`).

- [ ] **Step 1: Find the insertion point**

```bash
grep -n "^## Scenes" standards/motion-graphics.md
```

Expected: line number where the `## Scenes` heading starts.

- [ ] **Step 2: Insert the orthogonal-axes section above `## Scenes`**

Insert (above the `## Scenes` heading):

```markdown
## Two orthogonal axes

Every scene is described by two independent decisions:

1. **Scene mode** (head / split / broll / overlay) — *how visible is the host*. Project-specific axis. Constrains what graphics may appear (see catalog table below).
2. **HF transition** (selected via `tools/hyperframes-skills/hyperframes/references/transitions.md`) — *how this scene gives way to the next*. HF's axes apply: energy + mood + narrative position. The project's default primary is set in `DESIGN.md` (calm / crossfade 0.4 s / `power2.inOut`); deviations are justified per-scene.

The axes do not collapse. Choosing `mode = broll` does not imply a particular transition; choosing `transition = blur-crossfade` does not imply a particular mode.

```

- [ ] **Step 3: Verify**

```bash
grep -n "^## " standards/motion-graphics.md | head -10
```

Expected: order of headings is `## Purpose` → `## Two orthogonal axes` → `## Scenes` → `## Core rule` → ...

- [ ] **Step 4: Commit**

```bash
git add standards/motion-graphics.md
git commit -m "standards(motion-graphics): formalise scene_mode vs HF transition as orthogonal axes"
```

---

### Task 3: Update `standards/motion-graphics.md` per P4 (mood inheritance)

**Files:**
- Modify: `standards/motion-graphics.md` (append a section after `## Visual language`, before `## Graphic specs are mandatory`).

- [ ] **Step 1: Find the insertion point**

```bash
grep -n "^## Graphic specs are mandatory" standards/motion-graphics.md
```

Expected: line number for the section heading.

- [ ] **Step 2: Insert the mood inheritance section above it**

Insert (above the `## Graphic specs are mandatory` heading):

```markdown
## Mood inheritance

Project mood is fixed in `DESIGN.md`'s Style Prompt and applies to every scene unless explicitly overridden. The seam-plan's `mood_hint` field is optional; populate it only when a specific scene deliberately departs from project mood (e.g. project is *calm* but a climax scene is *dramatic*). Default mood = project mood.

```

- [ ] **Step 3: Commit**

```bash
git add standards/motion-graphics.md
git commit -m "standards(motion-graphics): codify project-fixed mood with optional per-scene override"
```

---

### Task 4: Append P5 entry to `standards/retro-changelog.md`

**Files:**
- Modify: `standards/retro-changelog.md` (append at end).

- [ ] **Step 1: Verify the file ends with a newline**

```bash
tail -c 1 standards/retro-changelog.md | xxd
```

Expected: `0a` (newline). If not, add one before the new entry.

- [ ] **Step 2: Append the entry**

Append to `standards/retro-changelog.md`:

```markdown
## 2026-04-28 — HF methodology promotions (D6 + Delta 4)
- Source: `episodes/2026-04-28-desktop-software-licensing-it-turns-out/retro.md` deltas 4 + 6.
- HF gates (`lint`, `validate`, `inspect --strict-all`) are required-pass before any preview/final render. Promoted to AGENTS.md hard rule.
- `standards/motion-graphics.md` "Scene length" replaced: scenes are ≤5 s hard cap, decoupled from EDL seams, with `max_seams_per_scene` per mode (head=1, others=N). Retires the prior "scene = seam-to-seam regardless of duration" rule.
- `standards/motion-graphics.md` adds "Two orthogonal axes" section: `scene_mode` and HF transition are independent decisions; both made per scene.
- `standards/motion-graphics.md` adds "Mood inheritance" section: project mood from `DESIGN.md` is the default; per-scene `mood_hint` is an optional override.
- Reason: HF methodology audit (spec `docs/superpowers/specs/2026-04-28-hf-methodology-promotions-design.md`) confirmed our previous "scene = seam" model was inverted vs the HF transition matrix; the retired rule made it impossible to pace visual dynamism on long beats. The orthogonality + mood promotions formalise distinctions that surfaced informally during the 6a-aftermath retro.
```

- [ ] **Step 3: Commit**

```bash
git add standards/retro-changelog.md
git commit -m "standards(retro-changelog): record 2026-04-28 HF methodology promotions"
```

---

### Task 5: Add `--strict-all` to compose-stage HF gates

**Files:**
- Modify: `tools/scripts/run-stage2-compose.sh:66-72`.
- Modify: `tools/scripts/test/test-run-stage2.sh` (extend with regression assertion).

- [ ] **Step 1: Write the failing test for `--strict-all` enforcement**

Open `tools/scripts/test/test-run-stage2.sh`. Find the section after the existing successful compose run (search for `run-stage2-compose.sh 2026-04-27-demo`). Append after the existing assertions, before final cleanup:

```bash
# --- regression: --strict-all must abort on a warning-level issue ---
# Inject a contrast warning by adding low-contrast text to a sub-composition.
# WCAG validate is the easiest gate to fail at warning level.
WARN_INDEX="$EP/stage-2-composite/index.html"
# Find the closing </body> tag and insert a low-contrast text element before it.
python3 - <<PY
path = "$WARN_INDEX"
with open(path, "r", encoding="utf-8") as f:
    html = f.read()
# Insert a barely-visible grey-on-grey element to trigger WCAG contrast warning
inject = '<div style="background-color:#666666;color:#777777;padding:8px;">low-contrast text</div>'
html = html.replace("</body>", inject + "</body>", 1)
with open(path, "w", encoding="utf-8") as f:
    f.write(html)
PY

# Re-run compose; expect non-zero exit when --strict-all is in effect.
if ./tools/scripts/run-stage2-compose.sh 2026-04-27-demo 2>"$WORK/strict.stderr"; then
  echo "FAIL: run-stage2-compose succeeded with a contrast warning; --strict-all not enforced"
  cat "$WORK/strict.stderr"
  exit 1
fi
if ! grep -q -i "warning\|strict\|contrast" "$WORK/strict.stderr"; then
  echo "FAIL: compose aborted but stderr does not mention the contrast warning"
  cat "$WORK/strict.stderr"
  exit 1
fi
echo "PASS: --strict-all aborts compose on contrast warning"
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `bash tools/scripts/test/test-run-stage2.sh`
Expected: FAIL with `--strict-all not enforced` (the wrapper currently succeeds despite the injected warning).

- [ ] **Step 3: Add `--strict-all` to the three HF invocations**

In `tools/scripts/run-stage2-compose.sh`, change lines around `:66-72` from:

```bash
"$HF_BIN" lint "$COMPOSITE_DIR"      || { echo "ERROR: hyperframes lint failed"; exit 1; }
"$HF_BIN" validate "$COMPOSITE_DIR" || { echo "ERROR: hyperframes validate failed"; exit 1; }
"$HF_BIN" inspect "$COMPOSITE_DIR" --json > "$COMPOSITE_DIR/.inspect.json" || {
  echo "ERROR: hyperframes inspect failed; see $COMPOSITE_DIR/.inspect.json"
  echo "       annotate intentional overflow with data-layout-allow-overflow / data-layout-ignore"
  exit 1
}
```

To:

```bash
"$HF_BIN" lint "$COMPOSITE_DIR" --strict-all      || { echo "ERROR: hyperframes lint failed (strict-all)"; exit 1; }
"$HF_BIN" validate "$COMPOSITE_DIR" --strict-all  || { echo "ERROR: hyperframes validate failed (strict-all)"; exit 1; }
"$HF_BIN" inspect "$COMPOSITE_DIR" --strict-all --json > "$COMPOSITE_DIR/.inspect.json" || {
  echo "ERROR: hyperframes inspect failed (strict-all); see $COMPOSITE_DIR/.inspect.json"
  echo "       annotate intentional overflow with data-layout-allow-overflow / data-layout-ignore"
  exit 1
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `bash tools/scripts/test/test-run-stage2.sh`
Expected: `PASS: --strict-all aborts compose on contrast warning` plus all prior PASS lines.

- [ ] **Step 5: Commit**

```bash
git add tools/scripts/run-stage2-compose.sh tools/scripts/test/test-run-stage2.sh
git commit -m "feat(scripts): require --strict-all on HF gates (lint/validate/inspect)

Per docs/superpowers/specs/2026-04-28-hf-methodology-promotions-design.md
P1: HF gates fail on warnings as well as errors before any render
runs. Tests cover the new behaviour by injecting a WCAG contrast
warning and asserting compose aborts."
```

---

### Task 6: Add hard rule to `AGENTS.md` per P1

**Files:**
- Modify: `AGENTS.md` (`## Hard rules` section).

- [ ] **Step 1: Find the hard rules section**

```bash
grep -n "^## Hard rules" AGENTS.md
```

Expected: line number of the heading.

- [ ] **Step 2: Add the new bullet at the end of the section**

Locate the `## Hard rules` block and append, just before the next `## ` heading (probably `## Communication`):

```markdown
- **No preview or final render runs without `lint` + `validate` + `inspect --strict-all` all green.** The compose wrapper enforces this; do not bypass with `--allow-warnings` or by editing the wrapper unless you have a written justification in the run log and explicit user approval. See `tools/scripts/run-stage2-compose.sh`.
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): require HF gates --strict-all before any render"
```

---

### Task 7: Create `docs/operations/render-environment.md`

**Files:**
- Create: `docs/operations/render-environment.md`.

**Why:** Spec P1 second-half — `npx hyperframes doctor` should run as a one-shot pre-flight on fresh dev environments. Captured in a doc, not gated per-render.

- [ ] **Step 1: Create the doc**

```markdown
# Render Environment Pre-flight

This pre-flight runs once per dev environment (fresh checkout, new machine, after a Node / FFmpeg / Chrome upgrade). It is *not* required per-render — `tools/scripts/lib/preflight.sh` runs `hyperframes doctor` before every compose / preview / final.

## When to run

- First clone of the repo on a new machine.
- After upgrading Node, FFmpeg, or system Chrome.
- After a `tools/compositor/` `npm install` that bumped `hyperframes`.
- When investigating a render failure (capture full doctor output for the investigation; see `docs/operations/render-oom/findings.md` for an example).

## How to run

```bash
"$(pwd)/tools/compositor/node_modules/.bin/hyperframes" doctor 2>&1 \
  | tee docs/operations/render-environment.<host>.txt
```

Replace `<host>` with a short hostname. The output is human-readable; scan for:
- `✗` markers — critical (Node / FFmpeg / FFprobe / Chrome / Docker missing). `lib/preflight.sh` catches these on every render; capturing them here as a one-shot is for debugging.
- Warnings about memory / GPU / hardware acceleration — *not* gated by `lib/preflight.sh`; surface them here for manual triage.
- HF version + Chrome channel + Node version recorded for later cross-reference.

## What the per-render preflight already checks

`tools/scripts/lib/preflight.sh:hf_preflight()` (sourced by every render wrapper) gates on:
- Node, FFmpeg, FFprobe, Chrome present (always fatal).
- Docker present + running (fatal only when `HF_RENDER_MODE != local`).

It does *not* gate on:
- Memory warnings.
- GPU / NVENC / hardware acceleration availability.
- HF version skew.

If you need any of those gated, propose the change in `lib/preflight.sh` with a regression test in `tools/scripts/test/`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/operations/render-environment.md
git commit -m "docs(operations): one-shot render-environment doctor pre-flight"
```

---

## Self-review

**Spec coverage:**
- P1 (HF gates --strict-all required + AGENTS.md hard rule + doctor one-shot doc) → Tasks 5 + 6 + 7 ✓
- P2 (motion-graphics scene length / scene ≠ seam / max_seams) → Task 1 ✓
- P3 (orthogonal axes section) → Task 2 ✓
- P4 (mood inheritance section) → Task 3 ✓
- P5 (retro-changelog entry) → Task 4 ✓

**Placeholders:** all replacement / insert text is concrete; no `<TBD>` or `<fill in>` in the standards / AGENTS / changelog edits.

**Type/name consistency:** new `mood_hint` field name matches the Topic 2 spec's seam-plan schema and the future Topic 2 plan. `scene_mode` casing matches existing `standards/motion-graphics.md`. `--strict-all` flag spelling matches `tools/hyperframes-skills/hyperframes-cli/SKILL.md` exactly.
