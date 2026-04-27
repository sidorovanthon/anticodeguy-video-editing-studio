# Editing standards

## Purpose
Defines what to cut, what to keep, and the philosophy behind pacing for shorts.

## Pacing target
- Shorts run 1–3 minutes total. Aim for high density — every second earns its place.
- Remove silences > 250 ms unless they sit on a deliberate rhetorical pause.
- Remove filler words ("um", "uh", "you know", "like" used as filler) unless they precede a deliberate beat.
- Remove stumbles, restarts, and aborted sentences. Keep only the take that the speaker repeated successfully.

## Cut detection responsibility
- video-use produces the initial `cut-list.md`. The agent does not invent cuts outside what video-use proposes.
- The agent may *suppress* cuts (mark "keep") that video-use proposed if a rule below applies.

## Always-keep rules
- Pause > 300 ms when followed by a tonal shift (drop or rise) — likely deliberate.
- Filler word "you know" when followed by a question form — usually rhetorical.
- The very first 200 ms after the speaker takes a breath at start of a phrase.

## Always-cut rules
- Repeated word at phrase start ("the the", "I I") — keep the second instance.
- Restart of a sentence ("So I — so I think") — keep only the final attempt.
- Audible breath cluster > 400 ms with no speech.

## Seam handling
The visual seam handling rules live in `standards/motion-graphics.md`. This file only governs which cuts to make, not how to mask them.
