# Section 7 retro fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the canon-audited fix set from `docs/superpowers/specs/2026-05-01-section7-fixes-design.md` as five focused PRs, eight durable-feedback memory entries, and two upstream HyperFrames issues.

**Architecture:** Each PR is a small, atomic change on its own feature branch (per `CLAUDE.md` non-negotiable branching workflow). PR-1 and PR-4 are independent and can be parallelized; PR-2 and PR-3 are sequential (same file). Memory entries land alongside PR-1. Upstream issues are async, after PR-1 demonstrates the fix.

**Tech Stack:** Python 3.11 (`scripts/`), pytest (`tests/`), GitHub markdown (briefs and CLAUDE.md), `gh` CLI for PRs/issues, `git worktree` for branch isolation.

---

## File map

| File | Touch type | PR | Why |
|---|---|---|---|
| `scripts/scaffold_hyperframes.py` | Modify (template constant) | PR-1 | Add `data-has-audio="false"` to video element |
| `tests/test_scaffold_hyperframes.py` | Modify (3 assertions) | PR-1 | Existing tests assert `"data-has-audio" not in out` — must invert |
| `memory/feedback_design_md_opt_outs.md` | Create | PR-1 | Memory entry 1 |
| `memory/feedback_multi_beat_sub_compositions.md` | Create | PR-1 | Memory entry 2 |
| `memory/feedback_bundled_helper_path.md` | Create | PR-1 | Memory entry 3 |
| `memory/feedback_hf_always_read_canon.md` | Create | PR-1 | Memory entry 4 |
| `memory/feedback_hf_step2_prompt_expansion.md` | Create | PR-1 | Memory entry 5 |
| `memory/feedback_hf_catalog_orchestrator_gate.md` | Create | PR-1 | Memory entry 6 |
| `memory/feedback_translucent_transitions.md` | Create | PR-1 | Memory entry 7 |
| `memory/feedback_hf_video_audio_canon_bug.md` | Create | PR-1 | Memory entry 8 |
| `memory/MEMORY.md` | Modify (append 8 lines) | PR-1 | Index pointers |
| `scripts/remap_transcript.py` | Modify (add EDL hash check) | PR-4 | Self-healing on EDL change |
| `tests/test_remap_transcript.py` | Modify (add 1 test) | PR-4 | Lock in regen-on-mismatch behavior |
| `.claude/commands/edit-episode.md` (re-cut block §"Idempotency and rebuild guidance" lines 218-220) | Modify | PR-4 | Mention `final.json` deletion on re-cut |
| `.claude/commands/edit-episode.md` (Phase 4 brief lines 147-192) | Modify (large rewrite) | PR-2 | Reading list + Step 2 + catalog + captions |
| `.claude/commands/edit-episode.md` (Phase 4 brief, multi-scene + transitions block) | Modify | PR-3 | Sub-compositions + parallel dispatch + transition mechanism |
| `CLAUDE.md` (Skill copies block) | Modify (append paragraph) | PR-5 | Windows bootstrap note |

## Memory entry path convention

Per the auto-memory section in system prompt: each memory file lives under `C:\Users\sidor\.claude\projects\C--Users-sidor-repos-anticodeguy-video-editing-studio\memory\`. The `MEMORY.md` index also lives there. **None of these files live in the project repo** — they're under `~/.claude/projects/...`. PR-1 commits do NOT include memory files; the project repo only carries the spec and plan. Memory writes happen in the implementer's session as a separate side-effect step within the PR-1 workflow but produce no git diff.

This was missed in the spec — clarification:
- Memory files are **out-of-tree** artifacts. Created during PR-1 task execution but not part of the PR diff.
- They influence future Claude sessions in this project; they are not part of code review.

PR-1 still groups the conceptual work (scaffold fix + memory entries) but the memory entries are file-system writes outside the repo, not commits.

---

## Phase A — PR-1: Scaffold audio fix + memory entries

### Task A1: Create worktree

**Files:**
- Create: `.worktrees/fix-scaffold-audio/` (worktree directory)

- [ ] **Step 1: Create branch worktree**

```bash
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio
git worktree add .worktrees/fix-scaffold-audio -b fix/scaffold-audio-data-has-audio
```

Expected output:
```
Preparing worktree (new branch 'fix/scaffold-audio-data-has-audio')
HEAD is now at <sha> docs(spec): add design for Section 7 retro fixes (#9)
```

- [ ] **Step 2: Set worktree as the active cwd for the rest of Phase A**

All subsequent Task A* commands run from `C:/Users/sidor/repos/anticodeguy-video-editing-studio/.worktrees/fix-scaffold-audio/`.

### Task A2: Update existing tests to expect `data-has-audio="false"`

**Files:**
- Modify: `tests/test_scaffold_hyperframes.py:95-99` and line 171

The existing tests assert the **opposite** of what the spec requires (they were written when the team thought "no `data-has-audio` attribute" was canon-correct). We invert them first per TDD — failing test, then implementation.

- [ ] **Step 1: Read current test lines**

```bash
sed -n '95,99p' tests/test_scaffold_hyperframes.py
sed -n '170,172p' tests/test_scaffold_hyperframes.py
```

Expected: confirms current state asserts `"data-has-audio" not in out` (line 98) and `"data-has-audio" not in html` (line 171).

- [ ] **Step 2: Replace `test_patch_index_html_no_data_has_audio` test**

Edit `tests/test_scaffold_hyperframes.py`. Find this block (lines 95-99):

```python
def test_patch_index_html_no_data_has_audio():
    """Canonical pattern uses two-element pair, NOT data-has-audio."""
    out = patch_index_html(DEFAULT_INDEX_HTML, width=1080, height=1920, duration=58.8, video_src="../edit/final.mp4")
    assert "data-has-audio" not in out
```

Replace with:

```python
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
```

- [ ] **Step 3: Update the end-to-end test assertion**

In `tests/test_scaffold_hyperframes.py` line 171, change:

```python
    assert "data-has-audio" not in html
```

to:

```python
    assert 'data-has-audio="false"' in html
```

- [ ] **Step 4: Run the tests — they MUST fail**

```bash
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio/.worktrees/fix-scaffold-audio
python -m pytest tests/test_scaffold_hyperframes.py -v 2>&1 | tail -20
```

Expected: at least two failures, including `test_patch_index_html_video_has_explicit_data_has_audio_false` with message similar to `AssertionError: assert 'data-has-audio="false"' in '<...html without the attribute...>'`.

- [ ] **Step 5: Commit the failing tests (TDD discipline)**

```bash
git add tests/test_scaffold_hyperframes.py
git commit -m "test(scaffold): assert data-has-audio=false on video to silence StaticGuard

Inverts the previous assertion. Background: HF compiler auto-injects
data-has-audio=true on every <video> without an explicit attribute,
which combined with muted trips StaticGuard 'invalid contract'.
Explicit data-has-audio=false blocks the auto-inject and silences
the runtime warning. Upstream tracking: heygen-com/hyperframes#586."
```

### Task A3: Update `VIDEO_AUDIO_PAIR_TEMPLATE`

**Files:**
- Modify: `scripts/scaffold_hyperframes.py:16-19`

- [ ] **Step 1: Read current template**

```bash
sed -n '14,20p' scripts/scaffold_hyperframes.py
```

Expected: lines 16-19 show the current template with `<video id="el-video" class="clip" data-start="0" data-track-index="0"  src="{src}" muted playsinline></video>`.

- [ ] **Step 2: Replace the template constant block**

Edit `scripts/scaffold_hyperframes.py`. Find lines 16-19:

```python
VIDEO_AUDIO_PAIR_TEMPLATE = """      <video id="el-video" class="clip" data-start="0" data-track-index="0"
             src="{src}" muted playsinline></video>
      <audio id="el-audio" class="clip" data-start="0" data-track-index="2"
             src="{src}" data-volume="1"></audio>"""
```

Replace with:

```python
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
```

- [ ] **Step 3: Run tests — they MUST pass now**

```bash
python -m pytest tests/test_scaffold_hyperframes.py -v 2>&1 | tail -20
```

Expected: all tests pass, including `test_patch_index_html_video_has_explicit_data_has_audio_false`. If `test_scaffold_end_to_end` is skipped because no `npx` is on PATH, that's fine — the unit tests cover the template behavior.

- [ ] **Step 4: Run the full test suite for regressions**

```bash
python -m pytest tests/ -v 2>&1 | tail -10
```

Expected: 0 failures across all test files.

- [ ] **Step 5: Commit the fix**

```bash
git add scripts/scaffold_hyperframes.py
git commit -m "fix(scaffold): inject data-has-audio=false on <video> to silence StaticGuard

The HF compiler auto-injects data-has-audio=true on every <video> without
an explicit attribute. With muted+same-src on both <video> and <audio>,
this trips StaticGuard 'invalid contract' (media.ts:274) and produces
audible audio doubling in studio preview (audioMixer.ts:55-56 picks the
<video> up as a second source).

Setting data-has-audio=false is canonical per HF CLI docs
(packages/cli/src/docs/data-attributes.md) but missing from the
agent-facing SKILL.md. This patch documents the gap and links the
upstream issue.

Upstream tracking: heygen-com/hyperframes#586"
```

### Task A4: Runtime smoke test on existing episode (manual verification)

**Files:**
- Read-only: `episodes/2026-04-30-desktop-software-licensing-it-turns-out-is/hyperframes/index.html`

The scaffold change only takes effect on **new** episodes. To verify the runtime behavior end-to-end before merging, manually edit the existing episode's `index.html` to mirror the new template, run `validate`, then revert.

- [ ] **Step 1: Edit existing episode's index.html in-place**

```bash
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio/.worktrees/fix-scaffold-audio
EP="../../episodes/2026-04-30-desktop-software-licensing-it-turns-out-is/hyperframes"
cp "$EP/index.html" "$EP/index.html.smoketest.bak"
```

Then edit `$EP/index.html` line 267-268. Find:

```html
      <video id="el-video" class="clip" data-start="0" data-track-index="0"
             src="final.mp4" muted playsinline></video>
```

Replace with:

```html
      <video id="el-video" class="clip" data-start="0" data-track-index="0"
             src="final.mp4" data-has-audio="false" muted playsinline></video>
```

- [ ] **Step 2: Run validate**

```bash
cd "$EP" && npx hyperframes validate 2>&1 | head -8
```

Expected: NO `[StaticGuard] Invalid HyperFrame contract` line. The validate output starts directly with the WCAG contrast warnings block (which is a separate, unrelated retro item §2.6).

- [ ] **Step 3: Revert the smoke-test edit**

```bash
mv "$EP/index.html.smoketest.bak" "$EP/index.html"
```

Verify revert:

```bash
grep -c "data-has-audio" "$EP/index.html"
```

Expected: `0` (the existing episode is left untouched until /edit-episode is re-run for it).

### Task A5: Write 8 memory entries

**Files** (all out-of-tree, no git diff):
- Create: `~/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_design_md_opt_outs.md`
- Create: `~/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_multi_beat_sub_compositions.md`
- Create: `~/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_bundled_helper_path.md`
- Create: `~/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_hf_always_read_canon.md`
- Create: `~/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_hf_step2_prompt_expansion.md`
- Create: `~/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_hf_catalog_orchestrator_gate.md`
- Create: `~/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_translucent_transitions.md`
- Create: `~/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_hf_video_audio_canon_bug.md`

The memory directory already exists per the auto-memory system prompt. Each file uses the YAML-frontmatter schema specified there.

- [ ] **Step 1: Write memory file 1 — DESIGN.md opt-outs**

Path: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_design_md_opt_outs.md`

Content:

```markdown
---
name: DESIGN.md opt-outs are bounded
description: Skill executor must not opt out via DESIGN.md from anything mandated by canon OR by this orchestrator's brief
type: feedback
---

DESIGN.md → "What NOT to Do" section may document anti-patterns specific to the episode but MUST NOT opt out of canonical mechanics or orchestrator-mandated mechanics. Validate every opt-out against both layers.

**Why:** In retro 2026-05-01 (Section 7 verification), Skill executor wrote *"Captions are NOT used"* into DESIGN.md → What NOT to Do, treating captions as optional and shipping a composition without them. Captions are mandated by this orchestrator's Phase 4 brief (canon treats them as conditional, but our pipeline always produces audio-synced text — the conditional trigger always fires).

**How to apply:** Before adding any opt-out line to DESIGN.md → What NOT to Do, check (a) HF SKILL.md and references for whether the mechanism is canon-mandated, (b) `.claude/commands/edit-episode.md` Phase 4 brief for whether the orchestrator mandates it. Mandated items can only be omitted by explicit user request, not by Skill-author judgment.
```

- [ ] **Step 2: Write memory file 2 — multi-beat sub-compositions**

Path: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_multi_beat_sub_compositions.md`

Content:

```markdown
---
name: Multi-beat HF compositions split per-beat in compositions/
description: Multi-beat HyperFrames compositions split into per-beat sub-compositions; root index.html only mounts them
type: feedback
---

Multi-beat compositions: split each beat ≥ 3 into `compositions/beat-{N}-{slug}.html`, mount via `<div data-composition-id data-composition-src="compositions/beat-N.html">`. Root `index.html` stays ≤ 100 lines (video + audio + captions + mount points).

**Why:** Inline 381-line `index.html` triggered HF lint warning `composition_file_too_large` ("Agents produce better results when large scenes are split into smaller sub-compositions"). The warning is informational, not blocking — but it was added precisely because agents author large scenes worse than small ones. In retro 2026-05-01 the orchestrator shipped a 381-line monolith and the lint warning was dismissed as cosmetic.

**How to apply:** Phase 4 brief recommends sub-composition split as orchestrator best-practice, supported by the HF lint rule. This is NOT a HF canon mandate — `data-composition-src` is canonical mounting (`SKILL.md:149-185`), but per-beat split is design choice. Treat the lint warning as a real recommendation, not a tick-box.
```

- [ ] **Step 3: Write memory file 3 — bundled helper path**

Path: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_bundled_helper_path.md`

Content:

```markdown
---
name: Bundled path for external skill helper scripts
description: External skill helper scripts (animation-map.mjs, contrast-report.mjs) must run from project's bundled node_modules, not ~/.agents/
type: feedback
---

When invoking a helper script shipped with an external skill (HyperFrames `animation-map.mjs`, `contrast-report.mjs`, etc.), always invoke it from the project's bundled `node_modules/<skill>/dist/skills/<skill>/scripts/<name>.mjs`. Do NOT invoke the copy under `~/.agents/skills/<skill>/scripts/`.

**Why:** The `~/.agents/...` copies bootstrap their dependencies via ancestor-walk from the script's own directory, looking for the package's `package.json` as an ancestor. Inside the global skill directory, no such manifest exists, so `package-loader.mjs` enters an eager-eval bag and fails. The bundled `node_modules/<skill>/...` location resolves the version probe via the package's own manifest. Verified working in retro 2026-04-30 (PR #7) and again in retro 2026-05-01.

**How to apply:** Phase 4 brief and any orchestrator script that calls HF helpers should use the bundled path verbatim: `<hyperframes-dir>/node_modules/hyperframes/dist/skills/hyperframes/scripts/<helper>.mjs`. CLAUDE.md "Skill copies: docs vs. runnable" block documents this rule — keep it consistent.
```

- [ ] **Step 4: Write memory file 4 — HF Always-read canon list**

Path: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_hf_always_read_canon.md`

Content:

```markdown
---
name: HF SKILL.md "Always read" is a contract
description: HyperFrames "Always read" reference list is mandatory; conditional refs may be added by this orchestrator
type: feedback
---

HF SKILL.md "Always read" tags = contract, not recommendation. Skipping any of them produces composition that looks "like HTML with overlays", not like video.

Canon list (from `~/.agents/skills/hyperframes/SKILL.md`):
- `references/video-composition.md` — *Always read*
- `references/typography.md` — *Always read*
- `references/motion-principles.md` — *Always read*
- `references/beat-direction.md` — *Always read for multi-scene*
- `references/transitions.md` — *Always read for multi-scene*

This orchestrator additionally mandates (with explicit justification — every episode produces audio-synced text):
- `references/captions.md` — orchestrator-house addition
- `references/transcript-guide.md` — orchestrator-house addition

**Why:** In retro 2026-05-01, comparison with a clean HyperFrames executor session showed both sessions skipped all 5 Always-read documents — and both produced compositions with the same canon-decay pattern (no canonical caption pattern, no vignette layers, missed beat-direction rhythm). Phase 4 brief now enforces the verbatim list with first-response confirmation gate.

**How to apply:** When writing or reviewing Phase 4 brief content, the verbatim list is non-negotiable. Empty first-response confirmation = stop, do not proceed to composition.
```

- [ ] **Step 5: Write memory file 5 — Step 2 prompt expansion**

Path: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_hf_step2_prompt_expansion.md`

Content:

```markdown
---
name: HF Step 2 prompt expansion mandatory for multi-scene
description: HyperFrames Step 2 (prompt expansion) is mandatory for multi-scene compositions; canonical artifact is .hyperframes/expanded-prompt.md
type: feedback
---

HF SKILL.md Step 2 (prompt expansion) is mandatory for every multi-scene composition. Output is a real artifact at `<hyperframes-dir>/.hyperframes/expanded-prompt.md` per `references/prompt-expansion.md:57-68`. Skipping it produces scenes authored independently of the script narrative and design.md.

**Why:** In retro 2026-05-01, Skill executor jumped from Step 1 (Visual Identity Gate) directly to Step 3 (Plan), skipping the grounding intermediate. Result: each beat was visually authored without a unified intent ground-truth. The same pattern was visible in the comparison clean session.

**How to apply:** Phase 4 brief enforces this with an explicit artifact gate. The artifact name is the canonical `expanded-prompt.md` (NOT `PROMPT.md` — earlier orchestrator drafts used the wrong name). If the artifact does not exist after Step 2, the executor has not run Step 2.
```

- [ ] **Step 6: Write memory file 6 — catalog gate**

Path: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_hf_catalog_orchestrator_gate.md`

Content:

```markdown
---
name: hyperframes catalog scan is an orchestrator-house gate
description: npx hyperframes catalog scan before custom HTML is an orchestrator gate, not HF canon
type: feedback
---

Before writing any custom HTML for a beat, run `npx hyperframes catalog --json > .hyperframes/catalog.json`. For each beat, write one sentence in `DESIGN.md` → `Beat→Visual Mapping`: which catalog block was considered (or installed via `npx hyperframes add`), and why custom HTML was justified if it was. Empty per-beat justification list = stop.

**Why:** This is an orchestrator productivity gate, NOT a HF canon mandate. HF canon mentions `catalog` only in Step 1 / Design Picker context. In retro 2026-05-01, neither our orchestrator session nor the comparison clean session ran `catalog` — both authored every beat as custom HTML without considering existing blocks. This wastes time and produces less-tested visuals than installed registry blocks.

**How to apply:** Apply when working on Phase 4 brief content. Frame the rule as "orchestrator productivity practice, not HF canon mandate" so future updates don't conflate the two layers.
```

- [ ] **Step 7: Write memory file 7 — translucent transitions**

Path: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_translucent_transitions.md`

Content:

```markdown
---
name: Translucent overlays + entrance-only-cover do not visually clear scenes
description: Translucent compositions need explicit per-beat transition mechanism; canon allows CSS, shader, or final-fade
type: feedback
---

Translucent overlays (e.g., glass panels) + Scene Transitions canon entrance-only-cover do NOT visually clear the previous scene. For each inter-beat boundary in a translucent composition, choose one mechanism explicitly per `DESIGN.md`:
- CSS clip-path / mask transition — canon-allowed, simpler;
- Shader transition via `npx hyperframes add transition-shader-<name>` — canon-allowed, more capable;
- Final-scene fade — only between beat-N and beat-(N+1) where N+1 is final.

Do not rely on entrance-only-cover with translucent panels.

**Why:** HF canon `transitions.md:85-95` says CSS and shader are equal first-class options ("CSS transitions are simpler... Choose based on the effect you want, not based on which is easier"). An earlier draft of this orchestrator's brief mandated shader transitions for translucent overlays — that was canon-misreading. The real issue is that ANY translucent composition needs an explicit transition mechanism documented per-beat.

**How to apply:** When reviewing or writing Phase 4 brief composition-structure content, do NOT mandate shader-only. Canon allows three mechanisms; pick one per beat with documented justification.
```

- [ ] **Step 8: Write memory file 8 — Video and Audio canon bug**

Path: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/feedback_hf_video_audio_canon_bug.md`

Content:

```markdown
---
name: HF SKILL.md "Video and Audio" canonical example triggers StaticGuard
description: HF canonical <video>+<audio> same-src example triggers StaticGuard 'invalid contract'; orchestrator workaround data-has-audio="false"
type: feedback
---

HF SKILL.md §"Video and Audio" canonical example uses `<video src="video.mp4" muted>` + `<audio src="video.mp4">` — same `src` on both elements. This pattern triggers a runtime StaticGuard "invalid contract" warning in studio preview because:
1. HF compiler unconditionally injects `data-has-audio="true"` on every `<video>` without an explicit attribute (`timingCompiler.ts:104-106`).
2. Combined with `muted`, this trips the StaticGuard rule (`media.ts:274`).
3. audioMixer (`audioMixer.ts:55-56`) picks the `<video>` up as an audio source alongside the `<audio>` element — same muxed file routed twice.

**Workaround in this orchestrator:** explicit `data-has-audio="false"` on `<video>`. Documented in HF CLI docs (`packages/cli/src/docs/data-attributes.md`) and recognized by HF lint, but absent from agent-facing `SKILL.md` canon.

**Why:** Discovered in retro 2026-05-01 Section 7 verification. Reproduced on a minimal blank-init project. Capture engine bypasses both DOM pipelines and produces clean output, so `final.mp4` on disk is fine — only studio preview is affected. Filed upstream: https://github.com/heygen-com/hyperframes/issues/586

**How to apply:** Apply via `scripts/scaffold_hyperframes.py:VIDEO_AUDIO_PAIR_TEMPLATE`. If upstream resolves the issue (doc fix, lint fix, or compiler fix), revisit the workaround. Until then, treat canon Rule #2 ("always muted video + separate `<audio>`") as requiring the explicit `data-has-audio="false"` for muxed-source case.
```

- [ ] **Step 9: Update MEMORY.md index**

Path: `C:/Users/sidor/.claude/projects/C--Users-sidor-repos-anticodeguy-video-editing-studio/memory/MEMORY.md`

Append the following 8 lines at the end of the file (existing lines stay):

```markdown
- [DESIGN.md opt-outs are bounded](feedback_design_md_opt_outs.md) — captions/transitions are mandated; "What NOT to Do" can't disable canonical or orchestrator-house mechanics
- [Multi-beat HF compositions split per-beat](feedback_multi_beat_sub_compositions.md) — sub-compositions in compositions/, root index.html ≤ 100 lines; lint warning is real
- [Bundled path for external skill helpers](feedback_bundled_helper_path.md) — node_modules/<skill>/dist/, not ~/.agents/...
- [HF SKILL.md "Always read" is a contract](feedback_hf_always_read_canon.md) — verbatim canon list + 2 orchestrator-house additions
- [HF Step 2 prompt expansion mandatory](feedback_hf_step2_prompt_expansion.md) — output to .hyperframes/expanded-prompt.md (canonical name)
- [hyperframes catalog scan is orchestrator-house gate](feedback_hf_catalog_orchestrator_gate.md) — per-beat justification in DESIGN.md, not HF canon
- [Translucent overlays need explicit transition mechanism](feedback_translucent_transitions.md) — CSS / shader / final-fade per-beat; canon allows all three
- [HF "Video and Audio" canon example triggers StaticGuard](feedback_hf_video_audio_canon_bug.md) — workaround data-has-audio=false; upstream #586
```

- [ ] **Step 10: Verify memory writes are not in git diff**

```bash
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio/.worktrees/fix-scaffold-audio
git status
```

Expected: clean working tree (commits already done in Tasks A2, A3). Memory files are out-of-tree and do not appear.

### Task A6: Push branch + open PR

**Files:** none (push + PR ops)

- [ ] **Step 1: Push branch**

```bash
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio/.worktrees/fix-scaffold-audio
git push -u origin fix/scaffold-audio-data-has-audio 2>&1 | tail -3
```

Expected: `branch 'fix/scaffold-audio-data-has-audio' set up to track 'origin/fix/scaffold-audio-data-has-audio'.`

- [ ] **Step 2: Create PR**

```bash
gh pr create --base main --title "fix(scaffold): inject data-has-audio=false to silence StaticGuard" --body "$(cat <<'EOF'
## Summary

Add `data-has-audio="false"` to the `<video>` element in `scripts/scaffold_hyperframes.py:VIDEO_AUDIO_PAIR_TEMPLATE`. Without it, HF's compiler unconditionally auto-injects `data-has-audio="true"`, which combined with `muted` trips StaticGuard "invalid contract" (`media.ts:274`) and routes the `<video>` into audioMixer alongside the `<audio>` element — same muxed file mixed twice, audible distortion in studio preview.

The attribute is documented in HF CLI docs (`packages/cli/src/docs/data-attributes.md`) but absent from agent-facing SKILL.md. Upstream tracking: heygen-com/hyperframes#586.

## Test plan

- [x] Existing tests inverted: `tests/test_scaffold_hyperframes.py` now asserts `data-has-audio="false"` IS present (was: NOT present). All 12 tests pass.
- [x] Smoke-test on existing episode: temporarily edited `episodes/2026-04-30-...-licensing-it-turns-out-is/hyperframes/index.html` to mirror the new template, ran `npx hyperframes validate`, confirmed StaticGuard "invalid contract" no longer fires. Reverted the edit.
- [ ] Reviewer: run `python -m pytest tests/ -v` from clean checkout — expect 0 failures.
EOF
)" 2>&1 | tail -3
```

Expected: PR URL on stdout. Capture it for reference.

### Task A7: Merge PR-1, clean up worktree

- [ ] **Step 1: Merge PR with squash**

Capture the PR number from Step 2 above (e.g., `PR_NUM=10`).

```bash
gh pr merge $PR_NUM --squash --delete-branch
```

Expected: merge succeeds. Note the failing-to-delete-local-branch message (worktree holds the branch); we clean it up next.

- [ ] **Step 2: Remove worktree, delete local branch**

```bash
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio
git worktree remove .worktrees/fix-scaffold-audio
git branch -D fix/scaffold-audio-data-has-audio
```

- [ ] **Step 3: Update main**

```bash
git checkout main
git pull origin main --ff-only
```

Verify the change landed:

```bash
grep -c 'data-has-audio="false"' scripts/scaffold_hyperframes.py
```

Expected: `1`.

---

## Phase B — PR-4: Re-cut idempotency for `final.json`

This phase can run **in parallel** with Phase A — different files, no conflicts.

### Task B1: Create worktree

- [ ] **Step 1: Create branch worktree**

```bash
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio
git worktree add .worktrees/fix-recut-final-json -b fix/recut-final-json-idempotency
```

All subsequent Task B* commands run from `C:/Users/sidor/repos/anticodeguy-video-editing-studio/.worktrees/fix-recut-final-json/`.

### Task B2: Add EDL hash to `final.json` metadata + regen on mismatch

**Files:**
- Modify: `scripts/remap_transcript.py` (add hash check)
- Modify: `tests/test_remap_transcript.py` (add 2 tests)

The current `remap()` function returns a flat array of word entries. To enable self-healing, change the on-disk shape from a bare array to an envelope `{"edl_hash": "...", "words": [...]}`. The reader (`scaffold_hyperframes.py`'s call site in glue) currently doesn't read `final.json` directly — it's consumed only by HF skill via `transcript.json` copy. So we have freedom to change the schema. Cross-check before committing.

- [ ] **Step 1: Verify the on-disk schema is internal**

```bash
grep -rn "final.json" scripts/ .claude/ 2>&1 | head -20
```

Expected output should reveal that `final.json` is read only by `remap_transcript.py` (writer) and copied as `transcript.json` by `scaffold_hyperframes.py:196-197`. The HF skill consumes `transcript.json`, not `final.json`. **If grep shows additional readers, the schema change is breaking and we revert to a sidecar file approach (`final.json.meta`) instead of envelope.**

If the only readers found are the two scripts above, proceed with the envelope shape. Otherwise, switch to sidecar approach (record decision in commit message and adjust the rest of this task).

- [ ] **Step 2: Write failing test for hash-stamping**

Append to `tests/test_remap_transcript.py`:

```python
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _edl_hash(edl_dict: dict) -> str:
    """Stable SHA-256 of EDL JSON content (sort_keys for determinism)."""
    blob = json.dumps(edl_dict, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def test_main_writes_envelope_with_edl_hash(tmp_path: Path):
    """final.json on disk is an envelope {edl_hash, words}, not a bare array."""
    edl = {"ranges": [{"start": 0.0, "end": 1.0}], "sources": [{"file": "raw.mp4"}]}
    raw = {"words": [{"type": "word", "text": "hi", "start": 0.1, "end": 0.4}]}

    edl_path = tmp_path / "edl.json"
    raw_path = tmp_path / "raw.json"
    out_path = tmp_path / "final.json"
    edl_path.write_text(json.dumps(edl), encoding="utf-8")
    raw_path.write_text(json.dumps(raw), encoding="utf-8")

    rc = subprocess.run(
        [sys.executable, "-m", "scripts.remap_transcript",
         "--raw", str(raw_path), "--edl", str(edl_path), "--out", str(out_path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True,
    ).returncode
    assert rc == 0

    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(on_disk, dict)
    assert "edl_hash" in on_disk
    assert on_disk["edl_hash"] == _edl_hash(edl)
    assert isinstance(on_disk["words"], list)
    assert len(on_disk["words"]) == 1


def test_main_regens_on_edl_hash_mismatch(tmp_path: Path):
    """Re-running with different EDL produces new hash + new words (not stale cache)."""
    edl_a = {"ranges": [{"start": 0.0, "end": 1.0}], "sources": []}
    edl_b = {"ranges": [{"start": 5.0, "end": 6.0}], "sources": []}
    raw = {"words": [
        {"type": "word", "text": "early", "start": 0.1, "end": 0.4},
        {"type": "word", "text": "late",  "start": 5.1, "end": 5.4},
    ]}

    edl_path = tmp_path / "edl.json"
    raw_path = tmp_path / "raw.json"
    out_path = tmp_path / "final.json"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")

    # First run with edl_a — captures "early"
    edl_path.write_text(json.dumps(edl_a), encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "scripts.remap_transcript",
         "--raw", str(raw_path), "--edl", str(edl_path), "--out", str(out_path)],
        cwd=Path(__file__).resolve().parents[1], check=True,
    )
    first = json.loads(out_path.read_text(encoding="utf-8"))
    assert first["edl_hash"] == _edl_hash(edl_a)
    assert first["words"][0]["text"] == "early"

    # Second run with edl_b — must regen (hash differs from on-disk cache)
    edl_path.write_text(json.dumps(edl_b), encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "scripts.remap_transcript",
         "--raw", str(raw_path), "--edl", str(edl_path), "--out", str(out_path)],
        cwd=Path(__file__).resolve().parents[1], check=True,
    )
    second = json.loads(out_path.read_text(encoding="utf-8"))
    assert second["edl_hash"] == _edl_hash(edl_b)
    assert second["words"][0]["text"] == "late"
```

- [ ] **Step 3: Run the new tests — they MUST fail**

```bash
python -m pytest tests/test_remap_transcript.py -v 2>&1 | tail -20
```

Expected: at least the two new tests fail (`test_main_writes_envelope_with_edl_hash` failing on `assert isinstance(on_disk, dict)` because current schema is a bare list).

- [ ] **Step 4: Update `remap_transcript.py` to write envelope + verify glue reader**

Edit `scripts/remap_transcript.py`. Replace the entire `main()` function (lines 46-59) with:

```python
def _edl_hash(edl: dict) -> str:
    """Stable SHA-256 of the EDL dict (sort_keys for determinism)."""
    import hashlib
    blob = json.dumps(edl, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remap Scribe transcript to hyperframes captions schema.")
    parser.add_argument("--raw", type=Path, required=True, help="Path to edit/transcripts/raw.json")
    parser.add_argument("--edl", type=Path, required=True, help="Path to edit/edl.json")
    parser.add_argument("--out", type=Path, required=True, help="Path to write edit/transcripts/final.json")
    args = parser.parse_args(argv)

    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    edl = json.loads(args.edl.read_text(encoding="utf-8"))
    edl_hash = _edl_hash(edl)

    # Self-healing: if final.json exists and its edl_hash matches the current EDL, skip work.
    if args.out.exists():
        try:
            existing = json.loads(args.out.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and existing.get("edl_hash") == edl_hash:
                print(f"final.json up to date for current EDL (hash {edl_hash[:8]}) — skipping remap", file=sys.stderr)
                return 0
        except (json.JSONDecodeError, OSError):
            pass  # fall through and regenerate

    words = remap(raw=raw, edl=edl)
    envelope = {"edl_hash": edl_hash, "words": words}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote envelope with {len(words)} word entries to {args.out} (edl_hash {edl_hash[:8]})", file=sys.stderr)
    return 0
```

- [ ] **Step 5: Update `scaffold_hyperframes.py` to read envelope and emit bare array for HF**

The HF skill expects `transcript.json` as a bare array (per `references/transcript-guide.md`). Our scaffold copies `final.json` to `transcript.json` directly (`scaffold_hyperframes.py:196-197`). Since `final.json` is now an envelope, the copy must extract `words`.

Edit `scripts/scaffold_hyperframes.py`. Find lines 195-197:

```python
    # Copy transcript
    if final_json.exists():
        shutil.copyfile(final_json, hf / "transcript.json")
```

Replace with:

```python
    # Copy transcript: final.json is an envelope ({edl_hash, words}); HF expects a bare array.
    if final_json.exists():
        envelope = json.loads(final_json.read_text(encoding="utf-8"))
        words = envelope["words"] if isinstance(envelope, dict) else envelope
        (hf / "transcript.json").write_text(
            json.dumps(words, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
```

- [ ] **Step 6: Run the new remap tests + the existing scaffold tests**

```bash
python -m pytest tests/test_remap_transcript.py tests/test_scaffold_hyperframes.py -v 2>&1 | tail -20
```

Expected: all pass. The scaffold end-to-end test (`test_scaffold_end_to_end`) writes a bare-array `final.json` in the tmp fixture (line 137-139 of `test_scaffold_hyperframes.py`); our new copy code falls back to `envelope` as-is when it's a list, so the test should still pass.

- [ ] **Step 7: Run full test suite for regressions**

```bash
python -m pytest tests/ -v 2>&1 | tail -10
```

Expected: 0 failures.

- [ ] **Step 8: Commit**

```bash
git add scripts/remap_transcript.py scripts/scaffold_hyperframes.py tests/test_remap_transcript.py
git commit -m "fix(remap): stamp final.json with edl_hash and regen on mismatch

When EDL changes (re-cut), the previous final.json contains stale word
mappings against the old EDL. The current 'skip if final.json exists'
glue rule was anti-idempotent: it preserved stale captions.

Stamp final.json on write with sha256 of the EDL content. On re-run,
compare hash; regenerate if mismatch. scaffold_hyperframes.py copies
the envelope's words array into transcript.json for HF (HF expects
a bare array).

Closes the 'final.json on re-cut' gap from retro 2026-05-01 §2.9."
```

### Task B3: Update edit-episode.md rebuild guidance

**Files:**
- Modify: `.claude/commands/edit-episode.md` (lines 208-220, "Idempotency and rebuild guidance")

- [ ] **Step 1: Read current rebuild guidance**

```bash
sed -n '208,220p' .claude/commands/edit-episode.md
```

Expected output ends with:
```
- **Re-cut:** delete `<EPISODE_DIR>/edit/final.mp4` AND `<EPISODE_DIR>/hyperframes/`. `transcripts/raw.json` stays — **no Scribe re-spend**. The audio tag on `raw.<ext>` survives — **no Audio Isolation re-spend either**.
```

- [ ] **Step 2: Update glue note (line 131) and re-cut paragraph (line 218)**

Edit `.claude/commands/edit-episode.md`. Find line 131:

```markdown
(Skip if `<EPISODE_DIR>/edit/transcripts/final.json` already exists — idempotent.)
```

Replace with:

```markdown
(Skip if `<EPISODE_DIR>/edit/transcripts/final.json` already exists AND its stored `edl_hash` matches the current `edl.json` content. `scripts/remap_transcript.py` self-checks and short-circuits on hash match, so calling it unconditionally is safe and idempotent.)
```

Find line 213 (`### Skip rules` item 3):

```markdown
3. `<EPISODE_DIR>/edit/transcripts/final.json` exists → skip glue remap.
```

Replace with:

```markdown
3. `<EPISODE_DIR>/edit/transcripts/final.json` exists **and its `edl_hash` matches the current `edl.json`** → skip glue remap. (The glue script self-checks this — calling it always is safe.)
```

Find line 218 (`Re-cut:` bullet):

```markdown
- **Re-cut:** delete `<EPISODE_DIR>/edit/final.mp4` AND `<EPISODE_DIR>/hyperframes/`. `transcripts/raw.json` stays — **no Scribe re-spend**. The audio tag on `raw.<ext>` survives — **no Audio Isolation re-spend either**.
```

Replace with:

```markdown
- **Re-cut:** delete `<EPISODE_DIR>/edit/final.mp4` AND `<EPISODE_DIR>/hyperframes/`. `transcripts/raw.json` stays — **no Scribe re-spend**. The audio tag on `raw.<ext>` survives — **no Audio Isolation re-spend either**. `transcripts/final.json` does NOT need manual deletion — `scripts/remap_transcript.py` self-checks the EDL hash and regenerates automatically when EDL changes (per the envelope schema introduced in 2026-05-01).
```

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "docs(brief): document edl_hash self-healing in re-cut guidance

remap_transcript.py now stamps final.json with sha256 of edl.json and
regenerates on mismatch. Update the Phase 3→4 glue note and the
'Idempotency and rebuild guidance' block to reflect that final.json
no longer needs manual deletion on re-cut — the glue is self-healing."
```

### Task B4: Push branch + open PR

- [ ] **Step 1: Push**

```bash
git push -u origin fix/recut-final-json-idempotency
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --base main --title "fix(remap): self-healing final.json via EDL hash" --body "$(cat <<'EOF'
## Summary

Stamp `transcripts/final.json` with `sha256(edl.json)` on write. On re-run, compare; regenerate on mismatch. Closes the anti-idempotent 'skip if final.json exists' gap (retro 2026-05-01 §2.9) without requiring users or briefs to manually delete the file on re-cut.

## Test plan

- [x] `tests/test_remap_transcript.py` — 2 new tests cover envelope shape + regen-on-mismatch.
- [x] `tests/test_scaffold_hyperframes.py` — existing `test_scaffold_end_to_end` still passes (bare-array fallback in copy code preserves backward compat for fixtures).
- [x] Full suite green: `python -m pytest tests/ -v`.
- [ ] Reviewer: pull, run pytest, confirm 0 failures.
EOF
)"
```

### Task B5: Merge PR-4, clean up worktree

- [ ] **Step 1: Merge with squash**

```bash
gh pr merge $PR_NUM --squash --delete-branch
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio
git worktree remove .worktrees/fix-recut-final-json
git branch -D fix/recut-final-json-idempotency
git checkout main
git pull origin main --ff-only
```

---

## Phase C — PR-2: Phase 4 brief — reading + Step 2 + catalog + captions

### Task C1: Create worktree

- [ ] **Step 1: Create branch worktree**

```bash
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio
git worktree add .worktrees/phase4-brief-canon-reading -b feat/phase4-brief-canon-reading
```

All subsequent Task C* commands run from `.worktrees/phase4-brief-canon-reading/`.

### Task C2: Insert mandatory reading list block

**Files:**
- Modify: `.claude/commands/edit-episode.md:147-149` (Phase 4 brief opening — before Visual Identity Gate)

- [ ] **Step 1: Read current opening**

```bash
sed -n '147,154p' .claude/commands/edit-episode.md
```

Expected: shows the brief intro starting with `> Read \`~/.agents/skills/hyperframes/SKILL.md\` first, ...`.

- [ ] **Step 2: Replace lines 149-151 to inject the reading block**

Find the line ending at 151 (just before `> **Visual Identity Gate**`):

```markdown
> Read `~/.agents/skills/hyperframes/SKILL.md` first, then build a HyperFrames composition in `<EPISODE_DIR>/hyperframes/`. The project is **already scaffolded** — do not run `npx hyperframes init`. The scaffolded `index.html`, `package.json`, `hyperframes.json`, `meta.json` are in place. The video and audio are wired as a canonical `<video muted playsinline> + <audio>` pair both pointing at `../edit/final.mp4`. The word-level transcript (output-timeline, hyperframes captions schema) is at `hyperframes/transcript.json`.
>
> The author's script is at `<EPISODE_DIR>/script.txt` — use it as the source of truth for caption wording when it diverges from the transcript.
```

Replace with:

```markdown
> Read `~/.agents/skills/hyperframes/SKILL.md` first, then build a HyperFrames composition in `<EPISODE_DIR>/hyperframes/`. The project is **already scaffolded** — do not run `npx hyperframes init`. The scaffolded `index.html`, `package.json`, `hyperframes.json`, `meta.json` are in place. The video and audio are wired as a canonical `<video muted playsinline data-has-audio="false"> + <audio>` pair both pointing at `final.mp4` (sibling hardlink). The word-level transcript (output-timeline, hyperframes captions schema) is at `hyperframes/transcript.json`.
>
> The author's script is at `<EPISODE_DIR>/script.txt` — use it as the source of truth for caption wording when it diverges from the transcript.
>
> **Required reading before composing — verbatim list.** Read these in order, then confirm in your first response which files were read. Empty confirmation = stop, do not proceed.
> 1. `~/.agents/skills/hyperframes/SKILL.md` (you already opened this — re-confirm).
> 2. `~/.agents/skills/hyperframes/references/video-composition.md` — *Always read* (canon).
> 3. `~/.agents/skills/hyperframes/references/typography.md` — *Always read* (canon).
> 4. `~/.agents/skills/hyperframes/references/motion-principles.md` — *Always read* (canon).
> 5. `~/.agents/skills/hyperframes/references/beat-direction.md` — *Always read for multi-scene compositions* (canon).
> 6. `~/.agents/skills/hyperframes/references/transitions.md` — *Always read for multi-scene compositions* (canon).
> 7. `~/.agents/skills/hyperframes/references/captions.md` — orchestrator-house addition. Canon treats captions as conditional ("when adding any text synced to audio"); this orchestrator's pipeline always produces audio-synced text, so the conditional trigger always fires, making it effectively mandatory here.
> 8. `~/.agents/skills/hyperframes/references/transcript-guide.md` — orchestrator-house addition for the same reason.
>
> **Step 2 — Prompt expansion (mandatory for multi-scene).** After reading the canon, run Step 2 per `references/prompt-expansion.md`. Output goes to `<EPISODE_DIR>/hyperframes/.hyperframes/expanded-prompt.md` (canonical path and name per `references/prompt-expansion.md:57-68`). This artifact MUST exist before any composition HTML is written. If it does not exist after Step 2, you have not run Step 2.
>
> **Catalog discovery — orchestrator-house gate.** Before writing any custom HTML for a beat, run `npx hyperframes catalog --json > .hyperframes/catalog.json` from `<EPISODE_DIR>/hyperframes/`. For each narrative beat, write one sentence in `DESIGN.md` → `Beat→Visual Mapping`: which catalog block was considered (or installed via `npx hyperframes add <name>`), and why custom HTML is justified. Empty per-beat justification list = stop. (Note: this is an orchestrator productivity rule, not HF canon — canon mentions `catalog` only in Step 1 / Design Picker context.)
```

- [ ] **Step 3: Verify the insertion**

```bash
grep -n "Required reading before composing" .claude/commands/edit-episode.md
grep -n "Step 2 — Prompt expansion" .claude/commands/edit-episode.md
grep -n "Catalog discovery — orchestrator-house gate" .claude/commands/edit-episode.md
```

Expected: each grep returns exactly one line number, all in ascending order, all between line 150 and ~175.

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "brief(phase4): mandatory canon reading + Step 2 + catalog gate

Phase 4 brief now enforces:
- Verbatim 'Required reading' list of HF SKILL.md 'Always read' refs
  + 2 orchestrator-house additions (captions, transcript-guide).
- Step 2 prompt expansion artifact at canonical
  .hyperframes/expanded-prompt.md.
- Pre-custom-HTML catalog scan with per-beat justification.

First-response confirmation gates the composition phase. Refs: spec
2026-05-01-section7-fixes-design.md, retro 2026-05-01 §3.2, §3.3, §3.4."
```

### Task C3: Replace captions paragraph + add output-checklist captions item + add post-launch StaticGuard listener

**Files:**
- Modify: `.claude/commands/edit-episode.md` (the `Subtitles` paragraph in Phase 3 brief at line 95, the Phase 4 Output Checklist around line 168, and Studio launch block around line 188)

- [ ] **Step 1: Update the Phase 3 brief subtitles paragraph (line 95)**

Edit `.claude/commands/edit-episode.md`. Find line 95:

```markdown
> **Subtitles.** Do NOT burn subtitles into `final.mp4`. Omit the `subtitles` field from EDL **and** pass `--no-subtitles` to `helpers/render.py` (defense in depth — canon §8 of `docs/cheatsheets/video-use.md`). Do not pass `--build-subtitles`. Captions are produced downstream by Phase 4 (HyperFrames `references/captions.md`).
```

Replace with:

```markdown
> **Subtitles.** Do NOT burn subtitles into `final.mp4`. Omit the `subtitles` field from EDL **and** pass `--no-subtitles` to `helpers/render.py` (defense in depth — canon §8 of `docs/cheatsheets/video-use.md`). Do not pass `--build-subtitles`. Captions are produced by Phase 4 (HyperFrames `references/captions.md`) — they are **mandatory in this orchestrator** (see Phase 4 brief; the only acceptable reason to omit captions is an explicit user request, never a Skill-author decision).
```

- [ ] **Step 2: Add captions reminder + house-rule clarification in Phase 4 brief**

Find this line (currently around line 165 — after the multi-scene narrative composition paragraph block):

```markdown
> **Output Checklist (canonical):**
```

Insert **above** that line (before "Output Checklist"):

```markdown
> **Captions track — orchestrator-mandatory.** A captions track is mandatory in every composition produced by this orchestrator. Use `hyperframes/transcript.json` (already prepared as the bare-array per-word schema HF expects) per `references/captions.md`. Caption styling adapts to the chosen visual identity. The only acceptable reason to omit captions is an explicit user request — never a Skill-author decision documented in `DESIGN.md` → "What NOT to Do". (Canon treats captions as conditional; this is an orchestrator-house rule because every episode here produces audio-synced text, so the conditional trigger always fires.)
>
```

- [ ] **Step 3: Add captions verification to Output Checklist**

Find the Output Checklist block (currently lines 168-174). Find item 3:

```markdown
> 3. `npx hyperframes inspect` — passes, or every reported overflow is intentional and marked.
```

Insert a new item **after** item 3 and renumber subsequent items:

```markdown
> 4. **Captions track present.** `index.html` references `transcript.json` and renders captions via the `references/captions.md` canonical pattern. `grep -c "transcript.json" <EPISODE_DIR>/hyperframes/index.html` ≥ 1.
```

The previous items 4 and 5 (`animation-map.mjs` and `contrast-report.mjs`) become 5 and 6. Renumber explicitly when editing.

- [ ] **Step 4: Add post-launch StaticGuard fail-fast in Studio launch block**

Find the Studio launch block (currently around line 188-192). Find:

```markdown
> Report `http://localhost:3002` to the user.
```

Replace with:

```markdown
> **Post-launch StaticGuard check.** After the studio is up, tail `.hyperframes/preview.log` for the first 5 seconds. If any line matches `[StaticGuard]`, report the message verbatim and **stop without handing off to the user** — a StaticGuard warning post-PR-1 indicates a real new contract violation, not the legacy doubling issue we already fixed.
>
> Bash:
> ```bash
> for i in 1 2 3 4 5; do sleep 1; if grep -q '\[StaticGuard\]' .hyperframes/preview.log 2>/dev/null; then echo "StaticGuard fired:"; grep '\[StaticGuard\]' .hyperframes/preview.log; exit 1; fi; done
> ```
>
> PowerShell:
> ```powershell
> 1..5 | ForEach-Object { Start-Sleep -Seconds 1; if (Select-String -Path .hyperframes\preview.log -Pattern '\[StaticGuard\]' -Quiet -ErrorAction SilentlyContinue) { Write-Host 'StaticGuard fired:'; Select-String -Path .hyperframes\preview.log -Pattern '\[StaticGuard\]'; exit 1 } }
> ```
>
> Only if the 5-second window is clean, report `http://localhost:3002` to the user.
```

- [ ] **Step 5: Verify changes integrate**

```bash
grep -n "Captions track — orchestrator-mandatory" .claude/commands/edit-episode.md
grep -n "Captions track present" .claude/commands/edit-episode.md
grep -n "Post-launch StaticGuard check" .claude/commands/edit-episode.md
```

Expected: 3 grep hits, line numbers in ascending order.

- [ ] **Step 6: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "brief(phase4): captions mandatory + StaticGuard post-launch gate

Captions now framed as orchestrator-house mandate (canon treats them
as conditional; our pipeline's conditional trigger always fires).
Output Checklist gains an explicit captions-track presence check.
Studio launch tails preview.log for [StaticGuard] for 5s — any hit
fails the phase to catch a future regression after PR-1's fix."
```

### Task C4: Push, open PR, merge, clean up

- [ ] **Step 1: Push**

```bash
git push -u origin feat/phase4-brief-canon-reading
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --base main --title "brief(phase4): canon reading list + Step 2 + catalog + captions mandate" --body "$(cat <<'EOF'
## Summary

Phase 4 brief in `.claude/commands/edit-episode.md` now:

1. Enforces verbatim mandatory-reading list of HF canon "Always read" + 2 orchestrator-house additions (captions, transcript-guide), with first-response confirmation gate.
2. Mandates Step 2 prompt expansion with canonical artifact at `.hyperframes/expanded-prompt.md`.
3. Requires `npx hyperframes catalog` scan + per-beat custom-HTML justification in `DESIGN.md`.
4. Frames captions as orchestrator-house mandate (canon-conditional always fires here).
5. Adds StaticGuard post-launch fail-fast on `.hyperframes/preview.log` to catch regressions after PR-1.

## Test plan

- [x] All edits target a single markdown file; no code changes; no test impact.
- [ ] Reviewer: read the diff and confirm the verbatim reading list matches `~/.agents/skills/hyperframes/SKILL.md` "Always read" tags.
- [ ] Next `/edit-episode` run: confirm executor reports the verbatim file list in its first response and writes `.hyperframes/expanded-prompt.md` before any composition HTML.
EOF
)"
```

- [ ] **Step 3: Merge + cleanup**

```bash
gh pr merge $PR_NUM --squash --delete-branch
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio
git worktree remove .worktrees/phase4-brief-canon-reading
git branch -D feat/phase4-brief-canon-reading
git checkout main
git pull origin main --ff-only
```

---

## Phase D — PR-3: Phase 4 brief — composition structure

### Task D1: Create worktree

- [ ] **Step 1**

```bash
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio
git worktree add .worktrees/phase4-brief-structure -b feat/phase4-brief-structure
```

### Task D2: Replace multi-scene narrative composition paragraph

**Files:**
- Modify: `.claude/commands/edit-episode.md` (the "Multi-scene narrative composition (mandatory)" paragraph, currently around line 166)

- [ ] **Step 1: Read current paragraph**

```bash
grep -n "Multi-scene narrative composition (mandatory)" .claude/commands/edit-episode.md
```

Expected: one line number around 166.

- [ ] **Step 2: Replace the paragraph**

Find the `> **Multi-scene narrative composition (mandatory).** ...` paragraph (single long bullet). Replace its entire body with:

```markdown
> **Multi-scene narrative composition (mandatory).** Read `<EPISODE_DIR>/script.txt` and identify ≥ 3 narrative beats. Compositions MUST be multi-scene with ≥ 3 beat-derived scenes. Apply Scene Transitions canon (`SKILL.md` §"Scene Transitions" — non-negotiable: always use transitions, every scene gets entrance animations, never exit animations except on the final scene).
>
> **Sub-composition split — strong recommendation.** Each beat ≥ 3 SHOULD live in `compositions/beat-{N}-{slug}.html`, mounted from the root via `<div data-composition-id data-composition-src="compositions/beat-N.html">` per `SKILL.md:149-185`. Root `index.html` SHOULD stay ≤ 100 lines (video + audio + captions + mount points). Basis: HF lint warning `composition_file_too_large` ("Agents produce better results when large scenes are split into smaller sub-compositions"). Treat the warning as real guidance, not cosmetic — the lint exists because authors produce better small files than big monoliths.
>
> **Parallel-agent dispatch — orchestrator pattern.** Beats are independent and parallelizable. Consider dispatching beat authoring to parallel sub-agents via the `superpowers:dispatching-parallel-agents` skill (this is an orchestrator pattern via superpowers, NOT HF canon).
>
> **Per-beat transition mechanism — explicit choice required.** Scene Transitions canon requires entrance animations and forbids exit animations on non-final beats. With translucent overlays (e.g., glass panels), an entrance-only-cover does NOT visually clear the previous scene — the older scene shows through the new translucent panels. For each inter-beat boundary, document one mechanism in `DESIGN.md` → `Beat→Visual Mapping`:
> - **CSS clip-path / mask transition** — canon-allowed, simpler (`transitions.md:85-95` — "CSS transitions are simpler... Choose based on the effect you want, not based on which is easier").
> - **Shader transition** via `npx hyperframes add transition-shader-<name>` — canon-allowed, more capable.
> - **Final-scene fade** — only between beat-N and the LAST beat (Scene Transitions canon allows fade only on the final scene).
>
> Do not rely on entrance-only-cover with translucent panels. (Canon allows CSS, shader, and final-fade equally — pick one explicitly per boundary, don't blanket-mandate any single mechanism.)
>
> **Catalog discovery before custom HTML.** Already covered above — see "Catalog discovery — orchestrator-house gate" earlier in this brief. For each beat, document in `DESIGN.md` → `Beat→Visual Mapping` whether you installed a registry block (`npx hyperframes add <name>`) or chose custom HTML, with one-sentence justification.
```

- [ ] **Step 3: Verify the substitution**

```bash
grep -n "Sub-composition split — strong recommendation" .claude/commands/edit-episode.md
grep -n "Parallel-agent dispatch — orchestrator pattern" .claude/commands/edit-episode.md
grep -n "Per-beat transition mechanism — explicit choice required" .claude/commands/edit-episode.md
```

Expected: 3 hits, ascending line numbers, all close together.

- [ ] **Step 4: Verify the old language is gone**

```bash
grep -n "shader-transition" .claude/commands/edit-episode.md
```

Expected: 1 hit at most, in the new "Per-beat transition mechanism" section as an option (not a mandate). If there are mentions of "shader required" or "must install transition-shader" in mandate language, hunt them down — there shouldn't be any left.

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "brief(phase4): sub-composition + parallel dispatch + explicit transition

Replace 'Multi-scene narrative composition (mandatory)' single paragraph
with four explicit blocks:
- Sub-composition split as strong recommendation (lint-warning basis).
- Parallel-agent dispatch as orchestrator pattern via superpowers
  (clearly NOT HF canon).
- Per-beat transition-mechanism choice (CSS / shader / final-fade)
  with translucent-overlay rationale. No single mechanism mandated —
  canon allows all three.
- Catalog discovery cross-reference.

Refs: spec 2026-05-01-section7-fixes-design.md, retro §2.3 / §3.7."
```

### Task D3: Push, PR, merge, cleanup

- [ ] **Step 1**

```bash
git push -u origin feat/phase4-brief-structure
gh pr create --base main --title "brief(phase4): sub-compositions + parallel dispatch + explicit transition mechanism" --body "$(cat <<'EOF'
## Summary

Phase 4 brief composition-structure block now:

1. Recommends per-beat sub-composition split into `compositions/beat-N.html` (HF lint warning basis, not canon mandate).
2. Hints at parallel-agent dispatch via superpowers (clearly NOT HF canon).
3. Replaces the previous draft's shader-mandate for translucent overlays with an explicit per-beat choice: CSS / shader / final-fade. Canon (`transitions.md:85-95`) allows all three equally.

## Test plan

- [x] Documentation-only edit; no code, no tests.
- [ ] Reviewer: confirm no language mandates a specific transition type for translucent overlays.
- [ ] Next `/edit-episode` run on a multi-beat episode: confirm executor produces `compositions/beat-N.html` files and a slim root `index.html`, with per-beat-boundary transition rows in DESIGN.md.
EOF
)"
gh pr merge $PR_NUM --squash --delete-branch
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio
git worktree remove .worktrees/phase4-brief-structure
git branch -D feat/phase4-brief-structure
git checkout main && git pull origin main --ff-only
```

---

## Phase E — PR-5: CLAUDE.md Windows bootstrap note

### Task E1: Create worktree, edit, commit, PR, merge

- [ ] **Step 1: Create worktree**

```bash
cd C:/Users/sidor/repos/anticodeguy-video-editing-studio
git worktree add .worktrees/docs-windows-bootstrap -b docs/claudemd-windows-bootstrap
cd .worktrees/docs-windows-bootstrap
```

- [ ] **Step 2: Read current "Skill copies" block**

```bash
grep -n "Skill copies: docs vs. runnable" CLAUDE.md
```

Note the line number — call it `LINE`. The block extends from there until the next blank-line-separated paragraph.

- [ ] **Step 3: Append the Windows note**

Edit `CLAUDE.md`. Find the closing of the "Skill copies: docs vs. runnable" block — the last paragraph of that block ends with `... helpers should always be read from the global location — that's their canonical home.`

After that line, append a blank line and the following:

```markdown
**Known Windows blocker:** both `animation-map.mjs` and `contrast-report.mjs` bootstrap `@hyperframes/producer` (and `sharp` for contrast-report) via `npm.cmd` `spawnSync`, which on Windows-Node yields `EINVAL` (a long-standing Node.js Windows quirk on `.cmd` shims). Workaround: once per project, `npm i -D @hyperframes/producer@<exact-version> sharp@<exact-version>` inside the `hyperframes/` project directory. The exact versions are taken from the script's missing-deps error message. After this one-time install, both helpers run without setting `HYPERFRAMES_SKILL_BOOTSTRAP_DEPS=1`. Refs: retro 2026-05-01 §2.7.
```

- [ ] **Step 4: Verify**

```bash
grep -c "Known Windows blocker" CLAUDE.md
```

Expected: `1`.

- [ ] **Step 5: Commit, push, PR, merge, cleanup**

```bash
git add CLAUDE.md
git commit -m "docs(claudemd): document Windows EINVAL workaround for HF helpers

animation-map.mjs and contrast-report.mjs bootstrap deps via npm.cmd
spawnSync, which yields EINVAL on Windows-Node. Workaround: once-per-
project npm i -D of the missing peer deps. From retro 2026-05-01 §2.7."
git push -u origin docs/claudemd-windows-bootstrap
gh pr create --base main --title "docs(claudemd): Windows EINVAL workaround for HF helper scripts" --body "$(cat <<'EOF'
## Summary

Append a 'Known Windows blocker' paragraph to the 'Skill copies: docs vs. runnable' block in CLAUDE.md, documenting the once-per-project npm install workaround for animation-map.mjs and contrast-report.mjs bootstrap failure on Windows.

## Test plan

- [x] Pure docs edit.
- [ ] Reviewer: confirm the wording is accurate vs. retro 2026-05-01 §2.7.
EOF
)"
gh pr merge $PR_NUM --squash --delete-branch
cd ../..
git worktree remove .worktrees/docs-windows-bootstrap
git branch -D docs/claudemd-windows-bootstrap
git checkout main && git pull origin main --ff-only
```

---

## Phase F — Upstream HyperFrames issues

These are async, no orchestrator code changes. Each issue follows the same pattern as #586 — minimal-repro repo + filed issue.

### Task F1: Snapshot portrait viewport (retro §2.5)

- [ ] **Step 1: Build minimal repro**

```bash
mkdir -p C:/Users/sidor/repos/hyperframes/repro-snapshot-portrait
cd C:/Users/sidor/repos/hyperframes/repro-snapshot-portrait
npx hyperframes init . --non-interactive --example blank
```

- [ ] **Step 2: Generate a portrait test video**

```bash
ffmpeg -y -f lavfi -i "color=c=red:s=1080x1920:r=30:d=5" -f lavfi -i "sine=f=440:duration=5" -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest video.mp4
```

- [ ] **Step 3: Edit `index.html` to portrait dimensions**

Set `data-width="1080"`, `data-height="1920"`, body width 1080px and height 1920px in CSS, viewport meta to `width=1080, height=1920`. Add a `<video>` element pointing to `video.mp4` with `data-has-audio="false" muted playsinline`. Place a visible block at `bottom: 100px` (so it's clearly in the lower 840px that the viewport bug clips).

Concrete patch — replace the `<!-- Add your clips here ... -->` comment block with:

```html
      <video id="el-v" class="clip" data-start="0" data-duration="5" data-track-index="0"
             src="video.mp4" data-has-audio="false" muted playsinline
             style="position:absolute;inset:0;width:1080px;height:1920px;object-fit:cover;"></video>
      <div id="bottom-marker" class="clip" data-start="0" data-duration="5" data-track-index="1"
           style="position:absolute;left:50%;bottom:100px;transform:translateX(-50%);font-size:96px;color:#fff;background:#000;padding:24px;">
        BOTTOM
      </div>
```

Also update body and root: `width: 1080px; height: 1920px;`, `data-width="1080" data-height="1920"`.

- [ ] **Step 4: Run snapshot, capture failure**

```bash
npx hyperframes snapshot --at 1
ls *.png 2>&1
```

Expected: a PNG appears, but it is 1920×1080 landscape (`identify` or `ffprobe` it). The "BOTTOM" marker is NOT visible — it sits at y=1820 in the 1080×1920 layout, which is below the captured viewport's lower edge (which sits at y=1080).

- [ ] **Step 5: Push to public repo and file issue**

```bash
git init -q -b main
git add -A
git -c user.name="sidorovanthon" -c user.email="a@preencipium.com" commit -q -m "minimal repro: snapshot defaults to 1920x1080 viewport, clips portrait composition"
gh repo create sidorovanthon/hyperframes-repro-snapshot-portrait --public --source=. --push --description "Minimal repro: npx hyperframes snapshot defaults to 1920x1080 regardless of root data-width/data-height"
```

Then file the issue at `heygen-com/hyperframes`:

```bash
gh issue create --repo heygen-com/hyperframes --title "\`hyperframes snapshot\` ignores root \`data-width\`/\`data-height\`, defaults to 1920×1080 viewport" --body "$(cat <<'EOF'
## Describe the bug

`npx hyperframes snapshot` captures at a hardcoded 1920×1080 viewport, regardless of the composition's root `data-width` / `data-height`. For portrait compositions (1080×1920), the body renders in the upper-left of the capture area, and the lower 840px (everything below y=1080 in the composition) is clipped.

There is no `--width` / `--height` flag to override.

## Link to reproduction

https://github.com/sidorovanthon/hyperframes-repro-snapshot-portrait

## Steps to reproduce

1. Clone the repo above.
2. `npm install`
3. `npx hyperframes snapshot --at 1`
4. Open the resulting PNG.

## Expected behavior

Either auto-detect viewport from root `data-width` / `data-height`, OR accept `--width` / `--height` flags. Currently neither happens.

## Actual behavior

PNG is 1920×1080. The composition's full 1080×1920 body is not visible — only the upper 1080px is captured. Anything authored at `bottom: <px>` is clipped.

## Suggested fix

`snapshot` should honor the same viewport-sizing logic that `validate` and `inspect` already do (both correctly use the root composition's declared dimensions). At minimum, expose `--width` / `--height` flags as an explicit override.

## Environment

- `hyperframes` 0.4.41
- Windows 11, Node 20.x
EOF
)"
```

### Task F2: validate / contrast-report null:1 false positives (retro §2.6)

- [ ] **Step 1: Build minimal repro with two non-overlapping clips containing text**

Setup: `npx hyperframes init . --non-interactive --example blank` in `C:/Users/sidor/repos/hyperframes/repro-contrast-out-of-clip`. Edit `index.html` to have two text divs on the same track:

```html
      <div id="t1" class="clip" data-start="0" data-duration="2" data-track-index="1"
           style="font-size:64px;color:#fff;background:#000;padding:40px;">A</div>
      <div id="t2" class="clip" data-start="3" data-duration="2" data-track-index="1"
           style="font-size:64px;color:#fff;background:#000;padding:40px;">B</div>
```

Composition `data-duration="5"`. Set body bg to `#fff` (so when the sampler reads computed colors of an inactive clip, it gets white-on-white-ish that resolves to NaN ratio).

- [ ] **Step 2: Run validate**

```bash
npx hyperframes validate
```

Expected: at sample timestamps where only `t1` is active (e.g., t=1s), `t2` is sampled and its computed colors come back invalid → `null:1` ratio in the WCAG contrast warnings list. Symmetrically at t=4s for `t1`.

- [ ] **Step 3: Push, file issue**

```bash
git init -q -b main
git add -A
git -c user.name="sidorovanthon" -c user.email="a@preencipium.com" commit -q -m "minimal repro: validate produces null:1 contrast warnings on out-of-clip text elements"
gh repo create sidorovanthon/hyperframes-repro-contrast-out-of-clip --public --source=. --push --description "Minimal repro: hyperframes validate samples ALL text elements regardless of clip activity, producing null:1 false positives"
gh issue create --repo heygen-com/hyperframes --title "\`validate\` (and \`contrast-report.mjs\`) flag \`null:1\` contrast on out-of-clip text elements at sample timestamps" --body "$(cat <<'EOF'
## Describe the bug

Both `npx hyperframes validate` and the bundled `scripts/contrast-report.mjs` iterate ALL text elements at fixed sample timestamps, regardless of whether each element's `clip` window is active at that timestamp. Out-of-window elements return invalid `getComputedStyle` colors (because the framework hides them via display/visibility), and the contrast samplers compute `NaN` / `null` ratio against those invalid colors.

In a typical multi-clip composition with non-overlapping per-clip text (e.g., 6 sequential narrative beats, each with its own text panels), this produces a flood of `null:1` warnings drowning out the real findings.

## Link to reproduction

https://github.com/sidorovanthon/hyperframes-repro-contrast-out-of-clip

## Steps to reproduce

1. Clone the repo, `npm install`.
2. `npx hyperframes validate`.

## Expected behavior

For each sample timestamp, only test text elements whose `data-start ≤ t < data-start + data-duration` (i.e., active at that timestamp). Inactive elements should be excluded from the contrast audit.

## Actual behavior

```
⚠ WCAG AA contrast warnings (N):
  · #t1 "A" — null:1 (need 3:1, t=4s)
  · #t2 "B" — null:1 (need 3:1, t=1s)
  ...
```

## Suggested fix

Filter the element list at sample time by clip activity. The same data the runtime uses for visibility (`data-start` + `data-duration` arithmetic, or the resolved active-set from the player state) can drive the audit's element selection.

## Environment

- `hyperframes` 0.4.41
- Windows 11, Node 20.x
EOF
)"
```

### Task F3: Cross-link upstream issues from #586 thread (optional)

- [ ] **Step 1: Add a comment to #586** with links to F1 and F2 issues so HF maintainers see they're the same author tackling the cluster:

```bash
gh issue comment 586 --repo heygen-com/hyperframes --body "Two more closely-related findings from the same retro: snapshot portrait viewport (#<F1_NUM>) and validate null:1 false positives on out-of-clip elements (#<F2_NUM>). All three came from the same orchestrator-build session; happy to roll repros into one repo if that's easier to triage."
```

(Replace `<F1_NUM>` / `<F2_NUM>` with the issue numbers from F1/F2.)

---

## Self-review

After all phases land, run the following checks:

**1. Spec coverage** — verify each section of `docs/superpowers/specs/2026-05-01-section7-fixes-design.md` has a task or explicit out-of-scope note in this plan:

- ✅ PR-1 audio scaffold → Phase A
- ✅ PR-2 Phase 4 reading + Step 2 + catalog + captions → Phase C
- ✅ PR-3 Phase 4 composition structure → Phase D
- ✅ PR-4 re-cut idempotency → Phase B
- ✅ PR-5 Windows note → Phase E
- ✅ Memory entries (8) → Task A5
- ✅ Upstream issues (§2.5, §2.6) → Tasks F1, F2
- ✅ Memory entries are out-of-tree (clarification) → "Memory entry path convention" block at top of plan

**2. Placeholder scan** — searched the plan for "TBD", "TODO", "implement later", "fill in details", "appropriate error handling". None found.

**3. Type/name consistency:**
- `VIDEO_AUDIO_PAIR_TEMPLATE` consistent across Tasks A2, A3.
- `_edl_hash` function name consistent across Task B2 step 4 and step 6.
- Branch names consistent: `fix/scaffold-audio-data-has-audio` (A), `fix/recut-final-json-idempotency` (B), `feat/phase4-brief-canon-reading` (C), `feat/phase4-brief-structure` (D), `docs/claudemd-windows-bootstrap` (E).
- Worktree paths consistent.

No issues found — plan is ready.
