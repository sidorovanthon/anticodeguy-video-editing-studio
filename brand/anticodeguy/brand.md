# anticodeguy — brand canon

The brand layer for the `anticodeguy` channel. Adds invariants ON TOP of skill
canon; it never forks or overrides skill-canon production-correctness rules.

## Voice

Direct, dry, builder-to-builder. No hype words, no "game-changer". Short
declarative sentences. Confident but self-aware. Speaks to people who ship.

## Visual identity

High-contrast editorial: near-black ink on off-white paper, one signature lime
accent used sparingly for emphasis. Clash Display for titles, Inter for body.
Generous negative space; motion is purposeful, never decorative for its own sake.

## Layer composition

The resolved brief composes four context layers, lowest precedence first:

`skill_canon  <  profile  <  brand  <  episode_intent`

- **skill_canon** — read-only upstream rules (video-use / hyperframes SKILL.md).
- **profile** — the video-class defaults (pacing, archetype, rhythm, captions).
- **brand** — these files (voice, palette, motion language, CTA, grade).
- **episode_intent** — optional per-episode `intent.yaml` overrides.

On a formal conflict the higher layer wins **except** skill-canon production-
correctness hard rules: the brand layer may NOT disable or override a canonical
hard rule (e.g. audio-pop fades, caption exit guarantees). Brand opinions live
only in the space the skill canon leaves to conversation/style. The precedence
engine that enforces this is the `resolve_episode_brief` node (HOM-166).
