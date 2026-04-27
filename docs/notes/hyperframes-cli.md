# HyperFrames CLI reference

Smoke-tested 2026-04-27 against `hyperframes@0.4.31` (npm, latest).
Source: <https://github.com/heygen-com/hyperframes>, package <https://www.npmjs.com/package/hyperframes>.

This note is the source of truth for what `npx hyperframes` actually offers on
this machine. Where the Phase-3 plan disagrees with reality the plan is wrong;
see the "Plan vs reality" section at the bottom.

## Smoke test

```bash
mkdir -p /tmp/hf-smoke && cd /tmp/hf-smoke
npx -y hyperframes init demo --non-interactive --skip-skills --skip-transcribe
cd demo
npx hyperframes render
```

Result on this machine (Win11, Node 24.11.1, i9-9900KF, 16 cores, FFmpeg from
gyan.dev build, no Docker):

- Rendered MP4: `C:\Users\sidor\AppData\Local\Temp\hf-smoke\demo\renders\demo_2026-04-27_13-28-19.mp4`
- 10 s output (1920x1080, 30 fps, 300 frames), 26.7 KB (black background, no clips), wall time **~14 s** for the render itself, **~29 s** end-to-end including the one-off ~101 MB Chrome download into `~/.cache/hyperframes/chrome/`.
- `npx hyperframes doctor` flagged Docker as missing/not running; everything else (FFmpeg, FFprobe, Chrome cache, Node, CPU, memory, disk) was green. Docker is only required for `--docker` deterministic mode.

## Top-level commands

`npx hyperframes --help` (v0.4.31):

| Group           | Command       | Purpose                                                      |
| --------------- | ------------- | ------------------------------------------------------------ |
| Getting started | `init`        | Scaffold a new composition project                           |
|                 | `add`         | Install a block or component from the registry               |
|                 | `capture`     | Capture a website for video production                       |
|                 | `catalog`     | Browse and install blocks and components                     |
|                 | `preview`     | Start the studio (browser preview server)                    |
|                 | `publish`     | Upload project, get a public URL                             |
|                 | `render`      | Render a composition to MP4 / WebM / MOV                     |
| Project         | `lint`        | Validate a composition                                       |
|                 | `inspect`     | Inspect rendered visual layout across the timeline           |
|                 | `snapshot`    | Capture key frames as PNGs                                   |
|                 | `info`        | Print project metadata                                       |
|                 | `compositions`| List all compositions in a project                           |
|                 | `docs`        | View inline docs in the terminal                             |
| Tooling         | `benchmark`   | Compare fps/quality/worker presets                           |
|                 | `browser`     | Manage the Chrome used for rendering                         |
|                 | `doctor`      | Check system dependencies                                    |
|                 | `upgrade`     | Check for updates                                            |
| AI              | `skills`      | Install AI coding skills                                     |
|                 | `transcribe`  | Word-level transcript via local model                        |
|                 | `tts`         | Speech audio via Kokoro-82M                                  |
| Settings        | `telemetry`   | Manage anonymous telemetry                                   |

Run `npx hyperframes <cmd> --help` for per-command flags. The compositor only
needs `init`, `add`, `lint`, `render`. We will not call `preview`, `publish`,
`capture`, `tts`, `transcribe`, or `skills` from automation.

## Project layout (post `init`)

`hyperframes init demo` writes:

```
demo/
  AGENTS.md           # rules for AI agents working in the project
  CLAUDE.md           # Claude-specific project instructions
  hyperframes.json    # project config (NOT hyperframes.config.json)
  index.html          # root composition
  meta.json           # { id, name, createdAt }
```

`init` flags worth knowing:

- `-e, --example <name>` — pick a starter (e.g. `warm-grain`, `swiss-grid`,
  `blank`). List via `npx hyperframes docs examples`.
- `-V, --video <path>`, `-a, --audio <path>` — preload media.
- `--non-interactive` — required for CI / agent use.
- `--skip-skills`, `--skip-transcribe` — skip prompts/downloads we don't want
  during automated bootstrap.
- `--model`, `--language` — whisper transcription tuning when audio is provided.

### `hyperframes.json` schema (observed)

```json
{
  "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
  "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
  "paths": {
    "blocks": "compositions",
    "components": "compositions/components",
    "assets": "assets"
  }
}
```

- `registry` — base URL for `add` / `catalog` lookups.
- `paths.blocks` — directory where `add <block-name>` writes block HTML files.
- `paths.components` — directory for installed components (smaller building blocks).
- `paths.assets` — directory where bundled images/fonts/audio land.

`meta.json` is purely informational (`id`, `name`, `createdAt`).

### Composition HTML format

Every composition is a standalone HTML document. Key conventions, copied from
`AGENTS.md` written by `init` and from `npx hyperframes docs data-attributes`:

- Root element carries `data-composition-id` and the canvas size:
  ```html
  <div id="root" data-composition-id="main"
       data-start="0" data-duration="10"
       data-width="1920" data-height="1080">…</div>
  ```
- Timed elements need **all three** of `data-start`, `data-duration`,
  `data-track-index` (track index controls z-order).
- Visible timed elements **must** have `class="clip"` — the runtime uses this
  for visibility lifecycle. Without it the element renders for the whole
  composition.
- Media attributes: `data-media-start` (trim offset), `data-volume` (0-1),
  `data-has-audio="true"` for video tracks. Videos must be `muted`; audio goes
  through a separate `<audio>` element.
- Sub-compositions: `<div data-composition-src="compositions/foo.html"
  data-start="…" data-duration="…">…</div>`. Variables passed in via
  `data-variable-values='{"key":"value"}'`; the child composition is
  responsible for reading and applying them.
- GSAP timelines must be **paused** and registered on
  `window.__timelines[compositionId]`. The runtime drives time, not the page.
- Determinism: no `Date.now()`, no `Math.random()`, no network fetches at
  render time. (The init scaffold loads GSAP from a CDN; the compiler
  inlines it before rendering — see "Compiler" log line in the smoke test.)

### Resolution, fps, codec — where each lives

| Knob       | Where it's set                                                                  |
| ---------- | ------------------------------------------------------------------------------- |
| Resolution | **HTML only** — `data-width` / `data-height` on the root composition `<div>`. The CLI has **no `--width` / `--height` flag**. To render 1440x2560 we set those values in `composition.html`. |
| FPS        | `npx hyperframes render -f 30` (allowed: `24`, `30`, `60`; default `30`). 60 fps is required for our final.       |
| Format     | `npx hyperframes render --format mp4|webm|mov`. WebM and MOV render with transparency; MP4 is opaque H.264. |
| Quality    | `-q draft|standard|high` (default `standard`).                                   |
| Bitrate    | `--video-bitrate 10M` **or** `--crf <n>` (mutually exclusive).                  |
| HDR        | `--hdr` opts into PQ/HLG H.265 10-bit BT.2020 — we never want this; final must be Rec.709 SDR. |
| GPU encode | `--gpu` (NVENC / VideoToolbox / VAAPI when available).                          |
| Workers    | `-w <n|auto>` parallel Chrome processes, ~256 MB RAM each. Default `auto`. Smoke test used 8 (16-core box, ended up running 6 in steady state). |
| Output     | `-o, --output <path>` (default `renders/<projectName>_<timestamp>.<ext>`).      |
| Strictness | `--strict` (fail on lint errors), `--strict-all` (fail on warnings too).        |
| Determinism| `--docker` runs the render inside a pinned Chrome image (Docker required).      |

`render` takes a positional `[DIR]` (defaults to cwd). There is **no
`--input`** flag — the input is always the project directory whose root
composition is `index.html`.

### `npx hyperframes add <name>`

`add` installs an item (block or component) from the registry into the project:

```bash
npx hyperframes add yt-lower-third --no-clipboard --json
```

Observed JSON for the smoke test:

```json
{
  "ok": true,
  "name": "yt-lower-third",
  "type": "hyperframes:block",
  "typeDir": "blocks",
  "written": [
    "…/demo/compositions/yt-lower-third.html",
    "…/demo/assets/avatar.jpg"
  ],
  "snippet": "<div data-composition-src=\"compositions/yt-lower-third.html\" data-duration=\"4.5\" data-width=\"1920\" data-height=\"1080\"></div>",
  "clipboardCopied": true
}
```

Notes:

- The argument is the **registry item name**, not a path. Discover names via
  `npx hyperframes catalog --json` (or `--type block|component`, `--tag <t>`).
  When the name is wrong, the CLI prints the full available list in its error.
- `--no-clipboard` — required in headless / CI environments to avoid clipboard writes.
- `--json` — machine-readable summary on stdout, including the include
  snippet you must paste into the parent composition. The compositor will
  consume this JSON.
- `--dir <path>` — target a project directory other than cwd.
- Files are written under the dirs declared in `hyperframes.json`:
  - blocks → `compositions/`
  - components → `compositions/components/`
  - bundled media → `assets/`
- `add` does **not** modify `index.html`. Wiring the snippet in is the
  caller's responsibility.

### Lint

`npx hyperframes lint [DIR]` validates compositions; `--json` for CI,
`--verbose` to surface info-level findings. The init scaffold's `AGENTS.md`
calls this out as mandatory after every HTML edit; we should run it from
`run-stage2.sh` before invoking `render`.

## Plan vs reality (read me first)

The Phase-3 plan was written before HyperFrames was inspected. Concrete
mismatches the downstream tasks must accommodate:

| Plan assumed                                          | Reality                                                     |
| ----------------------------------------------------- | ----------------------------------------------------------- |
| Config file `hyperframes.config.json`                 | `hyperframes.json`                                          |
| `render --input <html>`                               | `render [DIR]` — no `--input`; input is the project dir, root composition is `index.html` |
| `render --width / --height`                           | Resolution is set on the root composition's `data-width` / `data-height` attributes |
| `render --transparent`                                | Use `--format webm` or `--format mov` for transparency      |
| `add <component>` writes to a single components dir   | `add` installs **blocks** (→ `compositions/`) or **components** (→ `compositions/components/`); the registry decides which. Items also drop bundled media in `assets/`. |

Action items for the compositor:

1. Author `composition.html` with `data-width="1440"` and `data-height="2560"`
   on the root, and pass `-f 60 --format mp4 -q high` (or matching
   `--video-bitrate`) to `hyperframes render`. Do **not** invent CLI flags.
2. Treat the project dir (where `composition.html` lives) as the input. If we
   keep our entry filename as `composition.html` instead of `index.html`,
   either rename or symlink before invoking render — the CLI follows
   `index.html`.
3. Run `npx hyperframes lint --json` before render and fail fast on errors.
4. The final ffmpeg merge with `library/music/<track>.mp3` in
   `render-final.sh` stays on us — `hyperframes render` will only emit the
   visual + composition audio track defined in HTML; the music sidecar mix is
   our responsibility.

## Limitations observed

- **Browser**: HyperFrames downloads its own `chrome-headless-shell` (v131
  observed) into `~/.cache/hyperframes/chrome/` on first render. ~101 MB,
  one-off. Use `npx hyperframes browser` to manage.
- **Docker mode**: `--docker` is the only way to get bit-identical renders
  across machines. Docker is not installed on this box; `doctor` flags it as
  failed. Local mode is fine for iteration but not byte-deterministic.
- **GPU**: not exercised in the smoke test. `--gpu` claims NVENC /
  VideoToolbox / VAAPI support; verify before relying on it for the final
  render.
- **Render speed**: black 10 s @ 1920x1080 / 30 fps with 6 effective workers
  took ~14 s of render time (≈0.7x realtime per second of output, on an
  empty composition). Real compositions with many clips will be slower; plan
  on benchmarking once `composition.html` is non-trivial via
  `npx hyperframes benchmark`.
- **Workers cost RAM**: ~256 MB per worker per HyperFrames' own help text. On
  a 32 GB box `auto` is fine; on smaller machines pin `-w 2` or `-w 4`.
- **Determinism caveats**: even in local mode, the runtime forbids
  `Date.now()`, `Math.random()`, and network fetches inside compositions. CDN
  scripts in HTML are inlined by the compiler before render (confirmed by
  the `Inlined CDN script: …gsap.min.js` log line in our smoke test), so
  CDN-loaded GSAP is OK, but only at compile time.
- **Telemetry**: anonymous usage data is on by default. Disable with
  `npx hyperframes telemetry disable` if we don't want it from CI.
