# Segmenter — Scene Pass

The beat below is longer than the 5-second hard cap. Subdivide it into N sub-scenes ≤ 5 s each.

## Inputs

### Beat metadata
{{BEAT_JSON}}

### Beat script chunk
{{SCRIPT_CHUNK}}

### Beat duration
{{BEAT_DURATION_MS}} ms (target ceil(duration/5000) sub-scenes)

## Output

Return a JSON array, no prose. Each object:
```json
{
  "key_phrase": "DRM is a moving target",
  "script_chunk": "...verbatim slice...",
  "char_offset_start": 0,
  "char_offset_end": 47
}
```

`key_phrase`: 5–8 words, the visual hook. Not a summary — the most quotable line.

`char_offset_start` / `char_offset_end`: offsets into the parent beat's script chunk. Sub-scenes are sequential, cover the full beat.

Inherit `narrative_position`, `energy_hint`, `mood_hint`, `beat_id` from the parent beat.
