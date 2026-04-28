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

## Delta 4 — scene segmentation must be script-context-driven, not seam-driven

**User observation:** Current architecture maps scenes 1:1 to EDL seams (6 seams →
6 scenes). This is backwards. Seams define edit cut boundaries (where there is a
hard cut that needs to be covered by animation or a transition). Scenes must be
derived independently from script meaning and context, then mapped onto seam
boundaries — not the other way around.

**Correct mental model:**
- EDL seams = where the footage cuts (structural, audio-driven)
- Scenes = what the viewer should see (semantic, script-driven)
- One scene can span multiple seams; one seam does not imply a new scene

**Second anchor — max 5s per scene:** No scene should exceed 5 seconds regardless
of script structure. If the script beat is 12s, it must be subdivided into 2-3
sub-scenes to maintain visual dynamism. The planner must enforce this ceiling as a
hard constraint, not a preference.

**PROMOTE** — scene planning must use two independent inputs: (1) script context
(semantic segmentation by the agentic planner), (2) 5s hard cap per scene. EDL
seam boundaries inform transition placement, not scene count.

## Delta 5 — render OOM is likely misconfiguration, not hardware limitation

**User observation:** This host has 32 GB RAM + NVIDIA RTX GPU. Adobe Media Encoder
renders multiple concurrent heavy videos without stressing the system. Our
hyperframes render crashes the same machine. This is not a hardware problem — it is
a configuration or tooling problem.

**Hypothesis to investigate in brainstorm:**
- HF local mode may not leverage GPU encode (--gpu flag unused, defaulting to CPU)
- Worker count or memory allocation may be set incorrectly for this host spec
- Something in the render pipeline (Chromium headless at 1440×2560) may have
  pathological memory growth that --workers 1 does not fully contain
- Docker may or may not be the right solution for a host that can already handle
  heavy video workloads natively

**WATCH** — before requiring Docker as mandatory, investigate: (a) GPU-accelerated
local render via --gpu flag, (b) worker tuning for 32 GB host, (c) whether Chromium
headless memory is the bottleneck or the ffmpeg encode step.

## Delta 6 — HF pipeline methodology audit required

**User observation:** HF has its own documented methodology and pipeline steps (skills,
AGENTS.md inside HF projects, validation gates). We may be missing steps that HF
considers mandatory or that would improve quality/stability.

**Action for brainstorm:** Do a careful read of:
- tools/hyperframes-skills/hyperframes/SKILL.md
- tools/hyperframes-skills/hyperframes-cli/SKILL.md
- The HF project's own AGENTS.md (in stage-2-composite/ after init)
- hyperframes doctor output
- hyperframes validate + inspect gates

Map what HF recommends vs what our pipeline actually does. Surface gaps.

`WATCH` — any HF-recommended step not in our pipeline is a candidate for promotion
to a required gate.
