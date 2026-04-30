# anticodeguy-video-editing-studio

This project is an orchestrator for a two-stage video editing pipeline that chains the
globally-installed `video-use` and `hyperframes` skills into a single command.

## Layout convention

```
inbox/                  # drop zone (gitignored). User places raw video here as <slug>.<ext>.
episodes/               # processed archive (gitignored). One folder per episode.
  <slug>/
    raw.<ext>           # moved here from inbox/ by the orchestrator
    edit/               # produced by video-use: final.mp4, transcripts/raw.json
    hyperframes/        # produced by hyperframes: index.html, package.json, ...
```

**Slug:** filename stem of the raw video. `inbox/launch-promo.mp4` → `episodes/launch-promo/raw.mp4`.

**Supported raw extensions:** `.mp4`, `.mov`, `.mkv`, `.webm`.

## Entry point

The pipeline is invoked exclusively via the slash command `/edit-episode` (defined in
`.claude/commands/edit-episode.md`). Do not invoke `video-use` or `hyperframes` skills
directly from the user's prompt — go through the command so layout and idempotency rules
are honored.

If the user says "edit this video", "process the inbox", "обработай видео", or anything
semantically equivalent, invoke `/edit-episode` (with a slug argument if they named one).

## Idempotency

The command is safe to re-run on the same slug. It resumes from the first missing
artifact: `episodes/<slug>/edit/final.mp4`, then `episodes/<slug>/hyperframes/index.html`,
then studio launch. Skipping Phase 1 when `final.mp4` exists is important — it avoids
re-spending ElevenLabs Scribe credits.
