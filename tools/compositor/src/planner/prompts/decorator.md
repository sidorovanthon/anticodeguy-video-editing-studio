# Decorator — Mode + Graphic

You receive a list of scenes (already segmented and snapped) plus the project's visual direction. Decide, for each scene, the `scene_mode` (when rules don't pin it) and the `graphic` (when the scene is not pure talking head).

## Inputs

### Scenes
{{SCENES_JSON}}

### `seamsInsideScene` per scene index
{{SEAMS_INSIDE_JSON}}

### Project DESIGN.md (Style Prompt + What NOT to Do)
{{DESIGN_PROMPT}}

### `standards/motion-graphics.md` Catalog
{{CATALOG_TABLE}}

### Hard rules pre-applied
The dispatcher pre-narrowed `mode` candidates per scene to those allowed by hard rules. Where pre-narrow yielded one candidate, you must use it; only choose when multiple candidates remain.

## Output

Return a JSON array, no prose:

```json
{
  "scene_index": 0,
  "mode": "split",
  "graphic": {
    "source": "generative",
    "brief": "1–2 paragraph brief...",
    "data": { "items": ["A", "B", "C"] }
  }
}
```

`graphic.source`: `"none"` | `"catalog/<name>"` | `"generative"`. `<name>` must be from the catalog table. For `mode == "head"`, `graphic.source` must be `"none"`.

For `generative`, the brief names: layout (split-frame? overlay-plate? full broll?), entrance choreography (stagger, eases, durations), decorative elements (frosted glass surface? hairline rules? glow?), and data anchor (numbers, list items, quote).

**Same-graphic prohibition.** If the previous scene had the same mode (split→split or broll→broll), your `brief` must be visibly distinct from the previous scene's brief.
