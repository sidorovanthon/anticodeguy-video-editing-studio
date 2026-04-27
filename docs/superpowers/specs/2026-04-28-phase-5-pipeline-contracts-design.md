# Phase 5 — Pipeline Contracts Hardening (Design)

**Date:** 2026-04-28
**Status:** Approved (brainstorming)
**Predecessor:** Phase 4 (`phase-4-first-episode`, commit f9ccca4)
**Successor:** Phase 6 — agentic graphics planner (brief produced by this phase)

## 1. Goal and non-goals

**Goal.** Eliminate the Stage 1 → Stage 2 contract drift class of bugs by
making Stage 1 emit a single typed master-aligned bundle, consumed by Stage 2
through a typed loader. Rename the `full` scene mode to `broll` and lock all
four scene modes behind a TypeScript union.

**Non-goals.**
- Agentic graphics planner — Phase 6 (this phase produces a brief, not the planner).
- Audio pipeline integration, captions ground-truth from script.txt,
  final-render survival at 1440×2560 @ 60 fps, per-iteration grade preview
  frames automation. All deferred.
- Re-running, re-rendering, or migrating the pilot episode
  (`2026-04-27-desktop-software-licensing-it-turns-out`).
- Any new editorial rule changes.

**Success criteria.**
- `episodes/<slug>/master/bundle.json` exists after Stage 1, contains
  everything Stage 2 needs about master.
- Stage 2 has zero reads of `transcript.json` (raw form), zero reads of
  `cut-list.md` for timing, zero references to `audio_duration_secs`.
- TypeScript code uses a `SceneMode` union; the literal `'full'` no longer
  appears in source; `'broll'` does.
- All existing tests pass; new tests cover bundle schema, loader, and
  scene-mode rename.
- A Phase 6 brief exists at the path in §7.

## 2. Scope

Phase 5 ships three things:

1. **Master-aligned bundle** at the Stage 1 → Stage 2 boundary, consumed via
   a typed loader.
2. **Scene-mode TypeScript union** (`'head' | 'split' | 'broll' | 'overlay'`);
   rename of `full` → `broll` in code, fixtures, and (via promote at phase
   close) in `standards/motion-graphics.md`.
3. **Phase 6 brief** at
   `docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md` —
   message-in-a-bottle for the planner.

## 3. Bundle schema

`episodes/<slug>/master/bundle.json`:

```jsonc
{
  "schemaVersion": 1,
  "slug": "2026-04-27-...",
  "master": {
    "durationMs": 52700,        // ffprobe on master.mp4, authoritative
    "width": 1440,
    "height": 2560,
    "fps": 60
  },
  "boundaries": [                // EDL cumulative, master-aligned
    { "atMs": 0,     "kind": "start" },
    { "atMs": 8200,  "kind": "seam" },
    { "atMs": 17450, "kind": "seam" },
    // ...
    { "atMs": 52700, "kind": "end" }
  ],
  "transcript": {
    "language": "en",
    "words": [                   // master-aligned, post-EDL remap
      { "text": "Desktop", "startMs": 120, "endMs": 540 }
      // ...
    ]
  }
}
```

Notes:
- `master.durationMs` is authoritative; nothing else (transcript, EDL)
  computes duration.
- `boundaries` are derived from EDL cumulative range lengths in master-time.
  First boundary always `atMs: 0`, last always `master.durationMs`.
- `words` are master-aligned already — Stage 1 runs the remap before writing.
  Stage 2 never re-remaps.
- Field naming: camelCase, all timestamps suffix `Ms`. Differs from current
  ad-hoc `start_ms`/`end_ms`; addressed in §5.
- `schemaVersion: 1` — explicit, so we can bump non-breaking later.

## 4. Where the bundle is generated

Decision: bundle writer in TypeScript, invoked from `run-stage1.sh` after
`_render_edl.py` finishes.

Rationale: the master-time remap function lives in TS today (added during
the pilot's hot-fix path). Porting to Python is rework with no payoff.
`run-stage1.sh` already orchestrates a multi-language pipeline (Python EDL
render); adding a TS bundle writer step at the tail is consistent.

Stage 1 is "done" only after the bundle write succeeds. If the writer fails,
Stage 1 is failed.

The remap function moves from Stage 2's hot-fix location to a Stage 1 module
(`tools/compositor/src/stage1/`). Stage 2 callers of the remap are deleted
(they consume the bundle's already-master-aligned words).

## 5. Stage 2 refactor

Today Stage 2 reads:
- `transcript.json` — raw ElevenLabs format, sec timestamps,
  `audio_duration_secs`.
- `edl.json` — cumulative timing.
- `cut-list.md` — parsed for `at_ms=` markers (the contract drift).
- `seam-plan.md` — editorial.
- `master.mp4` — rendered video.

After Phase 5, Stage 2 reads:
- `master/bundle.json` — the only timing source, via typed loader.
- `seam-plan.md` — editorial, unchanged.
- `master.mp4` — rendered video, unchanged.

Removed from Stage 2:
- Reads of `transcript.json` raw form.
- Parsing of `cut-list.md` for timing.
- Invocation of `remapWordsToMaster` (moved to Stage 1).
- Any `audio_duration_secs` / `duration_ms` field-name handling.

Loader contract: `tools/compositor/src/stage2/loadBundle.ts` exports
`loadBundle(episodeDir): MasterBundle`. Implementation is a hand-rolled
discriminated-union parser — no zod dependency for a single-schema project.
Throws `BundleSchemaError` with the offending field path on mismatch.

Field naming inside compositor switches to camelCase (`startMs`, `endMs`,
`durationMs`, `atMs`). Caption components today consume `start_ms`/`end_ms`
— they are updated to camelCase in the same phase (small change, one place,
removes the snake_case island).

## 6. Scene-mode rename

- New file `tools/compositor/src/sceneMode.ts` exports
  `type SceneMode = 'head' | 'split' | 'broll' | 'overlay'` and
  `parseSceneMode(s: string): SceneMode` (throws on unknown).
- All compositor code that today types scene mode as `string` switches to
  `SceneMode`.
- `seamPlanner.ts` transition matrix uses the union; matrix typed as
  `Record<SceneMode, Record<SceneMode, ...>>`.
- `seam-plan.md` parser calls `parseSceneMode` on each `mode:` line.
- Pilot's `seam-plan.md` is **not migrated** (frozen artifact). Test fixtures
  and any non-frozen `seam-plan.md` examples in repo get `full` → `broll`.
- `standards/motion-graphics.md` rename from `full` to `broll` lands at phase
  close via `retro-promote.sh`, not as part of the implementation step. Code
  lands first; standards-side rename comes through the retro flow as
  designed.

## 7. Phase 6 brief

Path: `docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md`.

Contents (target ~1-2 pages):
- Motivation — without a planner, scene modes are decorative labels and
  videos ship as talking-head + captions only.
- Decision: agentic, **not** LLM API. Reasoning.
- Dispatch model: coding subagent per seam (or batched).
- I/O contract (input: spoken text + scene mode + standards excerpt +
  component catalog; output: `graphic:` + `data:` lines patched into
  `seam-plan.md`).
- Validation layer (transition matrix + per-component data shape, enforced
  at write time).
- Open questions for Phase 6 brainstorming (batched vs per-seam,
  retry-on-violation, cost estimate, ambiguous-seam handling).
- Pointers to:
  - `standards/motion-graphics.md` — WATCH catalog `scene_mode →
    allowed_components`, "Graphic specs are mandatory" section.
  - `episodes/2026-04-27-.../retro.md` — Macro-retro item 1.
  - `standards/retro-changelog.md` — Phase 5 prep entry.

This brief is not a spec. It is input to the next brainstorming session.

## 8. Testing strategy

- **Bundle writer unit test (TS):** given a synthetic `transcript.json` +
  `edl.json` + ffprobe stub, assert produced bundle matches expected JSON
  shape, master-aligned timestamps, schema version.
- **Loader unit test (TS):** valid bundle parses; each missing or wrong
  field produces `BundleSchemaError` with the right path. One test per
  drift class observed in pilot (the five cases in
  `standards/pipeline-contracts.md`) — a living regression list.
- **`parseSceneMode` unit test:** each canonical name parses; `'full'`
  fails (the rename guard); unknown strings fail with the offending value in
  the message.
- **Compositor integration test (`test-run-stage2.sh`):** fixture replaced
  with a synthetic `master/bundle.json`; assertion that no read of
  `transcript.json` / `cut-list.md` happens (verified by deleting those from
  the fixture and confirming compose succeeds).
- **End-to-end smoke (`test-run-stage1.sh` + `test-run-stage2.sh`):** fixture
  pipeline runs; bundle is produced by Stage 1, consumed by Stage 2, no
  errors.

No retro-driven verification with a real episode in this phase. That comes
at the next real episode (Phase 6 dogfooding). The phase is operationally
done when fixtures pass.

## 9. File structure produced

```
tools/compositor/src/sceneMode.ts                          (new)
tools/compositor/src/stage1/writeBundle.ts                 (new)
tools/compositor/src/stage1/remapWordsToMaster.ts          (moved from stage 2 hot-fix path)
tools/compositor/src/stage2/loadBundle.ts                  (new)
tools/compositor/src/stage2/types.ts                       (extended — MasterBundle types)
tools/compositor/src/{composer,seamPlanner,...}.ts         (updated — read bundle, use SceneMode)
tools/compositor/test/                                     (new + updated tests)
tools/scripts/run-stage1.sh                                (updated — invoke writeBundle at end)
tools/scripts/test/test-run-stage1.sh                      (updated — assert bundle exists)
tools/scripts/test/test-run-stage2.sh                      (updated — bundle fixture, no transcript/cut-list reads)
docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md  (new)
```

At phase close (via `retro-promote.sh`):

```
standards/motion-graphics.md                               (full → broll rename in canonical block)
standards/retro-changelog.md                               (Phase 5 close entry)
```

## 10. Risks and open questions

**Risks.**
- Caption components consume `start_ms`/`end_ms` today; switching to
  camelCase touches caption rendering. Mitigation: narrow change (single
  file in caption pipeline), tests catch regression.
- `_render_edl.py` does not expose master `durationMs` directly; bundle
  writer must ffprobe `master.mp4`. Negligible cost.
- TS-side bundle writer needs the EDL → master remap function that the pilot
  put in compositor's hot-fix path. We move it to `stage1/`. Risk: Stage 2
  still has callers. Mitigation: codemod the imports, then delete the Stage
  2 copy.

**Open questions** (resolve during implementation, not blocking design).
- `boundaries` may be unused by Stage 2 in Phase 5; emit anyway because the
  planner needs it in Phase 6.
- Caption component naming is out of scope; only field-naming inside the
  data contract changes.

## 11. Tag and close

- Phase 5 git tag: `phase-5-pipeline-contracts`.
- Retro at close: capture any drift discovered while implementing, promote
  `full → broll` to `standards/motion-graphics.md`, append changelog entry,
  confirm Phase 6 brief is in place.
