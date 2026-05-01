# Retro 2026-05-01 Action Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land six retro findings as four parallel PRs, one investigation, and one conditional follow-up PR — with memory predating the work as behavioral foundation.

**Architecture:** Memory batch first (local, no PR). Then four independent PRs against `main` (PR-3, PR-2, PR-1, PR-4) in dependency-aware order. Phase 0 investigation runs in a separate worktree. PR-5 is scoped post-investigation. Held memory writes follow Phase 0.

**Tech Stack:** Markdown (briefs, memory, CLAUDE.md), Python (hook script + tests, follows existing pytest convention in `tests/`), JSON (`.claude/settings.json` for hook registration), Bash + gh CLI for PR workflow.

**Source spec:** `docs/superpowers/specs/2026-05-01-retro-action-items-design.md` (PR #18).

---

## Pre-flight (run before Step 1)

- [ ] **Verify on `planning/retro-action-items-design` branch is OK to leave for now.** PR #18 is open and pending review/merge. We can do Step 1 (memory writes — no git involvement) from any branch. For Steps 2+ we go to main.

```bash
git status
git branch --show-current
# Expected: planning/retro-action-items-design, clean working tree (the retro file should still be untracked).
```

- [ ] **Confirm memory dir exists.**

```bash
ls "C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/"
# Expected: existing feedback_*.md files + MEMORY.md
```

---

## Step 1: Memory batch (4 entries, immediate write)

**Files:**
- Create: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_brief_consider_means_mandatory.md`
- Create: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_studio_player_empty_state.md`
- Create: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_text_box_overflow_glyph_bearing.md`
- Create: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_wcag_headless_opacity_artifact.md`
- Modify: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/MEMORY.md` (append 4 index lines)

No PR — memory is local user state.

- [ ] **Step 1.1: Write `feedback_brief_consider_means_mandatory.md`**

```markdown
---
name: Brief 'Consider' / 'SHOULD' / 'recommended' = mandatory
description: In .claude/commands/edit-episode.md, soft modals are sugar for mandatory orchestrator-house mechanics, not optional optimization
type: feedback
---

In `.claude/commands/edit-episode.md` (Phase 4 brief especially), the words `Consider`, `SHOULD`, and `recommended` are shorthand for mandatory orchestrator-house behavior — not optional optimization. The brief uses them to soften imperative voice while keeping the rule load-bearing. Treat `Consider X` as `Do X unless X is technically impossible`. Applies retroactively to: parallel-agent dispatch, sub-composition split (until Phase 0 confirms approach), snapshot-before-studio.

**Why:** Verified 2026-05-01 — skipped parallel-agent dispatch under "Consider dispatching beat authoring" wording → Phase 4 took ~80 min sequential vs ~30-40 min parallel, and an upstream-suspect bug went undetected for 60 min instead of 10 min. This is a recurring behavioural drift documented across multiple retros (Section 7 §2.2 captions, §2.4 inline shortcut, 2026-05-01 §2.6 parallel dispatch). Discipline alone does not scale; the brief wording must be the fix.

**How to apply:** When reading the brief, parse soft modals as imperatives. When editing the brief, prefer imperative verbs and `(optional, skip without consequence)` tags over soft modals. After PR-2 (`phase4/soft-language-audit`) lands, the brief preamble will codify this convention; until then this memory is the load-bearing safeguard.
```

- [ ] **Step 1.2: Write `feedback_studio_player_empty_state.md`**

```markdown
---
name: HF studio player 'Drop media here' = default UI, not render fail
description: HF studio shows empty-state until a composition is selected in sidebar; verify renders via snapshot, not by studio appearance
type: feedback
---

HF studio (`npx hyperframes preview`) shows the "Drop media here" empty-state hint until a composition is explicitly selected in the sidebar. This is **default UI behavior, not a render failure**. A blank player tells you nothing about whether the composition is broken.

**Why:** Verified 2026-05-01 — interpreted blank studio player as render fail and spent ~25 min hunting non-existent bugs (track-index reshuffles, malformed div, file rename, server restart) before realizing the actual problem was a different bug (sub-comp loader §2.1) and the studio was simply showing its empty-state because no composition was selected.

**How to apply:** **Verify renders via `npx hyperframes snapshot --at <beat_timestamps>` BEFORE assuming studio is broken.** Snapshot is definitive (deterministic offline screenshot at named timestamps); studio is ambiguous (interactive UI with empty-state hint). If snapshot shows expected overlays at expected timestamps and studio shows blank — the studio is fine, the user just needs to click `index` in the sidebar. If snapshot ALSO shows missing elements — the composition is broken, fix it.
```

- [ ] **Step 1.3: Write `feedback_text_box_overflow_glyph_bearing.md`**

```markdown
---
name: text_box_overflow 2-3px on heavy display fonts = glyph bearing, use canon escape
description: Heavy display fonts (Manrope 800 at 60+ px) produce 2-3 px positive overflow from negative side bearing; mark wrapper with data-layout-allow-overflow
type: feedback
---

Heavy display fonts (e.g. Manrope 800 at 60+ px) produce 2-3 px `text_box_overflow` reports from `npx hyperframes inspect`. Root cause is **negative left side-bearing on the first glyph** — the glyph metric extends past the layout box by a few pixels. This is a font property, not a layout bug. The canonical hatch `data-layout-allow-overflow` (HF SKILL.md §"Visual Inspect") applies — same hatch, extended scenario.

**Why:** Verified 2026-05-01 — wasted ~10 min iterating on font-size and card-width when overflow was 2-3 px and stable. Canon's `data-layout-allow-overflow` is documented as escape for "intentional entrance/exit animation overflow"; extending it to glyph-bearing overflow is consistent reading of the hatch (the inspect tool reports both with the same shape, the hatch suppresses both).

**How to apply:** When `inspect` reports `text_box_overflow` with magnitude ≤ 5 px on heavy display fonts (weights ≥ 700, sizes ≥ 60 px), **immediately mark the wrapper with `data-layout-allow-overflow`**. Do NOT iterate font-size, letter-spacing, or container width. Phrase the rationale in any DESIGN.md note as "glyph bearing, canon hatch extended" — preserves traceability. Heavier overflow (> 5 px) probably is a real layout issue; investigate normally.
```

- [ ] **Step 1.4: Write `feedback_wcag_headless_opacity_artifact.md`**

```markdown
---
name: WCAG fg=rgb(0,0,0) on opacity:0 entrance = headless artifact
description: WCAG validator reports fg rgb(0,0,0) for elements that use opacity:0 in entrance fromTo; this is a static-screenshot artifact, not a real contrast fail
type: feedback
---

`npx hyperframes validate`'s WCAG audit takes 5 timestamp screenshots and samples background pixels behind each text element. Elements using `gsap.fromTo(..., { opacity: 0, ... }, ...)` for entrance render with `opacity: 0` at static screenshot timestamps (GSAP `immediateRender: true` is default). The validator then samples a transparent text region → `fg: rgb(0,0,0)` → contrast ~1.1:1. **This is a headless-render artifact, not a real fail.** In the played composition the timeline runs and the text is visible.

**Why:** Verified 2026-05-01 — chased 68 contrast warnings through the canonical fix ladder (palette family iteration per HF SKILL.md §"Contrast"). All three iterations failed because the symptom was an artifact, not a real contrast issue. ~10 min wasted before recognizing the pattern.

**How to apply:** **Triage step BEFORE applying canon's palette iteration.** If ALL these conditions hold:
- All warnings have `fg: rgb(0,0,0)`
- Elements set a visible color in CSS (e.g., `color: #E6F1FF`)
- Elements use `opacity: 0` in entrance `tl.fromTo()` or `gsap.fromTo()`

Then it is the headless artifact. Document in DESIGN.md → "WCAG Validator — Headless Artifact" with one-line rationale and proceed. Do NOT iterate palette — it cannot fix what is not broken. Otherwise (mixed warnings, real `fg` values, no opacity-0 entrance), apply canon's palette iteration normally.

**Where this is canon-clean:** Triage layered BEFORE canon (HF SKILL.md §"Contrast") fix ladder, not replacing it. Canon stays load-bearing for real contrast fails.
```

- [ ] **Step 1.5: Update `MEMORY.md` index — append 4 lines, preserve existing entries**

Read current `MEMORY.md` to know existing index, then append 4 new lines at the end. Final content of new lines:

```
- [Brief 'Consider' = mandatory](feedback_brief_consider_means_mandatory.md) — soft modals in edit-episode.md are sugar for orchestrator-house imperatives; treat as Do X unless impossible
- [HF studio empty-state](feedback_studio_player_empty_state.md) — 'Drop media here' = default UI until composition selected, NOT render fail; verify via snapshot
- [text_box_overflow on heavy display fonts](feedback_text_box_overflow_glyph_bearing.md) — 2-3 px overflow from glyph bearing; mark data-layout-allow-overflow immediately, don't iterate font-size
- [WCAG headless artifact](feedback_wcag_headless_opacity_artifact.md) — fg rgb(0,0,0) on opacity:0 entrance fromTo = static screenshot artifact; triage BEFORE canon palette iteration
```

- [ ] **Step 1.6: Verify all 4 files exist and MEMORY.md grew by 4 lines**

```bash
ls "C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/" | grep -E "consider_means|studio_player|glyph_bearing|headless_opacity"
# Expected: 4 lines, the 4 new files

wc -l "C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/MEMORY.md"
# Expected: previous count + 4
```

No commit — local memory.

---

## Step 2: Retro commit PR (`docs/retro-2026-05-01-liquid-glass`)

The retro file is currently untracked on main worktree. Land it via small PR so PR #18's reference resolves.

**Files:**
- Add to git: `docs/retros/retro-2026-05-01-liquid-glass-subcomp-loader.md`

- [ ] **Step 2.1: Switch to main and pull**

```bash
git checkout main
git pull origin main
```

- [ ] **Step 2.2: Create worktree from main**

```bash
git worktree add .worktrees/docs-retro-2026-05-01 -b docs/retro-2026-05-01-liquid-glass origin/main
cd .worktrees/docs-retro-2026-05-01
```

The retro file lives in the main working tree (untracked). Copy it to the new worktree.

```bash
cp ../../docs/retros/retro-2026-05-01-liquid-glass-subcomp-loader.md docs/retros/
git add docs/retros/retro-2026-05-01-liquid-glass-subcomp-loader.md
git status
# Expected: new file: docs/retros/retro-2026-05-01-liquid-glass-subcomp-loader.md
```

- [ ] **Step 2.3: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs(retro): 2026-05-01 liquid glass subcomp loader retro

Documents Phase 4 of the Liquid Glass episode: sub-composition
loader emitting A-roll-only render, WCAG headless artifact, blank
studio preview, lint regex false positive on comments, glyph
bearing overflow, and selective compliance with parallel-dispatch
brief instruction. Input artifact for retro action-items design
spec (PR #18).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2.4: Push and open PR**

```bash
git push -u origin docs/retro-2026-05-01-liquid-glass
gh pr create --base main --title "docs(retro): 2026-05-01 liquid glass subcomp loader" --body "$(cat <<'EOF'
## Summary
- Lands the 2026-05-01 retro file as input artifact for the action-items design spec (PR #18).
- No code changes; pure documentation.

## Test plan
- [ ] Markdown renders correctly on GitHub.
- [ ] Spec PR #18 reference to this file resolves on main after merge.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2.5: Merge and cleanup**

```bash
gh pr merge --squash --delete-branch
cd ../..
git worktree remove .worktrees/docs-retro-2026-05-01
git branch -d docs/retro-2026-05-01-liquid-glass 2>/dev/null || true
git checkout main
git pull origin main
```

---

## Step 3: PR-3 `meta/bare-repro-rule` (CLAUDE.md, single paragraph)

**Files:**
- Modify: `CLAUDE.md` — add new section "Investigation methodology" (or append to "External skill canon" block)

- [ ] **Step 3.1: Worktree create**

```bash
git worktree add .worktrees/meta-bare-repro-rule -b meta/bare-repro-rule origin/main
cd .worktrees/meta-bare-repro-rule
```

- [ ] **Step 3.2: Read current CLAUDE.md to find insertion point**

The "External skill canon — non-negotiable" section starts around line ~50 of CLAUDE.md. The new paragraph belongs RIGHT AFTER that section's bulleted list (after the rule about `~/.agents/skills/...` paths) but BEFORE the "Skill copies: docs vs. runnable" sub-section.

```bash
grep -n "Investigation\|bare-repro\|External skill canon\|docs vs. runnable" CLAUDE.md
```

- [ ] **Step 3.3: Apply edit**

Insert the following block in `CLAUDE.md` immediately after the line ending the "External skill canon — non-negotiable" intro paragraph (`...all glue lives in this orchestrator (scripts/, .claude/commands/edit-episode.md).`) and before the `### Skill copies: docs vs. runnable` subheading:

```markdown
### Investigation methodology — bare-repro before upstream-blame

Before claiming any HF or `video-use` behavior is an upstream bug or doc-bug, reproduce in a bare scaffold (`npx hyperframes init` for HF; clean install for `video-use`). If bare-repro succeeds while our pipeline fails — the bug is orchestrator-side. Investigate `scripts/scaffold_*.py`, glue scripts, and brief deltas before opening an upstream issue.

Verified necessary 2026-05-01: three suspected upstream bugs from retro 2026-05-01 (`data-composition-src` sub-comp loader, `gsap_infinite_repeat` lint regex on comments, `<template>` doc-bug) all required investigation before claim. Premature canonization of an "upstream bug" produces wrong memory entries, wrong brief workarounds, and stale GitHub issues — all of which corrupt future sessions.

```

- [ ] **Step 3.4: Verify edit landed cleanly**

```bash
grep -n "bare-repro before upstream-blame" CLAUDE.md
# Expected: one line, in the External skill canon area
```

- [ ] **Step 3.5: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
meta(claudemd): bare-repro before upstream-blame

Generalizes the Phase 0 investigation methodology from retro
2026-05-01 into a permanent rule. Three suspected upstream bugs
in that retro (sub-comp loader, lint regex, template doc-bug) all
required bare-scaffold reproduction before claim. Codifying the
rule prevents premature canonization in future retros.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3.6: Push, PR, merge, cleanup**

```bash
git push -u origin meta/bare-repro-rule
gh pr create --base main --title "meta(claudemd): bare-repro before upstream-blame" --body "$(cat <<'EOF'
## Summary
- Adds new section to CLAUDE.md: investigation methodology requiring bare-scaffold reproduction before claiming HF or video-use upstream bugs.
- Codifies the Phase 0 methodology from retro 2026-05-01 design spec (PR #18) as a permanent rule, so future retros don't have to re-derive it.

## Test plan
- [ ] CLAUDE.md still renders correctly.
- [ ] Section lands between "External skill canon" intro and "Skill copies: docs vs. runnable" subheading.
- [ ] Phase 0 investigation (separate workstream) cites this rule.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --squash --delete-branch
cd ../..
git worktree remove .worktrees/meta-bare-repro-rule
git branch -d meta/bare-repro-rule 2>/dev/null || true
git checkout main
git pull origin main
```

---

## Step 4: PR-2 `phase4/soft-language-audit` (sweeping)

**Files:**
- Modify: `.claude/commands/edit-episode.md` — preamble + per-modal flips + Output Checklist verifiers

This PR has a **user-approval gate** between disposition and apply. Do not skip it.

- [ ] **Step 4.1: Worktree create**

```bash
git worktree add .worktrees/phase4-soft-language-audit -b phase4/soft-language-audit origin/main
cd .worktrees/phase4-soft-language-audit
```

- [ ] **Step 4.2: Mechanical grep — enumerate all soft modals**

```bash
grep -n -i -E '\b(consider|should|recommend(ed)?|strongly?|may|might|encourage)\b' .claude/commands/edit-episode.md > /tmp/soft-modals-raw.txt
cat /tmp/soft-modals-raw.txt
```

Expected: 8-15 lines with line:column hits. Each will become one row in the disposition table.

- [ ] **Step 4.3: Build disposition table**

For each grep hit, classify into exactly one of:
- `imperative` — flip body to imperative verb; if the rule is checkable, add an Output Checklist verifier.
- `explicit-optional` — tag the rule with `(optional, skip without consequence)`.
- `leave-as-is` — modal is non-modal English (e.g., "may diverge from the script" — describing a fact, not a directive).

Produce a markdown table at `/tmp/soft-modals-disposition.md`:

```markdown
| Line | Original snippet | Disposition | Replacement |
|------|------------------|-------------|-------------|
| 89   | "may pause for further confirmation" | leave-as-is | (no change — describes a possibility, not a directive) |
| 184  | "Consider dispatching beat authoring..." | imperative | "Dispatch one sub-agent per beat..." + Output Checklist verifier |
| ... | ... | ... | ... |
```

- [ ] **Step 4.4: GATE — present disposition table to user, get approval**

Show user the full disposition table. **Do NOT proceed to Step 4.5 without explicit user approval.** Record approval in commit message later.

If user requests changes, update the table and re-present.

- [ ] **Step 4.5: Add preamble convention to top of brief**

Insert this block at the start of `.claude/commands/edit-episode.md` content (after the YAML frontmatter, before the existing intro paragraph):

```markdown
## Conventions

Every directive in this brief is mandatory unless tagged `(optional, skip without consequence)`. Treat soft modals (`Consider`, `SHOULD`, `recommended`, `may`, `might`) as bugs to report — file an issue or open a PR rather than interpreting them as optional. The brief uses imperative voice deliberately; orchestrator-house mechanics are load-bearing even when phrased softly.

This convention applies retroactively to all rules — including Output Checklist items, Visual Identity Gate steps, and Visual Verification gates.

---
```

- [ ] **Step 4.6: Apply per-modal flips per disposition table**

For each `imperative` row in the table:
1. Find the line in the brief.
2. Replace the soft-modal phrase with imperative voice.
3. If the rule is checkable, add a corresponding line to the Phase 4 Output Checklist (around line 197-204).

For each `explicit-optional` row:
1. Append `(optional, skip without consequence)` to the rule.

`leave-as-is` rows: no edit.

- [ ] **Step 4.7: Apply the parallel-dispatch flip specifically (the highest-leverage instance, §2.6)**

Replace the existing block (around lines 183-185):

```markdown
> **Parallel-agent dispatch — orchestrator pattern.** Beats are independent and parallelizable. Consider dispatching beat authoring to parallel sub-agents via the `superpowers:dispatching-parallel-agents` skill (this is an orchestrator pattern via superpowers, NOT HF canon).
```

with:

```markdown
> **Beat authoring — parallel-agent dispatch (mandatory for ≥ 3 beats).** After DESIGN.md and `.hyperframes/expanded-prompt.md` exist, dispatch one sub-agent per beat via the `superpowers:dispatching-parallel-agents` skill. Each agent gets the beat's section from `expanded-prompt.md` and writes its `compositions/beat-{N}-{slug}.html` independently. Main session waits, then assembles the root `index.html`. Do not write beats sequentially in the main session — that path forfeits independently-testable artifacts and adds 2-5× wall-time.
>
> Canonical mirror: video-use SKILL.md Hard Rule 10 ("Parallel sub-agents for multiple animations. Never sequential."). HF Phase 4 beat authoring inherits the same rule applied to a different unit (beats instead of animations).
```

And add to the Phase 4 Output Checklist (after the existing items 1-5):

```markdown
> 6. Beats authored by ≥ 3 parallel sub-agents — verifiable by checking session transcript for parallel `Agent` tool calls during Phase 4. If zero parallel dispatches occurred for a composition with ≥ 3 beats listed in `DESIGN.md` → `Beat→Visual Mapping`, Phase 4 is incomplete.
```

- [ ] **Step 4.8: Re-grep verify**

```bash
grep -n -i -E '\b(consider|should|recommend(ed)?|strongly?|may|might|encourage)\b' .claude/commands/edit-episode.md
```

Every remaining hit must be one of: tagged `(optional, skip without consequence)`, in a leave-as-is row from the disposition table, or in the new preamble itself (which intentionally names the modals). No surprises.

- [ ] **Step 4.9: Manual review pass**

Read the full brief end-to-end once. Look for:
- Newly-introduced contradictions (e.g., a flipped imperative that clashes with a neighboring rule).
- Loss of nuance (a `leave-as-is` flipped accidentally).
- Verifier items in Output Checklist that reference data not actually produced (e.g., asking to verify a transcript entry that won't exist for skip-build runs).

Fix any issues inline.

- [ ] **Step 4.10: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "$(cat <<'EOF'
brief(phase4): soft-language audit + parallel-dispatch imperative

Adds a Conventions preamble declaring that every directive is
mandatory unless tagged (optional, skip without consequence) —
soft modals like Consider/SHOULD/recommended are bugs to report.
Mechanically audits the existing brief and flips, tags, or
leaves-as-is each soft modal per a user-approved disposition table.

The highest-leverage flip: parallel-agent dispatch for beat
authoring becomes mandatory for >=3 beats, with a corresponding
Output Checklist verifier (zero parallel Agent calls in transcript
for a >=3 beat composition = Phase 4 incomplete). Mirrors video-use
SKILL.md Hard Rule 10 ("Parallel sub-agents for multiple
animations. Never sequential.") applied to beats instead of
animations.

Closes retro 2026-05-01 §2.6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4.11: Push, PR, merge, cleanup**

```bash
git push -u origin phase4/soft-language-audit
gh pr create --base main --title "brief(phase4): soft-language audit + parallel-dispatch imperative" --body "$(cat <<'EOF'
## Summary
- Adds a Conventions preamble: every directive is mandatory unless tagged (optional, skip without consequence). Soft modals are bugs to report.
- Mechanical audit of all `consider|should|recommended|strongly|may|might|encourage` hits in the brief; each row classified as imperative / explicit-optional / leave-as-is per a user-approved disposition table.
- §2.6 parallel-dispatch becomes mandatory for ≥ 3 beats, with Output Checklist verifier. Mirrors video-use SKILL.md Hard Rule 10.

## Canon respect
Pure orchestrator-house brief polish. Does not edit canon. Adds verifier item to orchestrator-house Output Checklist (already extends canon checklist, justified inline).

## Test plan
- [ ] Re-grep shows zero unaudited soft modals.
- [ ] Brief reads coherently end-to-end (no contradictions introduced).
- [ ] Parallel-dispatch verifier is checkable from session transcript (manual confirmation).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --squash --delete-branch
cd ../..
git worktree remove .worktrees/phase4-soft-language-audit
git branch -d phase4/soft-language-audit 2>/dev/null || true
git checkout main
git pull origin main
```

---

## Step 5: PR-1 `phase4/diagnostics-and-triage` (three brief additions)

**Files:**
- Modify: `.claude/commands/edit-episode.md` — three additions in Phase 4 brief

PR-1 lands AFTER PR-2 so it inherits the Conventions preamble. Each addition uses imperative voice from the start.

- [ ] **Step 5.1: Worktree create**

```bash
git worktree add .worktrees/phase4-diagnostics-and-triage -b phase4/diagnostics-and-triage origin/main
cd .worktrees/phase4-diagnostics-and-triage
```

- [ ] **Step 5.2: Add WCAG headless-artifact triage step**

Insert IMMEDIATELY BEFORE the existing `> **WCAG fail handling.**` block (around line 178), so it triages first:

```markdown
> **WCAG triage step (apply BEFORE canon's palette iteration).** If `npx hyperframes validate` reports contrast warnings, first check this triage:
>
> If ALL warnings have `fg: rgb(0,0,0)` AND elements set a visible color in CSS AND elements use `opacity: 0` in entrance `tl.fromTo()` / `gsap.fromTo()` — this is the headless-screenshot artifact (validator samples 5 static timestamps; GSAP `immediateRender: true` makes entrance-state opacity-0 elements transparent at sample time). Document in `DESIGN.md` → "WCAG Validator — Headless Artifact" with one-line rationale and proceed. Do NOT iterate palette — palette iteration cannot fix what is not broken.
>
> Otherwise (mixed warnings, real `fg` values, no opacity-0 entrance), apply canon's palette-family iteration per the next block.
```

The existing canon-iteration block (`> **WCAG fail handling.** WCAG fails are resolved by adjusting hue...`) stays unchanged immediately after.

- [ ] **Step 5.3: Add snapshot interpretation rule**

Find the existing Visual Verification block (around lines 207-214). After step 2 (`Canonical screenshots at beat boundaries`), add a new clarification step:

```markdown
> 2.5. **Interpret snapshots against Beat→Visual Mapping, not absolute presence.** An empty snapshot at a timestamp where `DESIGN.md` → `Beat→Visual Mapping` declares a visible element = composition is broken; do NOT proceed to studio launch. An empty snapshot in the first 0.3s of a beat-start is canonical entrance offset (HF SKILL.md §"Animation Guardrails" — first animation offset 0.1-0.3s) — not a bug. Snapshot is definitive only when checked against the expected-visible list, not in absolute terms.
```

- [ ] **Step 5.4: Add diagnostic entry-point section**

Insert as a NEW block AT THE END of the Phase 4 brief, immediately AFTER the `Post-launch StaticGuard check.` block (around line 222) and BEFORE the line `Only if the 5-second window is clean, report http://localhost:3002 to the user.` Actually, place it as its own subsection BEFORE `Studio launch:` (around line 218):

```markdown
> **Diagnostic entry-point — when Phase 4 output is unexpectedly empty or broken.** Before forming any hypothesis, run in this order:
> 1. `cd <EPISODE_DIR>/hyperframes && npx hyperframes compositions` — verify each sub-composition listed via `data-composition-src` reports non-zero `elements` and matching `duration`. If any sub-comp shows `0 elements / 0.0s`, mounting failed — do NOT debug content, styles, or track-index. Investigate the mount path (file present? path correct? `<template>` wrapper structure per SKILL.md:165-183?).
> 2. `npx hyperframes snapshot --at <beat_timestamps>` (timestamps from `DESIGN.md` → `Beat→Visual Mapping`) — verify expected-visible elements per the snapshot interpretation rule above.
> 3. ONLY after (1) and (2) report definite results, form hypotheses about specific elements (z-overlap, malformed CSS, GSAP timing).
>
> Anti-pattern (verified retro 2026-05-01 §2.3, ~40 min wasted): gradient-descend through symptoms — track-index reshuffles, file rename, server restart, malformed div hunt — before running (1) and (2). The structural diagnostic ordering catches sub-comp mounting bugs in 30 seconds; symptom-chase takes 40 minutes and reaches the same conclusion.
```

- [ ] **Step 5.5: Verify additions are placed correctly**

```bash
grep -n "WCAG triage step\|Interpret snapshots against\|Diagnostic entry-point" .claude/commands/edit-episode.md
# Expected: 3 lines, in Phase 4 brief, in the order WCAG-triage / snapshot-interpret / diagnostic-entry
```

Read the surrounding context for each match (5 lines before/after) to confirm no broken block boundaries.

- [ ] **Step 5.6: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "$(cat <<'EOF'
brief(phase4): diagnostics and triage additions

Adds three structural defenses to the Phase 4 brief, all
phrased as triage / qualifier / diagnostic-ordering layered
BEFORE canon — never replacing it:

1. WCAG headless-artifact triage step before canon's palette
   iteration (catches GSAP opacity-0 entrance artifact in seconds
   instead of 10 min of palette iteration).

2. Snapshot interpretation rule tied to DESIGN.md
   Beat→Visual Mapping (canonical fade-in offset is not a bug;
   empty-vs-expected is the real signal).

3. Diagnostic entry-point: when Phase 4 output is empty/broken,
   run npx hyperframes compositions and snapshot FIRST, before
   hypothesis-formation. Catches sub-comp mounting bugs in 30s
   instead of 40 min of symptom-chase.

Closes retro 2026-05-01 §2.2, §2.3 partial (studio empty-state
covered by memory entry, not brief), and the meta finding on
overwhelm.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5.7: Push, PR, merge, cleanup**

```bash
git push -u origin phase4/diagnostics-and-triage
gh pr create --base main --title "brief(phase4): diagnostics and triage additions" --body "$(cat <<'EOF'
## Summary
- WCAG triage step BEFORE canon palette iteration (catches headless artifact in seconds).
- Snapshot interpretation tied to DESIGN.md → Beat→Visual Mapping (canonical entrance offset is not a bug).
- Diagnostic entry-point: `npx hyperframes compositions` + snapshot run FIRST when output is broken.

## Canon respect
All three additions are triage / qualifier / ordering — layered BEFORE canon, never replacing. Verified against `~/.agents/skills/hyperframes/SKILL.md` §"Contrast", §"Visual Inspect", §"Animation Guardrails" (first animation 0.1-0.3s offset).

## Test plan
- [ ] Three additions land at correct insertion points.
- [ ] Brief reads coherently with PR-2's Conventions preamble.
- [ ] Diagnostic entry-point block is reachable from a "Phase 4 output is broken" entry by Find-on-page.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --squash --delete-branch
cd ../..
git worktree remove .worktrees/phase4-diagnostics-and-triage
git branch -d phase4/diagnostics-and-triage 2>/dev/null || true
git checkout main
git pull origin main
```

---

## Step 6: PR-4 `hooks/parallel-dispatch-detector` (machine-enforced warning)

**Files:**
- Create: `scripts/check_parallel_dispatch.py` — hook script.
- Create: `.claude/settings.json` — register the hook.
- Create: `tests/test_check_parallel_dispatch.py` — pytest with fixtures.
- Create: `tests/fixtures/transcripts/sequential.jsonl` — fixture (sequential authoring).
- Create: `tests/fixtures/transcripts/parallel.jsonl` — fixture (3 parallel Agent dispatches).
- Create: `tests/fixtures/transcripts/skip_build.jsonl` — fixture (Phase 4 skip-build).

This step has a **research substep** because Claude Code hook event semantics and `$CLAUDE_TRANSCRIPT_PATH`-equivalent env vars must be confirmed before script implementation.

- [ ] **Step 6.1: Worktree create**

```bash
git worktree add .worktrees/hooks-parallel-dispatch-detector -b hooks/parallel-dispatch-detector origin/main
cd .worktrees/hooks-parallel-dispatch-detector
```

- [ ] **Step 6.2: Research — confirm Claude Code hook event types and transcript path access**

Use the `claude-code-guide` agent (it's a sub-agent specialized for CC questions). Prompt:

> Confirm: (1) which CC hook event fires at session end? (2) what env var or argument gives the hook script access to the current session's transcript path? (3) what is the JSONL schema for tool_use entries — specifically the `Agent` tool — in transcripts? (4) can a hook write to stderr and have that text shown to the user, or does it need to be a `user-prompt-submit-hook` style? Report under 200 words.

Record the agent's findings inline in the plan AS A COMMENT in `scripts/check_parallel_dispatch.py` so future readers know what was confirmed.

- [ ] **Step 6.3: Write fixtures FIRST (TDD: tests with fixtures, then script)**

Create `tests/fixtures/transcripts/parallel.jsonl` — minimal but realistic JSONL with:
- One scaffold tool_use creating `episodes/test-slug/hyperframes/index.html` skeleton.
- Three parallel `Agent` tool_use entries with descriptions matching beat authoring (e.g. `"Author beat-1-hook composition"`).
- One file_create tool_use for the final `index.html`.

Use real CC transcript JSONL shape (key fields: `type`, `role`, `tool_use_id`, `name`, `input`, `timestamp`). Look at one existing transcript at `C:/Users/sidor/.claude/projects/.../<session-id>.jsonl` for shape, redact identifiers.

```jsonl
{"type":"tool_use","name":"Bash","input":{"command":"python -m scripts.scaffold_hyperframes ..."},"timestamp":"2026-05-01T10:00:00Z"}
{"type":"tool_use","name":"Agent","input":{"description":"Author beat-1-hook composition","subagent_type":"general-purpose"},"timestamp":"2026-05-01T10:05:00Z"}
{"type":"tool_use","name":"Agent","input":{"description":"Author beat-2-online composition","subagent_type":"general-purpose"},"timestamp":"2026-05-01T10:05:01Z"}
{"type":"tool_use","name":"Agent","input":{"description":"Author beat-3-offline composition","subagent_type":"general-purpose"},"timestamp":"2026-05-01T10:05:02Z"}
{"type":"tool_use","name":"Write","input":{"file_path":"episodes/test-slug/hyperframes/index.html","content":"<html>...</html>"},"timestamp":"2026-05-01T10:15:00Z"}
```

Create `tests/fixtures/transcripts/sequential.jsonl` — same scaffold + index.html create, but ZERO `Agent` tool_use entries between them (only `Write` calls for each beat HTML in main session).

Create `tests/fixtures/transcripts/skip_build.jsonl` — skip-build path: Phase 4 brief recognizes existing `index.html` and only launches studio. No new `index.html` Write.

Create accompanying minimal `DESIGN.md` content embedded in the test fixtures (some test fixtures may need a paired DESIGN.md indicating ≥ 3 beats; keep these alongside the JSONL or inline as multi-line strings in the test file).

- [ ] **Step 6.4: Write tests for `check_parallel_dispatch.py`**

`tests/test_check_parallel_dispatch.py`:

```python
"""Tests for the parallel-dispatch-detector hook script."""
from pathlib import Path
import json
import subprocess
import sys

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"
SCRIPT = Path(__file__).parent.parent / "scripts" / "check_parallel_dispatch.py"


def _run(transcript_path: Path) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--transcript", str(transcript_path)],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_parallel_dispatch_does_not_trigger_warning():
    """3+ parallel Agent dispatches detected — silence."""
    rc, out, err = _run(FIXTURES / "parallel.jsonl")
    assert rc == 0
    assert "warning" not in err.lower()
    assert "no parallel" not in err.lower()


def test_sequential_authoring_triggers_warning():
    """No Agent dispatches between scaffold and index.html with >=3 beats — warn."""
    rc, out, err = _run(FIXTURES / "sequential.jsonl")
    assert rc == 0  # non-blocking
    assert "parallel" in err.lower()
    assert "phase 4" in err.lower() or "beat" in err.lower()


def test_skip_build_does_not_trigger_warning():
    """No new index.html in this session — no warn."""
    rc, out, err = _run(FIXTURES / "skip_build.jsonl")
    assert rc == 0
    assert err.strip() == ""


def test_missing_transcript_silent_exit():
    """Hook script must not crash if transcript path is missing or malformed."""
    rc, out, err = _run(Path("/nonexistent/transcript.jsonl"))
    assert rc == 0  # never block the user
    # err may have a debug line but no Python traceback
    assert "Traceback" not in err
```

- [ ] **Step 6.5: Run tests, expect all to fail (script doesn't exist yet)**

```bash
python -m pytest tests/test_check_parallel_dispatch.py -v
# Expected: 4 failures (FileNotFoundError on SCRIPT or import errors)
```

- [ ] **Step 6.6: Implement `scripts/check_parallel_dispatch.py`**

Skeleton — fill in details from Step 6.2 research:

```python
"""Parallel-dispatch-detector hook for /edit-episode Phase 4.

Runs at session end. Scans the session transcript for the pattern:
  - A new episodes/<slug>/hyperframes/index.html was created in this session.
  - The DESIGN.md / expanded-prompt.md referenced by that composition
    declares >= 3 beats.
  - Zero parallel `Agent` tool_use entries occurred between the scaffold
    Bash call and the final index.html write.

If the pattern matches, emit a non-blocking warning to stderr. Never block.

Confirmed via Step 6.2 research:
  - Hook event: SessionEnd (or PostToolUse — chosen: <fill in>)
  - Transcript path env var: <fill in>
  - JSONL schema: tool_use entries have `name`, `input`, `timestamp`
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def parse_transcript(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def find_new_index_html(entries: list[dict]) -> dict | None:
    """Find the most recent Write tool_use creating a new episodes/<slug>/hyperframes/index.html."""
    pattern = re.compile(r"episodes[/\\][^/\\]+[/\\]hyperframes[/\\]index\.html$")
    for entry in reversed(entries):
        if entry.get("name") == "Write":
            file_path = entry.get("input", {}).get("file_path", "")
            if pattern.search(file_path):
                return entry
    return None


def count_parallel_agent_dispatches(entries: list[dict], end_entry: dict) -> int:
    """Count Agent tool_use entries with timestamps within ~10s of each other, before end_entry."""
    end_ts = end_entry.get("timestamp", "")
    agent_entries = [
        e for e in entries
        if e.get("name") == "Agent" and e.get("timestamp", "") < end_ts
    ]
    if len(agent_entries) < 3:
        return len(agent_entries)
    # Heuristic: parallel = 3+ Agent calls within 5 seconds of each other.
    # Timestamps are ISO 8601; lexicographic sort is chronological.
    sorted_ts = sorted(e.get("timestamp", "") for e in agent_entries)
    # Simple: count any 3 within 5s window. Returns max found.
    # (Implementation detail — refine after Step 6.2 research confirms transcript timing fidelity.)
    return len(agent_entries)  # Placeholder; replace with windowed count.


def design_md_beat_count(transcript_dir: Path) -> int:
    """Read DESIGN.md from the episode dir referenced in the transcript's index.html write.
    Return the number of beats in 'Beat→Visual Mapping' section. Returns 0 if not found.
    """
    # Implementation: locate DESIGN.md in the same directory as the index.html
    # Parse for "Beat→Visual Mapping" or "Beat-by-beat" headings; count list items.
    # Specifics deferred to implementation; conservative default: count occurrences of
    # `- **Beat ` or `### Beat ` in the file.
    return 0  # Placeholder.


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript", type=Path, default=None)
    args = parser.parse_args()

    transcript_path = args.transcript or Path(os.environ.get("CLAUDE_TRANSCRIPT_PATH", ""))
    if not transcript_path or not transcript_path.exists():
        return 0

    entries = parse_transcript(transcript_path)
    if not entries:
        return 0

    index_entry = find_new_index_html(entries)
    if index_entry is None:
        return 0  # no new index.html → skip-build or non-Phase-4 session

    file_path = Path(index_entry["input"]["file_path"])
    beat_count = design_md_beat_count(file_path.parent)
    if beat_count < 3:
        return 0  # < 3 beats: parallel dispatch not required

    parallel_count = count_parallel_agent_dispatches(entries, index_entry)
    if parallel_count >= 3:
        return 0  # parallel dispatch detected → silent

    print(
        "[parallel-dispatch-detector] Phase 4 produced index.html with "
        f">= 3 beats but {parallel_count} parallel Agent dispatches were "
        "detected in this session. This may indicate sequential beat "
        "authoring (retro 2026-05-01 §2.6). If intentional (resumed "
        "session, single-beat re-author), ignore.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Note placeholders — replace with research-confirmed details from Step 6.2.

- [ ] **Step 6.7: Iterate tests until green**

```bash
python -m pytest tests/test_check_parallel_dispatch.py -v
```

If a test fails, refine the script (windowed counter, DESIGN.md parser, transcript schema details). Re-run until 4/4 pass.

- [ ] **Step 6.8: Register hook in `.claude/settings.json`**

Create `.claude/settings.json` (it doesn't exist yet):

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "command": "python -m scripts.check_parallel_dispatch",
        "description": "Warn if Phase 4 produced a >=3-beat composition without parallel Agent dispatches (retro 2026-05-01 §2.6)"
      }
    ]
  }
}
```

(Adjust event name and command shape per Step 6.2 research.)

- [ ] **Step 6.9: Manual verification — dry-run on a real transcript**

Locate a real session transcript at `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/<session-id>.jsonl` and run:

```bash
python scripts/check_parallel_dispatch.py --transcript "C:/Users/sidor/.claude/projects/.../<session-id>.jsonl"
echo "Exit code: $?"
```

Confirm:
- Exit code 0 always.
- Warning fires only if the heuristic actually matches.
- No Python traceback on malformed lines.

- [ ] **Step 6.10: Commit**

```bash
git add scripts/check_parallel_dispatch.py .claude/settings.json tests/test_check_parallel_dispatch.py tests/fixtures/transcripts/
git commit -m "$(cat <<'EOF'
hooks(parallel-dispatch): detector for sequential beat authoring

Adds a SessionEnd hook that scans the session transcript for the
pattern: new episodes/<slug>/hyperframes/index.html written, paired
DESIGN.md declares >= 3 beats, fewer than 3 parallel Agent
dispatches in this session. If matched, emits a non-blocking
stderr warning citing retro 2026-05-01 §2.6.

Machine-enforced complement to PR-2's brief imperative + Output
Checklist verifier. Defends against the discipline-doesn't-scale
failure mode that retro documented twice (Section 7 §2.4 and
2026-05-01 §2.6).

Pytest suite covers parallel/sequential/skip-build/missing-transcript
cases. Hook never blocks: exit code 0 in all paths.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6.11: Push, PR, merge, cleanup**

```bash
git push -u origin hooks/parallel-dispatch-detector
gh pr create --base main --title "hooks(parallel-dispatch): detector for sequential beat authoring" --body "$(cat <<'EOF'
## Summary
- New SessionEnd hook in .claude/settings.json + scripts/check_parallel_dispatch.py.
- Warns (non-blocking) when Phase 4 produces a >=3-beat composition without parallel Agent dispatches in this session.
- Machine-enforced mirror of video-use SKILL.md Hard Rule 10, applied to HF beat authoring.

## Canon respect
Pure orchestrator-side machine-enforce. Does not edit canon. Mirrors the canonical principle that retro 2026-05-01 surfaced twice as a behavioural drift.

## Test plan
- [x] pytest tests/test_check_parallel_dispatch.py — 4/4 pass.
- [x] Manual dry-run on a real session transcript: no false trigger on this session, exit code 0.
- [ ] Next /edit-episode run: warning fires on intentional sequential beat-authoring (or doesn't fire on parallel) — to be verified live.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --squash --delete-branch
cd ../..
git worktree remove .worktrees/hooks-parallel-dispatch-detector
git branch -d hooks/parallel-dispatch-detector 2>/dev/null || true
git checkout main
git pull origin main
```

---

## Step 7: Phase 0 investigation (`investigate/subcomp-loader-bare-repro`)

This step **does not produce a PR to main** — it produces a findings document that informs PR-5. Runs in a separate worktree.

**Files (in worktree):**
- Create: `tmp/bare-hf-repro/` (gitignored — local scratch).
- Create: `docs/superpowers/specs/2026-05-01-phase0-findings.md` — findings doc.
- Create: `docs/upstream-todo.md` — IF Phase 0 confirms upstream bugs (placeholder, may not need).

- [ ] **Step 7.1: Worktree create**

```bash
git worktree add .worktrees/investigate-subcomp-loader-bare-repro -b investigate/subcomp-loader-bare-repro origin/main
cd .worktrees/investigate-subcomp-loader-bare-repro
```

- [ ] **Step 7.2: Read motion-principles.md (canon prerequisite per design spec §"Phase 0 investigation")**

```bash
cat ~/.agents/skills/hyperframes/references/motion-principles.md | grep -A 30 -i "fromTo\|sub-composition\|load-bearing"
```

Confirm: does canon require `gsap.fromTo()` (not `gsap.from()`) inside `data-composition-src` sub-comps? If yes, this is a candidate root cause for §2.1 and a key delta to check in our scaffold-generated patterns.

Record findings in `docs/superpowers/specs/2026-05-01-phase0-findings.md` (file created in Step 7.5).

- [ ] **Step 7.3: Bare HF scaffold setup**

```bash
mkdir -p tmp/bare-hf-repro
cd tmp/bare-hf-repro
npx hyperframes init
```

Confirm scaffold output: `index.html`, `package.json`, `hyperframes.json`, possibly `meta.json`. Note shape vs our `scripts/scaffold_hyperframes.py` output for diff in Step 7.6.

- [ ] **Step 7.4: §2.1 sub-comp loader bare-repro**

In `tmp/bare-hf-repro/`:

1. Create `compositions/foo.html` with **canon-blessed `<template>` pattern from HF SKILL.md:165-183**, exact verbatim except `my-comp` → `foo` and one visible static red div:

```html
<template id="foo-template">
  <div data-composition-id="foo" data-width="1920" data-height="1080">
    <div style="position:absolute;inset:0;background:red"></div>
    <script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      tl.from("[data-composition-id='foo']", { opacity: 0, duration: 0.5 }, 0);
      window.__timelines["foo"] = tl;
    </script>
  </div>
</template>
```

2. Modify `index.html` to mount it:

```html
<div id="el-1" data-composition-id="foo" data-composition-src="compositions/foo.html" data-start="0" data-duration="3" data-track-index="1"></div>
```

3. Run:

```bash
npx hyperframes lint
npx hyperframes validate
npx hyperframes compositions
npx hyperframes render --out test.mp4
```

4. Open `test.mp4`. **Outcome A:** red is visible → bare-repro PASSED, sub-comp loader works in bare. The bug is orchestrator-side; proceed to Step 7.6 (diff). **Outcome B:** red is NOT visible → bare-repro FAILED, real upstream bug; document for GH issue.

Record outcome verbatim in findings doc.

- [ ] **Step 7.5: §2.4 lint regex bare-repro**

In `tmp/bare-hf-repro/index.html` or a sub-comp, add a comment:

```js
// avoid repeat:-1
```

Run `npx hyperframes lint`. **Outcome A:** lint flags `gsap_infinite_repeat` on the comment → real upstream regex bug. **Outcome B:** lint clean → something in our pipeline generates this literal differently.

Record outcome.

- [ ] **Step 7.6: §2.3 `<template>` in `compositions` CLI bare-repro**

Same `tmp/bare-hf-repro/` with `compositions/foo.html` from Step 7.4. Run:

```bash
npx hyperframes compositions
```

**Outcome A:** `foo` shows non-zero `elements` and matching `duration` → upstream loader works with `<template>`; our scaffold breaks it somehow. **Outcome B:** `foo` shows `0 elements / 0.0s` → real upstream loader edge case with `<template>` and `compositions` CLI.

Record outcome.

- [ ] **Step 7.7: If §2.1 outcome A (orchestrator-side) — diff scaffold output vs bare**

```bash
diff -ru tmp/bare-hf-repro/ ../episodes/2026-05-01-desktop-software-licensing-it-turns-out-is/hyperframes/ | head -100
```

Look for: differences in `hyperframes.json`, `meta.json`, `index.html` template, `package.json`, presence of audio hardlink, `data-has-audio="false"` workaround. Each diff hunk is a candidate root cause; test by reverting each delta in `tmp/bare-hf-repro/` and re-rendering until red disappears. The reverted delta is the root cause.

Record root cause delta.

- [ ] **Step 7.8: Write findings doc**

Create `docs/superpowers/specs/2026-05-01-phase0-findings.md` with structure:

```markdown
# Phase 0 Investigation Findings

**Date:** 2026-05-01
**Worktree:** investigate/subcomp-loader-bare-repro
**Scope:** retro 2026-05-01 findings §2.1 (sub-comp loader), §2.4 (lint regex), §2.3 (template in compositions CLI).

## Canon prerequisites read

- `~/.agents/skills/hyperframes/references/motion-principles.md` — [summary of fromTo / sub-comp guidance]

## §2.1 sub-comp loader

**Bare-repro outcome:** A or B (with timestamp + screenshots).
**If A:** identified delta = [exact field/file/value]. Root cause = [hypothesis].
**If B:** minimal repro for upstream issue = [steps].

## §2.4 lint regex

[Same shape.]

## §2.3 template in compositions CLI

[Same shape.]

## PR-5 scope recommendation

Based on findings:
- [ ] orchestrator-side fix in `scripts/scaffold_hyperframes.py` (specific change).
- [ ] upstream issue with bare-repro (specific repro steps).
- [ ] memory entries to write (specific content).
- [ ] brief updates needed (specific wording).
```

- [ ] **Step 7.9: Commit findings**

```bash
git add docs/superpowers/specs/2026-05-01-phase0-findings.md
git commit -m "$(cat <<'EOF'
docs(spec): phase 0 investigation findings — retro 2026-05-01

Documents bare-scaffold reproduction outcomes for three suspected
upstream bugs from retro 2026-05-01: sub-comp loader, lint regex
on comments, template-in-compositions CLI. Per CLAUDE.md
bare-repro rule, each finding classified as orchestrator-side
(with identified delta) or upstream (with minimal repro).

Informs PR-5 scope.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7.10: Push, PR, merge, cleanup**

```bash
git push -u origin investigate/subcomp-loader-bare-repro
gh pr create --base main --title "docs(spec): phase 0 investigation findings" --body "$(cat <<'EOF'
## Summary
- Bare-scaffold reproduction outcomes for retro 2026-05-01 findings §2.1, §2.4, §2.3.
- Each finding classified per CLAUDE.md bare-repro rule: orchestrator-side (with delta) or upstream (with repro).
- Recommends PR-5 scope.

## Test plan
- [ ] Findings doc reads as definitive — no "TBD" or "couldn't reproduce".

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --squash --delete-branch
cd ../..
git worktree remove .worktrees/investigate-subcomp-loader-bare-repro
git branch -d investigate/subcomp-loader-bare-repro 2>/dev/null || true
git checkout main
git pull origin main
```

---

## Step 8: PR-5 (post-investigation, scope from Phase 0)

This step **cannot be fully planned until Phase 0 findings exist**. After Step 7 lands, write a plan addendum at `docs/superpowers/plans/2026-05-01-pr5-addendum.md` that follows the same structure as Steps 4-6 (worktree, edits, tests, commit, PR, merge, cleanup) but with content informed by the findings.

Two possible shapes (per design spec):

- [ ] **If orchestrator-side:** plan addendum specifies code fix in `scripts/scaffold_hyperframes.py` (or wherever delta lives), brief update reverting the "broken in 0.4.41" wording to the real root cause, and held memory writes (Step 9) with correct content.

- [ ] **If upstream:** plan addendum specifies brief workaround (close to retro action items proposal), 1-3 GH issues opened on `heygen-com/hyperframes` with bare-repro, and held memory writes (Step 9) with upstream-bug framing.

- [ ] **Step 8.1: Trigger.** When Step 7 PR is merged, open this plan, write the addendum, then execute the addendum the same way as Steps 4-6.

---

## Step 9: Held memory writes (after Phase 0)

**Files:**
- Create: `C:/Users/sidor/.claude/projects/.../memory/feedback_hf_subcomp_loader_<scope>.md` — exact name depends on root cause.
- Create: `C:/Users/sidor/.claude/projects/.../memory/feedback_lint_regex_repeat_minus_one_in_comments.md` — same.
- Modify: `MEMORY.md` index — add 2 new entries.
- Delete or replace: `feedback_multi_beat_sub_compositions.md` — old, misleading entry.

- [ ] **Step 9.1: Read Phase 0 findings (Step 7.8 output) to determine memory content.**

- [ ] **Step 9.2: Write `feedback_hf_subcomp_loader_<scope>.md`** — content mirrors findings (orchestrator-side workaround OR upstream bug + workaround). Filename:
- `feedback_hf_subcomp_loader_orchestrator_delta.md` if orchestrator-side.
- `feedback_hf_subcomp_loader_broken.md` if upstream.

- [ ] **Step 9.3: Write `feedback_lint_regex_repeat_minus_one_in_comments.md`** — same approach.

- [ ] **Step 9.4: Update `MEMORY.md` index — add 2 new lines, remove the line for `feedback_multi_beat_sub_compositions.md`.**

- [ ] **Step 9.5: Delete `feedback_multi_beat_sub_compositions.md`** — its claim ("split per-beat for orchestrator best-practice") was false per retro 2026-05-01 §2.1.

```bash
rm "C:/Users/sidor/.claude/projects/.../memory/feedback_multi_beat_sub_compositions.md"
```

No commit — local memory.

---

## Self-review checklist (run before declaring plan complete)

- [ ] **Spec coverage:** Each section in `2026-05-01-retro-action-items-design.md` is implemented by at least one task in this plan? Check the failure-mode coverage table at the end of the spec — every row mapped to a Step here.
- [ ] **Placeholders:** No "TBD" / "TODO" / "implement later" outside Step 8 (which is intentionally deferred per spec).
- [ ] **Type/symbol consistency:** Functions and filenames referenced across steps match (e.g. `check_parallel_dispatch.py` is consistent across Steps 6.4, 6.6, 6.8).
- [ ] **Branch names match CLAUDE.md convention:** `<area>/<topic>` — verified for all 6 PRs.
- [ ] **Each PR uses worktree per CLAUDE.md:** `.worktrees/<branch>` — verified for Steps 2, 3, 4, 5, 6, 7.
- [ ] **Each PR ends with `gh pr merge --squash --delete-branch` + worktree cleanup:** verified.

---

## Out of plan (deferred indefinitely)

- Editing `~/.agents/skills/hyperframes/` or `~/.claude/skills/video-use/` — read-only canon.
- Changing `scripts/pickup.py`, `scripts/isolate_audio.py`, `scripts/remap_transcript.py` — retro doesn't touch these.
- Extending `superpowers:dispatching-parallel-agents` — used as-is.
