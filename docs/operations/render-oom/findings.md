# Render OOM Investigation — Findings

**Status:** complete (closed 2026-04-29)
**Spec:** `docs/superpowers/specs/2026-04-28-render-oom-diagnosis-design.md`
**Plan:** `docs/superpowers/plans/2026-04-28-render-oom-diagnosis.md`

## Step 1 — `hyperframes doctor` capture

Output: `docs/operations/render-oom/doctor-output.txt`

Notable lines:

- `✗ Version  0.4.31 → 0.4.32 available` — version-bump nag. Not OOM-relevant.
- `✓ Memory   31.9 GB total · 11.0 GB free` — informational; HF doctor reports `os.freemem()`, which excludes Windows standby/cache. Real Available memory varies hour-to-hour by tens of GB depending on background apps. Not a stable diagnostic.
- `✗ Docker / ✗ Docker running` — already gated by `lib/preflight.sh` (and bypassed by `HF_RENDER_MODE=local`); not relevant to the OOM cause.

GPU detection: **not surfaced.** Doctor v0.4.31 emits no GPU / NVENC / CUDA / hardware-acceleration line. `--gpu` plumbing (Task 1) is the only way to discover whether the GPU path is viable.

Memory hint: **none.** No `--max-old-space-size`, Chrome flag, or headless-shell tuning recommendation.

**Conclusion of Step 1:** doctor is clean. Proceed to Step 2 (`--gpu`) on a 10 s slice first per safety protocol.

## Step 2 — `--gpu` flag (on 10 s slice)

The diagnostic was run on a 10 s slice fixture (`episodes/2026-04-28-oom-slice/`, since cleaned up) rather than the full failing episode, per the safety protocol agreed with the user. Note: even though the slice's `master.mp4` was 10 s, HF rendered the full **1607-frame composition** (53.566 s × 30 fps) because composition duration is read from `compositions/*/index.html` metadata, not from the master source. So Step 2 effectively measured the full failing-episode workload.

Two passes were run, side by side:

### Pass A — `HF_RENDER_MODE=local` without `--gpu`

Command:
```
HF_RENDER_MODE=local bash tools/scripts/run-stage2-preview.sh 2026-04-28-oom-slice
```
Log: `docs/operations/render-oom/preview-10s-slice.log`
Snapshot: `docs/operations/render-oom/process-snapshot.log`

Outcome: **A — succeeds.** Exit 0; `preview.mp4` produced (8.3 MB).

Peak RSS:
- `chrome-headless-shell`: 538 MB
- `ffmpeg`: 544 MB
- `node` (HF orchestrator): 168 MB
- Total ≈ 1.25 GB

System Available memory dropped from 20131 MB → 18940 MB during render (Δ 1.2 GB).

### Pass B — `HF_RENDER_MODE=local` with `--gpu`

Command:
```
HF_RENDER_MODE=local bash tools/scripts/run-stage2-preview.sh 2026-04-28-oom-slice --gpu
```
Log: `docs/operations/render-oom/preview-10s-slice-gpu.log`
Snapshot: `docs/operations/render-oom/process-snapshot-gpu.log`

Outcome: **A — succeeds.** Exit 0; `preview.mp4` produced (7.4 MB). No NVENC / encoder errors.

Peak RSS:
- `chrome-headless-shell`: 531 MB
- `ffmpeg`: 308 MB ← ~236 MB saving from NVENC offload
- `node`: 174 MB
- Total ≈ 1.0 GB

System Available memory dropped from 20112 MB → 18845 MB during render (Δ 1.3 GB).

**Conclusion of Step 2:** the wrapper's already-forced local-mode defaults (`--workers 1 --quality draft --max-concurrent-renders 1`) render the full failing composition successfully on this 32 GB host. `--gpu` is supported and saves ~240 MB on encoder buffers but is not required. Headroom is enormous (~17 GB Available remaining at peak). Steps 4 (narrow measurement) and 5 (additional fallback diagnostics) are unnecessary — the data resolves the question.

## Step 3 — `--quality draft`

Already in effect: in `HF_RENDER_MODE=local` the wrapper forces `QUALITY=draft` (`tools/scripts/run-stage2-preview.sh`). Confirmed by reading the wrapper. Skipped as a separate diagnostic.

## Step 4 — Narrow empirical measurement

**Skipped.** Step 2 already revealed peak Chromium and ffmpeg RSS for the full composition workload. Both are well under 1 GB each, with no growth pattern requiring further extrapolation. The slice ran the full 1607 frames; that *is* the measurement.

## Conclusion

**Root cause of the original OOM (commit 339b5c6, 2026-04-28):** background load on the host, not pathological HF behavior. Per the motivation in commit `c280f57`, the original wedging happened "while the host browser had ~45 chrome.exe instances open." With those defaults already in place (`--workers 1 --quality draft --max-concurrent-renders 1`), HF + Chromium peak combined RSS is ~1.0–1.3 GB — orders of magnitude below the 32 GB host ceiling. The OOM cliff was driven by background memory pressure, not by HF's render path.

**Resolution:** the wrapper is already configured correctly. No new defaults needed; `--gpu` remains a useful opt-in flag (~20% memory saving on the encoder side) but should not be default-on because (a) it requires NVENC on the host and would error on hosts without it, and (b) the savings are immaterial when `--workers 1 --quality draft` already keeps total peak < 1.5 GB.

Action items (covered in subsequent commits):

- Update `docs/operations/docker-render-verification.md`: replace "HF requires Docker" framing. Docker is **not** a memory-safety requirement on this host class with the current wrapper defaults; it remains valid for byte-identical reproducibility on production-final renders.
- Relax `AGENTS.md` hard rule from "never run local-mode preview/final on real episodes" to a host-discipline guideline: free up Available memory before running, the wrapper's duration warning (Task 2) is the tripwire if defaults are ever loosened, hand to user on hosts without sufficient headroom.
- **No wrapper default change.** The current defaults (`WORKERS=1 QUALITY=draft` forced in local mode) are the working configuration. `--gpu` stays opt-in.
