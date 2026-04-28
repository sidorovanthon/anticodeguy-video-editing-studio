# HyperFrames integration — contract surface

The single living document of HF surfaces this project depends on. During an HF version upgrade (see `docs/hyperframes-upgrade.md`), changes to anything below are a methodology event, not a routine bump.

## Pinned version

- CLI: `tools/compositor/package.json` `dependencies.hyperframes` (exact pin, no caret).
- Skills: `tools/hyperframes-skills/VERSION` — must equal the CLI pin.

## CLI commands and parsed flags

We invoke and parse output from:

- `hyperframes lint <dir>` — pass/fail; failure aborts compose.
- `hyperframes validate <dir>` — pass/fail; failure aborts compose.
- `hyperframes inspect <dir> --json` — JSON written to `.inspect.json`; non-zero exit aborts compose.
- `hyperframes animation-map <dir>` — informational; via `tools/hyperframes-skills/hyperframes/scripts/animation-map.mjs`.
- `hyperframes render <dir> -o <name> -f <fps> -q <quality> --format mp4 --workers <n> --max-concurrent-renders <n> [--docker]` — `--docker` is the default render mode.
- `hyperframes doctor` — parsed by `tools/scripts/lib/preflight.sh`.

## DOM data-attributes

- `data-composition-id`, `data-composition-src`
- `data-start`, `data-duration`
- `data-width`, `data-height`
- `data-track-index`
- `data-layout-allow-overflow`, `data-layout-ignore`
- `data-no-capture` (reserved for shader-transition adoption)

## Runtime globals

- `window.__timelines["<id>"]` — timeline registration; `<id>` matches `data-composition-id`.
- `window.__hyperframes.fitTextFontSize(el, { maxFontSize, minFontSize })` — overflow primitive used by captions.

## JSON schemas

- `hyperframes.json` (per-episode `stage-2-composite/`) — `{ $schema, registry, paths: { blocks, components, assets } }`.
- `meta.json` (per-episode `stage-2-composite/`) — `{ id, name, createdAt }`.

## Methodology rules from SKILL.md / references

Pointers; the source files are authoritative. We propagate these into our standards:

- **Visual Identity Gate ordering** (`SKILL.md`) — DESIGN.md is consulted first.
- **Composition Structure** (`SKILL.md`) — `<template>`, scoped styles, `window.__timelines["<id>"]` registration.
- **Scene Transitions Non-Negotiable** (`SKILL.md`, `references/transitions.md`) — every multi-scene composition uses transitions.
- **Captions authoring rules** (`references/captions.md`) — word grouping, per-group hard-kill, `fitTextFontSize`, post-build self-lint.
- **Animation entrance/exit policy** (`SKILL.md`, `references/motion-principles.md`) — entrance on every scene; exits banned except final scene; build/breathe/resolve phasing.
- **Layout Before Animation** (`SKILL.md`) — hero-frame in static CSS, animate from offset.
- **Shader-compat CSS rules** (`references/transitions.md`) — literal hex/RGBA, no `transparent` keyword in gradients, `data-no-capture` for uncapturable elements.
- **Typography compensation** (`references/typography.md`) — weight contrast, tracking, dark-bg compensation; codified in `standards/typography.md`.

## Update protocol

When step 3 of the upgrade procedure (`docs/hyperframes-upgrade.md`) finds a methodology change, update the relevant section above in the same PR. Empty diffs are fine; out-of-date sections are not.
