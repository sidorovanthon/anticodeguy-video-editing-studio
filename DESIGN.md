# DESIGN.md — anticodeguy video editing studio

Brand identity for motion graphics across all episodes. This file is the single source of truth for the visual contract, and the compositor parses the fenced `hyperframes-tokens` JSON block below to emit `:root` CSS variables. Prose sections are read by humans and by coding subagents (Phase 6b) but not parsed.

## Style Prompt

Calm, deliberate, frosted-glass aesthetic on top of talking-head footage. Surfaces are translucent white with subtle blue accents; text is high-contrast white with a quieter secondary tone. Motion is deliberate and short — entrances under half a second, eases ranging from `power3.out` for arrivals to `power2.in` for the rare exit. Nothing flashes, strobes, or screams; the channel's tone is technical-confident, not loud.

## Colors

Roles:
- **bg.transparent** — full-canvas transparent background; the talking-head video sits underneath.
- **glass.fill / glass.stroke / glass.shadow** — frosted-glass surface stack. All sub-compositions that overlay text on video sit on a glass surface.
- **text.primary** — pure white for headings and active captions.
- **text.secondary** — 72%-opacity white for supporting copy.
- **text.accent** — soft sky-blue for highlights, links, and one-word emphasis.
- **caption.active / caption.inactive** — karaoke caption pair: full-white when the word is being spoken, 55% white before/after.

```json hyperframes-tokens
{
  "color": {
    "bg":      { "transparent": "rgba(0,0,0,0)" },
    "glass":   { "fill": "rgba(255,255,255,0.18)", "stroke": "rgba(255,255,255,0.32)", "shadow": "rgba(0,0,0,0.35)" },
    "text":    { "primary": "#FFFFFF", "secondary": "rgba(255,255,255,0.72)", "accent": "#7CC4FF" },
    "caption": { "active": "#FFFFFF", "inactive": "rgba(255,255,255,0.55)" }
  },
  "type": {
    "family": { "caption": "'Inter', system-ui, sans-serif", "display": "'Inter Display', 'Inter', sans-serif" },
    "weight": { "regular": 500, "bold": 700, "black": 900 },
    "size":   { "caption": "64px", "title": "96px", "body": "44px" }
  },
  "blur":     { "glass-sm": "16px", "glass-md": "24px", "glass-lg": "40px" },
  "radius":   { "sm": "16px", "md": "28px", "lg": "44px", "pill": "9999px" },
  "spacing":  { "xs": "8px", "sm": "16px", "md": "24px", "lg": "40px", "xl": "64px" },
  "safezone": { "top": "8%", "bottom": "22%", "side": "6%" },
  "video":    { "width": 1440, "height": 2560, "fps": 60, "color": "rec709-sdr" }
}
```

## Typography

- **Caption / body copy:** `Inter` 500 — 44–64 px depending on emphasis. Tabular-nums on any numeric column.
- **Display / headings:** `Inter Display` 700–900 — 96 px+. Used for title cards and seam-level emphasis only, never on captions.

System-font fallback chain: `system-ui, sans-serif`. The HyperFrames compiler embeds Inter on render.

## Motion

- **Entrances:** `gsap.from()` with `power3.out`, 0.4–0.7 s duration, offset 0.1–0.3 s after the seam start.
- **Holds:** the body of every non-`head` seam is held still — no idle motion, no looping shimmer.
- **Exits:** none, except the final scene of the episode (per HyperFrames scene-transition rules). Seam boundaries handle scene change; the outgoing scene must be fully visible at transition.
- **Vary eases per scene:** at least three different easings across entrances within a single seam composition.

## What NOT to Do

1. **No flashing or strobing.** Anything blinking faster than 2 Hz is rejected at review.
2. **No exit animations except on the final scene.** The scene transition is the exit; per-element fade-out tweens before a transition are a bug.
3. **No off-palette colors.** Hex values come from the JSON block above; no `#333`, no `#3b82f6`, no on-the-fly tints. Adjust within the palette family to fix contrast warnings.
4. **No full-screen linear gradients on dark backgrounds.** H.264 banding makes them ugly. Use a radial gradient or solid + localized glow.
5. **No `Math.random()` / `Date.now()` / network fetches** in any composition — HyperFrames runtime forbids them and the render breaks.
