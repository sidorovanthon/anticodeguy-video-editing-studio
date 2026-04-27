# Script Fidelity Check — Design Spec

**Status:** Approved (brainstorming complete 2026-04-27).
**Position in roadmap:** Phase 3.5 — between Phase 3 (compositor) and Phase 4 (first episode + retro). Implemented before Phase 4 runs so the first real episode's retro uses real fidelity numbers.

## Problem

The pipeline relies on a Claude subagent to author `edl.json` from a packed transcript. There is currently no objective check that the resulting cut preserves the lines the host meant to deliver. Mistakes — a dropped script line, a flubbed take left in, a take chosen over a better one — are invisible until viewing the rendered draft, by which point ffmpeg work has already been spent and judgement is subjective.

The host's recordings are read from a **verbatim plain-text script**. That script is ground truth and can be diffed against what the pipeline actually preserved.

## Solution at a glance

Add an optional `script.txt` input. After CP1 (when `edl.json` exists), produce a deterministic two-axis diff:

- **D1 — audit-of-cuts:** `script.txt` ↔ reconstructed final transcript (words from `raw.json` whose timestamps fall inside an `edl.json` kept range). Tells us what the EDL agent dropped or kept.
- **D2 — audit-of-recording:** `script.txt` ↔ full raw transcript (`raw.json` as-is). Tells us what the host actually said on camera vs what was planned.

Both diffs are pure-Python, zero LLM tokens, zero new ElevenLabs API calls — they reuse the single Scribe transcription already paid for in CP1.

The diff lands as an artifact alongside `edl.json` so the user can review both before approving CP1, and surfaces in `retro.md` as quantitative episode-fidelity numbers.

## Non-goals

- Re-transcribing `final.mp4`. Scribe is paid per minute; the reconstructed-from-timestamps approach is exact for word-level fidelity.
- Catching ASR errors that occur identically in both `raw.json` and the reconstructed final (Scribe is consistent — same audio yields the same mistake in both views, so the diff is silent on it).
- Semantic / paraphrase comparison. The script is verbatim by design, so word-level alignment is appropriate. No LLM judge.
- Changing the EDL subagent prompt or feeding the script into it (option D from brainstorming, deferred — only adopt if retro shows the agent missing script-anchored content).
- Catching subtle audio-domain effects (crossfades, ducking) — they shift word boundaries by tens of ms, irrelevant to word-level fidelity.

## User-visible flow

1. Host drops `incoming/raw.mp4` and optionally `incoming/script.txt` (verbatim text of what was read on camera).
2. `new-episode.sh <slug>` moves both into `episodes/<slug>/source/` (script optional, no error if absent).
3. `run-stage1.sh <slug>` (CP1 mode):
   a. Existing flow: Scribe → pack → EDL subagent → validate `edl.json`.
   b. **New step:** if `source/script.txt` exists, run `script-diff.py` and emit `stage-1-cut/script-diff.md` + `stage-1-cut/script-diff.json`.
   c. CP1 message lists both artifacts.
4. User reviews `edl.json` and `script-diff.md` together before saying `go`. If diff reveals a bad cut, user can hand-edit `edl.json` and re-run CP1 (the script-diff step re-runs against the new EDL).
5. `retro.md` template (added in Phase 4) reads `script-diff.json` to populate a "Script fidelity" section with hard numbers.

## Inputs

| Path | Producer | Required | Purpose |
| --- | --- | --- | --- |
| `episodes/<slug>/source/script.txt` | host (via `incoming/`) | yes (gate for whole feature) | verbatim ground truth |
| `episodes/<slug>/stage-1-cut/edit/transcripts/raw.json` | `video-use/helpers/transcribe.py` (Scribe) | yes | word-level timestamps on raw |
| `episodes/<slug>/stage-1-cut/edl.json` | EDL subagent | yes | kept ranges in raw |

If any of the three is missing, `script-diff.py` exits 0 with a one-line skip note. The pipeline never fails because of script-fidelity tooling — it is purely informational.

## Outputs

### `stage-1-cut/script-diff.md` — human-readable

Sections, in order:

1. **Summary** — one line each: total script words, % covered in final, count of dropped script spans, count of ad-libs in final not in script, count of detected retakes.
2. **Dropped from script** — script spans (≥ 3 consecutive words) present in `script.txt` but absent from the reconstructed final. Each entry shows the script text and whether it appears anywhere in `raw.json` (i.e. dropped because the host skipped it vs dropped because the EDL agent cut it).
3. **Ad-libs in final** — final spans (≥ 3 consecutive words) not in `script.txt`. Each entry shows the text and the raw-time range it occupies.
4. **Retakes detected** — script spans that appear multiple times in `raw.json` (the host did the line twice). Each entry lists all raw-time ranges and marks which one (if any) survived in the final.
5. **Word-level alignment block** — script vs final, side-by-side, ≤ 200 lines (truncate with a note if longer). Uses unified-diff-like markers: ` ` keep, `-` script-only, `+` final-only.

### `stage-1-cut/script-diff.json` — machine-readable for retro

```json
{
  "script_words_total": 312,
  "final_words_total": 298,
  "script_coverage_pct": 92.3,
  "dropped_spans": [
    {"text": "and the second thing is", "in_raw": false, "raw_ranges": []},
    {"text": "let me show you something", "in_raw": true, "raw_ranges": [[42.18, 44.10]]}
  ],
  "ad_libs": [
    {"text": "uh actually wait", "raw_range": [12.05, 13.40]}
  ],
  "retakes": [
    {"text": "the key insight here is", "raw_ranges": [[8.20, 9.95], [21.40, 23.10]], "kept_range": [21.40, 23.10]}
  ]
}
```

Schema is stable; retro and any future tooling depend on it.

## Algorithm

### Step 1 — tokenize and normalize

Both `script.txt` and `raw.json[*].text` go through the same normalizer:

- Lowercase.
- Strip punctuation except apostrophes inside words (`don't` stays one token).
- Collapse whitespace.
- Tokenize on whitespace.

Each `raw.json` token retains its `(start_s, end_s)` from Scribe word timings. Script tokens carry their position only.

### Step 2 — reconstruct the final transcript

Walk `raw.json` words in order; emit a word into `final_tokens` if its `start_s` falls inside any `edl.json` range (`source == "raw"`). Half-open interval at the right edge to match ffmpeg `-ss/-to` semantics.

This is the "what survived the cut" view. Zero approximation: if `render-final.sh` later applies fades or ducking, those affect amplitude envelopes, not which words are present.

### Step 3 — alignment

`difflib.SequenceMatcher` on `(script_tokens, final_tokens)` for D1, and `(script_tokens, raw_tokens)` for D2. Use `get_opcodes()` to walk equal/replace/delete/insert blocks.

Span extraction:
- A **dropped span** = a `delete` block from D1 whose script side is ≥ 3 tokens.
- An **ad-lib** = an `insert` block from D1 whose final side is ≥ 3 tokens.
- A **retake** = a script span (≥ 3 tokens) that matches in `raw_tokens` more than once. Detect by sliding a window of script-span tokens across `raw_tokens` and counting fuzzy matches (ratio ≥ 0.85). For each match, look up whether its raw-time range lies inside an `edl.json` kept range to mark `kept_range`.

The 3-token threshold filters single-word noise (filler corrections, common ASR slips) and keeps spans large enough to be meaningfully reportable.

### Step 4 — emit

Render `script-diff.md` from a template that reads the structured result; emit the same result as `script-diff.json`.

## Components and contracts

```
tools/scripts/script_diff/
├── __init__.py
├── normalize.py          # tokenize + lowercase + punctuation rules
├── reconstruct.py        # raw.json + edl.json → final_tokens with timestamps
├── align.py              # SequenceMatcher wrapper, span extraction
├── retake.py             # multi-match detection on raw_tokens
└── render.py             # JSON + Markdown emitters
tools/scripts/script-diff.py    # CLI entrypoint, thin wrapper
tools/scripts/test/
├── fixtures/
│   ├── basic-script.txt
│   ├── basic-raw.json
│   └── basic-edl.json
└── test-script-diff.sh   # end-to-end + unit smoke
```

Each module has one job, can be tested with synthetic dicts, and `script-diff.py` orchestrates them. The CLI signature:

```
tools/scripts/script-diff.py --episode <path>
```

It reads `<path>/source/script.txt`, `<path>/stage-1-cut/edit/transcripts/raw.json`, `<path>/stage-1-cut/edl.json` and writes alongside.

## Integration points

### `new-episode.sh`

After the existing optional `notes.md` move, add a parallel optional `script.txt` move from `incoming/script.txt` to `<dir>/source/script.txt`. No validation beyond "is a file." Update the `Next steps:` echo to mention that a script was detected, if so.

### `run-stage1.sh` (CP1 mode)

After the inline EDL validation Python block (currently the last step), add:

```
if [ -f "$EPISODE/source/script.txt" ]; then
  python "$SCRIPT_DIR/script-diff.py" --episode "$EPISODE" || \
    echo "WARN: script-diff.py failed; CP1 still valid"
fi
```

Failure of the diff is a warning, not an error — the cut list is still reviewable without it.

The CP1 message becomes:

```
CP1 ready: stage-1-cut/edl.json (+ script-diff.md). Awaiting review.
```

### Retro template (Phase 4)

Phase 4's retro template adds a "Script fidelity" section that reads `script-diff.json` if present. Minimum content:

```markdown
## Script fidelity
- Script coverage: <coverage_pct>% (<final_words>/<script_words> words)
- Dropped script spans: <count> (<host-skipped> | <agent-cut>)
- Ad-libs preserved: <count>
- Retakes detected: <count> (<chose-later> | <chose-earlier> | <none-survived>)
```

This integration is part of the Phase 4 plan, not Phase 3.5, but is listed here so Phase 4 knows the shape of the data.

## Testing strategy

`difflib`-based core lends itself to unit-style tests with hand-built fixtures.

- **Unit (Python, no Scribe):** `tools/scripts/test/fixtures/basic-*` — a fake `raw.json` (12-15 words with hand-set timestamps), a fake `edl.json` keeping a subset, a fake `script.txt`. Three test cases cover: clean match (100% coverage, no ad-libs), one dropped script line, one ad-lib + one retake. Each case asserts on the JSON output.
- **Smoke (bash):** `test-script-diff.sh` exercises the CLI: missing `script.txt` → exit 0 silent; missing `raw.json` → exit 0 with skip note; happy path → both files produced and `script-diff.json` parses.
- **Integration:** none in Phase 3.5 — Phase 4's first real episode is the integration test. If a real-episode diff is wildly off vs subjective viewing, that becomes a retro signal.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Script and ASR diverge on numbers/names (e.g. "v2" vs "version two") | Normalizer is conservative on purpose; mismatches will surface as small dropped spans below the 3-token threshold and stay out of the report. If they cluster, retro will flag and we extend the normalizer. |
| User has many episodes already in flight without `script.txt` | Feature is fully optional; absence skips silently. No backfill needed. |
| `difflib` slow on long scripts | Both texts are 5-10 minutes of speech ≈ 1.5–3k tokens. `SequenceMatcher` handles that in well under a second. |
| Retake detection has false positives on short repeated phrases | 3-token minimum + 0.85 fuzzy threshold; if still noisy, raise the floor in a retro pass rather than now. |
| Script-diff failure blocks CP1 | Wrapped in `|| echo WARN`; pipeline carries on. |

## Out of this spec

- Feeding the script into the EDL subagent (option D from brainstorming).
- Any change to the EDL subagent prompt.
- Re-transcription of final video.
- Retro-promote behavior beyond reading `script-diff.json` (Phase 4 owns retro tooling).
