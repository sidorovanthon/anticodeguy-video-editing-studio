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

**Production data lives on TrueNAS, not locally (HOM-349, 2026-05-24).** `inbox/` and `episodes/` shown above are the *logical* layout. The physical home is `/mnt/Daily SSD/DailySsd/anticodeguy-video-editing-studio/{inbox,episodes}/` on TrueNAS, bind-mounted into the server container at `/deps/graph/{inbox,episodes}`. The operator drops videos into `S:\anticodeguy-video-editing-studio\inbox\` on Windows (existing `\\TRUENAS\Daily SSD` SMB share, mapped as `S:`) — same physical directory the container sees, no rsync, no second path, no symlink. The repo-local `inbox/` and `episodes/` folders stay gitignored and **unused for production runs**; they exist only as path stubs and for local `langgraph dev` work (which per HOM-347 is non-canonical anyway). Tests / fixture-replay are unaffected — they override `HOMESTUDIO_PROJECT_ROOT` to `tests/fixtures/` and never touch production paths. **Never** put production videos in the repo-local `inbox/` — the container won't see them. Source of fix: `graph/docker-compose.truenas.yml` `volumes:` block + `Daily SSD` share permissions (777 / setgid for SMB-as-nobody writes to land usable by container-as-root).

**State-first artifacts (HOM-239 / spec §"Step D2", landed 2026-05-16, breaking).** Under the canonical fixture (`tests/fixtures/episodes/canonical-portrait-talking-head/`) the Phase 4 text artifacts — `hyperframes/index.html`, `hyperframes/captions.html`, `hyperframes/DESIGN.md`, `hyperframes/compositions/*.html`, `hyperframes/.hyperframes/expanded-prompt.md`, and `edit/project.md` — are NO LONGER committed. They are regenerated from `cache.db` on demand by `p4_materialize_disk_node`, the single deterministic disk writer. The producer nodes (`p4_design_system`, `p4_prompt_expansion`, `p4_beat`, `p4_captions_layer`, `p4_assemble_index`, `p4_transitions`, `p4_persist_session`) return body strings in state only — their pre-D2 dual-writes are stripped. Spec ref: `docs/superpowers/specs/2026-05-10-state-first-artifacts.md` §"Step D2".

## Entry point

The pipeline is invoked exclusively via the slash command `/edit-episode` (defined in
`.claude/commands/edit-episode.md`). Do not invoke `video-use` or `hyperframes` skills
directly from the user's prompt — go through the command so layout and idempotency rules
are honored.

If the user says "edit this video", "process the inbox", "обработай видео", or anything
semantically equivalent, invoke `/edit-episode` (with a slug argument if they named one).

## Idempotency

Re-running the graph on the same slug is **structurally safe**: every expensive node
carries a `langgraph.types.CachePolicy(key_func=…)` keyed on slug + content-fingerprint of
its upstream artifacts, and the compiled graph binds a `SqliteCache(graph/.cache/langgraph.db)`.
A re-run on identical inputs produces zero LLM dispatches and zero subprocess calls
(ElevenLabs Scribe, ffmpeg, npx hyperframes); editing one upstream artifact invalidates
exactly the nodes whose `files=` lists it, leaving everything else cached. Coarse
phase-skip edges (`route_after_preflight` short-circuits Phase 3 when `final.mp4` exists)
remain in place as routing — caching is the orthogonal node-body layer.

Source-of-truth design: `docs/superpowers/specs/2026-05-06-langgraph-node-caching-design.md`
(HOM-132 epic). Cache lifecycle is independent from the `langgraph dev` thread
checkpoint store (in-mem PersistentDict at `graph/.langgraph_api/.langgraph_checkpoint.*.pckl`,
or Postgres when running against the TrueNAS stack per HOM-347) — wiping the cache to
force re-execution does not lose thread history. Manual escape hatch:
`rm graph/.cache/langgraph.db`. Per-node `_CACHE_VERSION` integers (in each node module)
must be bumped when its brief / schema / tool-list changes; code-review enforces (spec §8).

**Thread-state persistence across Studio restarts (HOM-346 → HOM-347, AC #5 verified 2026-05-24).** `langgraph dev` uses `langgraph-runtime-inmem`, which serialises checkpoints to `graph/.langgraph_api/.langgraph_checkpoint.*.pckl`. Empirically on Windows this does NOT reliably survive hard `langgraph dev` process restarts — thread metadata persists, but checkpoint state does not (`'NoneType' object is not iterable` on resume). The native fix is LangGraph Self-Hosted Lite (postgres + redis + licensed `langchain/langgraph-api`), NOT a config flag on `langgraph dev`. The stack is deployed to the existing TrueNAS Docker host (no Docker on Windows dev box, by design).

**Live deployment.** Stack at `http://192.168.1.115:8124` (Studio + REST). Three containers, all `homestudio-langgraph-*` prefixed, all isolated from other TrueNAS stacks. Postgres + redis bound to `127.0.0.1` on TrueNAS (LAN-only); server bound to `0.0.0.0:8124` so Windows dev box can reach Studio. Operational commands from repo root: `./deploy.sh --rebuild` (full rebuild — also re-syncs compose + recreates container; use for any compose/env/volume change), `./deploy.sh` (fast server restart — `docker compose restart server` only, does NOT re-sync compose or pick up volume/env changes), `./deploy.sh --status` (container state + recent logs), `./deploy.sh --logs` (tail). For compose-only edits without a code rebuild, scp the file to `/var/lib/homestudio-langgraph/` and `sudo docker compose up -d` to recreate. Server-side secrets at `/var/lib/homestudio-langgraph/.env` on TrueNAS — `LANGSMITH_API_KEY` (free Developer tier, Self-Hosted Lite plan; obtained from <https://smith.langchain.com>) + `HOMESTUDIO_STEP_DEBUG=1` (step-debug walkthroughs always want this on). NEVER committed; local template at `.env.truenas` (gitignored) is your editing surface.

**All HOM-334 step-debug walkthroughs MUST use the TrueNAS stack** — `langgraph dev` is for single-session work only. Detailed runbook (deploy quirks, AC #5 verification curl recipe, troubleshooting) in `graph/README.md` §"Restart-resumable Studio on TrueNAS (HOM-347)".

**Self-Hosted Lite is FREE** (1M node-executions/year limit, irrelevant for step-debug usage). `LANGGRAPH_CLOUD_LICENSE_KEY` is for Enterprise tier — DO NOT confuse the two. Self-Hosted Lite authenticates with `LANGSMITH_API_KEY` (the same one a free Developer-tier LangSmith account gives you).

**Four structural quirks discovered during HOM-347 / HOM-351 / HOM-358 deploy** that any future change to `deploy.sh` / Dockerfile generation must preserve:
1. `uv` clonefile mode fails inside `docker build` on TrueNAS (overlay2 over ZFS) with `Resource temporarily unavailable (os error 11)`. `deploy.sh::ensure_dockerfile()` injects `ENV UV_LINK_MODE=copy` after the generated `FROM` via `sed`. Removing that patch re-breaks the build.
2. The container has no `.git/` (image build doesn't include it). `_paths.repo_root()` walks for `.git` and would crash at import time — fixed by honoring `HOMESTUDIO_REPO_ROOT` env var. Compose sets `HOMESTUDIO_REPO_ROOT=/deps/graph`. `scripts/` is rsynced into `graph/scripts/` for the build context (Approach B, see PR #186); `PYTHONPATH=/deps/graph` makes `python -m scripts.X` resolve. Restructuring without keeping all three pieces re-breaks graph import in the container.
3. The `langgraph dockerfile`-generated base image is Debian-slim with no media tooling; canon (`docs/canon/video-use-algorithm.md:21`) requires `ffmpeg`/`ffprobe` on PATH for `isolate_audio` + `p3_inventory` and any later ffmpeg-using node. `deploy.sh::ensure_dockerfile` injects `RUN apt-get install -y --no-install-recommends ffmpeg` via the same `/^FROM /a` sed mechanism, immediately after the FROM (lands before the UV_LINK_MODE ENV due to sed-append order). Removing that injection re-breaks every Phase 3 node that probes media. Discovered HOM-334 Phase B walkthrough 2026-05-24.
4. The same Debian-slim base ships no Node.js, and its packaged `nodejs` is far below HyperFrames' required `engines.node >=22`. `deploy.sh::ensure_dockerfile` injects a `RUN` layer that registers the NodeSource apt repo (`https://deb.nodesource.com/setup_22.x`) and installs `nodejs` (bundles `node`, `npm`, `npx`) via the same `/^FROM /a` sed mechanism. Required so `npx hyperframes` is resolvable by `p4_final_render` and any other HF-driven graph node. Do NOT swap for Debian's stock `nodejs` package — it's too old and HF will refuse to run. Removing the injection re-breaks every node that shells out to `npx`. Discovered HOM-334 static infra audit, 2026-05-24 (HOM-358).

**LLM cache keys include routing-config fingerprint (HOM-157).** LLM nodes use `make_llm_key`
(not `make_key`), which prepends a sha256 of the effective `NodeConfig`
(`tier`, `model`, `backend_preference`, `timeout_s`) to extras. Bumping `graph/config.yaml`
on a node — e.g. `p3_strategy.timeout_s: 120 → 300` to fix a transient timeout —
auto-invalidates that node's cache without touching anything else. Deterministic
nodes (ffmpeg, file IO) still use `make_key`. Spec §7 mechanism (3).

The legacy `/edit-episode` slash command separately walked artifact existence on disk
(final.mp4 → index.html → studio); that flow predates the LangGraph migration and is now
secondary. Phase 3+ runs through `graph/` + Studio.

## Working from the pipeline roadmap — read milestone before starting

Linear project `LangGraph pipeline migration` (UUID `d693a351-3f37-4053-b54f-297404769d50`) is the source of truth for the version-sequenced roadmap (M1..M6: deterministic graph → Phase 3 LLM → Phase 4 → cutover → hardening → brief/profile). **Before starting any ticket from this project, read its `projectMilestone.description`** — it carries the architectural rationale, sequencing constraints, and close-criteria that determine whether the ticket is even relevant right now, and which sibling tickets are prerequisites.

```powershell
# Get milestone for a ticket (also shows priority + state):
& 'C:\Users\sidor\go\bin\linear-pp-cli.exe' issues HOM-<n> --json | ConvertFrom-Json | Select-Object -ExpandProperty results | Select-Object identifier,priority,@{N='milestone';E={$_.projectMilestone.name}}

# Read milestone body (GraphQL — CLI doesn't surface description on list):
$apiKey = (Get-Content "$env:USERPROFILE\.config\linear-pp-cli\config.toml" | Select-String "api_key" | %% { $_ -replace ".*'(.+)'.*",'$1' })
$body = '{"query":"query { project(id:\"d693a351-3f37-4053-b54f-297404769d50\") { projectMilestones { nodes { name description } } } }"}'
Invoke-RestMethod "https://api.linear.app/graphql" -Method Post -Headers @{Authorization=$apiKey;"Content-Type"="application/json"} -Body $body
```

If a ticket has no milestone, that's a signal: either it predates the roadmap (verify-and-close it as part of an earlier milestone) or it belongs in one — don't just start coding, fix the milestone first. If a ticket's milestone description contradicts the ticket body, surface the contradiction before code lands.

This rule applies to tickets in `LangGraph pipeline migration` only. Other projects (e.g. `Data Migration v2`) have their own conventions.

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

**Disk-I/O lint + fresh-tier prewarm gate (HOM-283).** Any PR that adds a disk read/write call in `graph/src/edit_episode_graph/{nodes,gates}/` must either (a) land in the lint allowlist with a reviewer-justified rationale, OR (b) include a successful fresh-tier `record_fixture` prewarm in the same PR. The lint rule (`tests/test_disk_io_allowlist.py`) fails the build otherwise. Per-line `# disk-io-allow: <reason>` suppressions are honored for narrow exceptions; the reason is read at review time. Rationale: pre-HOM-277 we accumulated 4-5 latent disk-vs-state contract violations that only surfaced on the next fresh-tier prewarm weeks later. The invariant + fresh-tier-gate prevents recurrence.

**Spec amendments ride along with the implementation PR.** When implementation work surfaces a contradiction or omission in a spec under `docs/superpowers/specs/`, amend the spec in the same PR (separate commit, clear message). Don't open a separate spec-PR unless the amendment is large enough to warrant its own review. Rationale: the contradiction's context is freshest in the implementation PR, and reviewers see the fix and the surfaced inconsistency together.

**`gh pr merge` quirk on Windows worktrees.** If `main` exists as a separate git-worktree and you run `gh pr merge` from a feature worktree, the command exits with `failed to run git: fatal: 'main' is already used by worktree...`. **The remote merge succeeds anyway.** Verify via `gh pr view <n> --json state,mergedAt,mergeCommit` before assuming failure; pull main manually in the main worktree.

**Worktree data-dir resolution.** Graph nodes resolve `inbox/` and `episodes/` via `edit_episode_graph._paths.project_root()`. Default: walk up to the main git worktree (linked-worktree `.git` files are skipped) — so a worktree run reads/writes data from the main checkout automatically, no junctions needed. Explicit override: set `HOMESTUDIO_PROJECT_ROOT` to pin a specific path. **Never** create NTFS junctions to `inbox/`+`episodes/` inside a worktree — `Remove-Item -Recurse` on a worktree traverses junctions and wipes the target (lost 6 episodes 2026-05-06; see memory `feedback_powershell_recurse_through_junction`).

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

**Gates must match canon, or they are worse than no gate.** A gate whose blocking criteria
fire on canonical patterns (e.g. canonical caption opacity-0 hidden state flagged as
`invisible`; canonical z-stacked scenes flagged as `collision`) triggers `p4_redispatch_beat`
retry-with-feedback exhaustion and burns LLM budget on content that doesn't need fixing.
Free-form `/hyperframes` runs succeed in part because the agent **triages** lint warnings
(canon-aware FP dismissal); the graph has no triage layer for blocking-class findings, so
any FP in the gate is a redispatch loop. When adding or extending a gate, the carve-out list
MUST be cross-referenced against the canonical patterns that produce the flag — the gate's
own assertions are not the source of truth; canon is. See [retro 2026-05-17 — gate:animation_map
canonical false positives](docs/retros/retro-2026-05-17-gate-animation-map-canonical-false-positives.md)
(HOM-316) for the canonical case study; the diagnostic chain (free-form transcripts vs canon
vs gate code vs recordings) is reusable for the next gate-canon-mismatch hypothesis.

**Carve-out allowlists over LLM-emitted identifiers are structurally wrong.** The HOM-316 retro and follow-up verification (2026-05-17 — `animation-map.json` from the actual halted prewarm prog'd through post-HOM-316 `_extract_flags`) established this empirically: HOM-316's caption/scene carve-outs are correct because `#cg-N` and `#scene-*` are emitted by **code** (`p4_captions_layer`, `p4_scaffold`) and the set is bounded. The next layer of FPs (`div.halo`, `div.ghost`, `div.wash`, `div.plate-tint`, `div.col-rule`, …) is emitted **by the `p4_beat` LLM** as free-form class names — same canonical pattern produces a different vocabulary each prewarm (`grain` / `pf-grain` / `bg-noise` / `film-grain` / `texture-overlay` are all "the same canonical thing"). A substring allowlist against an LLM-emitted vocabulary is an infinite extension by construction; every prewarm produces new synonyms; the gate halts forever. **Do not file "HOM-317: extend `_DEFAULT_DECORATIVE_ALLOWLIST`"-shaped tickets** — that's the wrong direction even when each individual addition is canon-justified. The architecturally correct alternative is the LLM-triage layer (`gate_animation_map_classify`-style Haiku node) extended to all hard-blocking categories (`collision` / `invisible`), with hard-blocking reserved for canon-absolute violations where naming is irrelevant (`offscreen` per `SKILL.md:74` "CSS position is the ground truth"; infra failures). Memory: `feedback_finite_allowlists_against_llm_vocab`.

**Definition of done for LLM-node tickets** (fixture-replay model, HOM-179 / spec
`docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md`). Before opening
the PR, the node MUST satisfy all mandatory items, plus any conditional items that apply.

**Mandatory (every LLM-node PR):**

1. **Brief snapshot test landed/updated (HOM-183).** If your node uses a Jinja brief under
   `graph/src/edit_episode_graph/briefs/`, the corresponding snapshot at
   `tests/snapshots/briefs/<node>.txt` must be updated in the same PR. Run
   `pytest tests/test_brief_snapshots.py --update-snapshots` after authoring/editing
   the brief, then commit both files together. Reviewer reads the brief diff to enforce
   the canon-references-not-embeds rule (CLAUDE.md §"Decomposition via brief-references-canon"
   item 1) — briefs cite `SKILL.md` by path, they do NOT pre-paraphrase canon.

2. **Topology wiring in the same PR — no deferring to "the integration ticket".** The node
   MUST be added to `graph.py` (`g.add_node(...)` + conditional/static edges connecting it
   to the chain) and reachable from the entry point. Defer-until-HOM-127 was the original
   plan and it bit us: HOM-118 and HOM-119 both shipped un-wired, which meant a re-run on
   the same slug couldn't actually pick up where it left off. The whole idempotency story
   is "re-run with same slug → graph resumes from first missing artifact"; that only works
   if the new node is in the graph. Add a routing helper to `nodes/_routing.py` if a
   conditional edge is needed; extend `tests/test_p4_topology.py`'s `expected_edges` set
   with the new edges; extend `EXPECTED_NODES` in any topology test that enumerates the
   compiled-graph node set. The topology test (compiled-graph node-set + edge-set
   assertions) must turn green — this is the cheapest gate, catching "node added but edge
   not wired" without spending any LLM tokens.

3. **Update `halt_llm_boundary` notice text.** Whenever you wire a new node into the Phase 4
   chain, the `halt_llm_boundary_node` notice currently advertises the old "latest reachable"
   artifact (e.g. it still says "render requires p3_render_segments (future)" even though we
   now reach `p4_prompt_expansion`). Update the notice string to mention the newly-reachable
   artifact and what comes next. The notice is the operator's only signal in Studio about
   why the run halted — stale text actively misleads.

**Conditional (apply when the PR scope warrants):**

4. **Schema migration test (L0).** Required if the PR touches a Pydantic state schema.
   Assert the old shape still parses after loosening (forward-compat), so already-recorded
   fixture cache.db rows survive a schema change.

5. **Fingerprint invalidation assertion (HOM-184).** Required if a creative LLM node's
   input set changes (new `files=` entry or new context key in the brief). Add an entry to
   `_NODE_REGISTRY` in `tests/_helpers/fingerprint_assertions.py` so the three parametrised
   invariants (`_CACHE_VERSION` bump, routing-config bump, upstream artifact edit) cover
   the new node automatically. For one-off mutations not expressible via the registry,
   call `assert_fingerprint_changes_when` directly with a custom `mutation_fn`.

6. **Fixture-replay smoke (HOM-180..184).** Required for any creative LLM node. Add a
   `test_<node>_smoke` to `tests/test_graph_replay.py` using `mount_fixture_cache` plus
   the `requires_fixture_cache` `skipif` mark so the suite stays green while the canonical
   fixture cache.db is missing. Recording the fixture is the operator's responsibility:
   `HOMESTUDIO_TEST_MODE=record-on-miss pytest tests/test_graph_replay.py::test_<node>_smoke`
   populates `tests/fixtures/episodes/canonical-portrait-talking-head/cache.db` and the
   per-node JSON dump under `recordings/`. Replay-mode runs (the default) cost $0 once
   the recording lands.

**Removed:** the legacy "real-CLI Haiku smoke" item — `smoke_hom*.py` files were deleted
in HOM-184. Haiku-tier production smokes proved a false economy (HOM-154 retro: Haiku
output triggered `gate:lint` / `gate:design_adherence` redispatch loops costing more than
one successful Opus run; synthetic state missed regressions a real episode caught).
Production-tier replay against a committed cache.db is the new model — recorded once,
replayed deterministically at $0.

**Wave acceptance (L2)** is a separate manual step at M-wave close, NOT per-ticket:
`HOMESTUDIO_TEST_MODE=record pytest tests/test_graph_replay.py` for a paid full E2E real-tier
prewarm, plus eyeball acceptance vs the wave's spec criteria. End-to-end-on-a-real-episode
runs through Studio (pickup through Phase 4 on a real episode) remain HOM-127's
responsibility and are NOT part of the per-ticket DoD.

### Testing infra — fixture replay

Spec source-of-truth: `docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md`
(HOM-179 epic, sub-issues HOM-180..185). Operator runbook lives in `tests/README.md`.

The harness wraps native LangGraph `langgraph.cache.sqlite.SqliteCache` — no parallel
testing infrastructure was rolled, per the §"LangGraph primitives" rule. One env var
picks the behaviour:

| `HOMESTUDIO_TEST_MODE` | Default? | Cache file opened | LLM cost |
| --- | --- | --- | --- |
| `replay` | yes (CI + most dev runs) | fixture cache.db, `sqlite3 mode=ro` | $0 — fails on miss with `ReplayCacheMissError` |
| `record-on-miss` | local dev while iterating on a node | tmp working copy seeded from fixture; misses run real | pay-as-you-go on misses, $0 on hits |
| `record` | wave acceptance only | tmp working copy starts empty | full real-tier run |

**Reviewer expectations on a creative-node PR:**

- Brief snapshot diff — readable text, surfaces canon drift.
- `cache.db` diff under `tests/fixtures/episodes/canonical-portrait-talking-head/` — binary
  but canonical (`VACUUM INTO` + atomic rename produces a deterministic raw form, no WAL
  artefacts).
- JSON dump diff under `tests/fixtures/episodes/<slug>/recordings/<node>.json` — the
  human-readable review surface; the binary cache.db is opaque, the JSON is what you
  actually read. Generated via `python -m pytest --dump-recordings=<slug>` or
  `python -m tests.dump_recordings <slug>` (HOM-182).
- Topology test edits + (where applicable) `_NODE_REGISTRY` entry in
  `tests/_helpers/fingerprint_assertions.py`.

If a PR adds a creative node but ships no recording, the replay smoke skips with
`requires_fixture_cache` — that's expected until the operator records. The PR is mergeable;
recording is a follow-up step on the operator's machine (CI cannot do it, paid tier).

#### Studio replay (operator runbook)

To pick up a recorded fixture episode in `langgraph dev` Studio and walk it
through the full graph at $0 spend (every node hits the committed cache.db):

```powershell
copy tests\fixtures\episodes\canonical-portrait-talking-head\cache.db graph\.cache\langgraph.db
$env:HOMESTUDIO_PROJECT_ROOT = "$PWD\tests\fixtures"
cd graph
.venv\Scripts\langgraph.exe dev --allow-blocking --no-browser
# In the Studio UI: POST a run with slug = canonical-portrait-talking-head
# Resume both interrupts with payload {"resume":"approved"}
```

- **`--allow-blocking`** is required because `_caching.py::file_fingerprint`
  performs synchronous file I/O during graph draw (cache key resolution).
  Without the flag, `langgraph dev` aborts on the first sync read.
- **`HOMESTUDIO_PROJECT_ROOT`** must point at `tests/fixtures` so the
  graph's `_paths.project_root()` resolves `episodes/<slug>/` under the
  fixture tree rather than the repo's gitignored production `episodes/`.
  Without it, Studio sees an empty episode folder and the run halts on
  pickup.
- **Two HITL interrupts** fire on the recorded happy path —
  `strategy_confirmed_interrupt` (after `p3_strategy`) and
  `p3_review_interrupt` (after `p3_persist_session`). Resume each with
  `{"resume":"approved"}` to advance.
- **HF render is NOT in the graph.** The graph terminates at
  `p4_assemble_index` → `gate_*` cluster → `p4_persist_session` →
  `studio_launch`. The actual `npx hyperframes render` call is HOM-78
  (`p4_final_render` node, future). After Studio reports termination,
  the operator runs `npx hyperframes render` manually inside
  `tests/fixtures/episodes/canonical-portrait-talking-head/hyperframes/`.
  Do not conflate "graph terminated" with "pipeline complete".

### LangGraph primitives — search docs before rolling custom

For any LangGraph orchestration concept (idempotent re-run by slug, midpoint dispatch on injected state, per-node caching, conditional retry, durability/persistence tier, fan-out via `Send`, time-travel through thread checkpoints), **search the live LangGraph docs for the native primitive BEFORE designing custom code or scripts**.

Acceptable doc sources: `docs.langchain.com/oss/python/langgraph/*`, `langchain-ai.github.io/langgraph/`, `changelog.langchain.com`. The JS docs (`langchain-ai.lang.chat/langgraphjs/...`) often mirror the Python API and are useful when Python pages 404/redirect.

Concrete primitives that have already covered cases we tried to hand-roll:

- **Idempotent re-run (cache hits across threads/processes):** `langgraph.types.CachePolicy(ttl=…, key_func=…)` per node + `builder.compile(cache=SqliteCache(path=…))`. Hand-rolled "check artifact on disk and skip" was the wrong instinct. (HOM-132 epic adopts this.)
- **Dispatch from the middle of the graph (skip already-completed phases without re-running them):** `client.threads.update_state(thread_id, values=…, as_node="<previous_node>")` + `client.runs.create(thread_id, assistant_id, input=None)`. Graph treats that node as just-completed and follows its outgoing edge. Writing a Python script that imports `_build_node()` and bypasses the runtime is the wrong instinct — it fragments observability (no Trace, no Memory, no replay in Studio).
- **Pause/resume for human input:** `langgraph.types.interrupt({...})` + `Command(resume=...)`. We already use this for `strategy_confirmed_interrupt`.
- **Parallel beat dispatch:** `Send` API with `add_conditional_edges`. Spec §6.4 wires this for fan-out; don't implement parallelism by hand.

**Rules:**

- When you catch yourself thinking "we'd just need to add a check that…", "let me write a small helper that dispatches just this node…", "I'll script around the runtime…" — STOP and WebFetch the docs first. Those phrasings are the smell.
- Cite the specific primitive (with doc URL) in any design note / Linear ticket / PR description that uses it.
- If the docs genuinely don't cover the case, say so explicitly: "Checked $URL — no native primitive for X; rolling custom because Y." That sentence makes future-you not re-burn the cycle.

Burned 2026-05-04 in HOM-120 follow-up: proposed file-system idempotency, then wrote a one-off invocation script — both bypassed native LangGraph mechanisms. Memory `feedback_langgraph_native_primitives` carries the full retro.

**Exception — fixture-replay test inspection (HOM-186, 2026-05-08).** The `update_state(as_node=…)` + `runs.create()` rule applies to **production midpoint dispatch** (skipping already-completed phases on a real run, preserving Studio observability). It does NOT apply to fixture-replay test helpers, where the goal is structurally-guaranteed $0 verification that a recording exists in the cache.db. `tests/_helpers/replay_dispatch.py::dispatch_node` queries `SqliteCache` rows directly via raw SQL + LangGraph's own `JsonPlusSerializer` serde — same deserialization Pregel uses on a cache hit. Going through `compiled.invoke` / `runs.create` would re-evaluate `key_func` against the *test machine's* fingerprint inputs (file paths under `HOMESTUDIO_PROJECT_ROOT`, env, mtimes), so any drift vs the recording machine produces a silent cache miss → real LLM call → paid run inside what claimed to be a $0 replay smoke. Direct-SQL inspection sidesteps that failure mode by construction. The helper's docstring carries the same rationale; do not rewrite it to "go through the runtime" without re-reading this exception. Production code paths still owe `update_state(as_node=…)` — only fixture-inspection helpers are exempt.

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
