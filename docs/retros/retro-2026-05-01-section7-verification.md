# Retro: `/edit-episode` Section 7 verification + Liquid Glass прогон

Дата: 2026-05-01. Эпизод: `2026-04-30-desktop-software-licensing-it-turns-out-is` (1080×1920, 53.245s после re-cut). Этот заход — Section 7-верификация фиксов из spec `2026-04-30-edit-episode-second-retro-fixes-design.md` (PR #6, #7, #8 уже мержены) плюс полная пересборка Phase 3 + Phase 4 c намерением закрыть три гипотезы и выкатить готовую композицию.

Часть гипотез подтверждена, одна — переоткрыта на новом канале, и сверху всплыли свежие косяки в моей собственной интерпретации Phase 4 brief.

---

## Section 7 hypothesis check

| # | Retro | Гипотеза | Результат |
|---|---|---|---|
| a | 1.4 | scaffold пишет `class="clip"` на `<video>` и `<audio>` → phantom doubling в `final.mp4`-уровне исчез | ✅ Фикс на месте, doubling в самом файле не воспроизводится |
| b | 3.3 | StaticGuard-варнинг про `data-has-audio` исчезнет | ❌ Варнинг живой, причина (см. §2.1 ниже) — не наша, но симптом ЕСТЬ и он продолжает производить **новый** audio-doubling в studio preview |
| c | — | `animation-map.mjs` запускается из bundled path (`node_modules/hyperframes/dist/...`), eager-eval bag `~/.agents/...`-копии обходится | ✅ Запустился, JSON выписан, 0 flags |

Идемпотентность ресета (удалить `final.mp4` + `master.srt` + `hyperframes/`) сработала ровно как в спеке: Phase 1 short-circuit-нул на `transcripts/raw.json`, Phase 2 — на `ANTICODEGUY_AUDIO_CLEANED` теге контейнера. Ни одного credit-а не сожжено.

---

## Главные находки (этот прогон)

### 2.1 [H] Audio doubling вернулся — теперь в studio preview, не в файле

- **Что произошло:** `final.mp4` на диске чистый (mean -14.9 dB / max -0.8 dB / -15.2 LUFS — в пределах −14 LUFS / −1 dBTP таргета). При проигрывании в студии (`localhost:3002`) звук ощутимо перегружен по амплитуде. Пользователь это сразу услышал.
- **Корень (нашёл в `node_modules/@hyperframes/core/dist/`):**
  1. `compiler/timingCompiler.js:60`:
     ```js
     if (isVideo && !hasAttr(result, "data-has-audio")) {
       result = injectAttr(result, "data-has-audio", "true");
     }
     ```
     Компилятор HF **авто-инжектит `data-has-audio="true"` на каждый `<video>` без явного атрибута**.
  2. `engine/dist/services/audioMixer.js:41`:
     ```js
     const videoEls = document.querySelectorAll('video[id][src][data-has-audio="true"]');
     ```
     Studio audioMixer берёт ВСЕ `<video data-has-audio="true">` в mix — **игнорируя HTML-атрибут `muted`**.
  3. Параллельно `<audio src="final.mp4">` тоже идёт в mix.
  4. Итог: один и тот же стрим `final.mp4` суммируется дважды → +6 dB → перегрузка лимитера в студии. На файловом рендере audioMixer не используется → файл чистый.
- **Связь с retro 1.4 / 3.3:** retro 1.4 фиксил `class="clip"` (это убрало doubling в файле — подтверждено). Retro 3.3 списал StaticGuard-варнинг как пустой шум. Это была ошибка диагностики: варнинг — **симптом этого второго канала doubling-а**, который проявляется только при работающей студии.
- **Фикс (НЕ применён в этом прогоне — пользователь остановил):** в `scripts/scaffold_hyperframes.py` шаблон `VIDEO_AUDIO_PAIR_TEMPLATE` добавить `data-has-audio="false"` на `<video>` элемент. Компилятор инжектит **только если атрибут отсутствует** — явное `false` блокирует injection, audioMixer перестаёт видеть видео как источник аудио, doubling уходит, StaticGuard замолкает (документировано в его собственном fixHint, line 102720).
- **Дополнительно к фиксу:** прописать в `.claude/commands/edit-episode.md` Phase 4 brief валидационный шаг — после launch студии листенер preview-логов; если в первые 5s после запуска видим `[StaticGuard]` warning — fail-fast и stop, не отдавать пользователю.

### 2.2 [H] Я самостоятельно отключил captions, проигнорировав требование brief-а

- **Что произошло:** Phase 4 brief в `.claude/commands/edit-episode.md` явно говорит «Captions are produced downstream by Phase 4 (HyperFrames `references/captions.md`)». Я в `DESIGN.md` написал в раздел «What NOT to Do» строку *«Captions are NOT used — overlays already telegraph the beat; per-word karaoke would compete with the chip language»* и собрал композицию без captions track-а. Пользователь это сразу заметил и спросил «нет captions, почему».
- **Корень:** Phase 4 brief не оформлен как **non-negotiable** для captions. У меня в Skill-исполнении выработалась логика «DESIGN.md — это место где можно опт-аут любой каноничной механики», и captions попали в эту категорию вместе с шейдер-переходами или audio-reactive — то есть в категорию «опционально».
- **Фикс — на сторону brief-а:**
  - В Phase 4 brief переформулировать строку про captions с **«Captions are produced downstream»** (констативно) на **«Captions track is mandatory. Use `hyperframes/transcript.json` per `references/captions.md`. Caption styling adapts to the chosen visual identity. The only acceptable reason to omit captions is an explicit user request — never a Skill-author decision documented in `DESIGN.md`.»**
  - Добавить отдельный пункт в Output Checklist: «captions track present in `index.html` referencing `transcript.json`».
- **Дополнительно — feedback memory:** «captions всегда mandatory; нельзя отключить через DESIGN.md → What NOT to Do; единственный валидный опт-аут — явная просьба пользователя».

### 2.3 [H] Композиция написана inline (381 строка) вместо sub-compositions per beat

- **Что произошло:** Я собрал все 6 beat-ов прямо в `index.html` вместо того, чтобы разбить на `compositions/beat-{1..6}.html` через `data-composition-src`. `npx hyperframes lint` это поймал:
  > `composition_file_too_large: This HTML composition file has 381 lines. Agents produce better results when large scenes are split into smaller sub-compositions. Fix: Split coherent scenes or layers into separate .html files under compositions/`
  Я отрапортовал «лint passes (size warning only — informational)» и поехал дальше.
- **Корень:**
  1. HF lint выдаёт это как **warning**, а не **error** — формально не блокирует. Но HF SKILL.md прямо рекомендует разбиение, а сам warning сформулирован *«Agents produce better results when ...»* — это явно про работу с агентами.
  2. Phase 4 brief не указывает per-beat дробление и не говорит про parallel-agent-dispatch для авторизации beat-ов.
  3. `superpowers:dispatching-parallel-agents` — идеальный инструмент для этого случая (6 beat-ов независимы, нет shared state) — я его не задействовал.
- **Фикс — на brief:**
  - В Phase 4 brief заменить общую формулировку *«Multi-scene narrative composition (mandatory)»* на конкретную: каждый beat ≥3 живёт **отдельным файлом** в `compositions/beat-{N}-{slug}.html`, монтируется через `<div data-composition-id data-composition-src="compositions/beat-N.html">`. Root `index.html` ≤ 100 строк (video + audio + captions + mount-точки).
  - Добавить: «consider dispatching beat authoring to parallel sub-agents via the `dispatching-parallel-agents` superpower — beats are independent and parallelizable».
- **Дополнительно — feedback memory:** «multi-beat composition должна быть разбита на per-beat sub-compositions в `compositions/`; root index.html — только mount-точки + media; inline-вариант недопустим даже если lint пропускает с warning-ом».

### 2.4 [M] `loudnorm` идемпотентен, но canonical target -14 LUFS на чистом ElevenLabs source-е тесно по headroom-у

- **Что было исследовано (по вопросу пользователя «не нормализовали ли уже нормализованную дорожку»):**
  | Этап | Integrated | True Peak |
  |---|---|---|
  | `raw.mp4` (после Phase 2 ElevenLabs) | −27.9 LUFS | −6.0 dBTP |
  | `audio/raw.cleaned.wav` (Phase 2 кеш) | −27.9 LUFS | −6.0 dBTP |
  | `edit/clips_graded/seg_*_raw.mp4` (после нарезки) | −28.3 LUFS | −6.0 dBTP |
  | `edit/final.mp4` (после concat) | −15.2 LUFS | −0.8 dBTP |
  ElevenLabs Audio Isolation **не нормализует громкость** — оставляет исходный динамический диапазон. Per-clip нарезка идёт `stream-copy`, без re-encode аудио. Loudnorm применяется **ровно один раз** — на финальном concat-проходе. Идемпотентность чистая.
- **Что заметно:** −0.8 dBTP — это в 0.2 dB от 0 dBTP. На голосовом source-е с ярко выраженными согласными (как у этого диктора) +13.7 LU подъём через лимитер близко прижимает каждый пиковый слог. Если бы файл проигрывался без double-mixing студии — это было бы acceptable. На файле как есть пользователь не услышал перегруза, услышал только в студии (см. §2.1). Так что **здесь нет действия** — только зафиксировать, что у этой комбинации (canonical −14 LUFS таргет + ElevenLabs-cleaned source) headroom предельно тонкий, и на материале с более выраженными транзиентами (хлопки, плосивы) можно получить slight intersample-clip без явного двойного микса.
- **Опционально на будущее:** в `video-use` Phase 3 brief можно добавить флаг для `--loudnorm-target -16` если source уже cleaned (по тегу `ANTICODEGUY_AUDIO_CLEANED`). Не блокер, не приоритет, но красивый штрих.

### 2.5 [M] `npx hyperframes snapshot` дефолтит viewport 1920×1080, режет нижнюю половину portrait-композиции

- **Что произошло:** запустил snapshot на 7 beat-таймштампах, получил 7 png — все 1920×1080 landscape. Композиция 1080×1920 portrait → body отрисовалось в верхнем-левом углу, нижние 840px (где сидят все нижние glass-панели Beats 1–5) — **за пределами captured viewport-а**. Только Beat 6 b6-card видна потому что она по центру (`top: 50%`), что попало в верхние 1080px.
- **Корень:** `--width`/`--height` флагов нет. Snapshot не смотрит на `data-width`/`data-height` композиции — захват рендерится в дефолтном 1920×1080.
- **Workaround:** для верификации portrait-композиции лучше доверять `npx hyperframes inspect --at <timestamps>` (он 0 layout issues отдал на 7 таймштампах) и в студии. Snapshot на portrait — частично слепой.
- **Upstream issue:** обоснованный feature request к HF CLI. Сформулировать как «`snapshot` should auto-detect canvas dimensions from root `data-width`/`data-height`, or accept `--width`/`--height` flags for explicit override».

### 2.6 [M] `validate` и `contrast-report.mjs` сообщают `null:1` контраст для out-of-clip элементов

- **Что произошло:** `npx hyperframes validate` отдал 74 contrast warnings, `contrast-report.mjs` — 33 NaN entries. Звучит как «куча провалов AAA», на деле — **все 23 visible-element samples (validate) и 12 visible (contrast-report) проходят AA, большинство AAA с ratio 7–13:1**. NaN/null приходят на элементах, чьи clip-окна неактивны на момент сэмплирования — getComputedStyle возвращает невалидные цвета, и оба тула считают это failure.
- **Корень:** оба сэмплера итерируют **все** text-элементы по фикс-таймштампам, не сверяясь с активной clip-панелью.
- **Workaround в этом прогоне:** отделил false-positive (`null`/`NaN` ratio) от real-fail вручную в `validate-out.json` / `contrast-report.json`, отдельной колонкой в Session 3 блоке `project.md`.
- **Upstream issue:** обоснованно к HF — оба тула должны фильтровать text-элементы по `clip` activity на момент сэмпла. Иначе non-overlapping multi-clip композиции всегда будут шуметь.

### 2.7 [L] Bundled `animation-map.mjs` / `contrast-report.mjs` бутстрап ломается на Windows

- **Что произошло:** bundled-path запуск (по правилу из CLAUDE.md «Skill copies: docs vs. runnable») сначала просит missing peer dep:
  ```
  Error: Required helper package(s) are missing.
  To allow a one-time temporary dependency bootstrap for this run, set:
    HYPERFRAMES_SKILL_BOOTSTRAP_DEPS=1
  ```
  Установка флага → новая ошибка:
  ```
  Error: spawnSync npm.cmd EINVAL
  ```
  Это known Node.js Windows issue с `child_process.spawnSync` на `.cmd` shim-ах.
- **Workaround в этом прогоне:** `npm i -D @hyperframes/producer@0.4.41 sharp@0.34.5` в hyperframes-проекте — оба тула после этого работают.
- **Действие — в наш CLAUDE.md:** дополнить блок «Skill copies: docs vs. runnable» абзацем:
  > **Известный Windows-блокер:** оба `animation-map.mjs` и `contrast-report.mjs` пытаются bootstrap-нуть `@hyperframes/producer` (и `sharp` для contrast-report) через `npm.cmd` spawnSync, что на Windows-Node даёт `EINVAL`. Workaround: один раз `npm i -D @hyperframes/producer@<exact-version> sharp@<exact-version>` в `hyperframes/`-проекте. Версии берутся из ошибки скрипта.
- Опционально: `scripts/scaffold_hyperframes.py` мог бы проактивно ставить эти пакеты в `package.json` `devDependencies` при scaffold-инге — но это упирается в version-pinning и зависит от установленной версии `hyperframes` как root deps. Не приоритет.

### 2.8 [L] CLAUDE.md правило «bundled path для helper-скриптов» подтвердилось рабочим

- **Что было:** retro прошлого захода (PR #7) добавил «Skill copies: docs vs. runnable» в CLAUDE.md по результатам eager-eval bag в `package-loader.mjs` при запуске из `~/.agents/skills/...`.
- **В этом прогоне:** запустил оба helper-script-а строго из `node_modules/hyperframes/dist/skills/hyperframes/scripts/`, eager-eval bag не воспроизвёлся — version probe и sibling-package resolution отработали через manifest-предка. Правило **рабочее**.
- Действий не требуется. Запись здесь — позитивный signal: правило в CLAUDE.md ловит то, что должно ловить.

### 2.9 [L] `scripts/remap_transcript.py` не очищает `final.json` при re-cut → возможна рассинхронизация

- **Что произошло:** при ресете оставил `transcripts/final.json` от первого Session-1 захода. Phase 3 пересоздал `edl.json` (другие диапазоны) → `final.json` **уже был stale** (мапил старый EDL). Я заметил вручную и удалил перед `remap_transcript`. Текущая Phase 3 / glue логика этого не делает.
- **Корень:** в `.claude/commands/edit-episode.md` rebuild guidance: *«Re-cut: delete `<EPISODE_DIR>/edit/final.mp4` AND `<EPISODE_DIR>/hyperframes/`. `transcripts/raw.json` stays — no Scribe re-spend.»* — про `final.json` ни слова. Glue step *«Skip if `final.json` already exists — idempotent»* при re-cut делает наоборот **анти-идемпотентность** — переиспользует устаревший maps.
- **Фикс:** в rebuild guidance + glue brief добавить «`transcripts/final.json` MUST be deleted on Phase 3 re-cut. It's a derived output of `edl.json`; if EDL changes, `final.json` is invalidated.» Опционально — `scripts/remap_transcript.py` может сравнивать mtime / hash `edl.json` с записанным в `final.json` метаданным и регенерировать при mismatch автоматически.

---

## 3. Сравнение с clean-session HF executor (`init/5509a8c6-afa4-4a62-96c1-6585d1dd3404.jsonl`)

Сравнение текущего прогона с прошлой сессией, где пользователь работал с HyperFrames «как есть» (без оркестратора, без `/edit-episode`, ручной `npx hyperframes init` + сам Skill executor). Composition в clean session — 6 beat-ов (HOOK / MY_CASE / HOW / CAVEAT / ALTERNATIVE / CTA), 355 строк, multi-scene с переходами и captions. Не single-scene, как я ошибочно классифицировал в первой версии этого ретро.

Это сравнение проявляет **canon-decay-ы, общие для обеих сессий** (т.е. в нашем оркестраторе они системны, не одноразовые), и **отдельно — где наш прогон хуже clean-session-а**.

### 3.1 [H] SKILL.md «Video and Audio» пример производит audio doubling в студии

- **Канон в SKILL.md** (раздел *Video and Audio*):
  ```html
  <video id="el-v" data-start="0" data-track-index="0" src="video.mp4" muted playsinline></video>
  <audio id="el-a" data-start="0" data-track-index="2" src="video.mp4" data-volume="1"></audio>
  ```
- **Наш scaffold (`scripts/scaffold_hyperframes.py:VIDEO_AUDIO_PAIR_TEMPLATE`)** — буквально воспроизводит этот пример. И ловит double-mixing (см. §2.1).
- **Clean session отказался от двух-элементной модели:**
  ```html
  <video id="bg" class="clip" data-volume="1" src="media/source.mp4" muted playsinline ...></video>
  ```
  Один элемент. Аудио идёт через auto-injected `data-has-audio="true"`. Doubling-а нет, потому что нет двух источников. По букве SKILL.md это «нарушение» (канон требует separate `<audio>`), но по факту — единственный паттерн без doubling-а.
- **Вывод:** SKILL.md-пример **либо buggy, либо требует не-документированного `data-has-audio="false"` opt-out на video**. Clean-session executor (с большей дисциплиной к канону, чем у меня) тихо обошёл проблему отказом от паттерна. Наш scaffold честно следует букве и поэтому ломается.
- **Связь с §2.1:** наш фикс-кандидат (`data-has-audio="false"`) лечит каноничную двух-элементную модель. Альтернатива — переписать scaffold на одно-элементную (как clean session). Второй путь не требует workaround-флага, но отклоняется от текста SKILL.md.

### 3.2 [H] «Always read» reference-файлы из SKILL.md проигнорированы — и в clean-session, и у нас

SKILL.md помечает 5 файлов как mandatory:

| Файл | Тег | Clean session | Наша сессия |
|---|---|---|---|
| `references/video-composition.md` | **Always read** | ❌ | ❌ |
| `references/typography.md` | **Always read** | ❌ | ❌ |
| `references/motion-principles.md` | **Always read** | ❌ | ❌ |
| `references/beat-direction.md` | **Always read for multi-scene** | ❌ (multi-scene!) | ❌ (multi-scene!) |
| `references/transitions.md` | **Always read for multi-scene** | ❌ (multi-scene!) | ❌ (multi-scene!) |

Обе сессии — multi-scene; обе пропустили все 5 канон-документов. Это **системный canon-decay**, не личная небрежность.

- **Корень:** Phase 4 brief в `.claude/commands/edit-episode.md` декларирует «multi-scene composition (mandatory)», но **не enforce-ит чтение конкретных канон-документов**. Skill executor сам решает, что читать; экономия контекста выигрывает.
- **Фикс — на Phase 4 brief:** добавить блок «Required reading before composing — verbatim list»:
  > Before writing any composition HTML, read in this order:
  > 1. `~/.agents/skills/hyperframes/SKILL.md` (you're here)
  > 2. `~/.agents/skills/hyperframes/references/video-composition.md` — Always read
  > 3. `~/.agents/skills/hyperframes/references/typography.md` — Always read
  > 4. `~/.agents/skills/hyperframes/references/motion-principles.md` — Always read
  > 5. `~/.agents/skills/hyperframes/references/beat-direction.md` — multi-scene mandatory
  > 6. `~/.agents/skills/hyperframes/references/transitions.md` — multi-scene mandatory
  > 7. `~/.agents/skills/hyperframes/references/captions.md` — captions are mandatory in this orchestrator
  > 8. `~/.agents/skills/hyperframes/references/transcript-guide.md` — to understand transcript schema before captions
  > Skill agent must confirm in its first response which files were read. Empty confirmation = stop, do not proceed to composition.

### 3.3 [H] Step 2 «Prompt expansion» пропущен — и там, и тут

SKILL.md явно: *«Always run on every composition (except single-scene pieces and trivial edits). This step grounds the user's intent against `design.md` and `house-style.md` and produces a consistent intermediate that every downstream agent reads the same way.»*

- Документ — `references/prompt-expansion.md`. Ни одна из сессий его не открыла.
- Наша задача однозначно multi-scene narrative — Step 2 был обязателен. Я как Skill executor шагнул сразу с Step 1 (Visual Identity Gate) на Step 3 (Plan), пропустив grounding промежуточник.
- **Фикс:** в Phase 4 brief после блока «Required reading» добавить: *«Run Step 2 prompt expansion per `references/prompt-expansion.md`. Output goes to `<hyperframes-dir>/PROMPT.md`. Mandatory for multi-scene compositions per SKILL.md.»* Output должен быть осязаемым артефактом, чтобы шаг был верифицируем.

### 3.4 [H] `npx hyperframes catalog` / `hyperframes add` — не задействованы в обеих сессиях

- Phase 4 brief в `.claude/commands/edit-episode.md` дословно: *«run `npx hyperframes catalog` to browse before authoring custom HTML; install via `npx hyperframes add <name>`»*.
- Я не запустил `catalog`, не установил ни одного registry-блока — все 6 beat-ов вручную написал как glass HTML.
- Clean session — то же самое: catalog не запускался, всё custom.
- **Корень:** brief формулирует требование («browse before authoring»), но не enforce-ит. Нет ни sentinel-файла, ни требуемого артефакта (`hyperframes.json`-список installed blocks), ни блокирующей проверки.
- **Фикс:** в Phase 4 brief: *«Before writing custom HTML for any beat, run `npx hyperframes catalog --json > .hyperframes/catalog.json`. For each of your ≥3 narrative beats, write one sentence: which catalog block (or none) you considered, and why custom HTML is justified. This list goes in `DESIGN.md` → `Beat→Visual Mapping` next to each row. No catalog scan = stop.»*

### 3.5 [H] Captions — clean session реализовал, у нас отсутствуют (расширение §2.2)

Clean session (после нашей упомянутой переписки про `build_captions.py`) применил canonical caption-паттерн из `references/captions.md`:

- DOM-built из `transcripts/raw.json`, EDL-mapped per-word на final timeline (наш `scripts/remap_transcript.py` делает то же самое — у нас `transcript.json` уже готов в нужной schema)
- **Glass-pill swap** — один caption активен в момент времени, hard-kill через `tl.to(sel, { opacity:0 }, g.end - exitDur)`
- **Runtime self-lint в JS:**
  ```js
  console.warn("[caption-lint] cap-" + i + " still visible at " + (g.end + 0.01).toFixed(2));
  ```
  Defensive guard на canon §"Caption exit guarantees" — если group остаётся видимой после `data-end`, лог сразу скажет.

У нас captions нет вообще. Это уже §2.2; здесь — конкретный референс-паттерн, **которому я мог бы следовать дословно** при наличии всего нужного в hyperframes-проекте.

### 3.6 [M] Vignette-слои для легибильности — best-practice clean-session-а, мы упустили

Clean session добавляет два semi-transparent градиента поверх видео:
```css
.vignette-top    { top:0;    height:720px;
   background: linear-gradient(to bottom, rgba(0,0,0,0.55), rgba(0,0,0,0)); }
.vignette-bottom { bottom:0; height:640px;
   background: linear-gradient(to top, rgba(0,0,0,0.55), rgba(0,0,0,0)); }
```

Это canonical паттерн для легибильности captions/overlays на talking-head: vignette затемняет края, glass-fill можно делать лёгким (clean session: `rgba(255,255,255,0.18)` — почти прозрачно) и сохранять «дыхание» видео.

У нас vignette-ев нет. Чтобы вытянуть контраст панелей, мы накрутили scrim тяжелее (`rgba(8,12,20,0.55)`) — итог: панели выглядят темнее и тусклее, забивают видео. Это **компенсация отсутствия canonical-паттерна, не самостоятельное стилевое решение**.

- **Действие:** не enforce-ить через brief (это уже эстетическая микро-оптимизация), но добавить в `~/.agents/skills/hyperframes/references/video-composition.md`-чтение в Phase 4 — vignette-паттерн там описан.

### 3.7 [M] Inline монолит — общая беда; «Scene Transitions» канон clean-session нарушал явно, мы — формально соблюдали

- Clean session: 355 строк inline, ровно та же проблема, что у нас (§2.3). Lint warning тот же — игнорировался.
- Clean session **нарушил «Scene Transitions» канон**: в timeline есть `tl.to(sel, { opacity: 0, y: -20, scale: 0.96 }, exitAt)` для **каждого** beat-а, не только финального. SKILL.md §"Scene Transitions" однозначно: *«NEVER use exit animations except on the final scene. The transition IS the exit.»* Clean session применил exit-анимации на промежуточных beat-ах.
- Мы наоборот **технически соблюли** Scene Transitions (entrance-only на промежуточных, fade-out только на Beat 6) — но за счёт того, что переходы у нас по сути отсутствуют как отдельный механизм; полагались на «next beat covers via entrance». В clean session переходы видимые, потому и exit-анимации добавлены.
- **Что это значит:** Scene Transitions canon в нынешней формулировке предполагает **shader/wipe transitions** (CSS clip-path / WebGL), которые «съедают» предыдущую сцену. Без них entrance-only-cover работает только если новая сцена полностью непрозрачно перекрывает старую — что для translucent-glass панелей **не выполняется**.
- **Фикс — на Phase 4 brief:** добавить *«If your beats use translucent overlays (e.g., glass panels), you MUST install a shader transition between scenes (`npx hyperframes add transition-shader-<name>`). Translucent + entrance-only-cover does NOT visually clear the previous scene. Either install a transition OR violate Scene Transitions canon explicitly with a documented justification in `DESIGN.md`.»*

### 3.8 [M] HF CLI команды — мы используем больше, чем clean-session

(Здесь баланс в нашу пользу, но контекстно.)

| Команда | Clean session | Наша сессия |
|---|---|---|
| `lint` | ✅ | ✅ |
| `validate` | ✅ | ✅ |
| `inspect` | ❌ | ✅ |
| `snapshot` | ❌ | ✅ (с portrait-quirk-ом — §2.5) |
| `animation-map.mjs` | ❌ | ✅ (после Windows-bootstrap-фикса — §2.7) |
| `contrast-report.mjs` | ❌ | ✅ |
| `preview` | ✅ | ✅ |
| `studio` | ✅ (использовал) | ❌ (не пробовал) |
| `transcribe` | упоминали, не запускали | не запускали (у нас Scribe из video-use) |
| `catalog` | ❌ | ❌ (см. §3.4) |
| `add` | ❌ | ❌ |

Наш Phase 4 brief **enforce-ит больше QA-инструментов**, чем дисциплина чистого Skill executor-а. Это победа orchestrator-подхода — ровно то место, где orchestrator оправдан как обёртка.

### 3.9 [L] Размещение медиа

- Clean session: `media/source.mp4` (копия в подпапке).
- Наш orchestrator: `final.mp4` hardlink в корне `hyperframes/`.
- HF SKILL.md: *«All files live at the project root alongside `index.html`»*.
- Наш вариант формально каноничнее. Действий не требуется. Записано для полноты.

---

## Что можно унести как durable feedback (для memory)

Записи, которые проявляются и в этом, и в clean-session-сравнении как системные паттерны, а не одиночные косяки:

1. **DESIGN.md → "What NOT to Do" не должна отключать canonical mechanics** (captions, transitions, contrast audit). Если что-то прописано как mandatory в Phase brief или HF SKILL.md — это не предмет для Skill-уровневого опт-аут-а.
2. **Multi-beat HF композиция = sub-compositions per beat в `compositions/`**, никогда не inline в root `index.html`. Lint warning «file too large» — это **gate**, не информация.
3. **При запуске любого CLI-инструмента из external skill-а — bundled path (`node_modules/<skill>/dist/...`), не `~/.agents/...`**. Подтверждено вторым прогоном; правило в CLAUDE.md работает.
4. **HF SKILL.md «Always read» — это не рекомендация, а контракт**. Skipping видеo-composition.md / typography.md / motion-principles.md / beat-direction.md / transitions.md ведёт к композиции, которая выглядит «как HTML с overlay-ями», а не как видео. Phase 4 brief должен enforce-ить чтение через verbatim список + first-response confirmation.
5. **Step 2 prompt expansion обязателен для multi-scene** — без grounding-промежуточника каждая сцена авторизуется отдельно от script-нарратива и от design.md. Output должен быть осязаемым артефактом (`PROMPT.md`) для верифицируемости.
6. **`npx hyperframes catalog` — gate перед custom HTML, не «опция для интересующихся»**. Per-beat justification «catalog block X considered, custom because Y» должна жить в `DESIGN.md`. Без этого списка skill executor дефолтит на «всё custom».
7. **Translucent overlay (glass / frost) + Scene Transitions canon = требует shader-transition**. Entrance-only-cover работает только при непрозрачной перекрывающей сцене. Glass-композиции без shader-перехода либо нарушают канон, либо имеют видимое смешение сцен — выбрать одно явно.
8. **Канонический пример SKILL.md «Video and Audio» (двух-элементный `<video> + <audio>`) триггерит studio audio doubling** через auto-injection `data-has-audio="true"` в timingCompiler. Workaround — явное `data-has-audio="false"` на `<video>` ИЛИ одно-элементная модель (как в clean-session). Это upstream-баг канонического примера, не ошибка scaffold-а.

---

## Приоритизация фиксов

**Верхний эшелон — блокирует доставку pipeline-а пользователю:**

- §2.1 / §3.1 — `data-has-audio="false"` в scaffold template (или переписать на одно-элементный паттерн). **Критично** — без этого студия искажает звук на каждой композиции.
- §2.2 / §3.5 — captions mandatory в Phase 4 brief, с явным указанием `references/captions.md` как mandatory чтения. **Критично** — отсутствие = регресс относительно clean-session-baseline-а.
- §3.2 — Phase 4 brief: verbatim список mandatory чтения 5 «Always read» документов + `captions.md` + `transcript-guide.md`. **Критично** — это корень всех canon-decay-ев в композиции; без этого блока всё остальное лечит симптомы.
- §3.3 — Phase 4 brief: enforce Step 2 prompt expansion с осязаемым output-артефактом (`PROMPT.md`). **Важно** — gateway к качеству композиции.
- §3.4 — Phase 4 brief: enforce `npx hyperframes catalog --json` + per-beat justification в `DESIGN.md`. **Важно** — лечит «всё пишу custom HTML»-привычку.
- §2.3 / §3.7 — sub-compositions per beat + parallel-agent dispatch + явное правило про shader-transitions для translucent-overlay. **Важно** — архитектурный долг lint уже орёт; до фикса использовать shader-переходы или явно нарушать Scene Transitions canon с обоснованием.

**Средний эшелон — улучшает UX и устойчивость, не блокирует:**

- §2.5, §2.6 — upstream issues к HF CLI/core (snapshot landscape default, validate/contrast-report null-false-positives на out-of-clip элементах).
- §3.6 — vignette-слои для легибильности — best-practice, попадёт в композицию автоматически если §3.2 enforce-ит чтение `video-composition.md`.
- §2.9 — `final.json` на re-cut → удалять явно.
- §2.7 — заметка про Windows bootstrap в CLAUDE.md.

**Нижний эшелон — observability:**

- §2.4 — заметка про `−14 LUFS` headroom на cleaned source.
- §3.8 — наш QA-instrumentation богаче clean-session-а; это win, не fix.
- §3.9 — размещение медиа (canonически корректно, действий не требуется).

---

## Финальное состояние артефактов на момент этого ретро

- `episodes/2026-04-30-desktop-software-licensing-it-turns-out-is/edit/final.mp4` — корректный re-cut (53.245s, 23.9% reduction, audio чистый на файловом уровне).
- `episodes/.../hyperframes/index.html` — собран, lint passing (с size warning), validate clean (с null-false-positives), inspect 0 issues. **Composition в текущем виде НЕ production-ready** — нет captions (§2.2) и в студии phantom audio doubling (§2.1).
- Студия `localhost:3002` — остановлена пользователем по ходу разбора §2.1.
- Никаких git-веток / PR-ов от этого захода не осталось — `fix/studio-audio-doubling` worktree удалён по просьбе пользователя до коммита.
