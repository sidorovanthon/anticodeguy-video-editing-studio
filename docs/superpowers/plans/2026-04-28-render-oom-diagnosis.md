# Render OOM Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Diagnose the root cause of `hyperframes render` OOM on 32 GB / RTX dev host through an ordered, cheap-first investigation; instrument the wrapper script to support that investigation; act on findings (relax / revise / harden the operational guard).

**Architecture:** The plan is a hybrid of (a) deterministic instrumentation of `tools/scripts/run-stage2-preview.sh` (TDD-able), (b) investigation runs that capture data into `docs/operations/render-oom/`, and (c) documentation / guard updates that the engineer writes once findings are in hand. Investigation tasks have explicit decision points: each task says what to do based on the prior task's outcome.

**Tech Stack:** Bash (wrapper + tests, `set -euo pipefail`), HyperFrames CLI (`npx hyperframes` via pinned binary), Windows process inspection (PowerShell `Get-Process`, `nvidia-smi`).

**Spec:** [`docs/superpowers/specs/2026-04-28-render-oom-diagnosis-design.md`](../specs/2026-04-28-render-oom-diagnosis-design.md)

---

## Pre-flight context (read before starting)

The current state of `tools/scripts/run-stage2-preview.sh` (lines 80–96):
- Sources `lib/preflight.sh` which already runs `hyperframes doctor` but only checks Node / FFmpeg / FFprobe / Chrome / Docker for hard fails. Doctor's full output (memory warnings, GPU detection) is parsed and discarded.
- In `HF_RENDER_MODE=local`, the wrapper *forces* `WORKERS=1` and `QUALITY=draft`. This means the failing preview was already running with the most conservative settings the wrapper exposes.
- `--gpu` is not currently passed through — that's a real gap.

So the diagnostic adjusts the spec's Step 3 ("--quality draft") from "test if it helps" to "confirmed already in effect; proceed past it." Step 1 (capture full doctor output) and Step 2 (--gpu) remain primary diagnostic levers.

The existing shell-script test pattern (see `tools/scripts/test/test-run-stage2.sh`): copy repo to `mktemp`, run the wrapper in the sandbox, assert on outcomes. We follow that pattern for instrumentation tests.

---

## File Structure

**New files:**
- `tools/scripts/test/test-stage2-preview-flags.sh` — tests `--gpu` plumbing and duration-warning behaviour of the wrapper.
- `docs/operations/render-oom/doctor-output.txt` — captured `hyperframes doctor` output.
- `docs/operations/render-oom/findings.md` — the investigation log + conclusions.
- `docs/operations/render-oom/measurements.md` — narrow-measurement table (only if Task 5 runs).

**Modified files:**
- `tools/scripts/run-stage2-preview.sh` — add `--gpu` flag plumbing (Task 1); add duration warning (Task 2); revise defaults *only if Task 7 says config fix won* (Task 9).
- `docs/operations/docker-render-verification.md` — revise framing based on findings (Task 8).
- `AGENTS.md` — relax / clarify the local-mode preview hard rule based on findings (Task 8).

---

### Task 1: `--gpu` flag plumbing in `run-stage2-preview.sh`

**Files:**
- Modify: `tools/scripts/run-stage2-preview.sh:21-72` (usage block + arg parsing) and `:105-112` (render invocation).
- Create: `tools/scripts/test/test-stage2-preview-flags.sh`.

**Why:** Without `--gpu` exposed, we can't test whether GPU encoding resolves the OOM (spec diagnostic step 2).

- [ ] **Step 1: Write the failing test for `--gpu` plumbing**

Create `tools/scripts/test/test-stage2-preview-flags.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Stub the pinned hyperframes binary so we capture invocation flags
# without actually rendering. Real binary path is
# tools/compositor/node_modules/.bin/hyperframes; we shadow it via
# PATH-prepending a stub directory.
STUB_DIR="$WORK/stub-bin"
mkdir -p "$STUB_DIR"
cat > "$STUB_DIR/hyperframes" <<'STUB'
#!/usr/bin/env bash
# Capture all args to a known file so the test can assert.
echo "ARGS: $*" >> "$HF_STUB_LOG"
exit 0
STUB
chmod +x "$STUB_DIR/hyperframes"

# Override the wrapper's pinned-binary lookup by symlinking the stub
# into tools/compositor/node_modules/.bin/.
mkdir -p "$REPO_ROOT/tools/compositor/node_modules/.bin"
HF_BIN_REAL="$REPO_ROOT/tools/compositor/node_modules/.bin/hyperframes"
HF_BIN_BACKUP=""
if [ -e "$HF_BIN_REAL" ] && [ ! -L "$HF_BIN_REAL" ]; then
  HF_BIN_BACKUP="$HF_BIN_REAL.bak.$$"
  mv "$HF_BIN_REAL" "$HF_BIN_BACKUP"
fi
ln -sf "$STUB_DIR/hyperframes" "$HF_BIN_REAL"
restore_bin() {
  rm -f "$HF_BIN_REAL"
  if [ -n "$HF_BIN_BACKUP" ]; then mv "$HF_BIN_BACKUP" "$HF_BIN_REAL"; fi
}
trap 'restore_bin; rm -rf "$WORK"' EXIT

export HF_STUB_LOG="$WORK/hf-args.log"
: > "$HF_STUB_LOG"

# Minimal episode fixture — wrapper requires existing index.html
SLUG="2026-04-27-flagtest"
EP="$REPO_ROOT/episodes/$SLUG"
mkdir -p "$EP/stage-2-composite"
cat > "$EP/stage-2-composite/index.html" <<'HTML'
<!doctype html><html><body></body></html>
HTML
cleanup_ep() { rm -rf "$EP"; }
trap 'cleanup_ep; restore_bin; rm -rf "$WORK"' EXIT

# Run wrapper with --gpu flag in local mode
HF_RENDER_MODE=local "$REPO_ROOT/tools/scripts/run-stage2-preview.sh" "$SLUG" --gpu \
  || { echo "FAIL: wrapper exited non-zero"; exit 1; }

# Assert the stub saw --gpu among its args
if ! grep -q -- "--gpu" "$HF_STUB_LOG"; then
  echo "FAIL: hyperframes was not invoked with --gpu"
  echo "Captured args:"
  cat "$HF_STUB_LOG"
  exit 1
fi

echo "PASS: --gpu plumbing reaches hyperframes invocation"
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `bash tools/scripts/test/test-stage2-preview-flags.sh`
Expected: FAIL with `unknown flag '--gpu'` (the wrapper rejects unknown flags at `:73-75`).

- [ ] **Step 3: Add `--gpu` to wrapper usage and arg parsing**

In `tools/scripts/run-stage2-preview.sh`:

Update the usage block (around `:24-28`) to add the new flag:

```bash
usage() {
  echo "Usage: $0 <slug> [--workers N] [--fps N] [--quality Q] [--draft] [--gpu]"
  echo "  --workers N    Parallel Chromium render workers (default: 1)"
  echo "  --fps N        Frame rate: 24, 30, or 60 (default: 30)"
  echo "  --quality Q    HF encoder quality: draft, standard, high (default: standard)"
  echo "  --draft        Shortcut for --quality draft. Recommended for smoke tests."
  echo "  --gpu          Enable GPU-accelerated encoding (passes --gpu to hyperframes)"
}
```

Add a `GPU=0` initialiser near the other defaults (around `:42-44`):

```bash
SLUG=""
WORKERS=1
FPS=30
QUALITY=standard
GPU=0
```

Add a `--gpu` case to the arg-parsing loop (around `:46-71`, before the catch-all `-*`):

```bash
    --gpu)
      GPU=1; shift ;;
```

- [ ] **Step 4: Pass `--gpu` to hyperframes when set**

In the render invocation block (around `:105-112`), append `--gpu` to `RENDER_FLAGS` when `GPU=1`:

```bash
HF_RENDER_MODE="${HF_RENDER_MODE:-docker}"
RENDER_FLAGS=()
if [ "$HF_RENDER_MODE" = "docker" ]; then
  RENDER_FLAGS+=(--docker)
elif [ "$HF_RENDER_MODE" = "local" ]; then
  WORKERS=1
  QUALITY=draft
else
  echo "ERROR: HF_RENDER_MODE must be 'docker' or 'local' (got '$HF_RENDER_MODE')"
  exit 1
fi
if [ "$GPU" = "1" ]; then
  RENDER_FLAGS+=(--gpu)
fi
```

- [ ] **Step 5: Run the test, verify it passes**

Run: `bash tools/scripts/test/test-stage2-preview-flags.sh`
Expected: `PASS: --gpu plumbing reaches hyperframes invocation`

- [ ] **Step 6: Commit**

```bash
git add tools/scripts/run-stage2-preview.sh tools/scripts/test/test-stage2-preview-flags.sh
git commit -m "feat(scripts): expose --gpu flag through run-stage2-preview"
```

---

### Task 2: Duration warning in `run-stage2-preview.sh`

**Files:**
- Modify: `tools/scripts/run-stage2-preview.sh` (add warning emission before render invocation).
- Modify: `tools/scripts/test/test-stage2-preview-flags.sh` (extend with duration-warning assertions).

**Why:** D1 watch item — even after the diagnostic concludes, a long episode in local mode without `--draft` is a known OOM risk on 32 GB hosts. Defensive guard, independent of outcome.

The warning fires when:
- `HF_RENDER_MODE=local` AND
- master.mp4 duration > 30 s AND
- the user did not pass `--draft` (which is currently the only escape; in local mode the wrapper *forces* `QUALITY=draft` regardless, so technically the user is always at draft — but the warning still serves as a tripwire if that wrapper logic is ever loosened, and as a documentation surface).

For the duration source: `assets/master.mp4` exists by the time the wrapper runs (compose stage produces it). Use `ffprobe` (already a hard preflight requirement, so it must be present) to read duration.

- [ ] **Step 1: Extend test fixture with a long-master scenario**

Append to `tools/scripts/test/test-stage2-preview-flags.sh` (before the final `echo PASS` and after the existing `--gpu` assertion):

```bash
# --- duration warning scenario ---

# Build a 31-second placeholder master.mp4 so the wrapper sees > 30s
ffmpeg -y -f lavfi -i "color=c=black:s=320x240:r=30:d=31" -c:v libx264 -pix_fmt yuv420p \
  "$EP/stage-2-composite/assets/master.mp4" >/dev/null 2>&1
mkdir -p "$EP/stage-2-composite/assets"
mv -f "$EP/stage-2-composite/assets/master.mp4" "$EP/stage-2-composite/assets/master.mp4" 2>/dev/null || true

# Run wrapper, capture stderr
STDERR_LOG="$WORK/wrapper.stderr.log"
HF_RENDER_MODE=local "$REPO_ROOT/tools/scripts/run-stage2-preview.sh" "$SLUG" 2>"$STDERR_LOG" >/dev/null \
  || { echo "FAIL: wrapper exited non-zero on long-master scenario"; exit 1; }

if ! grep -q "WARNING: long episode in local mode" "$STDERR_LOG"; then
  echo "FAIL: duration warning not emitted for >30s master in local mode"
  echo "Captured stderr:"
  cat "$STDERR_LOG"
  exit 1
fi

echo "PASS: duration warning emitted for long episode in local mode"
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `bash tools/scripts/test/test-stage2-preview-flags.sh`
Expected: FAIL with `duration warning not emitted` (the wrapper does not yet emit any such warning).

- [ ] **Step 3: Add duration check + warning emission**

In `tools/scripts/run-stage2-preview.sh`, after the `[ -f "$HF_INDEX" ]` check (around `:101`) and before `HF_OUT=` (around `:103`), insert:

```bash
# D1 watch: warn on long episodes in local mode without --draft.
# Local mode currently forces QUALITY=draft, but the warning still serves
# as a tripwire and as documentation surface.
MASTER_MP4="$COMPOSITE_DIR/assets/master.mp4"
if [ "$HF_RENDER_MODE" = "local" ] && [ -f "$MASTER_MP4" ]; then
  DUR_S="$(ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 "$MASTER_MP4" 2>/dev/null | awk -F. '{print $1}')"
  if [ -n "$DUR_S" ] && [ "$DUR_S" -gt 30 ] && [ "$QUALITY" != "draft" ]; then
    echo "WARNING: long episode in local mode without --draft: ${DUR_S}s. OOM risk on 32 GB hosts. Pass --draft for previews." >&2
  fi
fi
```

Note: this branch reads `$QUALITY` *after* the local-mode block has forced it to `draft`. To make the warning meaningful, hoist the duration check *before* that forced override OR check the *user-supplied* quality. Cleanest: capture the user's quality intent into a separate variable before the forced override. Implement by adding `USER_QUALITY="$QUALITY"` immediately after arg parsing (around `:73-74`), then test `[ "$USER_QUALITY" != "draft" ]` in the warning branch.

Apply that:

After arg-parsing validation (around `:73`):
```bash
USER_QUALITY="$QUALITY"   # captured before HF_RENDER_MODE local forces it
```

In the warning branch above, replace `[ "$QUALITY" != "draft" ]` with `[ "$USER_QUALITY" != "draft" ]`.

- [ ] **Step 4: Run the test, verify it passes**

Run: `bash tools/scripts/test/test-stage2-preview-flags.sh`
Expected: both `PASS` lines (`--gpu plumbing` and `duration warning emitted`).

- [ ] **Step 5: Commit**

```bash
git add tools/scripts/run-stage2-preview.sh tools/scripts/test/test-stage2-preview-flags.sh
git commit -m "feat(scripts): emit OOM-risk warning for long local-mode previews

Closes D1 watch item from
episodes/2026-04-28-desktop-software-licensing-it-turns-out/retro.md."
```

---

### Task 3: Capture full `hyperframes doctor` output

**Files:**
- Create: `docs/operations/render-oom/doctor-output.txt`
- Create: `docs/operations/render-oom/findings.md` (initial scaffolding)

**Why:** Spec diagnostic step 1. `lib/preflight.sh` calls doctor but discards non-critical lines (memory hints, GPU detection, etc.). Capture the raw output for analysis.

- [ ] **Step 1: Run doctor, save output**

```bash
mkdir -p docs/operations/render-oom
"$(pwd)/tools/compositor/node_modules/.bin/hyperframes" doctor 2>&1 \
  | tee docs/operations/render-oom/doctor-output.txt
```

- [ ] **Step 2: Scaffold `findings.md`**

Create `docs/operations/render-oom/findings.md`:

```markdown
# Render OOM Investigation — Findings

**Status:** in progress (started 2026-04-28)
**Spec:** docs/superpowers/specs/2026-04-28-render-oom-diagnosis-design.md
**Plan:** docs/superpowers/plans/2026-04-28-render-oom-diagnosis.md

## Step 1 — `hyperframes doctor` capture

Output: `docs/operations/render-oom/doctor-output.txt`

Notable lines (warnings, non-critical observations beyond what `lib/preflight.sh` already gates):
- (fill in after reading the file)

GPU detection (yes / no / unknown):
- (fill in)

Memory hint (any low-RAM warning, recommended Chrome flags, etc.):
- (fill in)

**Conclusion of Step 1:** (does doctor point at a likely cause? yes / no / partial)

## Step 2 — `--gpu` flag

(filled in by Task 4)

## Step 3 — `--quality draft`

Already in effect: in `HF_RENDER_MODE=local` the wrapper forces `QUALITY=draft` (run-stage2-preview.sh:88). Confirmed by reading the wrapper. Skipping as a separate diagnostic.

## Step 4 — Narrow empirical measurement

(filled in by Task 5 if needed)

## Conclusion

(filled in by Task 6)
```

- [ ] **Step 3: Read `doctor-output.txt` and populate Step 1 in `findings.md`**

Open `docs/operations/render-oom/doctor-output.txt`. Look for:
- Any line marked `⚠`, `WARNING`, `WARN`, `note`, `hint` — copy verbatim into the "Notable lines" section.
- Lines about GPU / NVENC / hardware acceleration — copy into "GPU detection".
- Lines about memory / RAM / `--max-old-space` / Chrome flags — copy into "Memory hint".
- Set "Conclusion of Step 1" to one of:
  - `yes — doctor points at <X>; addressing it likely resolves OOM. Proceed to Step 5 directly with that fix.`
  - `partial — doctor surfaced <Y> but it's likely not the full story. Proceed to Step 2.`
  - `no — doctor is clean; proceed to Step 2.`

- [ ] **Step 4: Commit**

```bash
git add docs/operations/render-oom/doctor-output.txt docs/operations/render-oom/findings.md
git commit -m "docs(render-oom): capture hyperframes doctor output (Step 1)"
```

---

### Task 4: Run preview with `--gpu` on real episode

**Files:**
- Modify: `docs/operations/render-oom/findings.md` (Step 2 section)

**Why:** Spec diagnostic step 2. Test whether GPU encoding alone resolves the OOM.

**Decision gate:** If Task 3 Step 3's "Conclusion of Step 1" was `yes — doctor points at <X>`, skip this task and jump to Task 7 with the doctor's identified fix. Otherwise proceed.

- [ ] **Step 1: Run preview with `--gpu` on the failing real episode**

```bash
HF_RENDER_MODE=local bash tools/scripts/run-stage2-preview.sh \
  2026-04-28-desktop-software-licensing-it-turns-out --gpu 2>&1 \
  | tee docs/operations/render-oom/preview-with-gpu.log
```

Outcome categories:
- **A — succeeds:** `Preview ready: ... preview.mp4` line at the bottom; preview.mp4 exists.
- **B — OOM:** process killed / system unresponsive / explicit out-of-memory error.
- **C — different failure:** non-OOM error (e.g. NVENC unsupported, Chrome flag rejected). Capture the error text.

- [ ] **Step 2: Update `findings.md` Step 2 with the outcome**

Replace the `(filled in by Task 4)` placeholder with:

```markdown
## Step 2 — `--gpu` flag

Command: `HF_RENDER_MODE=local bash tools/scripts/run-stage2-preview.sh 2026-04-28-desktop-software-licensing-it-turns-out --gpu`
Log: `docs/operations/render-oom/preview-with-gpu.log`

Outcome: <A / B / C — describe>

If A (succeeded):
  - Wall time: <ms>
  - Peak RSS observed: <if known>
  - **Conclusion of Step 2:** `--gpu` resolves the OOM. Proceed to Task 7 with config fix = "default --gpu on for local-mode previews".

If B (OOM):
  - **Conclusion of Step 2:** GPU offload alone does not resolve. Proceed to Task 5 (narrow measurement).

If C (different failure):
  - Error text: <copy from log>
  - **Conclusion of Step 2:** GPU path is not viable on this host (e.g. NVENC not detected). Proceed to Task 5.
```

- [ ] **Step 3: Commit**

```bash
git add docs/operations/render-oom/findings.md docs/operations/render-oom/preview-with-gpu.log
git commit -m "docs(render-oom): record --gpu diagnostic outcome (Step 2)"
```

---

### Task 5: Narrow empirical measurement on 10 s slice

**Files:**
- Create: `docs/operations/render-oom/measurements.md`
- Modify: `docs/operations/render-oom/findings.md` (Step 4 section)

**Why:** Spec diagnostic step 4. Only runs if Task 4's Conclusion of Step 2 was B or C.

**Decision gate:** Skip if Task 4's outcome was A.

- [ ] **Step 1: Build a 10-second slice fixture**

```bash
mkdir -p episodes/2026-04-28-oom-slice/stage-2-composite/assets
ffmpeg -y -i episodes/2026-04-28-desktop-software-licensing-it-turns-out/master/master.mp4 \
  -t 10 -c copy episodes/2026-04-28-oom-slice/stage-2-composite/assets/master.mp4
# Copy index.html and meta.json from the failing episode
cp episodes/2026-04-28-desktop-software-licensing-it-turns-out/stage-2-composite/index.html \
   episodes/2026-04-28-oom-slice/stage-2-composite/index.html
cp episodes/2026-04-28-desktop-software-licensing-it-turns-out/stage-2-composite/meta.json \
   episodes/2026-04-28-oom-slice/stage-2-composite/meta.json 2>/dev/null || true
```

- [ ] **Step 2: Run with monitoring**

In one terminal, start a process snapshot loop (Windows / Git Bash):

```bash
{
  while sleep 1; do
    echo "=== $(date +%H:%M:%S) ==="
    powershell.exe -Command "Get-Process | Where-Object { \$_.ProcessName -match 'chrome|node|ffmpeg|hyperframes' } | Select-Object ProcessName,Id,@{N='RSS_MB';E={[math]::Round(\$_.WorkingSet64/1MB)}} | Format-Table -AutoSize" 2>/dev/null
    nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader 2>/dev/null
  done
} > docs/operations/render-oom/process-snapshot.log &
SNAPSHOT_PID=$!
```

In a second terminal, run the slice render:

```bash
HF_RENDER_MODE=local bash tools/scripts/run-stage2-preview.sh \
  2026-04-28-oom-slice 2>&1 \
  | tee docs/operations/render-oom/preview-10s-slice.log
```

After it completes (or crashes), stop the snapshot loop:

```bash
kill $SNAPSHOT_PID
```

- [ ] **Step 3: Extract peaks and write `measurements.md`**

Open `docs/operations/render-oom/process-snapshot.log`. For each named process (chrome, node, ffmpeg, hyperframes), find the maximum RSS_MB across all snapshots. Find peak GPU memory used.

Create `docs/operations/render-oom/measurements.md`:

```markdown
# Render OOM Measurements — 10s Slice

**Source:** `episodes/2026-04-28-oom-slice/` (first 10s of failing episode).
**Run command:** `HF_RENDER_MODE=local bash tools/scripts/run-stage2-preview.sh 2026-04-28-oom-slice`
**Snapshot log:** `docs/operations/render-oom/process-snapshot.log`
**Render log:** `docs/operations/render-oom/preview-10s-slice.log`

## Peaks

| Process | Peak RSS (MB) | Notes |
|---|---|---|
| chrome.exe (all instances summed) | <fill> | <count of concurrent processes> |
| node.exe (hyperframes) | <fill> | |
| ffmpeg.exe | <fill> | |
| hyperframes.exe | <fill> | if separate from node |

GPU memory peak: <fill> MB
GPU utilisation peak: <fill> %
Wall time: <fill> s

## Rate of growth

Frames rendered: ~300 (10 s × 30 fps).
Per-frame Chromium RSS delta: <peak - baseline> / 300 = <fill> MB/frame.

## Extrapolation to 53 s

If growth is linear: 53 s × 30 fps = ~1590 frames; projected Chromium peak = baseline + (per-frame RSS × 1590) = <fill> MB.

## Bottleneck identified

(circle one)
- Chromium frame buffer (RSS grows linearly with frames; not freed)
- Chromium per-tab/per-process leak (RSS grows but isn't tied to frame count)
- ffmpeg encode buffer (ffmpeg RSS dominates)
- GPU memory exhaustion (nvidia-smi reports >95 %)
- Other: <describe>

## Implication

- If Chromium frame buffer: HF holds frames in RAM until end-of-encode. Mitigation candidates: chunked render (split into N-second segments and concat); upstream HF fix; or accept Docker fallback.
- If Chromium leak: file upstream issue against HF; short term, Docker fallback contains.
- If ffmpeg buffer: switch encoder (NVENC if --gpu helped at all; or libx264 with `-preset ultrafast` to reduce buffering).
- If GPU exhaustion: not the OOM cause (host RAM is the wall, not GPU VRAM). Re-examine.
```

- [ ] **Step 4: Update `findings.md` Step 4 section**

Replace the `(filled in by Task 5 if needed)` placeholder with:

```markdown
## Step 4 — Narrow empirical measurement

Slice: `episodes/2026-04-28-oom-slice/` (first 10 s of failing episode).
Measurement table: `docs/operations/render-oom/measurements.md`.

Bottleneck identified: <copy from measurements.md>
Projected 53 s peak: <fill>
Projected vs 32 GB host: <within / over>

**Conclusion of Step 4:** <one line — what fix the data points to>
```

- [ ] **Step 5: Commit**

```bash
git add docs/operations/render-oom/measurements.md docs/operations/render-oom/findings.md \
        docs/operations/render-oom/process-snapshot.log docs/operations/render-oom/preview-10s-slice.log
git commit -m "docs(render-oom): narrow empirical measurement on 10s slice (Step 4)"
```

- [ ] **Step 6: Clean up the slice fixture**

The slice episode is investigation-only; delete it and confirm not committed:

```bash
rm -rf episodes/2026-04-28-oom-slice
git status   # confirm no episode directory shows up
```

---

### Task 6: Write final findings + decide

**Files:**
- Modify: `docs/operations/render-oom/findings.md` (Conclusion section)

**Why:** Synthesise Steps 1–4 into a single decision: did a config fix work, or does Docker stand?

- [ ] **Step 1: Write the Conclusion section**

Replace `(filled in by Task 6)` with one of these two templates, populated:

**Template A — config fix won:**
```markdown
## Conclusion

Root cause: <one sentence — e.g. "ffmpeg software encode held all 1590 frames in a software buffer">.
Resolved by: <flag / setting / wrapper change>.

Action items (covered in Tasks 8–9):
- Update `tools/scripts/run-stage2-preview.sh` to default <flag> on in local mode.
- Update `docs/operations/docker-render-verification.md` to reflect that Docker is not required on 32 GB hosts.
- Relax `AGENTS.md` hard rule from "never run local-mode preview/final on real episodes" to "use the wrapper defaults; the duration warning at >30s is sufficient guard".
```

**Template B — Docker stands:**
```markdown
## Conclusion

Root cause: <one sentence>.
Local-mode mitigations exhausted: <list what was tried and didn't resolve>.
Docker remains the only path: <why — e.g. "uncontained Chromium memory growth that no flag mitigates; cgroup needed">.

Action items (covered in Tasks 8–9):
- Revise `docs/operations/docker-render-verification.md` framing: replace "HF requires Docker" with "this dev host's local-mode render path has uncontained memory growth at our resolution × duration; Docker contains it via cgroup".
- Keep `AGENTS.md` hard rule banning local-mode preview/final on real episodes; clarify wording to reflect the host-specific reason rather than HF requirement.
- Schedule Docker installation on the dev host as a separate work item (out of scope of this plan).
```

- [ ] **Step 2: Commit**

```bash
git add docs/operations/render-oom/findings.md
git commit -m "docs(render-oom): conclusion + action items"
```

---

### Task 7: Update `docs/operations/docker-render-verification.md`

**Files:**
- Modify: `docs/operations/docker-render-verification.md`

**Why:** Spec Step 5: independent of which template Task 6 used, that doc currently frames Docker as "HF requirement" — wrong in template A (Docker not required) and inaccurately framed in template B (host-specific bug, not HF policy).

- [ ] **Step 1: Read current contents**

```bash
cat docs/operations/docker-render-verification.md
```

- [ ] **Step 2: Apply revision**

Edit the file. The exact edit depends on Task 6's template:

**If Template A (config fix won):**
- Add an opening section: `## Status: superseded by config fix`
- Body: link to `docs/operations/render-oom/findings.md`. State that on this host class (32 GB RAM, NVIDIA RTX), local mode with `<flag/setting>` renders successfully and Docker is not required for previews. Docker remains a valid byte-identical render path for production-final renders if reproducibility is required, but it is not a memory-safety requirement.
- Leave the rest of the file in place but mark as historical context.

**If Template B (Docker stands):**
- Replace any "HF requires Docker" / "HyperFrames mandates" framing with: "On this dev host (32 GB RAM, Windows), `hyperframes render` in local mode exhibits uncontained memory growth at 1440×2560 × 53 s, exceeding host RAM. Docker's cgroup memory cap contains this. The constraint is host-specific, not an HF policy requirement."
- Add a pointer to `docs/operations/render-oom/findings.md` for the diagnostic record.

- [ ] **Step 3: Commit**

```bash
git add docs/operations/docker-render-verification.md
git commit -m "docs(operations): revise docker-render framing per OOM findings"
```

---

### Task 8: Update `AGENTS.md` hard rule

**Files:**
- Modify: `AGENTS.md`

**Why:** Spec Step 5. Commit `5bce709` introduced a hard rule banning local-mode preview/final on real episodes. Either relax it (Template A) or clarify its rationale (Template B).

- [ ] **Step 1: Locate the current hard rule**

```bash
grep -n "render OOM\|local mode\|run-stage2-preview" AGENTS.md
```

Note the line range of the rule introduced in `5bce709` / `339b5c6`.

- [ ] **Step 2: Apply revision**

**If Template A (config fix won):**

Replace the hard rule with:

```markdown
- **Render in local mode is supported on hosts with `--gpu` available** (or `<other config flag>` per `docs/operations/render-oom/findings.md`).
  - `tools/scripts/run-stage2-preview.sh` defaults to the safe configuration. Do not override defaults unless you have measured the alternative on the same host class.
  - The wrapper emits a stderr warning when an episode > 30 s is rendered in local mode without `--draft`. Heed it.
  - `docs/operations/docker-render-verification.md` is now superseded; Docker is optional, not required.
```

**If Template B (Docker stands):**

Update the existing rule's rationale only:

```markdown
- **Never run `tools/scripts/run-stage2-preview.sh` or `tools/scripts/render-final.sh` in `HF_RENDER_MODE=local` on real episodes.**
  - **Reason (per `docs/operations/render-oom/findings.md`):** on this dev-host class, HF's local-mode render path has uncontained memory growth that exceeds 32 GB RAM at our resolution × duration. Docker's cgroup memory cap contains it. The constraint is host-specific.
  - On hosts without Docker available, hand the render command to the human user; do not attempt local-mode workarounds.
  - Smoke fixtures (short, synthetic) remain safe in local mode and are exempt.
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): revise local-mode render rule per OOM findings"
```

---

### Task 9 (conditional): Update wrapper defaults if config fix won

**Files:**
- Modify: `tools/scripts/run-stage2-preview.sh`

**Why:** Spec Step 5. Only runs if Task 6 used Template A. Bake the winning configuration into the wrapper defaults so future runs are safe by default.

**Decision gate:** Skip if Template B.

- [ ] **Step 1: Identify the winning configuration**

From `docs/operations/render-oom/findings.md` Conclusion: which flag / setting resolved OOM? Common cases:
- `--gpu` resolves → make `GPU=1` the default in local mode.
- `--workers 1` is already forced; no change needed.
- `--quality draft` is already forced; no change needed.
- Other (e.g. an env-var tuning a Chrome flag): apply via `RENDER_FLAGS` extension.

- [ ] **Step 2: Apply the change**

If `--gpu` was the winner, update the local-mode block in `tools/scripts/run-stage2-preview.sh:84-92`:

```bash
elif [ "$HF_RENDER_MODE" = "local" ]; then
  WORKERS=1
  QUALITY=draft
  GPU=1   # default-on for local mode per docs/operations/render-oom/findings.md
```

Otherwise apply the equivalent change for the actual winning configuration.

- [ ] **Step 3: Verify the existing test still passes**

Run: `bash tools/scripts/test/test-stage2-preview-flags.sh`
Expected: both PASS lines.

- [ ] **Step 4: Add a regression test for the new default**

Append to `tools/scripts/test/test-stage2-preview-flags.sh` (before final exit / cleanup):

```bash
# --- default-on regression: --gpu must reach hyperframes even WITHOUT --gpu CLI flag ---

# Reset stub log
: > "$HF_STUB_LOG"

HF_RENDER_MODE=local "$REPO_ROOT/tools/scripts/run-stage2-preview.sh" "$SLUG" \
  || { echo "FAIL: wrapper exited non-zero on default-on scenario"; exit 1; }

if ! grep -q -- "--gpu" "$HF_STUB_LOG"; then
  echo "FAIL: --gpu not default-on for local-mode preview"
  echo "Captured args:"
  cat "$HF_STUB_LOG"
  exit 1
fi

echo "PASS: --gpu default-on for local-mode preview"
```

(Adjust the assertion if a different flag won.)

Run: `bash tools/scripts/test/test-stage2-preview-flags.sh`
Expected: three PASS lines (existing two + new one).

- [ ] **Step 5: Commit**

```bash
git add tools/scripts/run-stage2-preview.sh tools/scripts/test/test-stage2-preview-flags.sh
git commit -m "feat(scripts): default --gpu on for local-mode preview

Per docs/operations/render-oom/findings.md — --gpu resolves OOM
on 32 GB / RTX hosts. Default-on so the wrapper is safe by default
without requiring callers to remember the flag."
```

---

## Self-review

**Spec coverage:**
- Spec Step 1 (doctor capture) → Task 3 ✓
- Spec Step 2 (--gpu flag) → Tasks 1 (plumbing) + 4 (run) ✓
- Spec Step 3 (--quality draft) → Task 3 Step 2 (documented as already-forced; not a separate run) ✓
- Spec Step 4 (narrow measurement) → Task 5 ✓
- Spec Step 5 (config fix or fallback) → Task 6 (decision) + Tasks 7, 8, 9 (action) ✓
- Operational guard (duration warning) → Task 2 ✓
- Artifacts: doctor-output.txt → Task 3; measurements.md → Task 5; findings.md → Tasks 3+4+5+6; updated wrapper → Tasks 1+2+9; updated docker-render-verification → Task 7; updated AGENTS.md → Task 8 ✓

**Placeholders:** all `<fill>` markers in `findings.md` and `measurements.md` are explicit captures the engineer fills as part of running the diagnostic — they are part of the artifact, not unfinished plan steps. Decision-gate language ("If A / If B / If C") reflects genuine branching the spec specifies; not vague TODOs.

**Type/name consistency:** wrapper variables `WORKERS`, `FPS`, `QUALITY`, `GPU`, `USER_QUALITY` are consistent across Tasks 1, 2, and 9.
