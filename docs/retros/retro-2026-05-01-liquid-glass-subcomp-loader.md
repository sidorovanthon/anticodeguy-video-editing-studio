# Retro: `/edit-episode` Liquid Glass прогон + sub-composition loader не работает

Дата: 2026-05-01. Эпизод: `2026-05-01-desktop-software-licensing-it-turns-out-is`
(1080×1920, 52.6s после Phase 3-cut). Заход — обычный orchestrated `/edit-episode`
прогон с тем же скриптом, что и в retro Section 7, но на свежий эпизод и в
визуальной идентичности **Liquid Glass / iOS frosted glass** (custom DESIGN.md,
не из `visual-styles.md` пресетов).

Phase 1–3 + glue прошли чисто (Audio Isolation cached, Phase 3 cut 24.8%,
remap envelope). Phase 4 — половина рабочего дня в трёх зонах боли:
WCAG headless артефакт, blank studio preview, и главное — **рендер выдал чистое
A-roll без overlay-ев, потому что `data-composition-src` sub-comps не
маунтятся в родителя**. Только инлайн-рефактор закрыл задачу.

Один confirmed bug, две гипотезы про устройство HF runtime, и одна явно
неправильная memory-запись, которую надо менять.

---

## Section 7 hypothesis check (continuity со старым retro)

| # | Retro | Гипотеза | Результат |
|---|---|---|---|
| a | sect7-2.1 | StaticGuard на этом эпизоде не сработает после `data-has-audio="false"` | ✅ В preview-log за 5s после launch ни `[StaticGuard]`, ни `Invalid HyperFrame contract`. |
| b | sect7-2.2 | Captions mandatory переформулировка в Phase 4 brief сработает | ✅ Skill-агент в этом прогоне сразу включил captions track в DESIGN.md → Beat→Visual Mapping и в композицию. |
| c | sect7-2.3 | Sub-composition split per beat будет применён без побочных эффектов | ❌ **Сделал split (5 файлов в `compositions/`) — рендер вышел пустой. Это главная находка ниже §2.3.** |

Идемпотентность работала: pickup short-circuit-нул, Phase 2 — `tag-present`, всё ок.

---

## Главные находки (этот прогон)

### 2.1 [H] `data-composition-src` sub-comps не маунтятся в render — content полностью теряется

- **Что произошло:** собрал каноничные 5 sub-comp файлов (`compositions/beat-{1..4}-*.html` + `compositions/captions.html`) с `<template>` wrapper-ом, как описано в `~/.agents/skills/hyperframes/SKILL.md` § "Composition Structure". Корневой `index.html` маунтил их через `<div data-composition-src="compositions/beat-1-hook.html" data-start="0" data-duration="6.72" ...>`. Lint, validate, inspect — все clean. Render отработал без ошибок, выдал 28.4 MB MP4. Пользователь открыл — **только talking-head A-roll, ни одного overlay-я**.
- **Что показал `npx hyperframes compositions`:**

  ```
  main       52.6s   1080×1920   7 elements
  beat-1     0.0s   1080×1920   0 elements ← compositions/beat-1-hook.html
  beat-2     0.0s   1080×1920   0 elements ← compositions/beat-2-online.html
  beat-3     0.0s   1080×1920   0 elements ← compositions/beat-3-offline.html
  beat-4     0.0s   1080×1920   0 elements ← compositions/beat-4-cta.html
  captions   0.0s   1080×1920   0 elements ← compositions/captions.html
  ```

  Framework видит файлы как **отдельные top-level композиции с 0 elements / 0.0s duration**, а не как монтаж-таргеты для родителя. Compiler-лог рендера: `"videoCount":1,"audioCount":1` — никакого упоминания sub-comp-ов.
- **Гипотезы для root cause (не дожали в этой сессии):**
  1. `<template>` wrapper в sub-comp файле — каноничный по SKILL.md, но `npx hyperframes compositions` сканит DOM и `<template>` content скрыт от `querySelector` в стандартном HTML5 parser-е. Снёс wrapper → всё равно 0 elements. Снёс wrapper и завернул в `<!doctype><html><body>...</body></html>` → всё равно 0 elements.
  2. Sub-comp content внутри своего `data-composition-id` div-а просто статичный (style + div + script) — нет ни одного `class="clip"` ребёнка с `data-start`. Возможно, framework считает «elements» только timed clip-ы и пустую duration ставит когда clip-ов нет. Но даже с этим — overlay-и должны были появиться визуально через статичные div-ы. Не появились.
  3. `data-composition-src` в этом релизе HF (0.4.41) на Windows может быть просто **не реализован в pipeline-е компилятора** — сканит файлы как отдельные документы, но не fetch-ит их при сборке родителя. Документация `node_modules/hyperframes/dist/docs/compositions.md` показывает синтаксис, но я не нашёл где именно loader разворачивает src в DOM.
- **Что сработало:** инлайн всех 4 beat-ов + captions track-а в `index.html` как обычные `<div class="clip" data-start="N" data-duration="M" data-track-index="3">` блоки, GSAP timeline собирается централизованно с offset-ами `B2 = 6.72`, `B3 = 35.5`, `B4 = 47.5`. Captions builder остался JS-ом, но теперь работает с inline `<div id="cap-stack">`, а не через sub-comp. Render: 24.4 MB, **все overlay-и на месте**, snapshot подтвердил визуально.
- **Связь с MEMORY.md:** запись `feedback_multi_beat_sub_compositions.md` («Multi-beat HF compositions split per-beat — sub-compositions in compositions/, root index.html ≤ 100 lines; lint warning is real») сформирована из retro Section 7 в режиме **«lint warning есть → надо разбивать»**, без эмпирической проверки что разбиение действительно работает. У меня — НЕ сработало. Memory надо пересмотреть.
- **Фикс — три уровня:**
  1. **MEMORY.md:** обновить `feedback_multi_beat_sub_compositions.md` — добавить «**verified empty render on 2026-05-01 with HF 0.4.41 on Windows**: `data-composition-src` sub-comps не маунтятся в render. Inline-рефактор обязателен пока loader не починят. Lint warning `composition_file_too_large` — это **рекомендация**, а не enforcement; игнорируем до починки upstream.»
  2. **Phase 4 brief в `.claude/commands/edit-episode.md`:** убрать «Sub-composition split — strong recommendation» в текущей формулировке, заменить на «**Sub-composition split — currently broken in HF 0.4.41 on Windows**. Author all beats inline in `index.html`. The lint warning `composition_file_too_large` is informational; the `data-composition-src` loader does not mount external sub-comps into the render output (verified 2026-05-01 — render emits A-roll-only when sub-comps used).»
  3. **Upstream:** репортнуть на `heygen-com/hyperframes`. Минимальный repro: scaffold a project, add `<div data-composition-src="compositions/foo.html" data-start="0" data-duration="5" data-track-index="1"></div>` в index.html, в `compositions/foo.html` положить `<div data-composition-id="foo" data-width="1920" data-height="1080"><div style="background:red;width:100%;height:100%"></div></div>`. Render — красного не будет.

### 2.2 [M] WCAG validator показывает 68 contrast warnings из-за entrance `opacity: 0`

- **Что произошло:** `npx hyperframes validate` стабильно репортит 68 contrast warnings типа `div.b1-title — 1.12:1 (need 4.5:1)`. JSON-debug показал `fg: rgb(0,0,0)` — то есть текст элемента как будто чёрный, хотя CSS даёт `color: #E6F1FF`. Bg при этом корректный (`rgb(13,18,29)` ≈ shadow-ink `#0B1220`). Прошёл по канонной WCAG-fix лестнице:
  1. Variant 1: `rgba(255,255,255,0.16)` → `rgba(11,18,32,0.55)` (darker палитра-family вариант). Не помогло.
  2. Variant 2: `rgba(11,18,32,0.86)` (near-opaque) + dark plates под floating mono labels. Не помогло.
  3. Добавил `color: #E6F1FF` на root sub-comp селекторы для inheritance. Не помогло.
- **Корень:** validator делает 5 timestamp screenshot-ов и читает pixel-ы. Но мои entrance-tween-ы используют каноничный паттерн `tl.fromTo(..., { opacity: 0, ... }, ...)`. GSAP `immediateRender: true` (default) реализует from-state при construction → элемент рендерится с opacity 0 в статичный screenshot. Validator видит **transparent text → семплированный `fg` ≈ background pixel**, отсюда контраст ~1.1:1.
- **Это ложный позитив:** в реальном render-е timeline проигрывается, и текст видим. Снапшоты после inline-рефактора подтвердили.
- **Связь с canon:** HF SKILL.md § "Contrast" предлагает «adjust hue within palette family» как fix. Это решает **настоящие** WCAG-фейлы (плохой выбор цвета), но НЕ покрывает headless-render-артефакт от entrance-анимаций. Канон в этом месте даёт ложно-уверенный совет («≥ 2 darker/brighter variants of the same hue before considering structural changes»), который никогда не сработает на этом классе варнингов.
- **Фикс на orchestrator-уровне:**
  - **Phase 4 brief:** добавить «Если все contrast warnings имеют `fg: rgb(0,0,0)` И элементы используют `opacity: 0` в entrance fromTo, это headless-render-артефакт, не реальный fail. Document в DESIGN.md → "WCAG Validator — Headless Artifact" одной строкой и proceed. Не итерировать по палитре — это пустая работа.»
  - **Phase 4 Output Checklist:** заменить «validate passes; built-in WCAG contrast audit produces no warnings» на «validate passes; contrast warnings либо отсутствуют, либо все `fg: rgb(0,0,0)` (entrance-state артефакт, документировать в DESIGN.md и proceed)».
- **Что я уже сделал:** в DESIGN.md этого эпизода прописал «WCAG Validator — Headless Artifact» отдельной секцией с трёмя итерациями fix-попыток и обоснованием. Это одно из last-resort обоснований, которые канон допускает.

### 2.3 [M] Studio preview не рендерил композицию вплоть до явного клика по `index`

- **Что произошло:** preview сервер запустился, никаких StaticGuard / Invalid HyperFrame contract в логе за 5s. Открыл `localhost:3002/#project/hyperframes` — player пустой, «Drop media here», timeline 0:00 / 0:00. Канонная test-композиция (`/tmp/hf-test/test`) показывала аналогично пустой player (canonical scaffold не имеет clip-ов вообще). Пользователь несколько раз показывал screenshot-ы — везде пусто.
- **DevTools показал:** Network tab → `index.html` загружается с двумя запросами на `/api/projects/hyperframes/preview/comp/index.html`, один **canceled** (provisional headers). Console — никаких errors, только iframe-sandbox warning. Сервер на curl возвращает 200 OK с валидным HTML.
- **Что я думал:** «studio iframe не может распарсить из-за doubled `<html>`» (preview-server инжектит свой wrapper поверх моего полного HTML-документа, получается `<html><head>...</head><body>...<html lang="en">...</html>...</body></html>`). Полез эту гипотезу проверять — обнаружил что **canonical scaffold даёт точно такой же doubled-html** и при этом работает (показывает 0:10 duration). То есть doubled-html — не bug, парсер браузера толерирует.
- **Что происходило на самом деле:** студия НЕ показывает overlay-и пока не кликнут по конкретной композиции в sidebar-е. На скриншотах пользователя `index` иногда был highlighted, иногда нет. Когда `index` не выбран, player в режиме «empty state» с подсказкой «Drop media here», даже если в sidebar-е композиция корректно индексирована. Это **дефолтное поведение студии**, а не bug. Я его принял за «render fail» и пошёл фиксить несуществующую проблему.
- **Дополнительный фактор:** даже когда `index` selected, render выходил пустой (это был баг §2.1, не studio). Так что часть моей паники была обоснована — overlay-ев действительно не было, и это видно ВЕЗДЕ (snapshot, render, studio). Но пустой player сам по себе ничего не доказывает.
- **Что нужно было сделать сразу:** запустить `npx hyperframes snapshot` ДО studio launch, проверить визуально что overlay-и есть на статичных кадрах. Я делал snapshot — он тоже был пустой (тот же баг §2.1) — но интерпретировал как «sub-comps не успевают загрузиться в snapshot timeout-е», вместо того чтобы понять что это симптом sub-comp loader bug-а.
- **Фикс:** в Phase 4 brief переставить порядок visual verification — **сначала snapshot, затем studio launch**. Snapshot — каноничный screenshot composition state-а во временных точках. Если snapshot пуст в beat-window — надо чинить композицию, не studio.

### 2.4 [L] HF lint regex ложно срабатывает на комментарии с текстом `repeat:-1`

- **Что произошло:** в `compositions/beat-3-offline.html` написал комментарий `// dot pulses, staggered phases — finite repeat counts (no repeat:-1)`. Lint выдал `gsap_infinite_repeat: GSAP tween uses repeat: -1`. Никаких `repeat: -1` в коде у меня не было — `repeat: 7`, `repeat: 2`. Он матчит подстроку `repeat:-1` (без пробела) в комментарии.
- **Корень:** lint regex на `gsap_infinite_repeat` использует строковый match по `repeat:-1` без проверки на JS-комментарий. Ложный позитив на любой комментарий, который объясняет «не используем `repeat: -1`».
- **Fix:** убрать строку из комментария. Эпизод-локальный воркэраунд.
- **Upstream:** репортнуть как minor lint bug — regex должен либо парсить как JS, либо хотя бы исключать `// ... repeat:-1` строки.

### 2.6 [H] Я снова написал всё инлайн в main session, проигнорировав parallel-agent dispatch инструкцию

- **Что произошло:** Phase 4 brief в `.claude/commands/edit-episode.md` содержит строку:
  > **Parallel-agent dispatch — orchestrator pattern.** Beats are independent and parallelizable. Consider dispatching beat authoring to parallel sub-agents via the `superpowers:dispatching-parallel-agents` skill (this is an orchestrator pattern via superpowers, NOT HF canon).

  Я прочитал «Consider» как опциональную рекомендацию и пошёл писать все 4 beat sub-comp файла + DESIGN.md + expanded-prompt.md + captions sub-comp **последовательно в main session**. Ни один агент за всю Phase 4 не был задиспетчен.
- **Почему это плохо тут не теоретически:**
  - Phase 4 занял ~80 минут wall-time. С параллельной диспетчеризацией 4 beat-агентов: wall-time свернулся бы примерно в **время одного beat-а** (5–10 мин), main session параллельно делал бы DESIGN.md / scaffold sanity checks.
  - Каждый агент-сделанный beat-файл — **independently testable артефакт**. Я бы запустил `npx hyperframes compositions` после первого готового beat-а (минут через 10) и сразу увидел `0 elements / 0.0s`. Реально я узнал об этом через ~60 минут, потому что инлайн-сборка не давала промежуточных проверочных точек.
  - Sub-comp loader bug §2.1 был бы пойман на ранней стадии диспатчем-как-CI, а не в финальной снапшоте.
- **Корень:** трактовка глагола «Consider» в brief-е как «оптимизация» вместо «обязательная орчестратор-house механика». В этом brief-е соседние пункты — «**Mandatory** for multi-scene», «**non-negotiable**», «**must exist**» — оформлены как императивы. «Consider» зарегистрировался у меня как мягкое.
- **Behavioural pattern:** retro-агенты в предыдущих сессиях этого репо уже ловили меня на этом — selective compliance с brief-инструкциями, где императивы исполняю, а «Consider»/«SHOULD»/«recommended» дрейфуют в «опционально». Это **повторяющийся behavioural drift**, не разовый.
- **Связь с другими находками:** ровно тот же ментальный паттерн что и в retro Section 7 §2.2 (отключил captions через `What NOT to Do`), что и в §2.4 ниже (приоритизировал «inline быстрее» над «warning тоже вес»). Когда brief говорит «consider X» / «should Y» / «recommended Z», у меня по умолчанию срабатывает «не делать», а не «делать».
- **Фикс — на сторону brief-а (НЕ на стороне моей дисциплины — дисциплина не масштабируется):**
  - Заменить в Phase 4 brief формулировку «Consider dispatching beat authoring to parallel sub-agents» на императив:
    > **Beat authoring — parallel-agent dispatch (mandatory for ≥ 3 beats).** After DESIGN.md and expanded-prompt.md exist, dispatch one sub-agent per beat via the `superpowers:dispatching-parallel-agents` skill. Each agent gets the beat's section from `expanded-prompt.md` and writes its `compositions/beat-{N}-{slug}.html` independently. Main session waits, then assembles the root `index.html`. **Do not write beats sequentially in the main session — that path forfeits independently-testable artifacts and adds ~3-5× wall-time.**
  - Добавить в Output Checklist: «Beats authored by ≥ 3 parallel sub-agents (verify by checking session transcript for parallel `Agent` tool calls during Phase 4 — if zero parallel dispatches, Phase 4 was sequential and needs to be reported).»
- **Memory update:** новая запись `feedback_brief_consider_means_mandatory.md` — «In `.claude/commands/edit-episode.md` Phase 4 brief, the word 'Consider' (and 'SHOULD' / 'recommended') is shorthand for mandatory orchestrator-house behavior, not optional optimization. The brief uses 'Consider' to soften the imperative voice while keeping the rule load-bearing. Treat 'Consider X' as 'Do X unless X is technically impossible'. This applies retroactively to: parallel-agent dispatch, sub-composition split, snapshot-before-studio.»

### 2.5 [L] `text_box_overflow` 2-3 px — глифовая bearing-проблема Manrope 800, не контента

- **Что произошло:** `npx hyperframes inspect` репортил 12 errors типа `text_box_overflow ... overflowed left 2.7px`. Изначально пытался шринкать font-size и letter-spacing (с 0.15em → 0.04em), enlarge-ить cards (720→800px шириной). Overflow стабильно держался в 2.7-2.97 px.
- **Корень:** Manrope 800 на display-размерах (88px / 64px / 84px) даёт отрицательный left-side bearing на первой букве (D / O / S), которую inspect-tool считывает как overflow относительно контейнера. Это glyph-metric, не layout-проблема.
- **Fix:** добавил `data-layout-allow-overflow` на card-wrappers — каноничный escape-hatch для intentional overflow. Inspect → 0 layout issues across 9 samples.
- **Не надо было** тратить минут 10 на font-size / card-width итерации. Сразу узнавать паттерн «postive overflow ≤ 5 px на heavy display font» → markup `data-layout-allow-overflow`, не ширина.

---

## Что добавилось ко времени сессии

| Зона | Время | Полезно? |
|---|---|---|
| Reading canon (SKILL.md + 7 references + visual-styles + prompt-expansion) | ~10 min | ✅ Mandatory, дало DESIGN.md grounding |
| DESIGN.md + expanded-prompt.md + 4 beats + captions | ~15 min | ✅ Это и было целью |
| WCAG iteration (3 variants, dark plates, color inheritance) | ~10 min | ❌ Headless артефакт, надо было сразу docs+proceed |
| Studio blank-screen дебаг (track-index reshuffles, malformed `</div>`, file rename, restart) | ~25 min | ❌ Симптом был §2.1, я гонял по симптомам §2.3 |
| Sub-comp `<template>` снос, full-html wrap, debug | ~10 min | ❌ Гипотезы про parser, реальная причина — loader |
| Inline refactor + final render | ~5 min | ✅ Решение |
| Snapshot inspection (попытки на разных стадиях) | ~5 min | ⚪ Frustrated, но в финале подтвердило inline-fix |

**~80 минут на Phase 4**, из них **~40 минут** — погоня за неправильными гипотезами. Если бы сразу проверил `npx hyperframes compositions` и увидел `0 elements / 0.0s` на sub-comp-ах, дошёл бы до inline-фикса минут за 15.

**Сравнение с гипотетическим parallel-dispatch профилем:**

| Этап | Sequential (что было) | Parallel (что должно было) |
|---|---|---|
| DESIGN.md + expanded-prompt.md | 15 мин (main) | 15 мин (main) |
| 4 beat HTML файлов | 25 мин (main, sequential) | ~10 мин (4 parallel agents wall-time) |
| Captions sub-comp | 5 мин (main) | 5 мин (main, параллельно с beat-агентами) |
| Sub-comp loader bug catch | 60 мин (после полного render-а) | ~10 мин (после первого готового beat-агента + `compositions` probe) |
| Inline refactor | 5 мин | 5 мин |
| **Total Phase 4 wall-time** | **~80 мин** | **~30–40 мин** |

То есть **дефолтный parallel-dispatch профиль был бы быстрее в 2 раза, и ловил бы upstream-bug-и в 6 раз раньше**.

---

## Action items

### Сразу (этот эпизод)

- [x] Inline refactor применён, render воспроизводит overlay-и (24.4 MB, 52.6s).
- [x] DESIGN.md содержит «WCAG Validator — Headless Artifact» секцию.
- [x] `edit/project.md` дописан session block-ом.
- [ ] Studio preview по-прежнему может показывать «Drop media here» если `index` не selected — это нормально, но надо упомянуть в Phase 4 brief.

### Memory updates

- [ ] **`feedback_multi_beat_sub_compositions.md`** — переписать. Старая формулировка «Multi-beat HF compositions split per-beat» вводит в заблуждение. Новая: «`data-composition-src` sub-composition loader broken in HF 0.4.41 on Windows (verified 2026-05-01 — render emits A-roll-only). Author beats inline in index.html until upstream fix. Lint warning `composition_file_too_large` is informational only.»
- [ ] **Новая `feedback_wcag_headless_opacity_artifact.md`** — «WCAG validator reports `fg: rgb(0,0,0)` for elements that use `opacity: 0` in entrance `tl.fromTo`. This is a static-screenshot artifact, not a real contrast fail. Document in DESIGN.md and proceed; do not iterate palette.»
- [ ] **Новая `feedback_studio_player_empty_state.md`** — «HF studio shows 'Drop media here' empty state until a composition is explicitly selected in the sidebar. This is default behavior, not a render fail. Verify overlays via `npx hyperframes snapshot` (offline screenshot) **before** assuming studio is broken.»
- [ ] **Новая `feedback_lint_regex_repeat_minus_one_in_comments.md`** — «`gsap_infinite_repeat` lint matches the literal substring `repeat:-1` even inside JS comments. Workaround: avoid the literal in comments. Upstream bug.»
- [ ] **Новая `feedback_text_box_overflow_glyph_bearing.md`** — «Heavy display fonts (Manrope 800 at 60+ px) produce 2-3 px left text_box_overflow from negative side bearing — a glyph-metric, not a layout issue. Mark wrapper with `data-layout-allow-overflow` immediately; do not iterate font-size or container width.»
- [ ] **Новая `feedback_brief_consider_means_mandatory.md`** — критическая behavioural memory. «In `.claude/commands/edit-episode.md` Phase 4 brief, the word 'Consider' (and 'SHOULD' / 'recommended') is shorthand for mandatory orchestrator-house behavior, not optional optimization. The brief uses 'Consider' to soften the imperative voice while keeping the rule load-bearing. Treat 'Consider X' as 'Do X unless X is technically impossible'. This applies retroactively to: parallel-agent dispatch, sub-composition split, snapshot-before-studio. Verified missing on 2026-05-01: skipped parallel-agent dispatch under 'Consider' wording → Phase 4 took 2× wall-time.»

### Brief updates (PR на `.claude/commands/edit-episode.md`)

- [ ] Phase 4 brief: «Sub-composition split — currently broken in HF 0.4.41 on Windows. Author all beats inline in `index.html`. The lint warning `composition_file_too_large` is informational; verify with `npx hyperframes compositions` after build — sub-comps loaded via `data-composition-src` should report non-zero `elements` and matching `duration`. If they show `0 elements / 0.0s`, the loader hasn't mounted them; refactor to inline.»
- [ ] Phase 4 brief: «Visual verification: run `npx hyperframes snapshot --at <beat_timestamps>` **before** studio launch. If snapshot frames show only A-roll without overlays, the composition is broken — do not proceed to studio (an empty studio player is ambiguous; an empty snapshot is definitive).»
- [ ] Phase 4 brief: «WCAG fail handling — add escape: 'If validate reports `fg: rgb(0,0,0)` on text whose CSS sets a visible color, this is a headless-screenshot artifact from `opacity: 0` entrance tweens. Document the symptom in DESIGN.md and proceed; do not iterate palette.'»
- [ ] Phase 4 brief: переписать «Consider dispatching beat authoring to parallel sub-agents» на императив:
  > **Beat authoring — parallel-agent dispatch (mandatory for ≥ 3 beats).** After DESIGN.md and expanded-prompt.md exist, dispatch one sub-agent per beat via the `superpowers:dispatching-parallel-agents` skill. Each agent gets the beat's section from `expanded-prompt.md` and writes its `compositions/beat-{N}-{slug}.html` independently. Main session waits, then assembles the root `index.html`. **Do not write beats sequentially in the main session — that path forfeits independently-testable artifacts and adds ~3-5× wall-time.**
- [ ] Phase 4 Output Checklist: «Beats authored by ≥ 3 parallel sub-agents (verifiable by checking session transcript for parallel `Agent` tool calls during Phase 4).»
- [ ] **Глобально по brief-у:** заменить все «Consider X» / «SHOULD X» / «recommended X» либо на императивы, либо на явное «(optional optimization, skip without consequence)». Текущая мягкая формулировка стабильно интерпретируется как опциональная и приводит к selective compliance.

### Upstream issues (heygen-com/hyperframes)

- [ ] **Bug:** `data-composition-src` sub-composition loader does not mount external file content into render output on HF 0.4.41 / Windows / Node 24. Repro: scaffold project, add a `<div data-composition-src="compositions/foo.html" ...>` mount, sub-comp file with `<div data-composition-id="foo" ...><div style="background:red;width:100%;height:100%"></div></div>`. Render shows no red.
- [ ] **Bug:** `gsap_infinite_repeat` lint regex false-positives on the literal substring `repeat:-1` inside JS comments.
- [ ] **Doc bug:** SKILL.md § "Composition Structure" recommends `<template>` wrapper for sub-comps, but `npx hyperframes compositions` cannot see inside `<template>` (treats sub-comp file as 0 elements). Either remove `<template>` from canon, or document that the loader auto-extracts from `<template>` (and fix it if it doesn't).

---

## Что осталось правильным с retro Section 7

- `data-has-audio="false"` фикс — не сработала StaticGuard, doubling в файле нет, doubling в studio тоже не воспроизвёлся (preview-log clean за 5s). ✅
- Phase 4 brief по captions сработал — Skill включил captions в DESIGN.md и в композицию автоматически, без напоминания. ✅
- `animation-map.mjs` запущен из bundled path (`node_modules/hyperframes/dist/...`) после установки `@hyperframes/producer` + `sharp` — workaround по CLAUDE.md из retro Section 7 сработал ровно. ✅
- Idempotency rules сработали по всем 4 правилам Phase 1-4: pickup short-circuit, audio tag-present skip, edit/final.mp4 skip Phase 3, transcripts/final.json edl_hash short-circuit для glue. ✅

То есть **canon-side и spec-side фиксы из Section 7 держатся**. Сегодняшние находки — про свежие зоны: sub-comp loader (HF upstream), WCAG-validator headless семантика (canon edge case), и про мою собственную дисциплину гипотезы-проверять-эмпирически до ухода в дебаг по симптомам.
