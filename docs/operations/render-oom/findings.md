# Render OOM Investigation — Findings

**Status:** in progress (started 2026-04-28)
**Spec:** `docs/superpowers/specs/2026-04-28-render-oom-diagnosis-design.md`
**Plan:** `docs/superpowers/plans/2026-04-28-render-oom-diagnosis.md`

## Step 1 — `hyperframes doctor` capture

Output: `docs/operations/render-oom/doctor-output.txt`

Notable lines (warnings / non-critical observations beyond what `lib/preflight.sh` already gates):

- `✗ Version  0.4.31 → 0.4.32 available` — slightly behind latest. Not OOM-relevant; flagging for hygiene.
- `✓ Memory   31.9 GB total · 11.0 GB free` — host has 32 GB total, but only 11 GB free at idle. The OOM ceiling is therefore ~11 GB of headroom for HF + Chromium + ffmpeg, not the full 32 GB.
- `✗ Docker / ✗ Docker running` — already gated by `lib/preflight.sh` (and bypassed by `HF_RENDER_MODE=local`); not relevant to the OOM cause.

GPU detection (yes / no / unknown):

- **Unknown.** `hyperframes doctor` v0.4.31 emits no GPU / NVENC / CUDA / hardware-acceleration line. The doctor surface does not probe GPU encode capability on this host. `--gpu` plumbing (Task 1) is therefore the only way to discover whether the GPU path is viable.

Memory hint (any low-RAM warning, recommended Chrome flags, etc.):

- **None.** Doctor does not surface any memory-related hint despite reporting 11 GB free out of 32 GB. No suggested `--max-old-space-size`, no Chrome-flag advice, no headless-shell tuning recommendation.

**Conclusion of Step 1:** no — doctor is clean (modulo the version-bump nag and the already-gated Docker rows). Doctor does not point at a likely cause and offers no GPU or memory-tuning surface. Proceed to Step 2 (`--gpu` flag run on the failing real episode).

Operational note: the 11 GB free figure is a useful headroom datum for Step 4 measurement extrapolation (32 GB total RAM is *not* the budget; ~11 GB before background drift is).

## Step 2 — `--gpu` flag

(filled in by Task 4)

## Step 3 — `--quality draft`

Already in effect: in `HF_RENDER_MODE=local` the wrapper forces `QUALITY=draft` (`tools/scripts/run-stage2-preview.sh`, current `elif [ "$HF_RENDER_MODE" = "local" ]` block). Confirmed by reading the wrapper. Skipping as a separate diagnostic.

## Step 4 — Narrow empirical measurement

(filled in by Task 5 if needed)

## Conclusion

(filled in by Task 6)
