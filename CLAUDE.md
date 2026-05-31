# anticodeguy-video-editing-studio

Orchestrator for a two-stage video editing pipeline that chains the globally-installed
`video-use` and `hyperframes` skills into a single command.

> **North star — read before any course-shaping decision: `docs/north-star.md`.** The end goal
> is a scalable video-editing system with predictable output and minimal operator intervention
> (one-config brand changes propagate to all future videos; point it at a folder of raw videos
> and it batch-processes them with style consistency). LangGraph decomposition is chosen because
> isolated skill runs are structurally non-deterministic (the agent executes the algorithm loosely,
> forgets steps under context overload). If a ticket/spec/edit doesn't move toward that state,
> stop and re-check course. Memory: `project_north_star`.

## Layout convention

```
inbox/                  # drop zone (gitignored). Raw video as <slug>.<ext>.
episodes/               # processed archive (gitignored). One folder per episode.
  <slug>/
    raw.<ext>           # moved here from inbox/ by the orchestrator
    edit/               # produced by video-use: final.mp4, transcripts/raw.json
    hyperframes/        # produced by hyperframes: index.html, package.json, ...
```

- **Slug:** filename without its final extension. `inbox/launch-promo.mp4` → `launch-promo`; `inbox/foo.bar.mp4` → `foo.bar`.
- **Supported raw extensions:** `.mp4`, `.mov`, `.mkv`, `.webm`.

**Production data lives on TrueNAS, not locally (HOM-349).** The `inbox/`/`episodes/` above are the *logical* layout; the physical home is `/mnt/Daily SSD/DailySsd/anticodeguy-video-editing-studio/{inbox,episodes}/`, bind-mounted into the server container at `/deps/graph/{inbox,episodes}`. The operator drops videos into `S:\anticodeguy-video-editing-studio\inbox\` on Windows (the `\\TRUENAS\Daily SSD` SMB share, mapped `S:`) — same physical dir the container sees, no rsync/symlink. The repo-local `inbox/`/`episodes/` stay gitignored and **unused for production**; they exist only as path stubs and for local `langgraph dev`. **Never** put production videos in the repo-local `inbox/` — the container won't see them. Tests override `HOMESTUDIO_PROJECT_ROOT` to `tests/fixtures/` and never touch production paths. Source of fix: `graph/docker-compose.truenas.yml` `volumes:` + `Daily SSD` share permissions (777/setgid).

**State-first artifacts (HOM-239, landed 2026-05-16, breaking).** Under the canonical fixture, the Phase 4 text artifacts (`hyperframes/{index.html,captions.html,DESIGN.md,compositions/*.html,.hyperframes/expanded-prompt.md}`, `edit/project.md`) are NO LONGER committed — they're regenerated from `cache.db` on demand by `p4_materialize_disk_node`, the single deterministic disk writer. Producer nodes return body strings in state only. Spec: `docs/superpowers/specs/2026-05-10-state-first-artifacts.md` §"Step D2".

## Entry point

The pipeline is invoked **exclusively** via the slash command `/edit-episode` (`.claude/commands/edit-episode.md`). Do not invoke `video-use` or `hyperframes` directly — go through the command so layout and idempotency rules are honored. If the user says "edit this video", "process the inbox", "обработай видео", or equivalent, invoke `/edit-episode` (with a slug argument if named).

The legacy `/edit-episode` flow walked artifact existence on disk (final.mp4 → index.html → studio); that predates the LangGraph migration and is now secondary. Phase 3+ runs through `graph/` + Studio (memory `project_graph_replaces_edit_episode`).

## Idempotency

Re-running the graph on the same slug is **structurally safe**: every expensive node carries a `langgraph.types.CachePolicy(key_func=…)` keyed on slug + content-fingerprint of upstream artifacts, and the compiled graph binds `SqliteCache(graph/.cache/langgraph.db)`. A re-run on identical inputs produces zero LLM dispatches and zero subprocess calls; editing one upstream artifact invalidates exactly the nodes whose `files=` lists it. Coarse phase-skip edges (`route_after_preflight` short-circuits Phase 3 when `final.mp4` exists) remain as routing — caching is the orthogonal node-body layer. Manual escape hatch: `rm graph/.cache/langgraph.db`. Per-node `_CACHE_VERSION` integers must be bumped when a node's brief/schema/tool-list changes (code-review enforces). Design: `docs/superpowers/specs/2026-05-06-langgraph-node-caching-design.md` (HOM-132).

- **LLM cache keys include a routing-config fingerprint (HOM-157).** LLM nodes use `make_llm_key` (not `make_key`), which prepends a sha256 of the effective `NodeConfig` (`tier`, `model`, `backend_preference`, `timeout_s`). So bumping `graph/config.yaml` on a node (e.g. `p3_strategy.timeout_s: 120 → 300`) auto-invalidates just that node. Deterministic nodes (ffmpeg, file IO) still use `make_key`.
- **Cache lifecycle is independent from thread checkpoints** — wiping the cache to force re-execution does not lose thread history.

### TrueNAS Studio deployment (step-debug)

`langgraph dev` is for **single-session work only**; its in-memory checkpoint store does not reliably survive hard restarts on Windows. **All HOM-334 step-debug walkthroughs MUST use the TrueNAS Self-Hosted Lite stack** (postgres + redis + licensed `langchain/langgraph-api`).

- **Live stack:** `http://192.168.1.115:8124` (Studio + REST). Three `homestudio-langgraph-*` containers; postgres+redis bound to `127.0.0.1`, server on `0.0.0.0:8124`.
- **Ops (from repo root):** `./deploy.sh --rebuild` (full rebuild — re-syncs compose, recreates container; use for any compose/env/volume change), `./deploy.sh` (fast `docker compose restart server` only), `./deploy.sh --status`, `./deploy.sh --logs`.
- **Secrets** at `/var/lib/homestudio-langgraph/.env` on TrueNAS — `LANGSMITH_API_KEY` + `HOMESTUDIO_STEP_DEBUG=1`. NEVER committed; edit via the gitignored local template `.env.truenas`.
- **Self-Hosted Lite is FREE** (1M node-executions/year, authenticated by `LANGSMITH_API_KEY` from a free Developer-tier LangSmith account). `LANGGRAPH_CLOUD_LICENSE_KEY` is Enterprise — DO NOT confuse them.
- **Full runbook** (one-time setup, AC #5 verification curls, the six deploy-time `sed`/volume quirks that any `deploy.sh`/Dockerfile/compose change MUST preserve): `graph/README.md` §"Restart-resumable Studio on TrueNAS". TrueNAS host access: memory `reference_truenas_access`.

## Working from the pipeline roadmap — read milestone before starting

Linear project `LangGraph pipeline migration` (UUID `d693a351-3f37-4053-b54f-297404769d50`) is the source of truth for the version-sequenced roadmap (M1..M6). **Before starting any ticket from this project, read its `projectMilestone.description`** — it carries the architectural rationale, sequencing constraints, and close-criteria that determine whether the ticket is even relevant right now, and which siblings are prerequisites.

```powershell
# Get milestone for a ticket (also shows priority + state):
& 'C:\Users\sidor\go\bin\linear-pp-cli.exe' issues HOM-<n> --json | ConvertFrom-Json | Select-Object -ExpandProperty results | Select-Object identifier,priority,@{N='milestone';E={$_.projectMilestone.name}}

# Read milestone body (GraphQL — CLI doesn't surface description on list):
$apiKey = (Get-Content "$env:USERPROFILE\.config\linear-pp-cli\config.toml" | Select-String "api_key" | %% { $_ -replace ".*'(.+)'.*",'$1' })
$body = '{"query":"query { project(id:\"d693a351-3f37-4053-b54f-297404769d50\") { projectMilestones { nodes { name description } } } }"}'
Invoke-RestMethod "https://api.linear.app/graphql" -Method Post -Headers @{Authorization=$apiKey;"Content-Type"="application/json"} -Body $body
```

If a ticket has no milestone, that's a signal: either it predates the roadmap (verify-and-close as part of an earlier milestone) or it belongs in one — fix the milestone first, don't just start coding. If a ticket's milestone description contradicts the ticket body, surface that before code lands. **This rule applies to `LangGraph pipeline migration` tickets only**; other projects have their own conventions.

## Branching workflow — non-negotiable

**Every non-trivial change goes through a feature branch and a GitHub PR. No direct commits to `main`.**

1. Create a feature branch (`git worktree add .worktrees/<branch> -b <branch>` is standard; the `superpowers:using-git-worktrees` skill handles this).
2. Commit on the branch with focused, frequent commits.
3. Push (`git push -u origin <branch>`) and open a PR via `gh pr create --base main` with Summary + Test plan.
4. The agent merges via `gh pr merge --squash --delete-branch` (or `--merge` when per-commit history matters) once tests pass and a code review has run. Skip auto-merge only if the user explicitly asks to review on GitHub.
5. After merge: `git checkout main && git pull` in the main worktree, then `git worktree remove .worktrees/<branch>` and `git branch -d <branch>`.

Trivial fixes (typo, single-line doc tweak) MAY land directly on main with explicit go-ahead, but the default is "branch + PR". If a session ends with uncommitted work or an unmerged branch, leave it as-is — never reset/discard to "tidy up" without explicit instruction.

- **Disk-I/O lint + fresh-tier prewarm gate (HOM-283).** Any PR adding a disk read/write in `graph/src/edit_episode_graph/{nodes,gates}/` must either (a) land in the lint allowlist with a reviewer-justified rationale, or (b) include a successful fresh-tier `record_fixture` prewarm in the same PR. `tests/test_disk_io_allowlist.py` fails the build otherwise; per-line `# disk-io-allow: <reason>` suppressions are honored. Prevents the latent disk-vs-state contract violations that used to surface weeks later on the next prewarm.
- **Spec amendments ride along with the implementation PR.** When implementation surfaces a contradiction/omission in a spec under `docs/superpowers/specs/`, amend the spec in the same PR (separate commit). The context is freshest there and reviewers see fix + inconsistency together.
- **`gh pr merge` quirk on Windows worktrees.** If `main` is a separate worktree, running `gh pr merge` from a feature worktree exits with `fatal: 'main' is already used by worktree...` — **but the remote merge succeeds anyway.** Verify via `gh pr view <n> --json state,mergedAt,mergeCommit`; pull main manually.
- **Worktree data-dir resolution.** Graph nodes resolve `inbox/`/`episodes/` via `_paths.project_root()` (walks up to the main worktree; linked-worktree `.git` files are skipped), so a worktree run reads/writes data from the main checkout automatically. Override with `HOMESTUDIO_PROJECT_ROOT`. **Never** create NTFS junctions to `inbox/`+`episodes/` inside a worktree — `Remove-Item -Recurse` traverses junctions and wipes the target (lost 6 episodes 2026-05-06; memory `feedback_powershell_recurse_through_junction`).

## External skill canon — non-negotiable

`video-use` (`~/repos/video-use`, junctioned to `~/.claude/skills/video-use`) and `hyperframes` (skills at `~/.agents/skills/hyperframes/`, CLI via `npx hyperframes`) are external products auto-updated via Task Scheduler. Their source, helpers, `SKILL.md` canons, and workflows are **read-only**. Any orchestrator-side proposal (script, glue step, brief addition, naming) must first be verified against the **live `SKILL.md`** (not `docs/cheatsheets/*`, not memory) to confirm we are not:

1. Duplicating something the skill already does (look for an existing helper/flag).
2. Pre-empting a canonical executor step (e.g. generating `DESIGN.md` ourselves short-circuits hyperframes' Visual Identity Gate).
3. Drifting from the contract the skill enforces (section numbers, hard-rule numbers, file shapes in our verbatim briefs must match canon).

Cheatsheets in `docs/cheatsheets/` are orientation summaries; the source of truth for canon checks is the SKILL.md itself. Never propose patches to upstream `video-use`/`hyperframes`; all glue lives in this orchestrator.

### Decomposition via brief-references-canon (graph orchestration model)

The LangGraph migration (`docs/superpowers/specs/2026-05-02-langgraph-pipeline-design.md`) extracts canonical workflow steps from the skills into individual LLM nodes in `graph/src/edit_episode_graph/nodes/`. This post-dates and amends the rules above — the "no pre-empting canonical executor" wording was written under the monolithic-agent model and doesn't apply to graph nodes that delegate canonical steps to dispatched sub-agents. Decomposition is the chosen orchestration mechanism, provided that:

1. **Briefs reference canon, do not embed it.** Each node's Jinja2 brief (`graph/src/edit_episode_graph/briefs/`) cites the canonical `SKILL.md` path (e.g. "Canon: `~/.claude/skills/video-use/SKILL.md` §The process — Step 2") and tells the sub-agent to read it. Briefs MUST NOT pre-paraphrase canon or hard-code canonical knowledge — that forks canon and rots on the next upstream update.
2. **Canonical opt-outs are honored, not bypassed.** When a node diverges from canon defaults (e.g. "no animations in Phase 3 — Phase 4 produces them"), use canon's own opt-out (for video-use animations: "do not propose animation plan in Step 4 strategy; emit `overlays: []` in EDL"), not a skipped step.
3. **Canonical sub-agent boundaries map to graph nodes 1:1.** Where canon defines a sub-agent (video-use Hard Rule 10 animation sub-agents; §"Editor sub-agent brief" for EDL; hyperframes scene sub-agents per `references/prompt-expansion.md`), those are the natural node boundaries. Where canon describes internal main-agent reasoning (pre-scan, strategy, self-eval, persist), extracting those into nodes IS the chosen mechanism for control + visibility (motivated by empirical monolithic-agent canon deviation).
4. **The "no duplication" rule still applies to canonical *content*.** Don't generate `DESIGN.md` before HF Step 1 has run (content duplication). But a node whose brief says "do canon Step 1 — here's the SKILL.md path — produce design.md" is fine: the canonical executor still runs, inside a graph-controlled sub-agent.

The decomposed model trades looser intra-step canon-trust for structurally-enforced step boundaries plus deterministic gates between artifacts. Memory: `feedback_graph_decomposition_brief_references_canon`.

### Gates must match canon, or they are worse than no gate

A gate whose blocking criteria fire on canonical patterns (e.g. canonical caption opacity-0 hidden state flagged as `invisible`; canonical z-stacked scenes flagged as `collision`) triggers `p4_redispatch_beat` retry exhaustion and burns LLM budget on content that doesn't need fixing. Free-form `/hyperframes` runs succeed partly because the agent **triages** lint warnings; the graph has no triage layer for blocking-class findings, so any FP is a redispatch loop. When adding/extending a gate, cross-reference the carve-out list against the canonical patterns that produce the flag — **canon is the source of truth, not the gate's own assertions.** Case study + reusable diagnostic chain: `docs/retros/retro-2026-05-17-gate-animation-map-canonical-false-positives.md` (HOM-316); memory `feedback_gate_carveouts_must_match_canon`.

- **Carve-out allowlists over LLM-emitted identifiers are structurally wrong.** Code-emitted IDs (`#cg-N`, `#scene-*` from `p4_captions_layer`/`p4_scaffold`) are bounded and fine to allowlist. But free-form class names emitted by the `p4_beat` LLM (`halo`/`ghost`/`wash`/`grain`/`film-grain`/`texture-overlay`/…) are an unbounded vocabulary — the same canonical thing gets a new synonym every prewarm, so a substring allowlist is an infinite extension and the gate halts forever. **Do not file "extend `_DEFAULT_DECORATIVE_ALLOWLIST`"-shaped tickets.** The correct alternative is the LLM-triage layer (`gate_animation_map_classify`-style cheap node) extended to all hard-blocking categories, with hard-blocking reserved for canon-absolute violations where naming is irrelevant (`offscreen` per `SKILL.md:74` "CSS position is the ground truth"; infra failures). Memory: `feedback_finite_allowlists_against_llm_vocab`.

### Definition of done for LLM-node tickets

Fixture-replay model (HOM-179, spec `docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md`). Before opening the PR, satisfy all mandatory items + any conditional ones that apply. Memory: `feedback_fixture_replay_dod`.

**Mandatory (every LLM-node PR):**
1. **Brief snapshot updated (HOM-183).** If the node uses a Jinja brief, update `tests/snapshots/briefs/<node>.txt` in the same PR (`pytest tests/test_brief_snapshots.py --update-snapshots`, commit both). The reviewer reads the diff to enforce the canon-references-not-embeds rule.
2. **Topology wiring in the same PR — no deferring to "the integration ticket".** Add the node to `graph.py` (`g.add_node` + edges) and make it reachable; add a routing helper to `nodes/_routing.py` if a conditional edge is needed; extend `expected_edges` in `tests/test_p4_topology.py` and `EXPECTED_NODES` in any topology test. The topology test must turn green — the cheapest gate, catching "node added but edge not wired" at $0. (Un-wired nodes broke resume in HOM-118/119.)
3. **Update `halt_llm_boundary` notice text** to mention the newly-reachable artifact and what comes next — it's the operator's only Studio signal for why the run halted; stale text misleads.

**Conditional (when scope warrants):**
4. **Schema migration test (L0)** — if the PR touches a Pydantic state schema, assert the old shape still parses (forward-compat) so recorded `cache.db` rows survive.
5. **Fingerprint invalidation assertion (HOM-184)** — if a creative node's input set changes (new `files=` or context key), add an entry to `_NODE_REGISTRY` in `tests/_helpers/fingerprint_assertions.py` (or call `assert_fingerprint_changes_when` for one-offs).
6. **Fixture-replay smoke (HOM-180..184)** — for any creative node, add `test_<node>_smoke` to `tests/test_graph_replay.py` using `mount_fixture_cache` + the `requires_fixture_cache` skipif. Recording is the operator's job: `HOMESTUDIO_TEST_MODE=record-on-miss pytest …::test_<node>_smoke`. Replay-mode runs cost $0 once the recording lands; a PR shipping no recording is still mergeable (smoke skips).

**Wave acceptance (L2)** is a separate manual step at M-wave close, NOT per-ticket: `HOMESTUDIO_TEST_MODE=record pytest tests/test_graph_replay.py` (paid full E2E) + eyeball acceptance vs the wave's spec. End-to-end-on-a-real-episode through Studio is HOM-127's responsibility. (The legacy "real-CLI Haiku smoke" was removed in HOM-184 — Haiku output triggered gate redispatch loops costing more than one Opus run.)

### Testing infra — fixture replay

Spec: `docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md` (HOM-179). Operator runbook + the full mode table: **`tests/README.md`**. The harness wraps native `langgraph.cache.sqlite.SqliteCache` — no parallel infra. `HOMESTUDIO_TEST_MODE` picks behaviour: `replay` (default, $0, fails on miss), `record-on-miss` (local dev, pay on misses), `record` (wave acceptance, full real-tier). Studio replay of the canonical fixture at $0: `tests/README.md` §"Studio replay (operator runbook)".

Reviewer expectations on a creative-node PR: brief snapshot diff; `cache.db` diff (binary but canonical); the human-readable JSON dump under `tests/fixtures/episodes/<slug>/recordings/<node>.json` (generated via `python -m tests.dump_recordings <slug>`, HOM-182); topology edits + any `_NODE_REGISTRY` entry.

### LangGraph primitives — search docs before rolling custom

For any LangGraph orchestration concept (idempotent re-run by slug, midpoint dispatch, per-node caching, conditional retry, durability tier, fan-out, time-travel), **search the live LangGraph docs for the native primitive BEFORE designing custom code.** Sources: `docs.langchain.com/oss/python/langgraph/*`, `langchain-ai.github.io/langgraph/`, `changelog.langchain.com` (the JS docs often mirror the Python API when Python pages 404).

Primitives that already covered cases we tried to hand-roll:
- **Idempotent re-run:** `CachePolicy(ttl=…, key_func=…)` per node + `compile(cache=SqliteCache(…))`. (HOM-132)
- **Midpoint dispatch (skip completed phases):** `client.threads.update_state(thread_id, values=…, as_node="<prev>")` + `client.runs.create(thread_id, assistant_id, input=None)`. Importing `_build_node()` and bypassing the runtime fragments observability — don't.
- **Pause/resume for human input:** `interrupt({...})` + `Command(resume=...)` (already used for `strategy_confirmed_interrupt`).
- **Parallel beat dispatch:** `Send` API with `add_conditional_edges` (spec §6.4).

When you catch yourself thinking "we'd just need a check that…" / "a small helper that dispatches just this node…" / "I'll script around the runtime…" — STOP and WebFetch the docs first. Cite the primitive (with URL) in the design note/ticket/PR. If the docs genuinely don't cover it, say so explicitly ("Checked $URL — no native primitive for X; rolling custom because Y"). Burned 2026-05-04 (HOM-120); memory `feedback_langgraph_native_primitives`.

- **Exception — fixture-replay test inspection (HOM-186).** The `update_state(as_node=…)` rule applies to **production** midpoint dispatch. It does NOT apply to fixture-replay helpers: `tests/_helpers/replay_dispatch.py::dispatch_node` queries `SqliteCache` rows directly via raw SQL + LangGraph's own `JsonPlusSerializer` — going through `compiled.invoke`/`runs.create` would re-evaluate `key_func` against the *test machine's* fingerprint inputs (paths, env, mtimes), so any drift vs the recording machine becomes a silent cache miss → real paid LLM call inside a "$0" smoke. Production code paths still owe `update_state(as_node=…)`.

### Investigation methodology — bare-repro before upstream-blame

Before claiming any HF or `video-use` behavior is an upstream bug, reproduce in a bare scaffold (`npx hyperframes init` for HF; clean install for `video-use`). If bare-repro succeeds while our pipeline fails, the bug is orchestrator-side — investigate `scripts/scaffold_*.py`, glue scripts, and brief deltas first. Verified necessary 2026-05-01: three suspected upstream bugs all required investigation before claim. Premature canonization of an "upstream bug" produces wrong memory, wrong brief workarounds, and stale GitHub issues.

### Skill copies: docs vs. runnable

The global skill copies (`~/.agents/skills/hyperframes/`, `~/.claude/skills/video-use/`) are **documentation surfaces** — read `SKILL.md`, `patterns.md`, `visual-styles.md` etc. from there. Helper scripts shipped alongside (`animation-map.mjs`, `contrast-report.mjs`) are present but generally **not runnable from those paths** (they bootstrap deps via ancestor-walk that only succeeds inside the package's own `node_modules/<skill>/dist/...` layout).

When invoking a helper script from an external skill:
1. Default to the bundled copy under `node_modules/<skill>/dist/skills/<skill>/scripts/<name>.mjs`.
2. Only fall back to the `~/.agents/...` / `~/.claude/...` copy if you've **verified it bootstraps** here (run it; check exit code, not just file existence).
3. Before declaring a helper "broken", try: (a) the bundled in-project copy, (b) `npx <skill>` subcommand, (c) the package's `bin`/`scripts` map for a non-obvious entry point. Code-reading alone is insufficient evidence.

This applies to *executable helpers*, not docs (always read SKILL.md/visual-styles.md from the global location). **Known Windows blocker:** both `animation-map.mjs` and `contrast-report.mjs` bootstrap `@hyperframes/producer` (and `sharp`) via `npm.cmd` `spawnSync`, which yields `EINVAL` on Windows-Node. Workaround: once per project, `npm i -D @hyperframes/producer@<exact-version> sharp@<exact-version>` inside the `hyperframes/` dir (exact versions from the script's error message). Memory: `feedback_bundled_helper_path`.
