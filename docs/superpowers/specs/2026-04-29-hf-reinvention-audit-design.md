# HF Reinvention Audit — Design

**Date:** 2026-04-29
**Status:** Stub — to be filled in after `2026-04-29-phase-6b-techdebt-cleanup` lands.
**Parent spec:** `2026-04-29-phase-6b-techdebt-cleanup-design.md` §6

## Goal

Audit the entire pipeline (`tools/compositor/`, `tools/scripts/`, `standards/`,
prompt templates, custom wrappers around HF) for places where we have built or
maintained functionality that HyperFrames already provides. Output is a findings
document plus N follow-up tickets, not a single-feature design.

The narrow audit in the parent spec (§0) answered four targeted questions for
the four planned changes. This spec is the broader sweep: read everything,
catalog every "thing we wrote," compare against HF capabilities.

## Method (to be expanded)

1. Catalog every "thing we wrote." Group by subsystem.
2. For each, identify the closest HF feature.
3. Tag as: `aligned` / `parallel-manifest` / `gap` / `unclear`.
4. For `parallel-manifest`: open a follow-up ticket to migrate to HF API.
5. For `gap`: confirm gap with HF docs; consider upstream feature request.

## Scope (to be defined)

- Reading list: HF source under `tools/compositor/node_modules/hyperframes/dist/`
  (commands, docs, skills, templates), HF README, any HF blog/release notes.
- Per-subsystem checklist:
  - `tools/compositor/src/composer.ts` and friends
  - `tools/compositor/src/planner/` (segmenter, dispatcher, prompts)
  - `tools/compositor/src/state/` (now exists post-D19; check whether HF gains a
    state mechanism in newer versions)
  - `tools/scripts/run-stage*.sh` wrappers
  - `tools/scripts/render-*.sh` wrappers
  - `standards/*.md`
  - Prompt templates under `tools/compositor/src/planner/prompts/`
- Stop condition: every entry in the catalog has a tag and (where applicable)
  a follow-up ticket reference.

## Deliverables

- This document filled in with findings.
- Follow-up tickets in this repo's issue tracker (or specs) per `parallel-manifest` finding.

## Triggering

Run this audit only after the parent spec's acceptance criteria are met. It is
intentionally lower-priority than D19/D3/catalog/flowchart because the parent
spec unblocks production episode work; this audit is hygiene.
