# Docker render-mode verification

Status: **deferred-with-reason** (2026-04-28). The current dev host has no
Docker installed, so the F-phase scripts default to `HF_RENDER_MODE=docker`
but are run with `HF_RENDER_MODE=local`. Before declaring `--docker` a hard
production requirement, an operator on a Docker-capable host must run
through this verification.

This document tracks the procedure so the verification is not silently
skipped when the next operator picks it up.

## Context

`hyperframes render --docker` is the only bit-deterministic mode HyperFrames
ships (per `docs/notes/hyperframes-cli.md`). It also gives a hard cgroup
memory cap, which matters at 1440×2560 where local mode wedged the dev host
during Phase 6a. F-phase scripts therefore default to docker mode, with
`HF_RENDER_MODE=local` as an explicit opt-out.

The architectural assumption is "docker mode works as advertised". This
document is the verification of that assumption.

## Prerequisites

- Linux, macOS, or Windows host with Docker Desktop or Docker Engine
  installed and the daemon running.
- Docker version: `docker version` returns a server version (any 24+ is fine).
- `hyperframes doctor` reports OK on Docker and Docker running:

  ```
  hyperframes doctor
  ```

  Expected lines (no leading `✗`):
  - `✓ Docker`
  - `✓ Docker running`

## Procedure

1. Clone or pull the repo at the latest `main`.
2. `cd tools/compositor && npm install` (installs the pinned hyperframes
   binary + applies the `patches/hyperframes+0.4.31.patch`).
3. `cd tools/hyperframes-skills && npm install` (provides
   `@hyperframes/producer` to the vendored skill scripts).
4. From repo root, run the smoke fixture in docker mode:

   ```bash
   HF_RENDER_MODE=docker bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test
   HF_RENDER_MODE=docker bash tools/scripts/run-stage2-preview.sh 2026-04-28-phase-6a-smoke-test
   ```

5. Capture the SHA-256 of the produced `preview.mp4`:

   ```bash
   sha256sum episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/preview.mp4
   ```

6. Repeat steps 4–5 once more (clean re-render, no cache reuse if avoidable).
7. Compare the two SHA-256 values.

## Success criteria

- Both runs complete with exit 0 and `Compose ready:` / `Preview ready:`.
- Both `preview.mp4` SHA-256s match.
- Memory consumption (observe via `docker stats` or host Activity Monitor)
  stays within the cgroup cap declared by HF defaults; the host does not
  swap or wedge.
- `vitest 76/76` (or current count) on the verifying host.

## On success

Append a verification entry to `standards/retro-changelog.md` documenting:

- Host OS + Docker version,
- The two matching SHAs,
- Date of verification.

After that, `HF_RENDER_MODE=docker` may be promoted from "default with local
opt-out" to "hard requirement for production", and `HF_RENDER_MODE=local` can
be marked development-only.

## On failure

Open an issue or retro entry capturing:

- The first failing step,
- `hyperframes doctor` output on the verifying host,
- Any `docker stats` excerpt at the failure point.

The fallback is to keep the current "docker default with local opt-out"
posture and re-evaluate at the next HF version bump.

## Why this is not in CI today

CI hosts on the project's current setup do not have Docker available
either. This is operator-driven verification on a host with Docker
installed.
