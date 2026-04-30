# video-use — Cheat Sheet

Conversation-driven video editor. Дроп footage в папку → запуск агента (`claude`, `codex`) в этой папке → бриф словами. Агент читает `SKILL.md`, выбирает кадры из транскрипта, оркестрирует хелперы, отдаёт готовый монтаж.

Скилл регистрируется как директория в `~/.claude/skills/video-use/` (или эквивалент для другого агента). `SKILL.md` и `helpers/` лежат рядом.

---

## 1. Quick start

```
cd <папка с видео>
claude
> "edit these into a launch video"
```

Канонические 8 шагов сессии:

| # | Шаг | Артефакт |
|---|---|---|
| 1 | **Inventory** — `ffprobe` + `transcribe_batch` + `pack_transcripts` + sample `timeline_view` | `transcripts/*.json`, `takes_packed.md` |
| 2 | **Pre-scan** — слипы, оговорки, фразы-избегайки | список заметок |
| 3 | **Converse** — тип, длительность, аспект, эстетика, темп, must-keep, must-cut | бриф |
| 4 | **Propose strategy** (4–8 предложений) → ждать подтверждения | план |
| 5 | **Execute** — `edl.json`, animations (параллельно), grade per-segment, `render.py` | EDL, animations/, clips_graded/ |
| 6 | **Preview** — `render.py --preview` | `preview.mp4` |
| 7 | **Self-eval** — `timeline_view` на каждом cut-edge ±1.5s + `ffprobe` длительности (max 3 итерации) | PNG в `verify/` |
| 8 | **Iterate + persist** — финал + запись в `project.md` | `final.mp4`, `project.md` |

**Все артефакты в `<videos_dir>/edit/`** — никогда внутри репо скилла (Hard Rule 12).

---

## 2. Helpers

| Скрипт | Назначение |
|---|---|
| `helpers/transcribe.py` | ASR один файл через ElevenLabs Scribe |
| `helpers/transcribe_batch.py` | Параллельная транскрипция директории (4 воркера) |
| `helpers/pack_transcripts.py` | `transcripts/*.json` → `takes_packed.md` |
| `helpers/timeline_view.py` | Filmstrip + waveform PNG для диапазона |
| `helpers/render.py` | Сборка финала из EDL: extract → concat → overlays → subtitles → loudnorm |
| `helpers/grade.py` | Цветокор через ffmpeg-фильтры (preset / auto / raw) |

---

## 3. Транскрипция (ElevenLabs Scribe)

### `transcribe.py`

```bash
python helpers/transcribe.py <video>
python helpers/transcribe.py <video> --edit-dir /custom/edit
python helpers/transcribe.py <video> --language en
python helpers/transcribe.py <video> --num-speakers 2
```

| Флаг | Что делает |
|---|---|
| `<video>` | Путь к источнику (обязательно) |
| `--edit-dir DIR` | Куда писать (default `<video_parent>/edit`) |
| `--language` | ISO-код языка; без флага — авто-детект |
| `--num-speakers N` | Подсказка по числу спикеров → точнее диаризация |

### `transcribe_batch.py`

```bash
python helpers/transcribe_batch.py <videos_dir>
python helpers/transcribe_batch.py <videos_dir> --workers 4 --num-speakers 2 --language en
```

| Флаг | Что делает |
|---|---|
| `--workers N` | Параллельные воркеры (default 4) |
| `--edit-dir`, `--language`, `--num-speakers` | как в `transcribe.py` |

### Что включено в каждый Scribe-вызов

- `model_id: scribe_v1`
- `diarize: true` — speaker labels (S0, S1, ...)
- `tag_audio_events: true` — `(laughs)`, `(applause)`, `(sighs)` в выходе
- `timestamps_granularity: word` — старт/конец на каждое слово

### Кэш (Hard Rule 9)

Если `<edit>/transcripts/<name>.json` существует — повторного вызова Scribe нет. Удалишь JSON — транскрипция повторится.

### API key

`ELEVENLABS_API_KEY` в `.env` в корне репо или в env var того же имени. Без ключа транскрипция не работает.

### Hard Rules для ASR

- Только **word-level verbatim** — никаких SRT/phrase-level (теряет sub-second gaps)
- Никакого Whisper локально на CPU — нормализует филлеры и медленно. Только Scribe
- Кэш на источник — пере-транскрибировать только если поменялся файл

---

## 4. Pack transcripts

```bash
python helpers/pack_transcripts.py --edit-dir <dir>
python helpers/pack_transcripts.py --edit-dir <dir> --silence-threshold 0.5
python helpers/pack_transcripts.py --edit-dir <dir> -o custom.md
```

| Флаг | Что делает |
|---|---|
| `--edit-dir` | Папка с `transcripts/` (обязательно) |
| `--silence-threshold` | Порог тишины для разрыва фразы (default 0.5s) |
| `-o, --output` | Выходной .md (default `<edit-dir>/takes_packed.md`) |

### Что получается

Markdown с фразами, разбитыми на тишинах ≥ N сек **или** смене спикера. **Это primary reading view** — то, что агент читает для выбора кадров.

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

PNG: filmstrip из `--n-frames` кадров + waveform с подписями слов и серыми зонами тишин ≥400ms.

| Флаг | Что делает |
|---|---|
| `start`, `end` | Секунды (обязательно) |
| `-o, --output` | Куда сохранять PNG (default `<video>/edit/verify/<name>_<start>-<end>.png`) |
| `--n-frames` | Кадров в filmstrip (default 10) |
| `--transcript` | JSON для подписей слов (auto-резолв если есть кэш) |

### Когда вызывать

- Self-eval после рендера — каждый cut-edge ±1.5s
- Disambiguate ambiguous pauses
- Retake selection
- **Не вызывать в цикле по всем фразам** — это on-demand drill-down, не background index

---

## 6. Резка и EDL

### Hard rules для cuts

| Правило | Значение |
|---|---|
| Word boundary | Каждый cut-edge снаппится на границу слова из Scribe (Hard Rule 6) |
| Padding | 30–200ms head + tail (Hard Rule 7). Туже = быстрее монтаж, шире = cinematic. Scribe-таймстемпы дрейфуют 50–100ms — паддинг компенсирует |
| Cut targets | Тишины ≥ 400ms — самые чистые. 150–400ms — usable с визуальной проверкой. <150ms — небезопасно (mid-phrase) |
| Speaker handoffs | 400–600ms воздуха между репликами (taste call) |
| Audio events | `(laughs)`, `(sighs)` — расширять cut за них, реакция = beat |
| Confirmation | Никаких разрезов до подтверждения стратегии (Hard Rule 11) |

### EDL format

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

### Архетипы структуры (для editor sub-agent)

- Tech launch / demo: HOOK → PROBLEM → SOLUTION → BENEFIT → EXAMPLE → CTA
- Tutorial: INTRO → SETUP → STEPS → GOTCHAS → RECAP
- Interview: (QUESTION → ANSWER → FOLLOWUP) repeat
- Travel / event: ARRIVAL → HIGHLIGHTS → QUIET MOMENTS → DEPARTURE
- Documentary: THESIS → EVIDENCE → COUNTERPOINT → CONCLUSION
- Music / performance: INTRO → VERSE → CHORUS → BRIDGE → OUTRO
- Или придумать свой

---

## 7. Грейдинг

### Через EDL (`grade` field)

```json
"grade": "subtle"
"grade": "warm_cinematic"
"grade": "auto"
"grade": "eq=contrast=1.08:saturation=1.05"
```

### Пресеты (`helpers/grade.py`)

| Имя | Filter | Назначение |
|---|---|---|
| `subtle` | `eq=contrast=1.03:saturation=0.98` | Минимальная коррекция, безопасная везде |
| `neutral_punch` | `eq=contrast=1.06,curves=master='0/0 0.25/0.23 0.75/0.77 1/1'` | Контраст + S-кривая, без сдвигов оттенка |
| `warm_cinematic` | `eq=contrast=1.12:brightness=-0.02:saturation=0.88, colorbalance=…, curves=…` | Retro/cinematic, teal/orange split. **Opt-in**, не дефолт |
| `none` | `""` | Skip grading |

### `auto` mode

Анализирует клип (mean brightness, RMS contrast, saturation), эмитит bounded correction (±8% per axis). Не применяет creative LUT, teal/orange split, filmic curves. Цель: «look clean without looking graded». Для creative looks — `--preset warm_cinematic` явно.

### Standalone `grade.py`

```bash
python helpers/grade.py <input> -o <output>                   # auto mode (default)
python helpers/grade.py <input> -o <output> --preset warm_cinematic
python helpers/grade.py <input> -o <output> --filter 'eq=contrast=1.1'
python helpers/grade.py --print-preset warm_cinematic         # печатает фильтр
python helpers/grade.py --analyze <input>                     # печатает auto-grade анализ
```

### Mental model: ASC CDL

Per channel: `out = (in * slope + offset) ** power`, потом global saturation.
- `slope` → highlights
- `offset` → shadows
- `power` → midtones

### Custom-фильтры

Любая ffmpeg-цепочка работает в `grade` поле EDL или в `--filter`: `eq=`, `curves=`, `colorbalance=`, `colorchannelmixer=`, `lutyuv=`, `lut3d=`, `tonemap=`, `vignette=` и т.д.

### Hard rule

Грейд применяется **per-segment во время extract**, не post-concat. Иначе двойное re-encode.

---

## 8. Субтитры (burn-in via libass)

### Включение/выключение в `render.py`

```bash
python helpers/render.py <edl> -o final.mp4 --build-subtitles
python helpers/render.py <edl> -o final.mp4 --no-subtitles
```

- `--build-subtitles` — генерит `master.srt` из транскриптов с output-timeline offsets перед композитингом
- `--no-subtitles` — игнорит `subtitles` поле в EDL
- Без флагов — берёт `subtitles` поле из EDL (если есть)

### Built-in style (`bold-overlay`, для вертикали 1080×1920)

Зашит в `SUB_FORCE_STYLE` константе `helpers/render.py`:

```
FontName=Helvetica,FontSize=18,Bold=1,
PrimaryColour=&H00FFFFFF, OutlineColour=&H00000000, BackColour=&H00000000,
BorderStyle=1, Outline=2, Shadow=0,
Alignment=2, MarginV=90
```

`MarginV=90` — не вкус, а правило safe-zone: caption baseline ~30% от низа, чтобы не перекрывался UI TikTok / Reels / Shorts (caption + username + music + right-rail). Не опускать ниже ~75 без особой причины.

### Группировка `bold-overlay`

- 2-word chunks
- UPPERCASE
- Punctuation breaks: `.,!?;:`

### `natural-sentence` (для documentary / education)

4–7 слов, sentence case, разрыв на естественных паузах, `MarginV=60–80`, шрифт побольше. **Шипованного force_style нет** — придумать свой если нужно.

### Три измерения стиля

1. **Chunking** — 1 / 2 / 3 / sentence слов на строку
2. **Case** — UPPER / Title / Natural
3. **Placement** — `MarginV` от низа

### Hard rules subtitles

1. Субтитры применяются **ПОСЛЕДНИМИ** в filter chain (Hard Rule 1) — иначе оверлеи их прячут
2. **Output-timeline offsets** (Hard Rule 5): `output_time = word.start - segment_start + segment_offset`

---

## 9. Анимации / overlays

### Tool options

| Tool | Когда |
|---|---|
| **PIL + PNG sequence + ffmpeg** | Простые карточки, counters, typewriter, bar reveals. Любая эстетика, быстрые итерации |
| **Manim** | Формальные диаграммы, equations, graph morphs (`skills/manim-video/SKILL.md` для глубины) |
| **Remotion** | Typography-heavy, brand-aligned, web-adjacent layouts (React/CSS) |

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

### Duration heuristics (context-dependent)

- **Sync-to-narration:** floor 3s, типично 5–7s simple cards, 8–14s complex diagrams
- **Beat-synced accents** (music, fast montage): 0.5–2s
- **Hold final frame** ≥ 1s before cut (universal)
- **Над voiceover:** total ≥ `narration_length + 1s` (universal)
- **Никогда не parallel-reveal** независимых элементов — глаз не отслеживает два новых одновременно

### Animation payoff timing

Получить timestamp payoff-слова. Стартовать оверлей `reveal_duration` секунд раньше, чтобы landing frame совпал со spoken payoff word.

### Easing (universal — никогда `linear`)

```python
def ease_out_cubic(t):    return 1 - (1 - t) ** 3
def ease_in_out_cubic(t):
    if t < 0.5: return 4 * t ** 3
    return 1 - (-2 * t + 2) ** 3 / 2
```

`ease_out_cubic` — single reveals (slow landing). `ease_in_out_cubic` — continuous draws.

### Typing text anchor trick

Центрировать на ширине **полной строки**, не partial. Иначе текст съезжает влево по мере роста.

### Worked example palette (один из бесконечных)

- BG `(10, 10, 10)` near-black
- Accent `#FF5A00` / `(255, 90, 0)` orange
- Labels `(110, 110, 110)` dim gray
- Font: Menlo Bold (`/System/Library/Fonts/Menlo.ttc`, index 1)
- ≤ 2 accent colors, ~40% empty space, minimal chrome

### Sub-agent brief (для каждой анимации)

10 пунктов на каждый параллельный sub-agent:
1. One-sentence goal: «Build ONE animation: [spec]. Nothing else.»
2. Absolute output path (`<edit>/animations/slot_<id>/render.mp4`)
3. Тех-спек: разрешение, fps, codec, pix_fmt, CRF, duration
4. Style palette (RGB tuples / hex)
5. Font path с index
6. Frame-by-frame timeline (что когда, с easing)
7. Anti-list (без chrome / extras / titles если не указано)
8. Code pattern reference (копировать helpers inline, не импортировать через slots)
9. Deliverable checklist (script, render, ffprobe-verify duration, report)
10. **«Do not ask questions. If anything is ambiguous, pick the most obvious interpretation and proceed.»**

### Hard rules animations

- **PTS shift**: `setpts=PTS-STARTPTS+T/TB` чтобы overlay's frame 0 → window start (Hard Rule 4)
- **Parallel sub-agents** для нескольких анимаций (Hard Rule 10) — никогда sequential

---

## 10. Render

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
| Default (final) | 1080p | `fast` | 20 | Финал |
| `--preview` | 1080p | `medium` | 22 | Self-eval, QC |
| `--draft` | 720p | `ultrafast` | 28 | Только cut-point check |

### Что происходит внутри

1. **Per-segment extract** с грейдом + 30ms audio fades (Hard Rule 3)
2. **Lossless `-c copy` concat** в base.mp4 (Hard Rule 2)
3. **HDR → SDR tone mapping** автоматически если source HLG/PQ
4. **Final composite**: overlays (PTS-shifted, Hard Rule 4) → subtitles ПОСЛЕДНИЕ (Hard Rule 1) → out
5. **Loudness normalization** двухпроходный: -14 LUFS / -1 dBTP / LRA 11

### Промежуточные файлы

- `clips_graded/` — финальные сегменты (или `clips_preview/` / `clips_draft/`)
- `base.mp4` — concat без overlays/subs (или `base_preview.mp4` / `base_draft.mp4`)
- `master.srt` — если `--build-subtitles`
- `_concat.txt` — временный список (удаляется)
- `<output>.prenorm.mp4` — pre-loudnorm temp (удаляется)

### Output scale

`render.py` дефолтит scale на 1080p из любого источника. Для других целей — `--filter` или править extract-команду.

---

## 11. Аудио

### Loudnorm (по умолчанию on)

- Цель: **-14 LUFS integrated, -1 dBTP true peak, LRA 11 LU**
- Стандарт: YouTube / IG / TikTok / X / LinkedIn
- Двухпроходный: pass 1 measure, pass 2 normalize
- В preview/draft режиме — однопроходный
- Отключить: `--no-loudnorm`

### Audio fades (Hard Rule 3)

30ms fade in + 30ms fade out на каждом сегменте:
```
afade=t=in:st=0:d=0.03,afade=t=out:st={dur-0.03}:d=0.03
```
Без них — клики/попы на каждом cut.

### Audio-events как сигналы

`(laughs)`, `(sighs)`, `(applause)` от Scribe — beat-маркеры. Резать **после** них, не на них.

---

## 12. Output формат

Common targets (произвольно меняются):

- `1920×1080@24` — cinematic
- `1920×1080@30` — screen content
- `1080×1920@30` — vertical social
- `3840×2160@24` — 4K cinema
- `1080×1080@30` — square

`render.py` дефолтит scale на 1080p; для других — `--filter` или править extract-команду.

---

## 13. Directory layout

```
<videos_dir>/
├── <source files>             ← сырьё
└── edit/                      ← всё, что генерит агент
    ├── project.md             ← memory сессий
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

## 14. Memory — `project.md`

Append-only лог сессий в `<edit>/project.md`. Один блок на сессию:

```markdown
## Session N — YYYY-MM-DD

**Strategy:** one paragraph describing the approach
**Decisions:** take choices, cuts, grades, animations + why
**Reasoning log:** one-line rationale for non-obvious decisions
**Outstanding:** deferred items
```

При следующем заходе в ту же папку — читать `project.md` первым делом, одной фразой суммировать прошлую сессию перед вопросом «продолжить?».

---

## 15. Hard Rules (production correctness — non-negotiable)

| # | Правило |
|---|---|
| 1 | Subtitles в filter chain — ПОСЛЕДНИМИ |
| 2 | Per-segment extract → lossless `-c copy` concat (НЕ single-pass filtergraph) |
| 3 | 30ms audio fades на каждом сегменте |
| 4 | Overlays через `setpts=PTS-STARTPTS+T/TB` |
| 5 | Master SRT через output-timeline offsets |
| 6 | Cut только на word boundary |
| 7 | Cut padding 30–200ms |
| 8 | Word-level verbatim ASR only (не SRT-mode, не нормализация филлеров) |
| 9 | Cache transcripts per source — никогда не re-transcribe без причины |
| 10 | Parallel sub-agents для нескольких анимаций (не sequential) |
| 11 | Strategy confirmation **до** execution |
| 12 | Все session outputs в `<videos_dir>/edit/`, не внутри репо скилла |

---

## 16. Anti-patterns

- Hierarchical pre-computed codec formats / USABILITY-теги — over-engineering
- Hand-tuned moment-scoring functions — LLM выбирает лучше любого heuristic'а
- Whisper SRT / phrase-level — теряет sub-second gap data
- Whisper local на CPU — медленно, нормализует filler-words
- Subs burned в base **до** overlays — overlays их перекроют (Hard Rule 1)
- Single-pass filtergraph при overlays — двойной re-encode (Hard Rule 2)
- Linear easing анимаций — выглядит роботно
- Hard cuts без 30ms fades — клики (Hard Rule 3)
- Typing text centered на partial string — съезжает влево
- Sequential sub-agents для анимаций (Hard Rule 10)
- Editing до confirm стратегии (Hard Rule 11)
- Re-transcribing кэшированных source'ов (Hard Rule 9)
- Assuming what kind of video it is — look first, ask second, edit last

---

## 17. Setup / окружение (на холодный старт)

Установка лежит в `install.md`. На холодный старт сессии — только верификация:

- `ELEVENLABS_API_KEY` резолвится (env var или `.env` в корне репо). Если нет — попросить пользователя один раз и записать в `.env` (никогда не в `<videos_dir>`)
- `ffmpeg` + `ffprobe` на PATH
- Python deps установлены (`uv sync` или `pip install -e .` внутри репо)
- `yt-dlp`, `manim`, Remotion ставятся **только при первом использовании**
- Скилл vendoрит `skills/manim-video/` — читать его SKILL.md когда строишь Manim slot

Хелперы (`helpers/transcribe.py`, etc.) живут рядом с этим SKILL.md. Резолвить пути относительно директории, содержащей этот файл — скилл обычно симлинкнут в `~/.claude/skills/video-use/` или `~/.codex/skills/video-use/`.
