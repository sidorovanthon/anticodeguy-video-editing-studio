# Retro: 2026-04-28-desktop-software-licensing-it-turns-out

## Delta 1 — run-stage2-preview.sh OOM in local mode

**What happened:** Preview render crashed the host twice. First time: run in foreground
Bash (session-killing OOM). Second time: run_in_background workaround proposed and
immediately rejected — background doesn't reduce RAM consumption, same OOM.

**Root cause:** hyperframes render at 1440×2560 with a 53s real episode is memory-
intensive enough to OOM the Windows dev host. Smoke-fixture passed in local mode
because the fixture is short (synthetic, few seconds). Real episode = ~1590 frames
at 30fps draft. Local mode has no cgroup cap; Docker mode does.

**User correction:** Do not paper over with run_in_background. The right fix is Docker
(cgroup memory cap). Confirmed by docs/operations/docker-render-verification.md.

**AGENTS.md fix committed (5bce709):** Hard rule added — never run preview/final in
local mode; Docker required; on hosts without Docker, hand command to user.

**Nuance vs HF methodology:** HF docs say local mode is "fine for iteration" and
Docker is for determinism, not memory safety. Our constraint is empirical: this
host OOMs on real-length episodes. docker-render-verification.md accurately captures
this but attributes it to HF requirement rather than host-specific limit. Should be
clarified in that doc.

`WATCH` — local-mode render is safe for short compositions (smoke fixtures); unsafe
for real episodes on this host. Threshold unknown. Add a duration warning to
run-stage2-preview.sh when HF_RENDER_MODE=local and episode > 30s?

## Delta 2 — pipeline produces no bespoke graphics (Phase 6b gap)

**What happened:** Ran full baseline pipeline new-episode → stage1 → stage2-compose.
seam-plan produced 6 scenes (7–12s each). Scene types assigned by positional cycle
(broll/split/head/split/broll/overlay), no script context. No graphics on any seam.

**User correction:** "Почему мы продолжаем избегать ключевой задачи всей системы?"
User rejected the explanation that this is intentional post-6a/pre-6b state. Decision:
complete baseline pipeline, record gap, then full brainstorm for Phase 6b (agentic
graphics planner + Docker render unblock as prerequisites).

**CONFIRM** — Phase 6b (agentic planner with script-context-driven scene selection
and bespoke per-seam graphics) is the core deliverable. Baseline pipeline is
infrastructure, not the product. Do not run another episode without 6b in place.

## Delta 3 — pipeline stopped at CP2.5 (no preview, no final)

**What happened:** Pipeline stopped at CP2.5 due to OOM. preview.mp4 not produced.
final.mp4 not produced. Episode artifacts: master.mp4 ✓, index.html ✓, seam-plan ✓.

**Blocker:** Docker not installed on dev host. Preview and final render not possible
until Docker is available or alternative render path is established.

**Next action:** Full brainstorm — Docker setup OR alternative render solution,
combined with Phase 6b (agentic planner) planning.
