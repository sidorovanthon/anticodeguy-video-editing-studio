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

**Slug:** filename without its final extension (everything before the last `.`). `inbox/launch-promo.mp4` → slug `launch-promo`. `inbox/foo.bar.mp4` → slug `foo.bar`.

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

## Branching workflow — non-negotiable

**Every change goes through a feature branch and a GitHub PR. No direct commits to `main`.**

For any non-trivial change (new feature, refactor, multi-file edit):

1. Create a feature branch (`git worktree add .worktrees/<branch> -b <branch>` is the standard pattern; the `superpowers:using-git-worktrees` skill handles this).
2. Commit work on the branch with focused, frequent commits.
3. Push the branch (`git push -u origin <branch>`) and open a PR via `gh pr create --base main` with a Summary + Test plan body.
4. Merge happens via the PR — typically a manual review-and-merge step on GitHub. Do not auto-merge from the agent unless the user explicitly says so.
5. After merge, clean up: `git worktree remove .worktrees/<branch>` and `git branch -d <branch>`.

Trivial fixes (typo, single-line doc tweak) MAY land directly on main with the user's explicit go-ahead, but the default is "branch + PR".

If a session ends with uncommitted work or an unmerged branch, leave the branch as-is — never reset/discard to "tidy up" without explicit instruction.

## External skill canon — non-negotiable

`video-use` (`~/repos/video-use`, junctioned to `~/.claude/skills/video-use`) and
`hyperframes` (skills at `~/.agents/skills/hyperframes/`, CLI via `npx hyperframes`)
are external products auto-updated on this machine via Task Scheduler. Their source
code, helpers, `SKILL.md` canons, and built-in workflows are **read-only**. Any
orchestrator-side proposal — new script, glue step, brief addition, naming convention
— must first be verified against the **live `SKILL.md`** (not against
`docs/cheatsheets/*` summaries, not against memory) to confirm we are not:

1. Duplicating something the skill already does (look for an existing helper / flag).
2. Pre-empting a canonical executor step (e.g., generating `DESIGN.md` ourselves
   would short-circuit hyperframes' Visual Identity Gate).
3. Drifting from the contract the skill enforces (section numbers, hard-rule
   numbers, file shapes referenced in our verbatim briefs must match canon).

Cheatsheets in `docs/cheatsheets/` are reference summaries — useful for orientation,
but the source of truth for canon checks is the SKILL.md itself. Never propose
patches to upstream `video-use` or `hyperframes` repos; all glue lives in this
orchestrator (`scripts/`, `.claude/commands/edit-episode.md`).
