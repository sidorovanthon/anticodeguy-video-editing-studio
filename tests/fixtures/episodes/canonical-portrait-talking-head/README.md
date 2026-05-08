# canonical-portrait-talking-head fixture

Canonical fixture episode for the L1 fixture-replay layer described in
`docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md` § 5.
A single short, real, portrait talking-head clip — kept in the repo so
graph-replay tests can run with `$0` cost on every push.

## Source

- **Episode:** `episodes/2026-05-06-who-else-is-tired-of-endless-monthly/raw.mp4`
  (the HOM-154 episode — already known to surface real regressions:
  semantic-dup in EDL, HF black-screen).
- **Source codec/dims:** H.264 + AAC, 1080×1920 portrait, 60 fps, ~106 s, ~597 MB.

## Chosen segment

- **Cut:** `-ss 10 -t 35` (start at 00:00:10.000, run 35 s → 00:00:45.000).
- **Why:** the first ~5 s of the source is silent intro
  (`mean_volume ≈ −80 dB` on a `volumedetect` probe of the 0–5 s window,
  vs. `≈ −29 dB` from 10 s onward). Starting at 10 s lands inside
  continuous speech; 35 s gives the graph enough beats to exercise
  Phase 3 strategy / EDL select / Phase 4 design system / plan / beats
  without padding the fixture beyond the ~10 MB direct-git ceiling.

## Output clip — `raw.mp4`

| field      | value                          |
| ---------- | ------------------------------ |
| codec      | H.264 (yuv420p) + AAC mono     |
| dimensions | 1080×1920 (portrait, SAR 1:1)  |
| frame rate | 60 fps                         |
| duration   | 35.000 s                       |
| bitrate    | ~1.14 Mb/s video, 96 kb/s audio |
| size       | ~4.99 MB                       |

Direct stream-copy was tried first; at the source's native 45 Mb/s the
35 s slice was ~200 MB — far over the spec's 5–10 MB target. The
checked-in clip is therefore re-encoded with:

```
ffmpeg -ss 10 -t 35 -i <source> \
       -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p \
       -c:a aac -b:a 96k -movflags +faststart \
       raw.mp4
```

CRF 26 / preset slow is comfortably above the perceptual-loss threshold
for a fixture used by deterministic graph runs — the LLM nodes do not
care about subtle compression artefacts; ffmpeg-side nodes hash the
input bytes (deterministic) and that hash becomes the fixture's anchor.

## Storage decision — direct git, no LFS

Final size 4.99 MB is well under the spec's 10 MB direct-commit ceiling
(§ 5 «LFS — open question»), and the repo has no `.gitattributes` LFS
rules in place. We commit the binary directly; no `git lfs install`
prerequisite for contributors.

If the fixture ever needs to grow past 10 MB (longer clip, additional
fixture episodes), revisit the LFS option per spec § 5.

## Initial prewarm — runs once, by the user, in a follow-up

This PR scaffolds the fixture but **does NOT** include a prewarmed
`cache.db`. The prewarm is a paid one-shot full-real-tier run; per the
HOM-181 plan it lives in a follow-up step that the human operator
executes after this scaffold lands.

Prewarm command (PowerShell, from repo root, after this PR is merged
back to `main`):

```powershell
$env:HOMESTUDIO_TEST_MODE = "record"
$env:HOMESTUDIO_PROJECT_ROOT = "tests\fixtures"
python -m pytest tests/test_graph_replay.py --record-fixtures
```

Bash equivalent:

```bash
HOMESTUDIO_TEST_MODE=record \
HOMESTUDIO_PROJECT_ROOT=tests/fixtures \
python -m pytest tests/test_graph_replay.py --record-fixtures
```

- **Cost:** ~$1–3 of LLM spend on a 35 s fixture, per spec § 3 (L2).
- **Runtime:** ~5–10 min (Phase 1 ElevenLabs Scribe + Phase 2 ffmpeg
  + ~10 creative LLM nodes on production tier).
- **Output:** writes `cache.db` (and, once the JSON-dump CLI is wired,
  `recordings/<node>.json`) into this directory. Commit them in a
  follow-up PR.

After the first prewarm, regular development (and CI, when added) runs
in the default `replay` mode at $0/run.

## Refreshing the fixture when canon updates

Per spec § 4 / § 5:

- **Single brief or schema bump in a creative node** — local dev
  iterates with `HOMESTUDIO_TEST_MODE=record-on-miss`, which only
  re-records the affected nodes (fingerprint mismatch ⇒ cache miss
  ⇒ real call). Commit the updated `cache.db` + `recordings/` diff
  in the same PR as the brief/schema change.
- **Major schema rework / new fixture-relevant pipeline node** — wipe
  and re-record from scratch with `HOMESTUDIO_TEST_MODE=record` (same
  command shape as the initial prewarm above). Treated as a wave-end
  L2 acceptance run; record retro alongside.
- **Source clip itself changes** — re-extract `raw.mp4` with the
  command in this README, document the new cut window here, then run
  the full `record` prewarm. The source-bytes change cascades through
  every cache key (Phase 1 `make_key` extras include the input hash),
  so partial re-record is not meaningful.

Never edit `cache.db` by hand. The harness writes it via SQLite
`VACUUM INTO` + atomic rename specifically so the file is in a
deterministic raw form and reviewers can read its diff sensibly
(see `tests/_helpers/replay_harness.py::finalize_record_on_miss`).

## Files in this directory

```
canonical-portrait-talking-head/
  raw.mp4        # 35 s, 1080×1920, 4.99 MB — the only source artefact
  intent.yaml    # profile_id + brand_id (matches spec § 5 layout)
  README.md      # this file
  cache.db       # PENDING — added by the user's prewarm follow-up
  recordings/    # PENDING — JSON dump CLI lands later in the M5 testing-infra epic
```
