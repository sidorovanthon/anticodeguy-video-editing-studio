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

**Base palette:** custom — not a derivative of any catalog palette in `tools/hyperframes-skills/hyperframes/palettes/`. The frosted-glass-on-dark aesthetic is channel-specific. If a palette deviation is requested per-episode, document it in that episode's `notes.md`; never override DESIGN.md's tokens.

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
  "video":    { "width": 1440, "height": 2560, "fps": 60, "color": "rec709-sdr" },
  "transition": { "primary": "crossfade", "duration": 0.4, "easing": "power2.inOut" }
}
```

## Typography

- **Caption / body copy:** `Inter` 500 — 44–64 px depending on emphasis. Tabular-nums on any numeric column.
- **Display / headings:** `Inter Display` 700–900 — 96 px+. Used for title cards and seam-level emphasis only, never on captions.

System-font fallback chain: `system-ui, sans-serif`. The HyperFrames compiler embeds Inter on render.

**Inter override (intentional):** HF's `references/typography.md` lists Inter on the banned-fonts catalogue (it's an over-used default). We override deliberately: the channel's calm-technical voice is well-served by a neutral grotesque, and Inter's tabular-nums + display variants cover our needs without introducing a second family. Re-evaluate during channel rebrands; do not switch silently.

## Transitions

The channel's primary scene-to-scene transition is a 0.4 s crossfade with `power2.inOut` easing — calm, neutral, non-disruptive. This matches the "calm / brand story" energy bucket from `tools/hyperframes-skills/hyperframes/references/transitions.md`. Per HF's non-negotiable rules, every multi-scene composition uses transitions; jump cuts are a bug. Bolder primaries (`blur-crossfade`, `push-slide`, `zoom-through`) are catalog-spelled and reserved for episodes whose mood explicitly calls for them.

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
6. **No `var(--…)` on captured elements.** html2canvas (used by shader transitions) does not reliably resolve custom properties. The compositor inlines literal hex/RGBA into element styles. `:root { --… }` declarations may exist in `<head>` for documentation/fallback, but no element style consumed by capture references them via `var()`.
7. **No `transparent` keyword in gradients.** Canvas interpolates `transparent` as `rgba(0,0,0,0)` — black at zero alpha — creating dark fringes. Use the target colour at zero alpha: `rgba(255,255,255,0)`, never `transparent`.
8. **No gradient backgrounds on elements thinner than 4 px.** Canvas can't match CSS gradient rendering at 1–2 px. Use a solid `background-color` on thin accent lines.
9. **Mark uncapturable decorative elements with `data-no-capture`.** They render in the live DOM but skip the shader texture; use this for elements that violate the rules above.
10. **No gradient opacity below 0.15.** Below 10 % opacity, canvas and CSS render gradients differently. Bump to 0.15+ or use a solid colour at equivalent brightness.
11. **Every `.scene` div carries an explicit `background-color`** matching the `init({ bgColor })` config. Without both, the scene texture renders as black.
