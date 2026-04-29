# Render OOM Diagnosis

**Status:** design (spec)
**Date:** 2026-04-28
**Closes retro deltas:** D1 (preview OOM), D3 (pipeline stopped at CP2.5), D5 (OOM is misconfig, not hardware)
**Supersedes:** the deferred-with-reason TODO in `docs/operations/docker-render-verification.md` insofar as it treats Docker as the only path forward.

## Problem

`hyperframes render` in local mode crashes the dev host (32 GB RAM, NVIDIA RTX) on a real 53 s episode at 1440×2560. Adobe Media Encoder renders multiple concurrent heavy videos on the same machine without stress, so this is not a hardware ceiling — it is a configuration problem with our HF render path.

The current operational guard (AGENTS.md hard rule banning local-mode preview/final on real episodes, committed in `5bce709`) is a tourniquet: it stops the bleeding but doesn't diagnose the wound. Until we know what's actually consuming memory, mandating Docker is treating a symptom.

## Goal

Identify the root cause of the OOM through a cheap, ordered diagnostic sequence that exhausts likely misconfigurations *before* concluding Docker is required. Update the operational guard to reflect what we actually learned.

## Non-goals

- Installing Docker on the dev host. (May still be the answer; not the first move.)
- Patching HyperFrames. (Out of scope; if HF has a real bug, file upstream — `tools/compositor/patches/` is for surgical fixes only, see `docs/hyperframes-patches/`.)
- Changing the resolution or fps of finals. The crash must be solvable at 1440×2560 native because that's the deliverable.

## Diagnostic sequence

Ordered cheapest to most expensive. Stop at the first step that resolves the OOM; record findings at every step regardless of outcome.

### Step 1 — `hyperframes doctor`

Never been run on this host. `npx hyperframes doctor` checks Chrome, FFmpeg, Node version, and memory. If it surfaces a known issue (low memory warning, wrong Chrome channel, stale FFmpeg) — that's likely the answer.

**Acceptance:** doctor output captured to `docs/operations/render-oom/doctor-output.txt`. Either it points at something or it doesn't; either is a finding.

### Step 2 — `--gpu` flag

`hyperframes render --gpu` is documented in `tools/hyperframes-skills/hyperframes-cli/SKILL.md` (default off). With NVENC available on the RTX, GPU encoding offloads ffmpeg's CPU/RAM pressure during the encode pass. We have never tested this flag.

**Hypothesis:** if the OOM is concentrated in the ffmpeg encode side (libx264 software encode of 1590 frames at 1440×2560), `--gpu` resolves it.

**Test:** `tools/scripts/run-stage2-preview.sh <slug> --gpu` — flag is *not currently exposed* by the wrapper, so this step also adds `--gpu` plumbing through the script. Run on the real episode (`2026-04-28-desktop-software-licensing-it-turns-out`).

**Acceptance:** preview render completes without OOM, OR completes with same/different failure (record which).

### Step 3 — `--quality draft`

The wrapper's default is `--quality standard`. For previews the right default is `draft` (HF docs: "draft for iterating"). `standard` does extra encode work that doesn't matter for a CP2.5 review preview.

**Hypothesis:** standard quality alone is enough to push a marginal-RAM run over the edge.

**Test:** `tools/scripts/run-stage2-preview.sh <slug> --draft` (already supported by the wrapper). Run after Step 2 if Step 2 didn't resolve, or *combined* with `--gpu` if Step 2 partially helped.

**Acceptance:** preview completes without OOM at draft quality.

### Step 4 — narrow empirical measurement

Only if Steps 1-3 don't resolve. Take a 10 s slice of the real episode (first 10 s of `master.mp4` re-clipped via ffmpeg into a sandbox HF project) and run preview with process-level memory monitoring:

- Peak RSS of every Chromium worker (Windows: `Get-Process -Name chrome | Select Id, WorkingSet64`).
- Peak RSS of ffmpeg.
- Peak `nvidia-smi` GPU memory.
- Pagefile growth over the run.

10 s = ~300 frames. Should fit comfortably in 32 GB regardless of how memory is held (batch vs streaming). If it doesn't, the bug is dramatic and visible early. If it does, extrapolate the rate to 53 s and compare to the OOM threshold.

**Acceptance:** measurement table saved to `docs/operations/render-oom/measurements.md` with rate-of-growth and projected 53 s peak. Conclusion names the dominant bottleneck (Chromium frame buffer / ffmpeg encoder / GPU memory / something else).

### Step 5 — config fix or honest fallback

Based on what Steps 1-4 showed:

- **If a configuration fix resolves the OOM:** update `tools/scripts/run-stage2-preview.sh` defaults to bake the fix in (e.g. `--gpu` on by default if it's the answer; `--quality draft` as the default for preview). Update `docs/operations/docker-render-verification.md` to reflect that Docker is *not required* on this host class. Relax the AGENTS.md hard rule from "never run local-mode" to "use the wrapper defaults; warn if `HF_RENDER_MODE=local` and episode > 30 s without `--draft`".
- **If no config fix works and the bottleneck is genuinely beyond what local mode can handle:** then Docker stands as the answer, but with honest framing — `docker-render-verification.md` says "HF requires Docker", which is wrong; the truth is "this dev host's local-mode render path has uncontained memory growth at our resolution × duration; Docker contains it via cgroup". Update wording. Schedule Docker installation on the dev host as a separate task; AGENTS.md hard rule stays until Docker is available.

## Operational guard update (regardless of outcome)

Independent of the diagnostic result, add a duration warning to `tools/scripts/run-stage2-preview.sh`:

> When `HF_RENDER_MODE=local` and the resolved master duration is > 30 s and `--draft` was not passed, emit a stderr warning before launching HF: "WARNING: long episode in local mode without --draft; OOM risk on 32 GB hosts. Pass --draft for previews."

This is the WATCH item from retro D1. Cheap, defensive, survives any outcome of the diagnosis.

## What gets committed

- `docs/operations/render-oom/doctor-output.txt` — Step 1 capture.
- `docs/operations/render-oom/measurements.md` — Step 4 capture (only if Steps 1-3 didn't resolve).
- `docs/operations/render-oom/findings.md` — short writeup naming the root cause + the chosen fix.
- Updated `tools/scripts/run-stage2-preview.sh` — `--gpu` plumbing (always); duration warning (always); revised defaults (only if config fix won).
- Updated `docs/operations/docker-render-verification.md` — accurate framing of Docker's role.
- Updated `AGENTS.md` hard rule — relaxed if config fix won; clarified language if Docker stands.

## Open question (for plan stage)

If Step 1 (`doctor`) immediately points at something obvious — say, a missing/outdated Chrome — does the diagnostic skip ahead? Yes. The sequence is "first cheap thing that explains the failure wins"; later steps run only if earlier ones don't conclude. Plan should encode the early-exit branches.

## Pointers

- `tools/hyperframes-skills/hyperframes-cli/SKILL.md` — `--gpu`, `--quality`, `--workers`, `--docker`, `doctor`.
- `tools/scripts/run-stage2-preview.sh` — current wrapper, defaults, comments on workers RAM ceiling.
- `docs/operations/docker-render-verification.md` — current Docker rationale (to be revised).
- `episodes/2026-04-28-desktop-software-licensing-it-turns-out/retro.md` — D1, D3, D5.
- `AGENTS.md` — current hard rule banning local-mode preview/final; revision target for Step 5.
- Commit `5bce709` — original guard; revision target.
- Commit `339b5c6` — corrected ban on foreground execution; stays.
