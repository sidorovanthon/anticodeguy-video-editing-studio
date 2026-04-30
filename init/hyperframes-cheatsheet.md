# HyperFrames — Cheat-Sheet

Полный справочник возможностей фреймворка `hyperframes` (CLI + скиллы для AI-агентов).
HTML-первый формат рендеринга видео: один `index.html` = одно видео. Скиллы установлены глобально в `~/.agents/skills/`, CLI работает из любой папки через `npx hyperframes …`.

---

## Table of Contents

1. [Workflow / процесс](#workflow--процесс)
2. [CLI команды](#cli-команды)
3. [Структура композиции](#структура-композиции)
4. [Data-атрибуты](#data-атрибуты)
5. [Видео и аудио](#видео-и-аудио)
6. [Timeline / GSAP контракт](#timeline--gsap-контракт)
7. [Captions / субтитры](#captions--субтитры)
8. [TTS (text-to-speech)](#tts-text-to-speech)
9. [Анимации и паттерны](#анимации-и-паттерны)
10. [Переходы между сценами](#переходы-между-сценами)
11. [Каталог блоков и компонентов](#каталог-блоков-и-компонентов)
12. [Веб-захват и интеграции](#веб-захват-и-интеграции)
13. [Опции рендера](#опции-рендера)
14. [Линтинг и валидация](#линтинг-и-валидация)
15. [Скиллы (для AI-агентов)](#скиллы-для-ai-агентов)
16. [Hard Rules](#hard-rules)
17. [Anti-patterns](#anti-patterns)
18. [Setup / окружение](#setup--окружение)
19. [Quick Reference Card](#quick-reference-card)

---

## Workflow / процесс

```
[scaffold]  npx hyperframes init <name>
   ↓
[author]    edit index.html (data-* атрибуты + GSAP timeline)
   ↓
[lint]      npx hyperframes lint     ← статический анализ HTML
   ↓
[validate]  npx hyperframes validate ← runtime в headless Chrome
   ↓
[preview]   npx hyperframes preview  ← студия с hot-reload (localhost)
   ↓
[render]    npx hyperframes render   ← финальный MP4/WebM
```

**Repo-less:** клон репо `hyperframes` НЕ нужен. CLI каждый раз тянет свежий пакет с npm.

---

## CLI команды

Запуск: `npx hyperframes <command> [options]`. Полный список через `npx hyperframes --help`.

### Getting Started

| Команда | Назначение |
|---|---|
| `init <name>` | Скаффолд проекта (HTML + meta.json + hyperframes.json + AGENTS.md/CLAUDE.md) |
| `add <block>` | Установить блок/компонент из каталога |
| `capture <url>` | Снять веб-страницу как клип |
| `catalog` | Браузер по каталогу 50+ блоков |
| `preview` | Запустить студию с hot-reload |
| `publish` | Залить проект на стабильный публичный URL |
| `render` | Финальный MP4/WebM |

### Project

| Команда | Назначение |
|---|---|
| `lint` | Статический анализ HTML (clip-классы, перекрытия, контракт) |
| `inspect` | Раскладка по таймлайну для проверки |
| `snapshot` | PNG-скриншоты ключевых кадров |
| `info` | Метаданные проекта |
| `compositions` | Список композиций в проекте |
| `docs` | Встроенная документация в терминале |

### Tooling

| Команда | Назначение |
|---|---|
| `benchmark` | Сравнение fps/quality/workers пресетов |
| `browser` | Управление встроенным Chrome |
| `doctor` | Проверка окружения (Chrome, FFmpeg, RAM, Node) |
| `upgrade` | Проверка обновлений |

### AI & Integrations

| Команда | Назначение |
|---|---|
| `skills` | Установка/обновление скиллов для AI-агентов |
| `transcribe` | ASR через whisper.cpp / импорт `.srt`/`.vtt`/JSON |
| `tts` | Text-to-speech (локальный, ~30+ голосов) |

### Параметры `init`

```bash
npx hyperframes init <name> [--video <file>] [--yes]
```
- `--video PATH` — добавить транскрипцию исходного видео в скаффолд
- `--yes` — не задавать интерактивных вопросов

### Параметры `transcribe`

```bash
npx hyperframes transcribe <input>
  [--model tiny|base|small|medium|large-v3]
  [--model small.en]                    # только если язык 100% английский
  [--language en|ru|es|...]              # без флага — авто-детект
```

Принимает: аудио/видео файлы, `.srt`, `.vtt`, OpenAI/Groq Whisper JSON. Вывод — нормализованный JSON с word-level timestamps.

### Параметры `tts`

```bash
npx hyperframes tts "<text>" --voice <name> --output <file.wav>
npx hyperframes tts script.txt --voice bf_emma
npx hyperframes tts --list             # все голоса
```

---

## Структура композиции

Минимальный `index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="10"
      data-width="1080"
      data-height="1920"
    >
      <!-- clips -->
    </div>
    <script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
```

### Standalone vs Sub-composition

| Тип | Где | Обёртка |
|---|---|---|
| **Standalone** (главный `index.html`) | `data-composition-id` div прямо в `<body>` | Без `<template>` |
| **Sub-composition** (загружается через `data-composition-src`) | Внутри `<template id="…">` | Обязательно `<template>` |

Sub-composition подключается:
```html
<div data-composition-id="my-comp"
     data-composition-src="compositions/my-comp.html"
     data-start="0" data-duration="10" data-track-index="1"></div>
```

---

## Data-атрибуты

### All Clips

| Атрибут | Required | Значения |
|---|---|---|
| `id` | Да | Уникальный идентификатор |
| `class="clip"` | **Да** для div/img с timing | Без него видим всё время композиции |
| `data-start` | Да | Секунды или ID-ссылка (`"el-1"`, `"intro + 2"`) |
| `data-duration` | Да для img/div/comp | Секунды. Video/audio дефолтятся к media duration |
| `data-track-index` | Да | Целое. Same-track clips **не могут перекрываться** |
| `data-media-start` | Нет | Trim-offset в источник (секунды) |
| `data-volume` | Нет | 0-1 (default 1) |
| `data-has-audio` | Нет | `"true"` для `<video>` со звуком в финальный микс |

⚠ `data-track-index` **не** влияет на визуальный layering — используйте CSS `z-index`.

### Composition Clips

| Атрибут | Required | Значения |
|---|---|---|
| `data-composition-id` | Да | Уникальный composition ID |
| `data-start` | Да | `"0"` для root |
| `data-duration` | Да | Перебивает GSAP timeline length |
| `data-width` / `data-height` | Да | Пиксели (1920×1080, 1080×1920, любые) |
| `data-composition-src` | Нет | Путь к внешнему HTML |

### Запрещённые атрибуты

- `data-layer` → используйте `data-track-index`
- `data-end` → используйте `data-duration`

---

## Видео и аудио

### Video

```html
<video id="el-v"
       class="clip"
       data-start="0" data-duration="30" data-track-index="0"
       src="video.mp4"
       muted playsinline></video>
```

⚠ HTML-атрибут `muted` обязателен для autoplay в браузере. Для **звука в финальном рендере**:
- Либо используйте отдельный `<audio>` (рекомендованный паттерн)
- Либо добавьте `data-has-audio="true"` + уберите `muted` (студия предупредит, но рендер заберёт звук)

### Audio

```html
<audio id="el-a"
       class="clip"
       data-start="0" data-duration="30" data-track-index="2"
       data-volume="1"
       data-media-start="12.0"
       src="music.mp3"></audio>
```

| Атрибут | Назначение |
|---|---|
| `data-volume` | 0-1, итоговая громкость в миксе |
| `data-media-start` | С какой секунды источника начинать |

Несколько `<audio>`-дорожек миксуются автоматически.

### Запрещено для медиа
- Анимировать размер `<video>` напрямую — анимируйте wrapper div
- Вызывать `video.play()` / `audio.play()` / `seek()` — runtime владеет playback'ом
- Класть `<video>` внутрь timed div — используйте non-timed wrapper

---

## Timeline / GSAP контракт

```js
window.__timelines = window.__timelines || {};
const tl = gsap.timeline({ paused: true });        // ← всегда paused
// tweens
tl.from(".title", { opacity: 0, y: -50, duration: 1 }, 0);
window.__timelines["main"] = tl;                    // ← регистрация по composition-id
```

### Правила
- Всегда `paused: true` — плеер/рендер сам сидит на `tl.seek(t)`
- Регистрировать каждый timeline в `window.__timelines["<composition-id>"]`
- Sub-timelines авто-nest'ятся — не делайте руками
- Длительность из `data-duration`, не из GSAP timeline length
- Никогда не создавайте пустых tween'ов для длительности
- **Синхронное построение** — никаких `async`/`await`/`setTimeout`/`Promise`. Шрифты подключаются автоматически

### GSAP допустимо анимировать
✅ `opacity`, `x`, `y`, `scale`, `rotation`, `color`, `backgroundColor`, `borderRadius`, transforms

### GSAP запрещено анимировать
❌ `visibility`, `display`
❌ Размеры `<video>`/`<audio>` элементов
❌ Один и тот же property на одном элементе из нескольких timeline'ов одновременно

### Детерминированность
- Никаких `Math.random()` без сидинга → используйте mulberry32
- Никаких `Date.now()`
- Никаких сетевых запросов на рендере
- `repeat: -1` ломает capture engine → считайте конечный repeat: `Math.ceil(duration / cycleDuration) - 1`

---

## Captions / субтитры

### Источник
- `npx hyperframes transcribe` локально через whisper.cpp
- Или импорт `.srt` / `.vtt` / OpenAI/Groq Whisper JSON
- Или внешний whisper + `transcribe <file.json>` для нормализации

### Whisper модели

| Модель | Размер | Скорость | Когда |
|---|---|---|---|
| `tiny` | 75 MB | Быстрее всего | Быстрые превью |
| `base` | 142 MB | Быстро | Короткие, чистый звук |
| `small` | 466 MB | Средне | **Default**, хорошо для большинства |
| `medium` | 1.5 GB | Медленно | Шумный звук, музыка |
| `large-v3` | 3.1 GB | Самая медленная | Production quality |

⚠ **Только** `.en`-вариант если речь 100% английская. `.en` модели **переводят** не-английский в английский, а не транскрибируют.

### Стиль captions

Три измерения:
1. **Chunking** — 1 / 2 / 3 / sentence слов на строку
2. **Case** — UPPER / Title / Natural
3. **Placement** — для landscape `bottom 80-120px`, для portrait `~600-700px от низа`

### Group rules
- High energy: 2-3 слова, быстрая смена
- Conversational: 3-5 слов, естественные фразы
- Calm: 4-6 слов, длинные группы
- Разрыв на: пунктуации, паузах ≥ 150ms, или max word count

### Code-pattern (паттерны для timeline)

```js
GROUPS.forEach(function(group, i) {
  var sel = "#cap-" + i;
  // entrance
  tl.fromTo(sel,
    { opacity: 0, y: 24, scale: 0.94 },
    { opacity: 1, y: 0,  scale: 1,    duration: 0.18, ease: "back.out(1.4)" },
    group.start);
  // exit
  tl.to(sel, { opacity: 0, y: -16, scale: 0.96, duration: 0.14, ease: "power2.in" }, group.end - 0.14);
  // hard kill — обязательно (deterministic)
  tl.set(sel, { opacity: 0 }, group.end);
});
```

### Self-lint после построения
Проверять, что каждая группа невидима после `group.end`:

```js
GROUPS.forEach(function(group, i) {
  var el = document.getElementById("cap-" + i);
  tl.seek(group.end + 0.01);
  if (parseFloat(getComputedStyle(el).opacity) > 0.01) {
    console.warn("[caption-lint] cap-" + i + " still visible");
  }
});
tl.seek(0);
```

### Containers
- `position: absolute` (никогда `relative`)
- `overflow: visible` (НЕ `hidden` — обрезает scaled-words и glow)
- При per-word `scale > 1` — `maxWidth = safeWidth / maxScale`

### Built-in fitText
```js
var result = window.__hyperframes.fitTextFontSize(text.toUpperCase(), {
  fontFamily: "Outfit",
  fontWeight: 900,
  maxWidth: 1600,            // 1600 landscape, 900 portrait
  baseFontSize: 78,
  minFontSize: 42,
  step: 2
});
```

### Per-word emphasis
- Бренд / продукт-нейм: больше размер, уникальный цвет
- ALL CAPS: scale boost, accent color
- Числа/статистика: bold + accent
- Marker highlight (sweep / circle / burst / scribble): см. css-patterns скилла

---

## TTS (text-to-speech)

```bash
npx hyperframes tts "<text>" --voice af_nova --output narration.wav
npx hyperframes tts script.txt --voice bf_emma --output script.wav
npx hyperframes tts --list                   # все доступные голоса
```

Локальный, без API-ключей, ~30+ голосов. Подключается как обычный `<audio>` клип.

### TTS + Captions workflow
1. `npx hyperframes tts "..." --output narration.wav`
2. `npx hyperframes transcribe narration.wav --model small.en` → word-level timestamps
3. Загрузить транскрипт + WAV в композицию → синхронные captions

---

## Анимации и паттерны

### Allowed properties (recap)
✅ opacity, x, y, scale, rotation, transforms, color, backgroundColor, borderRadius

### Длительности (rule of thumb)

| Тип | Длительность |
|---|---|
| Sync-to-narration card | 5-7s простая, 8-14s сложная |
| Beat-synced accent | 0.5-2s |
| Hold final frame | ≥ 1s перед cut'ом |
| Поверх voiceover | `narration_length + 1s` минимум |

### Easing presets (НЕ `linear`)
- `power3.out` — entrance default
- `power2.in` — exit
- `back.out(1.4)` — bouncy entrance
- `back.out(1.7)` — больше overshoot
- `elastic.out` — wobbly
- `power2.out` — gentle ease

### Patterns (paragraphs, не строгие правила)

#### Picture-in-Picture
```html
<div id="pip-frame" style="position:absolute;top:0;left:0;width:1920px;height:1080px;z-index:50;overflow:hidden;">
  <video id="el-video" data-start="0" data-duration="60" data-track-index="0"
         src="talking-head.mp4" muted playsinline></video>
</div>
```
```js
tl.to("#pip-frame", { top: 700, left: 1360, width: 500, height: 280, borderRadius: 16, duration: 1 }, 10);
```
Анимируется wrapper, видео заполняет его.

#### Slide Show
```html
<div class="slide" data-start="0"  data-duration="30" data-track-index="3">...</div>
<div class="slide" data-start="30" data-duration="25" data-track-index="3">...</div>
```
Каждый слайд auto-mount/unmount по своему окну.

#### Title Card with Fade
```html
<div id="title-card" class="clip" data-start="0" data-duration="5" data-track-index="5">
  <h1 style="opacity:0;">My Title</h1>
</div>
```
```js
tl.to("#title-card h1", { opacity: 1, duration: 0.6 }, 0.3);
tl.to("#title-card",    { opacity: 0, duration: 0.5 }, 4);
```

### Layout-Before-Animation (best practice)
1. Найти **hero frame** — момент с максимумом видимых элементов
2. Написать static CSS под него: `.scene-content { width:100%; height:100%; padding:Npx; display:flex; flex-direction:column; gap:Npx; box-sizing:border-box; }`
3. **Никогда** `position:absolute; top:Npx` для контент-контейнеров — оверфлоу при росте контента
4. Entrances через `gsap.from()` — анимировать ОТ offscreen К CSS-позиции
5. Exits через `gsap.to()` — анимировать ОТ CSS-позиции К offscreen

### Visual Identity Gate (HARD)
Перед написанием HTML **обязательно**:
1. `DESIGN.md` в проекте? → читать, использовать его palette/fonts/motion rules
2. `visual-style.md` есть? → применить `style_prompt_full`
3. Пользователь назвал стиль (Swiss Pulse, dark techy, luxury) → читать 8 пресетов из `visual-styles.md`
4. Ничего нет → задать 3 вопроса (mood/light-or-dark/refs) и сгенерить минимальный DESIGN.md

Без этого — **запрет** писать `#333`, `#3b82f6`, `Roboto`.

### Audio-reactive
- Bass band → `scale` пульс (3-6% вариации, не больше — иначе нечитаемо)
- Mid band → glow / emission
- Аудио-данные передаются на timeline синхронно с `tl.seek(t)`

---

## Переходы между сценами

### CSS-переходы (каталог)
- **Fade / dissolve** — gentle, default
- **Blur** — depth-of-field, dreamy
- **Scale / zoom** — through-camera, gravity drop
- **Slide / push** — direction-driven
- **Glitch / chromatic / VHS** — tense / digital
- **Light leak / film burn** — retro / analog
- **Ripple / clock wipe** — другие

### WebGL шейдер-переходы
- `ridged burn` — sharp lightning edges
- `cinematic zoom` / `gravitational lens`
- `domain warp` / `swirl vortex`
- `glitch` (shader) / `chromatic split`
- `ripple waves` / `light leak`

Ставятся через `npx hyperframes add <name>` или из каталога.

### По «энергии» сцены
| Energy | Подходит |
|---|---|
| High | Glitch, scale-pop, scatter, drop |
| Medium | Fade, dissolve, slide, blur |
| Low | Slow dissolve, gentle blur, light leak |

---

## Каталог блоков и компонентов

### Команды

```bash
npx hyperframes catalog                  # интерактивный браузер
npx hyperframes add <name>               # установить блок/компонент
npx hyperframes add flash-through-white  # пример: shader transition
npx hyperframes add instagram-follow     # пример: соц-оверлей
npx hyperframes add data-chart           # пример: animated chart
```

### Категории
- **Соц-оверлеи** — Instagram-follow, like-count и т.п.
- **Графики / data-viz** — bar chart race, animated charts
- **Шейдер-эффекты** — flash-through-white и др.
- **Кинематографические эффекты** — film burn, light leak, lens flare
- **Переходы** — все из секции выше

### `hyperframes.json`
Манифест проекта со списком установленных блоков:
```json
{
  "registry": [
    { "name": "flash-through-white", "version": "0.1.0" }
  ]
}
```

Скилл `hyperframes-registry` описывает структуру `registry-item.json` каждого блока.

---

## Веб-захват и интеграции

### `capture` — захват веб-страницы
```bash
npx hyperframes capture <url> [--output <file>] [--scroll]
```
Снимает страницу как видеоклип, который можно вставить в композицию.

### Полный URL → видео пайплайн
Скилл `website-to-hyperframes` — 7-шаговый пайплайн от URL до готового MP4.

### Импорт из Remotion
Скилл `remotion-to-hyperframes` транслирует React (`.tsx` с `useCurrentFrame` / `Sequence` / `interpolate` / `spring`) в HyperFrames HTML. Не поддерживается: `useState`, side-effect `useEffect`, async `calculateMetadata`, `@remotion/lambda`.

---

## Опции рендера

```bash
npx hyperframes render \
  [--fps 24|30|60] \
  [--quality draft|standard|high] \
  [--format mp4|webm] \
  [--workers 1-8|auto] \
  [--docker] \
  [--gpu] \
  [--strict] \
  [--strict-all] \
  [--output <path>]
```

| Флаг | Назначение |
|---|---|
| `--fps` | 24 / 30 / 60 (60 удваивает время рендера) |
| `--quality` | `draft` итерация / `standard` ревью / `high` финал |
| `--format` | `mp4` (H.264+AAC) / `webm` (с альфа-каналом) |
| `--workers` | Параллельные Chrome-инстансы |
| `--docker` | Детерминированный рендер в фиксированной среде |
| `--gpu` | GPU-ускорение энкодинга |
| `--strict` | Падать на lint-ошибках |
| `--strict-all` | Падать на ошибках И варнингах |

### Output разрешения
Из коробки любое — задаётся через `data-width`/`data-height` корневого `<div>`. Примеры:

| Формат | Использование |
|---|---|
| 1920×1080 @ 24 | Cinematic landscape |
| 1920×1080 @ 30 | Talking-head / screen content |
| 1080×1920 @ 30 | Vertical social (Reels/TikTok/Shorts) |
| 3840×2160 @ 24 | 4K cinema |
| 1080×1080 @ 30 | Square Instagram |

⚠ Один HTML под несколько разрешений из коробки **не делает**. Авторите под конкретный canvas или городите CSS-переменные/умножение чисел вручную.

### Что внутри рендера
1. Puppeteer открывает HTML в headless Chrome
2. Кадр-за-кадром: `tl.seek(t / fps)` → screenshot PNG
3. FFmpeg image2pipe → H.264 (или WebM)
4. Микс `<audio>` + `data-has-audio` видео-дорожек

---

## Линтинг и валидация

### `lint` — статика

```bash
npx hyperframes lint [<path>] [--strict]
```

Проверяет:
- `class="clip"` на timed-элементах
- Перекрытия клипов на одной дорожке
- Запрещённые атрибуты (`data-layer`, `data-end`)
- Контракт `window.__timelines`
- Запрещённые конструкции (`Math.random` без сидинга, `Date.now`, `repeat: -1`, async timelines)
- Размер файла (warning при > N строк)
- `composition-src` ведёт на существующий файл

### `validate` — runtime

```bash
npx hyperframes validate
```

Открывает в headless Chrome:
- JS-ошибки в консоли
- Контраст текста (WCAG AA)
- Missing assets (404)
- StaticGuard контракт нарушения
- Captions-lint (видимость после `group.end`)

### `inspect` — раскладка
```bash
npx hyperframes inspect [--at <time>] [--composition <id>]
```
Печатает таймлайн-граф: какие клипы активны на каждой секунде.

### `snapshot` — ключевые кадры
```bash
npx hyperframes snapshot [--at 0,5,10,30] [--out <dir>]
```
PNG ключевых кадров для визуальной проверки без полного рендера.

### `benchmark`
```bash
npx hyperframes benchmark .
```
Прогоняет несколько fps/quality/workers пресетов и сравнивает время + размер.

### `doctor` — окружение
```bash
npx hyperframes doctor
```
Проверяет: Chrome, FFmpeg, Node, RAM, версии. Запускать первым делом, если рендер падает.

---

## Скиллы (для AI-агентов)

Установка:
```bash
npx skills add heygen-com/hyperframes -y -g
```

Скиллы лежат в `~/.agents/skills/`. Это **markdown-инструкции для агента**, не код. Они читаются Claude Code / Cursor / Codex / Gemini / Copilot и учат правильно писать композиции.

### Доступные скиллы

| Skill | Что учит |
|---|---|
| `hyperframes` | Авторинг композиций, captions, TTS, audio-reactive, transitions |
| `hyperframes-cli` | CLI команды (init, lint, preview, render, transcribe, tts) |
| `hyperframes-registry` | Установка блоков через `hyperframes add` |
| `gsap` | GSAP API, timelines, easing, ScrollTrigger, плагины |
| `website-to-hyperframes` | Полный URL → video пайплайн |
| `remotion-to-hyperframes` | Перевод Remotion-композиций в HyperFrames |

### Slash-команды (Claude Code)

| Команда | Когда |
|---|---|
| `/hyperframes` | Авторинг композиций |
| `/hyperframes-cli` | Справочник CLI команд |
| `/hyperframes-registry` | Работа с каталогом |
| `/gsap` | GSAP-вопросы |
| `/website-to-hyperframes` | URL → video |

### Обновление скиллов
- На Windows у вас настроена локальная задача `HyperFrames Skills Update` через Task Scheduler — запускается при логине + 5 мин, тихо в фоне
- Лог: `%USERPROFILE%\hf-skills-update.log`
- Вручную: `npx skills add heygen-com/hyperframes -y -g`

---

## Hard Rules

Не опции — корректность.

| # | Правило |
|---|---|
| 1 | Все timeline'ы стартуют `paused: true` |
| 2 | Регистрировать каждый timeline в `window.__timelines["<composition-id>"]` |
| 3 | Sub-timelines авто-nest'ятся — не делать руками |
| 4 | Длительность из `data-duration`, не из GSAP |
| 5 | Никаких `Math.random()` без сидинга, `Date.now()`, network на рендере |
| 6 | Никаких `repeat: -1` — считать конечный repeat |
| 7 | Синхронное построение timeline'а (не async/await/setTimeout/Promise) |
| 8 | Не анимировать `visibility`, `display` |
| 9 | Не вызывать `play()` / `pause()` / `seek()` на медиа |
| 10 | `<video>` всегда `muted playsinline` (звук — отдельный `<audio>` либо `data-has-audio="true"`) |
| 11 | `<video>` не внутри timed div — wrapper non-timed |
| 12 | Каждая caption-группа — `tl.set` hard-kill в конце |
| 13 | Нет `data-layer` / `data-end` (использовать `data-track-index` / `data-duration`) |
| 14 | Visual Identity Gate — без DESIGN.md/style не писать HTML |

---

## Anti-patterns

- Использование video для audio (всегда `<video muted>` + отдельный `<audio>`)
- Анимация размера `<video>` напрямую вместо wrapper'а
- `Math.random()` без сидинга — недетерминированный рендер
- `repeat: -1` — ломает capture engine
- Async timeline construction — capture-engine не дождётся
- Hardcoded `width: 1920px` на содержимом (не масштабируется на другие canvas)
- `position: absolute; top: Npx` на content-контейнере (overflow при росте контента)
- `overflow: hidden` на caption-контейнере (обрезает scale > 1 слова и glow)
- Forget `class="clip"` на timed div/img — будут видимы всё время
- Same property animated from multiple timelines — конфликты
- Linear easing — выглядит роботично
- Бренд-цвета без DESIGN.md (`#3b82f6`, `Roboto`, `#333`)
- Авторинг под несколько разрешений в одном HTML — невозможно из коробки

---

## Setup / окружение

| Требование | Проверка |
|---|---|
| Node.js ≥ 22 | `node --version` |
| FFmpeg | `ffmpeg -version` |
| Chrome | автоматически качается через `npx hyperframes browser install` |
| Скиллы | `~/.agents/skills/hyperframes*` |

`npx hyperframes doctor` — проверка всего сразу.

### Файлы проекта (после `init`)

```
my-video/
├── index.html           ← главная композиция
├── meta.json            ← метаданные
├── hyperframes.json     ← манифест registry-блоков
├── AGENTS.md            ← инструкции для AI-агентов
├── CLAUDE.md            ← аналог для Claude Code
├── DESIGN.md            ← (опционально) визуальная идентичность
├── compositions/        ← (опционально) sub-compositions
│   └── intro.html
├── media/               ← ассеты (видео/аудио/изображения)
└── renders/             ← выходные MP4/WebM
```

### Лицензия
**Apache 2.0** — коммерческое использование без ограничений, без per-render fee, без seat caps.

---

## Quick Reference Card

```bash
# Scaffold
npx hyperframes init my-video
cd my-video

# Author (вручную правьте index.html)

# Validate
npx hyperframes lint
npx hyperframes validate

# Preview (студия с hot-reload)
npx hyperframes preview                 # http://localhost:3002

# Snapshots / inspect (без полного рендера)
npx hyperframes snapshot --at 0,2.5,5,10
npx hyperframes inspect --at 5

# Transcribe / TTS
npx hyperframes transcribe video.mp4 --model small
npx hyperframes tts "Hello" --voice af_nova --output narration.wav

# Render
npx hyperframes render --quality draft  --output draft.mp4
npx hyperframes render --quality high --fps 30 --output final.mp4
npx hyperframes render --docker --strict --output final.mp4

# Каталог
npx hyperframes catalog
npx hyperframes add flash-through-white

# Capture сайта
npx hyperframes capture https://example.com

# Окружение / диагностика
npx hyperframes doctor
npx hyperframes info
npx hyperframes upgrade
npx hyperframes benchmark .

# Скиллы
npx skills add heygen-com/hyperframes -y -g
```
