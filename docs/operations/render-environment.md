# Render Environment Pre-flight

This pre-flight runs once per dev environment (fresh checkout, new machine, after a Node / FFmpeg / Chrome upgrade). It is *not* required per-render — `tools/scripts/lib/preflight.sh` runs `hyperframes doctor` before every compose / preview / final.

## When to run

- First clone of the repo on a new machine.
- After upgrading Node, FFmpeg, or system Chrome.
- After a `tools/compositor/` `npm install` that bumped `hyperframes`.
- When investigating a render failure (capture full doctor output for the investigation; once Topic 1 lands, an example will live at `docs/operations/render-oom/findings.md` — pending).

## How to run

```bash
"$(pwd)/tools/compositor/node_modules/.bin/hyperframes" doctor 2>&1 \
  | tee docs/operations/render-environment.<host>.txt
```

Replace `<host>` with a short hostname. The output is human-readable; scan for:
- `✗` markers — critical (Node / FFmpeg / FFprobe / Chrome / Docker missing). `lib/preflight.sh` catches these on every render; capturing them here as a one-shot is for debugging.
- Warnings about memory / GPU / hardware acceleration — *not* gated by `lib/preflight.sh`; surface them here for manual triage.
- HF version + Chrome channel + Node version recorded for later cross-reference.

## What the per-render preflight already checks

`tools/scripts/lib/preflight.sh:hf_preflight()` (sourced by every render wrapper) gates on:
- Node, FFmpeg, FFprobe, Chrome present (always fatal).
- Docker present + running (only when `HF_RENDER_MODE=docker` is explicitly set; default mode is `local` and skips this check).

It does *not* gate on:
- Memory warnings.
- GPU / NVENC / hardware acceleration availability.
- HF version skew.

If you need any of those gated, propose the change in `lib/preflight.sh` with a regression test in `tools/scripts/test/`.
