# anticodeguy-video-editing-studio

This project is an orchestrator for a two-stage video editing pipeline that chains the
globally-installed `video-use` and `hyperframes` skills into a single command.

## Layout convention

```
inbox/                  # drop zone (gitignored). User places raw video here as <slug>.<ext>.
episodes/               # processed archive (gitignored). One folder per episode.
  <slug>/
    raw.<ext>           # moved here from inbox/ by the orchestrator
    edit/               # produced by video-use: final.mp4, transcripts/raw.json
    hyperframes/        # produced by hyperframes: index.html, package.json, ...
```

**Slug:** filename without its final extension (everything before the last `.`). `inbox/launch-promo.mp4` → slug `launch-promo`. `inbox/foo.bar.mp4` → slug `foo.bar`.

**Supported raw extensions:** `.mp4`, `.mov`, `.mkv`, `.webm`.

## Entry point

The pipeline is invoked exclusively via the slash command `/edit-episode` (defined in
`.claude/commands/edit-episode.md`). Do not invoke `video-use` or `hyperframes` skills
directly from the user's prompt — go through the command so layout and idempotency rules
are honored.

If the user says "edit this video", "process the inbox", "обработай видео", or anything
semantically equivalent, invoke `/edit-episode` (with a slug argument if they named one).

## Idempotency

The command is safe to re-run on the same slug. It resumes from the first missing
artifact: `episodes/<slug>/edit/final.mp4`, then `episodes/<slug>/hyperframes/index.html`,
then studio launch. Skipping Phase 1 when `final.mp4` exists is important — it avoids
re-spending ElevenLabs Scribe credits.

## Branching workflow — non-negotiable

**Every change goes through a feature branch and a GitHub PR. No direct commits to `main`.**

For any non-trivial change (new feature, refactor, multi-file edit):

1. Create a feature branch (`git worktree add .worktrees/<branch> -b <branch>` is the standard pattern; the `superpowers:using-git-worktrees` skill handles this).
2. Commit work on the branch with focused, frequent commits.
3. Push the branch (`git push -u origin <branch>`) and open a PR via `gh pr create --base main` with a Summary + Test plan body.
4. The agent merges the PR via `gh pr merge --squash` (or `--merge` when the per-commit history is worth preserving, like Spec B) once tests pass and the work is complete. Skip the auto-merge only if the user has explicitly asked to review on GitHub themselves.
5. After merge: `git checkout main && git pull` in the main worktree, then clean up: `git worktree remove .worktrees/<branch>` and `git branch -d <branch>` (local). The remote branch is auto-deleted by `gh pr merge --delete-branch` — pass that flag.

Trivial fixes (typo, single-line doc tweak) MAY land directly on main with the user's explicit go-ahead, but the default is "branch + PR".

If a session ends with uncommitted work or an unmerged branch, leave the branch as-is — never reset/discard to "tidy up" without explicit instruction.

**Spec amendments ride along with the implementation PR.** When implementation work surfaces a contradiction or omission in a spec under `docs/superpowers/specs/`, amend the spec in the same PR (separate commit, clear message). Don't open a separate spec-PR unless the amendment is large enough to warrant its own review. Rationale: the contradiction's context is freshest in the implementation PR, and reviewers see the fix and the surfaced inconsistency together.

**`gh pr merge` quirk on Windows worktrees.** If `main` exists as a separate git-worktree and you run `gh pr merge` from a feature worktree, the command exits with `failed to run git: fatal: 'main' is already used by worktree...`. **The remote merge succeeds anyway.** Verify via `gh pr view <n> --json state,mergedAt,mergeCommit` before assuming failure; pull main manually in the main worktree.

## External skill canon — non-negotiable

`video-use` (`~/repos/video-use`, junctioned to `~/.claude/skills/video-use`) and
`hyperframes` (skills at `~/.agents/skills/hyperframes/`, CLI via `npx hyperframes`)
are external products auto-updated on this machine via Task Scheduler. Their source
code, helpers, `SKILL.md` canons, and built-in workflows are **read-only**. Any
orchestrator-side proposal — new script, glue step, brief addition, naming convention
— must first be verified against the **live `SKILL.md`** (not against
`docs/cheatsheets/*` summaries, not against memory) to confirm we are not:

1. Duplicating something the skill already does (look for an existing helper / flag).
2. Pre-empting a canonical executor step (e.g., generating `DESIGN.md` ourselves
   would short-circuit hyperframes' Visual Identity Gate).
3. Drifting from the contract the skill enforces (section numbers, hard-rule
   numbers, file shapes referenced in our verbatim briefs must match canon).

Cheatsheets in `docs/cheatsheets/` are reference summaries — useful for orientation,
but the source of truth for canon checks is the SKILL.md itself. Never propose
patches to upstream `video-use` or `hyperframes` repos; all glue lives in this
orchestrator (`scripts/`, `.claude/commands/edit-episode.md`, `graph/`).

### Decomposition via brief-references-canon (graph orchestration model)

The LangGraph migration (see `docs/superpowers/specs/2026-05-02-langgraph-pipeline-design.md`)
extracts canonical workflow steps from `video-use` and `hyperframes` into individual LLM
nodes in `graph/src/edit_episode_graph/nodes/`. This model post-dates the rules above and
amends them — the original "no pre-empting canonical executor" wording was written under
the monolithic-agent model (`/edit-episode` brief) and does not directly apply to graph
nodes that delegate canonical steps to dispatched sub-agents.

**Decomposition is allowed (and is the chosen orchestration mechanism), provided that:**

1. **Briefs reference canon, do not embed it.** Each LLM node's Jinja2 brief in
   `graph/src/edit_episode_graph/briefs/` cites the canonical `SKILL.md` path
   (e.g. "Canon: `~/.claude/skills/video-use/SKILL.md` §"The process" — Step 2") and
   instructs the dispatched sub-agent to read it. Briefs MUST NOT pre-paraphrase canonical
   instructions or hard-code canonical knowledge — that would fork canon into our brief and
   rot the moment upstream updates. The agent reads canon at call time.
2. **Canonical opt-outs are honored, not bypassed.** When a graph node's policy diverges
   from canon defaults (e.g. "no animations in Phase 3 because Phase 4 produces them"),
   the brief uses the canon's own opt-out mechanism — for video-use animations: "do not
   propose animation plan in Step 4 strategy; emit `overlays: []` in EDL" — rather than
   skipping a canonical step entirely or rewriting the canonical workflow.
3. **Canonical sub-agent boundaries map to graph nodes 1:1.** Where canon explicitly
   defines a sub-agent (video-use Hard Rule 10 animation sub-agents; video-use
   §"Editor sub-agent brief" for EDL selection; hyperframes implicit scene sub-agents
   per `references/prompt-expansion.md`) — those become natural LLM-node boundaries.
   Where canon describes internal main-agent reasoning steps (pre-scan, strategy,
   self-eval, persist) — extracting these into separate nodes IS the chosen orchestration
   mechanism for control + visibility, motivated by empirical monolithic-agent canon
   deviation (see retro-2026-05-02 family — agents skipped fan-out, drew monolithic HTML
   instead of dispatching scene sub-agents, etc.).
4. **The "no duplication" rule (item 1 above) still applies to canonical *content*.**
   Don't generate `DESIGN.md` ourselves before HF Step 1 has run — that's content
   duplication. But spawning an LLM node whose brief says "do canon Step 1 — here's the
   SKILL.md path — produce design.md as your output" is fine; the canonical executor
   still runs, just inside a graph-controlled sub-agent.

The earlier monolithic-agent model trusted one big agent with ~300 lines of canon +
orchestration. Empirically this produced canon deviations. The decomposed graph model
trades looser intra-step canon-trust for structurally-enforced step boundaries plus
deterministic gates between artifacts.

**Definition of done for LLM-node tickets:** before opening the PR, the node MUST satisfy all three of:

1. **Real-CLI smoke.** Run at least one real-CLI invocation through the cheapest available model (e.g. Haiku via per-node `model:` override in `graph/config.yaml`) — a `smoke_<ticket>.py` that synthesizes minimal state and dispatches the node. Mocked unit tests prove parser correctness; only a real subprocess invocation proves the integration (subprocess shape, stdout parsing, schema extraction, telemetry append) actually works. Cost is negligible (~$0.001 per smoke run on Haiku). Document the smoke result in the PR's Test plan.

2. **Topology wiring in the same PR — no deferring to "the integration ticket".** The node MUST be added to `graph.py` (`g.add_node(...)` + conditional/static edges connecting it to the chain) and reachable from the entry point. Defer-until-HOM-127 was the original plan and it bit us: HOM-118 and HOM-119 both shipped un-wired, which meant a re-run on the same slug couldn't actually pick up where it left off. The whole idempotency story is "re-run with same slug → graph resumes from first missing artifact"; that only works if the new node is in the graph. Add a routing helper to `nodes/_routing.py` if a conditional edge is needed; extend `tests/test_p4_topology.py`'s `expected_edges` set with the new edges; extend `smoke_hom107.py`'s `EXPECTED_NODES` set.

3. **Topology check (free, deterministic).** `tests/test_p4_topology.py` (compiled-graph node-set + edge-set assertions) must turn green with the new node added to its `expected_edges`. This is the cheapest gate — it catches "node added but edge not wired" without spending any LLM tokens.

End-to-end-on-a-real-episode smoke (Studio invoke from `pickup` through Phase 4 with a stable fixture episode) is HOM-127's responsibility — the per-ticket DoD does NOT require it, because no stable fixture episode is checked in (`episodes/` is gitignored). But the topology check and the per-ticket node smoke together cover the regressions that matter day-to-day.

### Investigation methodology — bare-repro before upstream-blame

Before claiming any HF or `video-use` behavior is an upstream bug or doc-bug, reproduce in a bare scaffold (`npx hyperframes init` for HF; clean install for `video-use`). If bare-repro succeeds while our pipeline fails — the bug is orchestrator-side. Investigate `scripts/scaffold_*.py`, glue scripts, and brief deltas before opening an upstream issue.

Verified necessary 2026-05-01: three suspected upstream bugs from retro 2026-05-01 (`data-composition-src` sub-comp loader, `gsap_infinite_repeat` lint regex on comments, `<template>` doc-bug) all required investigation before claim. Premature canonization of an "upstream bug" produces wrong memory entries, wrong brief workarounds, and stale GitHub issues — all of which corrupt future sessions.

### Skill copies: docs vs. runnable

The global skill copies (`~/.agents/skills/hyperframes/`, `~/.claude/skills/video-use/`)
are **documentation surfaces** for AI agents — read `SKILL.md`, `patterns.md`,
`visual-styles.md`, etc. from there. Helper scripts shipped alongside (e.g.
`animation-map.mjs`, `contrast-report.mjs`) are present but generally **not runnable
from those paths**: they bootstrap their dependencies via ancestor-walk from the
script's own dir, which only succeeds when the script lives inside the package's
own `node_modules/<skill>/dist/...` layout.

**Rule when invoking a helper script from an external skill:**

1. Default to the bundled copy under the project's `node_modules/<skill>/dist/skills/<skill>/scripts/<name>.mjs`. The version probe and `@hyperframes/producer`-style sibling resolution rely on the package's own manifest as an ancestor.
2. Only fall back to the `~/.agents/...` / `~/.claude/...` copy if you've actually verified it bootstraps in our environment (run it; check exit code, not just file existence).
3. Before declaring a skill helper "broken", try at least: (a) the bundled in-project copy, (b) `npx <skill>` subcommand if the helper has been wrapped, (c) skim the package's `bin`/`scripts` map to see if there's a non-obvious entry point. Code-reading alone is insufficient evidence.

This rule applies to *executable helpers*, not docs. `~/.agents/skills/hyperframes/SKILL.md`, `visual-styles.md`, `house-style.md` etc. should always be read from the global location — that's their canonical home.

**Known Windows blocker:** both `animation-map.mjs` and `contrast-report.mjs` bootstrap `@hyperframes/producer` (and `sharp` for contrast-report) via `npm.cmd` `spawnSync`, which on Windows-Node yields `EINVAL` (a long-standing Node.js Windows quirk on `.cmd` shims). Workaround: once per project, `npm i -D @hyperframes/producer@<exact-version> sharp@<exact-version>` inside the `hyperframes/` project directory. The exact versions are taken from the script's missing-deps error message. After this one-time install, both helpers run without setting `HYPERFRAMES_SKILL_BOOTSTRAP_DEPS=1`. Refs: retro 2026-05-01 §2.7.
