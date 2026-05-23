# Canon File Index — 2026-05

Flat inventory of every canon file walked while writing the companion document
[`2026-05-canonical-pipeline-algorithm.md`](2026-05-canonical-pipeline-algorithm.md).
This is the source-set the walkthrough cites by `path:line(s)`.

Roots walked (read-only, per CLAUDE.md §"External skill canon — non-negotiable"):

- `C:\Users\sidor\.claude\skills\video-use\` — video-use canonical documentation copy
- `C:\Users\sidor\repos\video-use\` — video-use source repo (helpers, README, install)
- `C:\Users\sidor\.agents\skills\hyperframes\` — hyperframes canonical documentation copy
- `C:\Users\sidor\repos\anticodeguy-video-editing-studio\tests\fixtures\episodes\canonical-portrait-talking-head\hyperframes\node_modules\hyperframes\dist\` — bundled (live-wired) HyperFrames distribution
- `C:\Users\sidor\repos\anticodeguy-video-editing-studio\docs\clean-skills-usage-examples\{hyperframes,video-use}\*.jsonl` — free-form-agent transcripts (observational only, not canon)

**Total canon files walked: 67**
(58 markdown documentation files + 7 Python helpers + 3 JS scripts — counted unique by purpose; the bundled HF dist mirrors the `.agents` copy 1:1 so it counts once.)

Free-form transcripts (17 jsonl) are *observational sources* listed separately at the bottom; they are not canon.

---

## A. video-use canon (entry copy at `~/.claude/skills/video-use/`)

1. `C:\Users\sidor\.claude\skills\video-use\SKILL.md` — Top-level skill manifest. Hard Rules (12), "The process" 8-step pipeline, Cut craft, Editor sub-agent brief, Color grade / Subtitles / Animations sections, EDL format, `project.md` memory.
2. `C:\Users\sidor\.claude\skills\video-use\README.md` — Public-facing overview of the skill: cuts/grades/fades/subtitles/overlays/self-eval/persistence; design principles (5 numbered).
3. `C:\Users\sidor\.claude\skills\video-use\install.md` — First-time install procedure (clone, ffmpeg, skill registration, ElevenLabs API key, verification).
4. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\SKILL.md` — Vendored child skill for Manim-engine animations (read when building a Manim animation slot).
5. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\README.md` — Manim skill overview.
6. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\animation-design-thinking.md` — Designing Manim animations conceptually.
7. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\animations.md` — Manim animation primitives.
8. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\camera-and-3d.md` — Manim 3D and camera controls.
9. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\decorations.md` — Manim decorative elements.
10. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\equations.md` — Equation rendering in Manim.
11. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\graphs-and-data.md` — Charts and graphs in Manim.
12. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\mobjects.md` — Manim object primitives.
13. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\paper-explainer.md` — Paper-explainer Manim template.
14. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\production-quality.md` — Production-quality polish for Manim renders.
15. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\rendering.md` — Manim render commands and codec choices.
16. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\scene-planning.md` — Manim scene planning.
17. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\troubleshooting.md` — Manim troubleshooting.
18. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\updaters-and-trackers.md` — Manim updaters and value trackers.
19. `C:\Users\sidor\.claude\skills\video-use\skills\manim-video\references\visual-design.md` — Manim visual-design conventions.

## B. video-use source repo (`~/repos/video-use/`)

The repo root mirrors the `.claude/skills` copy; the new material is the helpers/ directory.

20. `C:\Users\sidor\repos\video-use\SKILL.md` — Identical to A.1 (read once via the .claude path).
21. `C:\Users\sidor\repos\video-use\README.md` — Identical to A.2.
22. `C:\Users\sidor\repos\video-use\install.md` — Identical to A.3.
23. `C:\Users\sidor\repos\video-use\helpers\transcribe.py` — Single-file ElevenLabs Scribe call (verbatim + diarize + audio events + word-level timestamps). Caches `<edit>/transcripts/<stem>.json`.
24. `C:\Users\sidor\repos\video-use\helpers\transcribe_batch.py` — 4-worker parallel `transcribe.py` across a video directory.
25. `C:\Users\sidor\repos\video-use\helpers\pack_transcripts.py` — Aggregates `transcripts/*.json` into one phrase-level `takes_packed.md` (breaks on silence ≥ 0.5s or speaker change). LLM's primary reading view.
26. `C:\Users\sidor\repos\video-use\helpers\timeline_view.py` — Filmstrip + waveform + word-label composite PNG for a time range (on-demand visual drill-down).
27. `C:\Users\sidor\repos\video-use\helpers\render.py` — Per-segment extract → lossless `-c copy` concat → overlays (PTS-shifted) → subtitles LAST. Hard Rules 1/2/3/4/5 live here.
28. `C:\Users\sidor\repos\video-use\helpers\grade.py` — ffmpeg color-grade filter chain (auto mode + named presets `warm_cinematic` / `neutral_punch` + `--filter '<raw>'`).
29. `C:\Users\sidor\repos\video-use\helpers\isolate_and_transcribe.py` — Combined audio-isolation + transcription helper.
30. `C:\Users\sidor\repos\video-use\helpers\classify_audio.py` — Audio classification helper.
31. `C:\Users\sidor\repos\video-use\helpers\make_previews.py` — Preview-generation helper.
32. `C:\Users\sidor\repos\video-use\helpers\transcribe_doctor_school.py` — Domain-specific transcription helper (Doctor School).

## C. hyperframes canon (entry copy at `~/.agents/skills/hyperframes/`)

33. `C:\Users\sidor\.agents\skills\hyperframes\SKILL.md` — HyperFrames entry: Approach / Step 1 design system / Step 2 prompt expansion / Step 3 plan, `<HARD-GATE>` for visual identity, Layout-Before-Animation rules, Data Attributes tables, Composition Structure, Variables, Video & Audio, Timeline Contract, Rules (Non-Negotiable, 11 items), Scene Transitions (4 non-negotiables), Animation Guardrails, Typography & Assets, Output Checklist, Quality Checks (Inspect / Contrast / Design Adherence / Animation Map), References list.
34. `C:\Users\sidor\.agents\skills\hyperframes\house-style.md` — Creative-direction defaults when no design.md exists: lazy-defaults to question, color, background-layer (2-5 decoratives), motion, typography, palette catalogue.
35. `C:\Users\sidor\.agents\skills\hyperframes\visual-styles.md` — 8 named visual styles (Swiss Pulse, Velvet Standard, Deconstructed, Maximalist Type, Data Drift, Soft Signal, Folk Frequency, Shadow Cut) with mood / best-for / shader pairing tables + DESIGN.md-compatible YAML token blocks.
36. `C:\Users\sidor\.agents\skills\hyperframes\patterns.md` — Composition patterns: Picture-in-Picture, Text-Behind-Subject (transparent webm overlay), slide-show patterns.
37. `C:\Users\sidor\.agents\skills\hyperframes\data-in-motion.md` — Data and stats in video compositions: visual continuity, visual weight pairing, web patterns to avoid (no pie charts / multi-axis / 6-panel dashboards / gridlines / chart libraries).
38. `C:\Users\sidor\.agents\skills\hyperframes\references\prompt-expansion.md` — Always-run Step 2: prerequisites, why-always-run rationale, 6-section output spec, write to `.hyperframes/expanded-prompt.md`.
39. `C:\Users\sidor\.agents\skills\hyperframes\references\beat-direction.md` — Per-beat planning: concept / mood / animation-choreography (energy verb table) / transition / depth layers / SFX cues; rhythm-planning patterns by video type; velocity-matched transition mechanics.
40. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions.md` — Scene-transition selection: 4 non-negotiable animation rules, Energy→Primary table, Mood→Transition table, Narrative-Position table, Blur-Intensity table, presets, CSS-vs-Shader, Shader-Compatible CSS Rules (6 items), Visual-Pattern Warning.
41. `C:\Users\sidor\.agents\skills\hyperframes\references\video-composition.md` — Always-read video-medium rules: design.md is brand not layout, density (8-10 elements), color presence, scale (web→video conversion table), motion intensity, frame composition.
42. `C:\Users\sidor\.agents\skills\hyperframes\references\captions.md` — Captions/subtitles/lyrics: `.en` language rule (non-negotiable), transcript source format, style detection 4 dimensions, per-word styling, script-to-style mapping, word grouping, positioning, text-overflow prevention, caption-exit guarantee (hard `tl.set` kill).
43. `C:\Users\sidor\.agents\skills\hyperframes\references\motion-principles.md` — Motion design: guardrails (don't-defaults), easing-as-emotion, speed-communicates-weight, scene structure (build/breathe/resolve), choreography is hierarchy, asymmetry, visual composition, image-motion treatment, load-bearing GSAP rules (no-iframes / no-double-transform / prefer-fromTo-inside-clip / ambient-pulses-on-tl / hard-kill-every-boundary).
44. `C:\Users\sidor\.agents\skills\hyperframes\references\typography.md` — Banned fonts list (Inter, Roboto, Outfit, Syne, …), guardrails (no-two-sans / one-expressive-per-scene / weight-contrast-extreme / video-sizes), selection thinking, font-discovery script, dark-background adjustments, OpenType features for data.
45. `C:\Users\sidor\.agents\skills\hyperframes\references\techniques.md` — 11 visual techniques with code patterns (SVG drawing, Canvas 2D, CSS 3D, kinetic type, Lottie, video compositing, typing effect, variable fonts, MotionPath, velocity transitions, audio-reactive).
46. `C:\Users\sidor\.agents\skills\hyperframes\references\narration.md` — Voiceover / TTS scripting: pacing (2.5 wps), tone, number pronunciation.
47. `C:\Users\sidor\.agents\skills\hyperframes\references\design-picker.md` — Interactive `.hyperframes/pick-design.html` picker workflow (mood boards / architectures / palettes / type pairings).
48. `C:\Users\sidor\.agents\skills\hyperframes\references\css-patterns.md` — CSS+GSAP marker highlighting: highlight, circle, burst, scribble, sketchout (deterministic, fully seekable).
49. `C:\Users\sidor\.agents\skills\hyperframes\references\audio-reactive.md` — Map audio bands/amplitude to GSAP properties.
50. `C:\Users\sidor\.agents\skills\hyperframes\references\dynamic-techniques.md` — Dynamic caption animation techniques (karaoke, clip-path reveals, slam, scatter, elastic, 3D).
51. `C:\Users\sidor\.agents\skills\hyperframes\references\transcript-guide.md` — Transcript input formats, mandatory quality check, cleaning JS, `.en`-translates-non-English fallback rules, OpenAI/Groq Whisper API curl recipes.
52. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\catalog.md` — Hard Rules (CSS), Scene Template, routing table to per-type implementation references.
53. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-3d.md` — 3D-flip transition implementations.
54. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-blur.md` — Blur-crossfade / focus-pull transitions.
55. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-cover.md` — Staggered blocks / blinds cover transitions.
56. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-destruction.md` — Glitch / VHS / chromatic-aberration / ripple transitions.
57. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-dissolve.md` — Crossfade / color dip dissolves.
58. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-distortion.md` — Distortion-family transitions.
59. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-grid.md` — Grid-dissolve transitions.
60. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-light.md` — Light leak / overexposure / film burn transitions.
61. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-mechanical.md` — Squeeze / shutter / blind mechanical transitions.
62. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-other.md` — Miscellaneous CSS transitions.
63. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-push.md` — Push-slide / whip-pan / vertical-push transitions.
64. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-radial.md` — Circle-iris / diamond-iris / clock-wipe transitions.
65. `C:\Users\sidor\.agents\skills\hyperframes\references\transitions\css-scale.md` — Zoom-through / zoom-out / gravity-drop scale transitions.
66. `C:\Users\sidor\.agents\skills\hyperframes\palettes\bold-energetic.md` — Bold/energetic palette tokens.
67. `C:\Users\sidor\.agents\skills\hyperframes\palettes\clean-corporate.md` — Clean/corporate palette tokens.
68. `C:\Users\sidor\.agents\skills\hyperframes\palettes\dark-premium.md` — Dark/premium palette tokens.
69. `C:\Users\sidor\.agents\skills\hyperframes\palettes\jewel-rich.md` — Jewel/rich palette tokens.
70. `C:\Users\sidor\.agents\skills\hyperframes\palettes\monochrome.md` — Monochrome palette tokens.
71. `C:\Users\sidor\.agents\skills\hyperframes\palettes\nature-earth.md` — Nature/earth palette tokens.
72. `C:\Users\sidor\.agents\skills\hyperframes\palettes\neon-electric.md` — Neon/electric palette tokens.
73. `C:\Users\sidor\.agents\skills\hyperframes\palettes\pastel-soft.md` — Pastel/soft palette tokens.
74. `C:\Users\sidor\.agents\skills\hyperframes\palettes\warm-editorial.md` — Warm/editorial palette tokens.
75. `C:\Users\sidor\.agents\skills\hyperframes\scripts\animation-map.mjs` — Helper script: animation choreography map (`anim-map/animation-map.json` per-tween summaries, ASCII Gantt, stagger detection, dead zones, lifecycle, flags: `offscreen` / `collision` / `invisible` / `paced-fast` / `paced-slow`). Per CLAUDE.md §"Skill copies: docs vs. runnable", invoke the bundled `node_modules/hyperframes/dist/skills/hyperframes/scripts/...` copy on Windows.
76. `C:\Users\sidor\.agents\skills\hyperframes\scripts\contrast-report.mjs` — WCAG contrast audit helper (samples 5 timestamps, screenshots, samples pixels, computes ratios).
77. `C:\Users\sidor\.agents\skills\hyperframes\scripts\package-loader.mjs` — Bootstrap loader for the two scripts above (Windows `npm.cmd` `spawnSync` `EINVAL` workaround: pre-install `@hyperframes/producer` + `sharp` into the HF project).
78. `C:\Users\sidor\.agents\skills\hyperframes\templates\design-picker.html` — HTML template for the `.hyperframes/pick-design.html` design picker.

## D. Bundled HyperFrames distribution (live-wired into HF projects)

At `C:\Users\sidor\repos\anticodeguy-video-editing-studio\tests\fixtures\episodes\canonical-portrait-talking-head\hyperframes\node_modules\hyperframes\dist\`. Each file mirrors a `.agents` counterpart 1:1 (verified by spot-checking `skills/hyperframes/SKILL.md` first 80 lines — byte-identical preamble). Additionally present:

- `dist\docs\compositions.md`, `dist\docs\data-attributes.md`, `dist\docs\examples.md`, `dist\docs\gsap.md`, `dist\docs\rendering.md`, `dist\docs\troubleshooting.md` — surfaced by `npx hyperframes docs <topic>` CLI subcommand.
- `dist\skills\hyperframes-cli\SKILL.md` — CLI sub-skill (init / lint / inspect / preview / render / doctor — invoked by orchestrator scaffolding).
- `dist\skills\gsap\SKILL.md` + `dist\skills\gsap\references\effects.md` — GSAP sub-skill (loaded via `/gsap` slash command).
- `dist\templates\_shared\AGENTS.md`, `dist\templates\_shared\CLAUDE.md` — per-project CLAUDE.md scaffolded by `hyperframes init` (the per-HF-project agent-facing memory; mirrored in the canonical fixture).
- `dist\skills\hyperframes\references\transitions\catalog.md` — bundled mirror of C.52.
- Bundled palettes / references / patterns / house-style / visual-styles / data-in-motion — all 1:1 mirrors of section C.

The bundled copy is what `npx hyperframes …` actually loads at runtime (CLAUDE.md §"Skill copies: docs vs. runnable" — the `.agents` copy is documentation, the bundled copy is runnable).

---

## E. Free-form-agent transcripts (observational, not canon)

Captured in this repo to inform what conventions the free-form agent actually invokes. The walkthrough cites canon, not transcripts; transcripts only surface in Appendix B (orchestrator mapping) where they show free-form behavior that the orchestrator may or may not mirror.

- `docs\clean-skills-usage-examples\hyperframes\0e14ed30-f92c-4555-90c1-49039c2b8ebf.jsonl`
- `docs\clean-skills-usage-examples\hyperframes\1d3276d2-8608-4063-8a44-87327ad6bc3a.jsonl`
- `docs\clean-skills-usage-examples\hyperframes\5509a8c6-afa4-4a62-96c1-6585d1dd3404.jsonl`
- `docs\clean-skills-usage-examples\hyperframes\70126e45-e86e-4063-b14a-aa02981894f9.jsonl`
- `docs\clean-skills-usage-examples\hyperframes\9cfded3d-ed2e-4d75-bedb-67715c5fc847.jsonl`
- `docs\clean-skills-usage-examples\hyperframes\ba749157-6dde-4398-aa04-baaff703403c.jsonl`
- `docs\clean-skills-usage-examples\hyperframes\bd562b6c-a802-413e-b637-889b65cb5e3b.jsonl`
- `docs\clean-skills-usage-examples\hyperframes\c70a1a71-8ea1-4e41-87b2-d3bc2579924e.jsonl`
- `docs\clean-skills-usage-examples\video-use\21030d26-8dc9-4fd0-8162-5a6cab1a6281.jsonl`
- `docs\clean-skills-usage-examples\video-use\2aad6c43-7864-4155-8186-0272eaf00083.jsonl`
- `docs\clean-skills-usage-examples\video-use\3a6055a8-fe1d-479d-af08-9e20c8cfc743.jsonl`
- `docs\clean-skills-usage-examples\video-use\455fd3f5-1750-4237-ba1c-36f545d36179.jsonl`
- `docs\clean-skills-usage-examples\video-use\6e72cf2e-cee1-447f-bab1-ef15dcc8b001.jsonl`
- `docs\clean-skills-usage-examples\video-use\a2317116-7c10-468e-9922-a6373f5f3245.jsonl`
- `docs\clean-skills-usage-examples\video-use\a72d1126-ae68-445b-b9ce-caf8b5c5a26d.jsonl`
- `docs\clean-skills-usage-examples\video-use\f442aa01-9152-4ab6-98c5-a1673fe75b03.jsonl`
- `docs\clean-skills-usage-examples\video-use\fb73f561-6a1a-48f9-8c75-d2b47eaed01d.jsonl`

---

## Notes on counting

- The `.claude/skills/video-use/` tree and the `~/repos/video-use/` tree share three files (SKILL.md, README.md, install.md) — counted once in section A and re-listed in B for traceability; not double-counted in the headline number.
- The Manim-video sub-skill (entries 4-19) is canon for *Manim animation slots only* (one of four animation engines listed in video-use SKILL.md §"Animations") — included for completeness, not deeply walked because the orchestrator does not currently dispatch Manim slots.
- The bundled HF distribution (section D) was confirmed to mirror the `.agents` copy 1:1 by reading `dist/skills/hyperframes/SKILL.md` first 80 lines; the bundled `dist/docs/*.md` and `dist/templates/_shared/{AGENTS,CLAUDE}.md` are unique to the bundle and counted separately in the total.
- Helper Python scripts under `~/repos/video-use/helpers/` are canon: video-use SKILL.md §"Helpers" cites them by bare name and §"Setup" instructs the agent to resolve their paths relative to SKILL.md's directory.
