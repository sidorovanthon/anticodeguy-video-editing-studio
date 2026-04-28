# HyperFrames upgrade procedure

Single PR per upgrade. The version of `hyperframes` resolved at runtime, the version of skills vendored at `tools/hyperframes-skills/`, and the contract surface in `docs/hyperframes-integration.md` must all stay in sync.

## When to upgrade

`tools/scripts/check-updates.sh` notices upstream versions newer than the local pin and prints a one-line note. That note is the trigger; do not bump on a whim.

## Procedure

1. **Bump the pin.** Edit `tools/compositor/package.json` `dependencies.hyperframes` to the new exact version (no caret, no tilde). Run `cd tools/compositor && npm install` to refresh the lockfile.

2. **Sync the skills.** Run `bash tools/scripts/sync-hf-skills.sh`. The script reads the new pinned version from `package.json` and refreshes `tools/hyperframes-skills/` + `VERSION` to match. If the script aborts on a non-exact pin, recheck step 1.

3. **Read the skills diff.** `git diff tools/hyperframes-skills/`. Pay particular attention to:
   - `SKILL.md` "non-negotiable" sections — new mandatory rules are methodology events.
   - New files under `references/` — new authoring patterns.
   - Removed APIs or deprecated patterns.
   - Changes to runtime globals (`window.__hyperframes.*`).
   Capture every methodology change in the PR description.

4. **Run doctor.** `npx hyperframes doctor` against the local host. All critical checks (Node, FFmpeg, Chrome) must pass. Docker passes only if `HF_RENDER_MODE` defaults to docker.

5. **Run the smoke test (mandatory).**

   ```bash
   bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test
   bash tools/scripts/run-stage2-preview.sh 2026-04-28-phase-6a-smoke-test --draft
   ```

   Both must exit 0 with `lint`/`validate`/`inspect`/`animation-map` green and `preview.mp4` rendering. If anything regresses, fix in the same PR or revert the bump.

6. **Update `docs/hyperframes-integration.md`** if the diff in step 3 added/removed any contract-surface entry (CLI flag, DOM attribute, runtime global, JSON schema, methodology rule).

7. **Open the PR.** Title: `chore(hf): upgrade to <version>`. Body lists methodology changes from step 3.

## Cadence

Operator-driven. A `/schedule`-able background agent that opens upgrade PRs on a cadence is a follow-up after Phase 6a-aftermath; not in this phase.
