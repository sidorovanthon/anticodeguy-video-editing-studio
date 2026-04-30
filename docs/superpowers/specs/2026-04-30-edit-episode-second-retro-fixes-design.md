# Design: `/edit-episode` second-retro fixes

**Date:** 2026-04-30
**Source retro:** `retro-2026-04-30-desktop-software-licensing-it-turns-out-is.md`
**Scope:** all 14 retro findings (5 high, 5 medium, 4 low) + meta-issue (retro→brief delivery gap).

## Preamble — why this spec exists

The first retro (`retro.md`) produced a pacing-policy formula that never reached the Phase 3 brief in `.claude/commands/edit-episode.md`. The second retro inherited that gap. **This spec is the single source of truth for all 14 findings; not merging a retro without an accompanying implementation PR is the process discipline that closes the meta-issue.**

Every fix below is verified against the live `SKILL.md` of `video-use` (`~/.claude/skills/video-use/SKILL.md`) and `hyperframes` (`~/.agents/skills/hyperframes/SKILL.md`) per CLAUDE.md's external-skill-canon rule.

## Files touched

1. `.claude/commands/edit-episode.md` — Phase 3 brief, Phase 4 brief, Visual Verification gate.
2. `scripts/scaffold_hyperframes.py` — `class="clip"`, canon track-index, hardlink for `final.mp4`, preview.log location.
3. `docs/cheatsheets/hyperframes.md` — gotchas (scaffold-from-cheatsheet-not-SKILL-example, parent-dir paths).
4. Investigation task (no fix yet): hyperframes-skill scripts bootstrap (animation-map.mjs / contrast-report.mjs).

## Section 1 — Phase 3 brief edits (`.claude/commands/edit-episode.md`)

### 1.1 Inter-phrase pacing policy (retro 1.1)

**Add to Phase 3 brief:**

> **Pacing target.** Aim for 25–35% runtime reduction from source. Treat any inter-phrase silence > 300ms as a cut candidate (canon line 106: silences ≥ 400ms are cleanest cut targets; 150–400ms usable with visual check). Remove all retakes and false starts. If final runtime > 75% of source, note in `project.md` why tighter cuts were not possible.

**Why:** The first retro's loose phrasing produced 9% reduction (one false-start cut, no inter-phrase tightening). Hard Rule 7 governs cut-edge padding (50-100ms drift absorption), not silence trimming — so this is artistic-freedom territory (canon line 14) where the brief must give explicit numerical targets.

### 1.2 No burned-in subtitles (retro 1.2)

**Add to Phase 3 brief:**

> **Subtitles.** Do not include subtitles in `final.mp4`. Omit the `subtitles` field from the EDL **and** pass `--no-subtitles` to `render.py` (defense in depth — canon §8 of `docs/cheatsheets/video-use.md`). Do not pass `--build-subtitles`. Captions are produced downstream by Phase 4 (HyperFrames `references/captions.md`).

**Remove from Phase 3 required outputs:** `master.srt`.

**Why:** video-use canon line 76 makes subtitles opt-in via the `subtitles` EDL field and `--build-subtitles` flag. Two caption tracks (burned-in + Liquid Glass pill) is a bug; Phase 4 owns captions exclusively.

### 1.3 Retake/false-start tie-breaker (retro 1.1 addendum)

**Add to Phase 3 brief:**

> **Retake selection.** When the same beat is recorded multiple times (false-starts, retakes within a single take or across takes), pick the cleanest delivery — fewer slips, better energy, completed thought. If two takes are roughly equal, prefer the later one (the speaker is usually warmed up). Note the choice briefly in EDL `reason`, e.g. `"Last take, first had stutter"` (canon line 269 example).

**Why:** Canon line 150 prioritizes content quality, not position. A pure "always last" rule fails when the first take is cleaner. Adding an explicit tie-breaker removes paralysis without sacrificing canon alignment.

## Section 2 — Phase 4 brief edits (`.claude/commands/edit-episode.md`)

### 2.1 Multi-scene narrative composition (retro 1.3, 2.5, 3.4)

**Add to Phase 4 brief:**

> **Multi-scene narrative composition (mandatory).** Read `script.txt` and identify ≥ 3 narrative beats. Compositions MUST be multi-scene with ≥ 3 beat-derived scenes. Apply Scene Transitions canon (HF SKILL.md §Scene Transitions — non-negotiable rules on transitions, entrances, exits). For each beat, choose either (a) a registry block (`npx hyperframes add` — browse the catalog before authoring custom HTML) or (b) custom motion / overlay justified by the script content. A single-scene caption-only composition is not acceptable.
>
> Document the beat→visual mapping in `DESIGN.md` alongside palette and typography decisions.

**Why:** HF canon line 14 already frames composition by narrative arc + emotional beats; brief makes this explicit. `script.txt` becomes the source of beats, not just caption spell-check (closes 3.4). Registry browsing becomes mandatory (closes 2.5).

### 2.2 Visual Identity Gate strictness (retro 2.2)

**Add to Phase 4 brief:**

> **DESIGN.md substance (Visual Identity Gate).** Per HF SKILL.md §Visual Identity Gate, generate a real DESIGN.md, not a template. Required sections:
> - **Style Prompt** — one-paragraph mood statement.
> - **Colors** — 3-5 hex values with named roles.
> - **Typography** — 1-2 font families.
> - **Visual References** — name ≥ 2 specific real-world references (e.g., "iOS 17 Control Center frosted panels", "Vision Pro spatial UI"). Generic references like "modern minimalist" do not count.
> - **Alternatives Considered** — describe ≥ 1 alternative direction and why it was rejected.
> - **What NOT to Do** — 3-5 anti-patterns specific to this episode.
> - **Beat→Visual Mapping** (from §2.1).

**Why:** Canon's Visual Identity Gate is a hard gate that we MUST NOT pre-empt with our own DESIGN.md generation (CLAUDE.md external-skill-canon rule). Brief raises the substance bar without overriding the gate.

### 2.3 WCAG fail handling — adjust hue, do not retreat (retro 2.3)

**Add to Phase 4 brief:**

> **WCAG fails are resolved by adjusting hue within the palette family (HF SKILL.md §Contrast, lines 311-315). Try ≥ 2 darker/brighter variants of the same hue before considering structural changes. Removing color in favor of weight-only emphasis is a last resort and requires a one-line justification in DESIGN.md.

**Why:** Canon already says "stay within palette family — don't invent a new color, adjust the existing one". The first run abandoned cyan accent on first WCAG fail; brief makes the canonical iterate-on-hue path the explicit default.

## Section 3 — Visual Verification gate (`.claude/commands/edit-episode.md`)

### 3.1 Add mandatory pre-completion verification step (retro 1.5)

**Add to `edit-episode.md` after `lint`/`validate`/`inspect`/animation-map pass and before launching the studio:**

> **Visual verification (mandatory before announcing done).** Use canonical HF tools — no ffmpeg shell-out.
>
> 1. **Canonical layout audit at beat boundaries.** Run `npx hyperframes inspect --at <beat_timestamps>` where beat timestamps come from §2.1 beat→visual mapping. This re-uses the canonical layout/overflow audit on the timestamps that matter narratively, not just default samples.
> 2. **Snapshot at beat boundaries.** Run `npx hyperframes snapshot --at <beat_timestamps>` (canonical PNG screenshots without full render — cheatsheet §"snapshot"). Timestamps: 1s, every narrative-beat boundary from §2.1, last 1s.
> 3. **Three explicit questions per snapshot** — answer in writing in the response, before announcing `Done.`:
>    a. Is the expected beat element visible (registry block / scene card / overlay from §2.1)?
>    b. Any unintended z-overlap (caption covering a key element, scene exit leaving residue)?
>    c. Is the A-roll video accidentally occluded by a semi-transparent overlay?
> 4. Only after this list is in the response, announce `Done.`

**Why:** Canon's Output Checklist (HF SKILL.md line 279-283) covers layout, contrast, choreography invariants — not narrative coherence. This gate combines `inspect --at` (canonical, free layout-bonus on the right timestamps) with manual narrative review. Cost is small; cost of "shipped a flat composition with caption overlap" is large.

## Section 4 — `scripts/scaffold_hyperframes.py` edits

### 4.1 Add `class="clip"` to video and audio elements (retro 1.4)

The framework's media-state-machine only manages elements with `class="clip"` (per-project HyperFrames `CLAUDE.md` Key Rule 2). Without it, `muted` is a passive HTML attribute the studio's media controller may not enforce → phantom audio doubling. The `npx hyperframes init` template applies `class="clip"`; our manual scaffold dropped it when we replaced init in retro 1.

**Update `VIDEO_AUDIO_PAIR_TEMPLATE`:**

```python
VIDEO_AUDIO_PAIR_TEMPLATE = """      <video id="el-video" class="clip" data-start="0" data-track-index="0"
             src="{src}" muted playsinline></video>
      <audio id="el-audio" class="clip" data-start="0" data-track-index="2"
             src="{src}" data-volume="1"></audio>"""
```

Note `data-track-index="2"` for audio — matches HF SKILL.md line 184 canon example. (Same-track clips cannot overlap; spacing tracks reduces accidental conflicts when overlays are added.)

### 4.2 Hardlink `final.mp4` into the hyperframes/ directory (retro 2.1)

Currently scaffold writes `<video src="../edit/final.mp4">`. HF lint/validate 404 on parent-directory paths. Manual workaround in last episode was `mklink /H hyperframes/final.mp4 ../edit/final.mp4`.

**Add to scaffold:**

```python
def _hardlink_final_mp4(episode_dir: Path) -> None:
    src = episode_dir / "edit" / "final.mp4"
    dst = episode_dir / "hyperframes" / "final.mp4"
    if dst.exists():
        return  # idempotent
    if os.name == "nt":
        # Windows: mklink /H requires cmd
        subprocess.run(
            ["cmd", "/c", "mklink", "/H", str(dst), str(src)],
            check=True,
        )
    else:
        os.link(src, dst)
```

**Update scaffold call site** to pass `video_src="final.mp4"` instead of `"../edit/final.mp4"`.

**Why hardlink, not copy:** zero additional disk vs ~30-100MB per episode for copy. Cross-platform: Windows `mklink /H`, Unix `os.link`.

### 4.3 Preview log to `.hyperframes/` (retro 3.1)

When orchestrator launches `npx hyperframes preview` in background, redirect stdout/stderr to `.hyperframes/preview.log` instead of `hyperframes/preview.log` in episode root. `.hyperframes/` is canon-gitignored.

## Section 5 — `docs/cheatsheets/hyperframes.md` updates

The cheatsheet is **already correct** on `class="clip"` (§"Видео и аудио" examples include it; §"Data-атрибуты" lists it required; §"Anti-patterns" line 936 catches its omission). The orchestrator scaffold drifted from the cheatsheet by porting from the main `SKILL.md` video/audio example, which omits `class="clip"`.

Add a single gotcha block near the §"Setup / окружение" section:

- **Scaffolding from canon: prefer this cheatsheet over `SKILL.md`'s `<video>`/`<audio>` example.** The main `SKILL.md` example (lines 171-188) omits `class="clip"`, which is required per per-project `CLAUDE.md` Key Rule 2 and enforced by `lint`. The cheatsheet examples in §"Видео и аудио" are the source of truth for media-element scaffolding.
- **Parent-directory paths (`../`) in `src` attributes break `lint`/`validate`.** All media referenced from `index.html` must live alongside it (or in subdirectories). Hardlinks (`mklink /H` on Windows, `os.link` on Unix) are zero-disk-cost workarounds when the file's logical home is a sibling directory.

## Section 6 — Investigation task (retro 2.4) — RESOLVED 2026-04-30

**Outcome:** Not blocked. The brief was wrong to invoke the global skill copy.

`~/.agents/skills/hyperframes/scripts/animation-map.mjs` and `contrast-report.mjs` are documentation-surface artifacts shipped by `npx hyperframes skills`. They are not runnable from that location because their `package-loader.mjs` walks ancestors of `HERE` looking for a `hyperframes`/`@hyperframes/cli` `package.json`, and the global skill dir has no such ancestor.

The same scripts ship inside the npm package at `<project>/node_modules/hyperframes/dist/skills/hyperframes/scripts/<name>.mjs`. Invoked from there, `node_modules/hyperframes/package.json` is on the ancestor chain, the version probe resolves, and the scripts run end-to-end. Verified on `2026-04-30-desktop-software-licensing-it-turns-out-is` — `animation-map.mjs` produces the full timeline output.

**Fix landed:** `.claude/commands/edit-episode.md` Phase 4 Output Checklist items 4 and the orchestrator-imposed contrast-report check now point at the bundled `<hyperframes-dir>/node_modules/hyperframes/dist/skills/hyperframes/scripts/...` path.

**Prevention rule** added to `CLAUDE.md` §"Skill copies: docs vs. runnable": for any external-skill helper script, default to the bundled in-project copy; the global `~/.agents/...` / `~/.claude/...` copy is for SKILL.md / patterns / cheatsheets only. Verify executability empirically (run it) before declaring a helper broken.

**Optional (not in this PR):** an upstream nicety — make the global skill copy of these scripts self-bootstrapping (defer `hyperframesPackageSpec` evaluation until the missing-package branch, or fall back to `npm view hyperframes version`). Low priority since the bundled copy is the canonical execution path.

## Section 7 — Verification after merge

These do not change scope but must be checked once §4.1 lands:

- **Phantom audio doubling (retro 1.4):** verify it disappears in studio after `class="clip"` is applied. If it persists → minimally reproduce in a clean HF project, file upstream issue.
- **`data-has-audio` warning (retro 3.3):** verify whether StaticGuard still emits it. If yes → diagnose separately (separate issue, not in this PR).

## Out of scope

- Patching upstream `video-use` or `hyperframes` repos (CLAUDE.md prohibition).
- Generating `DESIGN.md` ourselves before Phase 4 starts (would pre-empt Visual Identity Gate).
- Touching the security hook that scans file bodies on write (working as intended).

## Idempotency notes (for re-running on the affected episode)

After merging this spec's PR, to apply fixes to `2026-04-30-desktop-software-licensing-it-turns-out-is`:

```sh
rm episodes/<slug>/edit/final.mp4
rm episodes/<slug>/edit/master.srt
rm -rf episodes/<slug>/hyperframes/
/edit-episode <slug>
```

`transcripts/raw.json` survives → no re-spend on Scribe. `ANTICODEGUY_AUDIO_CLEANED` tag on `raw.mp4` survives → no re-spend on ElevenLabs Audio Isolation. Phase 1 + 0.5 are skipped; Phases 3 + 4 re-run with the new briefs.
