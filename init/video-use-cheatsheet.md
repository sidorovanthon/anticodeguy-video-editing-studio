# video-use — Cheat Sheet

Conversation-driven video editor. You drop footage in a folder, run an agent (`claude`, `codex`) there, say what you want — agent reads `SKILL.md`, runs helpers, hands you a finished cut.

Repo: `C:\Users\sidor\repos\video-use` → linked to `~/.claude/skills/video-use`. Auto-updates daily via Task Scheduler 10 min after logon.

---

## 1. Quick start

```
cd <папка с видео>
claude
> "edit these into a launch video"   (или любой brief на русском/английском)
```

Агент проводит inventory → транскрибация → пред-сканирование → стратегия → **подтверждение** → рендер → self-eval → preview/final.

**Все артефакты складываются в `<папка_видео>/edit/`** — никогда не в репо. Это Hard Rule 12.

---

## 2. Helpers — что вызывает чего

| Скрипт | Что делает | Когда вызывается |
|---|---|---|
| `helpers/transcribe.py` | один файл → ElevenLabs Scribe → JSON в `edit/transcripts/` | На одном видео или для отдельного файла |
| `helpers/transcribe_batch.py` | папка → 4 параллельных воркера → JSON-кэш | Mass-take inventory |
| `helpers/pack_transcripts.py` | JSON-ы → `edit/takes_packed.md` (phrase-level markdown) | Перед редактурой, как "первичный читальный артефакт" |
| `helpers/timeline_view.py` | filmstrip + waveform PNG за временной диапазон | Точечно: проверка кадра/паузы/cut-point |
| `helpers/render.py` | EDL → итоговое видео (extract → concat → overlays → subs → loudnorm) | Финальный рендер |
| `helpers/grade.py` | один файл → цветокор (preset / auto / raw filter) | Standalone грейдинг или вызывается из render.py |

---

## 3. Транскрибация (audio-to-text via ElevenLabs Scribe)

### Базовый вызов
```bash
python helpers/transcribe.py <video>
python helpers/transcribe.py <video> --edit-dir /custom/edit
python helpers/transcribe.py <video> --language en
python helpers/transcribe.py <video> --num-speakers 2
```

### Параметры
- `--edit-dir` — куда писать `transcripts/<name>.json` (по умолчанию `<video>/edit/`)
- `--language` — ISO код (`en`, `ru`, `de`, ...). Без флага — auto-detect
- `--num-speakers N` — точное число спикеров для лучшей диаризации

### Batch
```bash
python helpers/transcribe_batch.py <videos_dir>
python helpers/transcribe_batch.py <videos_dir> --workers 4 --num-speakers 2 --language en
```

### Что включено всегда
- `model_id: scribe_v1`
- `diarize: true` — speaker labels (S0, S1, ...)
- `tag_audio_events: true` — `(laughs)`, `(applause)`, `(sighs)` в выходе
- `timestamps_granularity: word` — старт/конец на каждое слово

### Кэширование (Hard Rule 9)
Если `<edit>/transcripts/<name>.json` существует — **повторного вызова Scribe не будет**, экономит API-кредиты. Удалишь JSON — транскрибация повторится.

### Куда не лезет Scribe
- Голосочистка / шумодав → **не делает**
- Аудио-изоляция → **не делает** (это другой endpoint ElevenLabs, в пайплайне нет)
- TTS (синтез голоса) → не нужно для редактуры

### API key
- `ELEVENLABS_API_KEY` в `~/repos/video-use/.env` (chmod 600)
- Или в env var того же имени
- Скоуп ключа: достаточно `speech_to_text`

---

## 4. Pack transcripts (читаемая форма)

```bash
python helpers/pack_transcripts.py --edit-dir <edit_dir>
python helpers/pack_transcripts.py --edit-dir <edit_dir> --silence-threshold 0.5
python helpers/pack_transcripts.py --edit-dir <edit_dir> -o custom.md
```

### Параметры
- `--edit-dir` — обязательно, папка где лежит `transcripts/*.json`
- `--silence-threshold` — на каких паузах резать на фразы (по умолчанию 0.5s)
- `-o`/`--output` — путь output (по умолчанию `<edit-dir>/takes_packed.md`)

### Что получается
Markdown с группировкой по тейку, фразовый level, время `[start-end]` на каждой фразе. **Это — основной артефакт, который агент читает для выбора кадров.**

```
## C0103  (duration: 43.0s, 8 phrases)
  [002.52-005.36] S0 Ninety percent of what a web agent does is completely wasted.
  [006.08-006.74] S0 We fixed this.
```

---

## 5. Visual drill-down

```bash
python helpers/timeline_view.py <video> <start> <end>
python helpers/timeline_view.py <video> <start> <end> -o out.png
python helpers/timeline_view.py <video> <start> <end> --n-frames 12
python helpers/timeline_view.py <video> <start> <end> --transcript <path>
```

Производит PNG: filmstrip из `--n-frames` кадров + waveform с пометками слов и серыми зонами тишин ≥400ms.

### Параметры
- `start`, `end` — секунды
- `-o` / `--output` — куда сохранять PNG (auto: `<video>/edit/verify/<name>_<start>-<end>.png`)
- `--n-frames` — количество кадров в filmstrip (по умолчанию 10)
- `--transcript` — путь к JSON для подписей слов (auto-резолв если есть кэш)

### Когда использовать
- Self-eval после рендера — проверка cut boundaries (±1.5s окно)
- Disambiguate ambiguous pauses
- Retake selection
- Не вызывать в цикле по всем фразам — это on-demand drill-down

---

## 6. Cutting (EDL ranges) — hard rules

| Правило | Значение |
|---|---|
| Word boundary | Каждый cut-edge снаппится на границу слова из Scribe (Hard Rule 6) |
| Padding | 30–200ms на head + tail (Hard Rule 7). Туже = быстрее монтаж, шире = кинематограф |
| Cut targets | Тишины ≥ 400ms — самые чистые. 150–400ms — usable с визуальной проверкой. <150ms — небезопасно (mid-phrase) |
| Speaker handoffs | 400–600ms воздуха между репликами (taste call) |
| Audio events | `(laughs)`, `(sighs)` — расширять cut за них, реакция = beat |
| Confirmation | Никаких разрезов до подтверждения стратегии (Hard Rule 11) |

---

## 7. Грейдинг (color)

### Через EDL (`grade` field)

```json
"grade": "subtle"                    // preset name
"grade": "warm_cinematic"            // preset name
"grade": "auto"                      // per-segment analysis (BROKEN on Windows)
"grade": "eq=contrast=1.08:saturation=1.05,vignette=PI/5"  // raw ffmpeg filter
```

### Available presets

| Preset | Что делает | Когда использовать |
|---|---|---|
| `subtle` | `eq=contrast=1.03:saturation=0.98` | Минимальная чистка, безопасно везде |
| `neutral_punch` | `eq=contrast=1.06,curves=master='0/0 0.25/0.23 0.75/0.77 1/1'` | S-кривая + контраст, без цветовых сдвигов |
| `warm_cinematic` | Teal/orange split, crushed blacks, -12% sat, warm shadows | Retro/cinematic talking heads, лаунч-видео |
| `none` | Нет фильтра | Когда не просили грейдить |
| `auto` | Анализ → bounded correction (±8%) | **Сломан на Windows** (path-escape bug) |

### Standalone grade.py
```bash
python helpers/grade.py <input> -o <output>                   # auto mode
python helpers/grade.py <input> -o <output> --preset warm_cinematic
python helpers/grade.py <input> -o <output> --filter 'eq=contrast=1.1'
python helpers/grade.py --print-preset warm_cinematic         # печатает фильтр
python helpers/grade.py --analyze <input>                     # печатает auto-grade анализ
```

### ASC CDL ментальная модель (для своих фильтров)
- `slope` → highlights
- `offset` → shadows
- `power` → midtones
- Затем глобальная saturation
- `out = (in * slope + offset) ** power`

### Произвольные ffmpeg-фильтры в grade
- `eq=contrast=X:brightness=X:saturation=X`
- `curves=master='0/0 0.25/0.20 0.75/0.80 1/1'`
- `colorbalance=rs=-0.1:gs=0:bs=0.1` (red shadows / blue shadows)
- `vignette=PI/5` (мягкая) / `PI/4` (заметная) / `PI/3` (драматичная)
- `eq=gamma_r=1.05:gamma_b=0.95` (warm/cool tilt)

### Hard rule
**Грейд применяется per-segment во время extract**, не post-concat. Иначе двойное re-encode.

---

## 8. Виньетка (built-in ffmpeg filter)

В EDL grade-цепочку:
```json
"grade": "eq=contrast=1.05,vignette=PI/5"
```

Параметры `vignette` filter:
- `angle=PI/N` — ширина (бóльший N = шире, мягче)
- `mode=backward` — пульсация
- `eval=init` — статичный (по умолчанию)

---

## 9. Субтитры (burn-in via libass)

### Вкл/выкл при рендере

```bash
python helpers/render.py <edl> -o final.mp4 --build-subtitles
python helpers/render.py <edl> -o final.mp4 --no-subtitles
```

- `--build-subtitles` — генерирует `master.srt` из транскриптов с output-timeline offsets
- `--no-subtitles` — игнорирует subtitle поле в EDL
- Нет флагов → берёт `subtitles` поле из EDL (если есть)

### Built-in style (`bold-overlay`, для вертикали 1080×1920)

```
FontName=Helvetica
FontSize=18
Bold=1
PrimaryColour=&H00FFFFFF (white)
OutlineColour=&H00000000 (black)
BorderStyle=1, Outline=2, Shadow=0
Alignment=2 (bottom-center)
MarginV=90  (~30% от низа — clear of TikTok/Reels/Shorts UI)
```

Стиль захардкожен в `SUB_FORCE_STYLE` константе `helpers/render.py`. Меняется правкой строки.

### Группировка
- 2-word chunks
- UPPERCASE (после break на пунктуации)
- Punctuation breaks: `.,!?;:`

### Hard rules
1. **Субтитры применяются ПОСЛЕДНИМИ** в filter chain (Hard Rule 1) — иначе оверлеи их прячут
2. **Output-timeline offsets** (Hard Rule 5) — `output_time = word.start - segment_start + segment_offset`

---

## 10. Анимации / overlays

### Tool options
- **PIL + PNG sequence + ffmpeg** — простые карточки, counters, typewriter, bar reveals
- **Manim** — формальные диаграммы, equations, graph morphs (`skills/manim-video/SKILL.md`)
- **Remotion** — typography-heavy, brand-aligned, web-adjacent layouts (React/CSS)

### EDL overlay format

```json
"overlays": [
  {
    "file": "edit/animations/slot_1/render.mp4",
    "start_in_output": 0.0,
    "duration": 5.0
  }
]
```

### Duration heuristics
- Sync-to-narration: 5–7s simple cards, 8–14s сложные диаграммы
- Beat-synced accents: 0.5–2s
- Hold final frame ≥ 1s before cut
- Над voiceover: total ≥ `narration_length + 1s`
- Никогда не parallel-reveal независимых элементов

### Easing (universal — никогда `linear`)
```python
def ease_out_cubic(t):    return 1 - (1 - t) ** 3
def ease_in_out_cubic(t):
    if t < 0.5: return 4 * t ** 3
    return 1 - (-2 * t + 2) ** 3 / 2
```

### Hard rules
- **PTS shift**: `setpts=PTS-STARTPTS+T/TB` чтобы overlay's frame 0 → window start (Hard Rule 4)
- **Parallel sub-agents** для нескольких анимаций (Hard Rule 10) — никогда не sequential

---

## 11. Render — главный pipeline

```bash
python helpers/render.py <edl.json> -o final.mp4
python helpers/render.py <edl.json> -o preview.mp4 --preview
python helpers/render.py <edl.json> -o draft.mp4 --draft
python helpers/render.py <edl.json> -o final.mp4 --build-subtitles
python helpers/render.py <edl.json> -o final.mp4 --no-subtitles
python helpers/render.py <edl.json> -o final.mp4 --no-loudnorm
```

### Quality ladder

| Mode | Resolution | Preset | CRF | Use case |
|---|---|---|---|---|
| Default (final) | 1080p (или 1080×1920 vertical) | `fast` | 20 | Финал |
| `--preview` | 1080p / 1080×1920 | `medium` | 22 | Self-eval, QC |
| `--draft` | 720p / 720×1280 | `ultrafast` | 28 | Только cut-point check |

### Что происходит внутри
1. **Per-segment extract** с грейдом + 30ms audio fades (Hard Rule 3)
2. **Lossless `-c copy` concat** в base.mp4 (Hard Rule 2)
3. **HDR → SDR tone mapping** автоматически если source HLG/PQ (Hard Rule безопасности)
4. **Final composite**: overlays (PTS-shifted) → subtitles ПОСЛЕДНИЕ → out
5. **Loudness normalization** двухпроходный: -14 LUFS / -1 dBTP / LRA 11

### Файловые артефакты
- `clips_graded/` — финальные сегменты (или `clips_preview/` / `clips_draft/`)
- `base.mp4` — concat без overlays/subs
- `master.srt` — если `--build-subtitles`
- `verify/` — debug PNG-кадры
- `_concat.txt` — временный список (удаляется после)
- `<output>.prenorm.mp4` — pre-loudnorm temp (удаляется после)

---

## 12. Аудио

### Loudness normalization (по умолчанию on)
- Цель: -14 LUFS integrated, -1 dBTP true peak, LRA 11 LU
- Стандарт: YouTube / IG / TikTok / X / LinkedIn
- Двухпроходный: pass 1 measure, pass 2 normalize
- В preview/draft режиме — однопроходный (быстрее, чуть менее точно)
- Отключить: `--no-loudnorm`

### Audio fades (всегда)
- 30ms fade in + 30ms fade out на каждом сегменте (Hard Rule 3)
- Без них слышны клики/попы на каждом cut

### Что НЕ в пайплайне
- Голосочистка (RNNoise, FFT denoise)
- Audio Isolation (ElevenLabs separate product)
- De-esser
- Equalization (графический EQ, multi-band compression)
- Music underbed / sidechain ducking

Всё перечисленное **можно добавить** ffmpeg-фильтрами в `extract_segment` или новым шагом, но из коробки этого нет.

---

## 13. Output формат

### Common targets (произвольно меняются)
- `1920×1080@24` — cinematic
- `1920×1080@30` — screen content
- `1080×1920@30` — vertical social ⭐ (default vertical)
- `3840×2160@24` — 4K cinema
- `1080×1080@30` — square

### Default scale в render.py
- Landscape source → `scale=1920:-2`
- Portrait source → `scale=-2:1920` (после fix PR #23)
- 24fps по умолчанию (libx264 -r 24)

### 1440p / 4K / custom resolution
**Не из коробки.** Чтобы получить — править `extract_segment` scale-фильтр или добавить аргумент `--height N`. Помни: апскейл (1080 source → 1440p output) реальной детализации не даст.

---

## 14. EDL format

```json
{
  "version": 1,
  "sources": {
    "C0103": "/abs/path/C0103.MP4",
    "C0108": "/abs/path/C0108.MP4"
  },
  "ranges": [
    {
      "source": "C0103",
      "start": 2.42,
      "end": 6.85,
      "beat": "HOOK",
      "quote": "...",
      "reason": "Cleanest delivery, stops before slip at 38.46."
    }
  ],
  "grade": "warm_cinematic",
  "overlays": [
    {"file": "edit/animations/slot_1/render.mp4", "start_in_output": 0.0, "duration": 5.0}
  ],
  "subtitles": "edit/master.srt",
  "total_duration_s": 87.4
}
```

Поля:
- `sources` — словарь `{name: abs_path}`. Имена используются в `ranges[].source`
- `ranges` — список cut'ов в порядке итогового тайминга
- `grade` — preset name / raw filter / `"auto"` / null
- `overlays` — opt
- `subtitles` — opt, путь к .srt
- `total_duration_s` — для self-check

---

## 15. Project memory

### `<edit>/project.md`
Append-only лог сессий. После каждой работы агент дописывает блок:
```markdown
## Session N — YYYY-MM-DD

**Strategy:** ...
**Decisions:** ...
**Reasoning log:** ...
**Outstanding:** ...
```

При следующем заходе в ту же папку агент **читает project.md первым** и одной фразой суммирует прошлую сессию.

### `<edit>/takes_packed.md` — primary reading view (см. §4)
### `<edit>/transcripts/*.json` — Scribe кэш (никогда не пере-транскрибируется без удаления)

---

## 16. Directory layout

```
<videos_dir>/
├── <source files>             ← твои сырьё
└── edit/                      ← всё, что генерит агент
    ├── project.md             ← memory
    ├── takes_packed.md        ← phrase-level view
    ├── edl.json               ← cut decisions
    ├── transcripts/<name>.json
    ├── animations/slot_<id>/  ← per-animation
    ├── clips_graded/          ← per-segment с грейдом + fades
    ├── master.srt             ← output-timeline subs
    ├── downloads/             ← yt-dlp pull results
    ├── verify/                ← debug timeline PNG
    ├── preview.mp4
    └── final.mp4
```

---

## 17. Hard Rules (production correctness — non-negotiable)

| # | Правило |
|---|---|
| 1 | Subtitles в filter chain — ПОСЛЕДНИМИ |
| 2 | Per-segment extract → lossless `-c copy` concat (НЕ single-pass) |
| 3 | 30ms audio fades на каждом сегменте |
| 4 | Overlays через `setpts=PTS-STARTPTS+T/TB` |
| 5 | Master SRT через output-timeline offsets |
| 6 | Cut только на word boundary |
| 7 | Cut padding 30–200ms |
| 8 | Word-level verbatim ASR only (не SRT-mode, не нормализация фиддлеров) |
| 9 | Cache transcripts per source — никогда не re-transcribe без причины |
| 10 | Parallel sub-agents для нескольких анимаций (не sequential) |
| 11 | Strategy confirmation **до** execution |
| 12 | Все session outputs в `<videos_dir>/edit/`, не внутри репо |

---

## 18. Anti-patterns (что НЕ делать)

- Hierarchical pre-computed codec formats / USABILITY-теги — over-engineering
- Hand-tuned moment-scoring functions — LLM выбирает лучше
- Whisper SRT / phrase-level — теряет sub-second gap data
- Whisper local на CPU — медленно, нормализует filler-words
- Subs burned в base **до** overlays — overlays их перекроют
- Single-pass filtergraph при overlays — двойной re-encode
- Linear easing анимаций — выглядит роботно
- Hard cuts без 30ms fades — клики
- Typing text centered на partial string — съезжает влево
- Sequential sub-agents для анимаций — параллельность обязательна
- Re-transcribing кэшированных source'ов
- Editing до confirm стратегии

---

## 19. URL pulls (yt-dlp)

Не in pipeline by default. Если нужен — установить `yt-dlp` лениво на первое использование:
```bash
# Windows (нет brew/apt) — pip
pip install yt-dlp
```
Скачанные файлы → `<edit>/downloads/`.

---

## 20. Что НЕ умеет из коробки (требует расширения)

| Feature | Сложность | Куда добавлять |
|---|---|---|
| Background music + sidechain ducking | ~50 LOC | новое поле `music` в EDL, шаг в `render.py` после composite |
| Voice denoise (RNNoise / arnndn) | ~10 LOC | в `extract_segment`, `-af` цепочка |
| ElevenLabs Audio Isolation | ~30 LOC | новый шаг перед `transcribe.py` или в `extract_segment` |
| Speed ramps / freeze frames | средне | новый range type в EDL + setpts/atempo в extract |
| J-cuts / L-cuts (audio leads/trails video) | средне | разделить video range и audio range в EDL |
| Dynamic crop / face tracking | сложно | внешний AI-инструмент |
| Auto poster/thumbnail | ~5 LOC | один ffmpeg вызов после final |
| Multi-camera sync | сложно | timecode-aware sync utility |
| Custom resolution arg | ~10 LOC | флаг `--height N` в render.py |
| Auto grade (Windows fix) | ~5 LOC | escape backslashes в filter string |

---

## 21. Auto-update (this machine)

Daily на твоей машине через Task Scheduler:
- Task: **"Video-use Daily Update"**
- Trigger: At log on, +10 min delay
- Action: `wscript.exe "C:\Users\sidor\bin\video-use-update.vbs"` (silent, no console flash)
- Скрипт: `git fetch origin → checkout main → pull --ff-only → checkout fix/vertical-source-scale → rebase main → uv sync`
- Лог: `C:\Users\sidor\video-use-update.log`
- При rebase-конфликте: aborts, логирует, ждёт ручного вмешательства

После мерджа PR #23 fix-ветка станет no-op, можно удалить:
```bash
git branch -d fix/vertical-source-scale
git push fork --delete fix/vertical-source-scale
```

---

## 22. Open issues / known bugs

1. **`grade.py` auto mode** ломается на Windows из-за path-escape (`metadata=print:file=C:\...`) — workaround: использовать preset вместо `auto` в EDL
2. **`pack_transcripts.py`** падал на Windows cp1251 codec при символе `≥` — workaround: `PYTHONUTF8=1 python helpers/pack_transcripts.py ...`
3. **`render.py` vertical scale** — фикс отправлен в PR #23, локально применён через rebase

---

## 23. Конфигурационные файлы

| Файл | Что |
|---|---|
| `~/.claude/CLAUDE.md` | глобальные стандарты (язык, default grade, default vignette, output naming) |
| `<videos_root>/CLAUDE.md` | per-folder стандарты (бренд-палитра, имена спикеров, шрифты) |
| `<videos>/edit/project.md` | per-project memory + standing preferences |
| `~/repos/video-use/.env` | ELEVENLABS_API_KEY |
| `~/.claude/skills/video-use` | junction → `~/repos/video-use` |
