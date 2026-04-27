# Color standards

## Purpose
Color grading parameters for stage 1, plus what we reject at ingest.

## Source format requirements
Source footage in `incoming/raw.mp4` must be:
- Container: MP4 / MOV
- Codec: H.264 or H.265
- Color space: **Rec.709 SDR (gamma 2.4)**. HDR/HLG sources are rejected at ingest.
- Resolution: at least 1440×2560 (higher OK; downscaled at output).
- Frame rate: 60 fps preferred; 30 fps acceptable (output upsampled to 60 fps with frame doubling — log warning in retro).

## Stage 1 grade (applied by video-use)
Defaults below are starting values. Adjust through retro loop.

- Auto color grading: enabled.
- Saturation bump: +8%.
- Contrast: +12 (Premiere-style scale).
- Vignette: intensity 0.25, feather 0.6, midpoint 0.5.
- Sharpening: disabled (already crisp from source).

If video-use's auto grade does not yield the above, an additional `stage-1.5` ffmpeg pass with explicit `eq` and `vignette` filters is added. The pass parameters live in `tools/compositor/grade.json` (created in Phase 2).

## Output format (set in compositor + render-final.sh)
- Resolution: 1440×2560
- Frame rate: 60 fps
- Codec: H.264 high profile, level 5.1
- Bitrate: ~35 Mbps VBR (1-pass)
- Color: Rec.709 SDR (gamma 2.4)

## Hard rules
- No HDR/HLG source accepted. Reject at `new-episode.sh` with clear error.
- Final `final.mp4` must validate as 1440×2560, 60 fps, Rec.709, AAC 320k 48kHz before declaring CP3 done.
