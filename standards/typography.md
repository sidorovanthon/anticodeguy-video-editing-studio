# Typography standards

Compensation rules drawn from `tools/hyperframes-skills/hyperframes/references/typography.md`. Apply to every text-bearing sub-composition (captions, titles, lower-thirds, plate copy, future bespoke seams).

## Weight contrast (display vs body)

Pair display weight 700–900 against body/caption weight 400–500. Same-weight stacks read flat on small mobile renders.

| Role | Family | Weight |
|------|--------|--------|
| Display / headline | Inter Display | 700–900 |
| Body / supporting | Inter | 400–500 |
| Caption (active) | Inter | 700 |
| Caption (inactive / muted) | Inter | 500 |

## Tracking (display sizes)

Display copy at 96 px+ tracks tighter to feel intentional, not stretched.

- 96–144 px: `letter-spacing: -0.03em`
- 144 px+:   `letter-spacing: -0.04em` to `-0.05em`

Body copy at ≤64 px uses default tracking. Tabular-nums on numeric columns.

## Dark-background weight compensation

Light text on dark surfaces appears thinner than the same weight on light surfaces. **Bump body and caption weights by one step** when on dark surfaces (which is the default for our talking-head footage):

- Body: 400 → 500
- Caption: 500 → 600 (or stay at 700 for active captions)

This is load-bearing for legibility — captions over the talking-head plate look "fine but slightly off" without it.

## The Inter override

HF's `references/typography.md` lists Inter on the banned-fonts catalogue. We override deliberately; see `DESIGN.md` § Typography for the rationale. Do not switch silently during episode polish — that is a brand decision, not a copy edit.
