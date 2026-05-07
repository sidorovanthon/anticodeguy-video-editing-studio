# Context-continuity improvements — design

> ⚠️ **SUPERSEDED 2026-05-07** by
> [`2026-05-07-resolved-brief-profiles-brand-architecture.md`](2026-05-07-resolved-brief-profiles-brand-architecture.md).
> Этот документ оставлен в git как контекст-якорь рассуждений
> (6 потоков, per-node anchor list, sprint sequencing) — но **финальный
> source of truth для работы — преемник**. Тактические идеи отсюда
> (Converse, schema loosening, neighbors_summary, content-review,
> brand-canon эпик) переехали в преемник в обобщённой форме
> (профильный слой, brief.resolved.yaml, music library).

**Дата:** 2026-05-07
**Статус:** Superseded
**Original status:** draft (готовится PR с этой спекой как первый шаг работы)
**Контекст-якорь:** ретро `docs/retros/retro-2026-05-07-hom-154-clean-e2e-attempt.md`, цикл вопросов от пользователя 2026-05-07 «почему декомпозиция работает хуже, чем монолитный вызов скилла».

## 0. Краткая суть

LangGraph-оркестратор, декомпозирующий канонические workflow `video-use` (Phase 3) и `hyperframes` (Phase 4) на атомарные LLM-ноды, эмпирически даёт результаты заметно хуже, чем одна сессия чистого скилла на тех же исходниках. HOM-154 E2E-прогон оставил в финале явный смысловой дубль фразы, который в чистой `video-use`-сессии вырезается с первого захода.

**Корневая причина:** декомпозиция заменила «один агент, держащий канон + транскрипт + замысел монтажа в рабочей памяти» на «N cold-context subprocess-вызовов, каждый получает узкий срез state через Pydantic-схему и ссылку на канон файлом». Конкретные потери:

1. Канонический шаг **«Converse»** (video-use SKILL.md L87, Step 3) полностью удалён из графа — `narrative_context` (тип контента, must-preserves, must-cuts, бренд-нотки, target runtime) нигде не собирается и нигде не лежит в state.
2. Pydantic-схема `Strategy` имеет `extra="forbid"` и пять коротких string-полей — структурно не может пронести прозовые рассуждения strategy-агента в editor.
3. **Brief-author** (Claude в главной сессии) — это lossy-компрессор канона. Каждая нода получает узкий срез instruction-канона, выбранный человеком/LLM, со своей ошибкой пропуска.
4. **Per-beat fan-out** атомизирует логику переходов и seam-coverage, которая канонически требует визуальности соседних сцен.
5. **Headless-гейты** (`lint`/`validate`/`p3_self_eval`) проходят зелёными при сломанном content-уровне (дубли, audio-doubling, чёрный рендер).
6. Топологические баги (HOM-160 cross-thread cache, мёртвый `RetryPolicy.retry_on=(BackendTimeout,)`, gate:lint cap=3 при 1-fix-per-iter LLM-сходимости) — компаундирующий шум.

Полный диагностический разбор лежит в этой же ветке conversation history (исследовательские агенты, 2026-05-07).

## 1. Маппинг на текущий бэклог

Что уже есть в Linear / что нужно завести:

| # | Поток работы | Существующий тикет | Действие |
|---|---|---|---|
| 1 | Converse + `narrative_context` state slot | — | **Новый тикет** (high impact) |
| 2 | Снять `extra="forbid"`, добавить прозовые `rationale`/`taste_notes` поля в Strategy/Plan/DesignSystem | — | **Новый тикет** (мелкий) |
| 3 | Детерминированная подгрузка skill-канон секций в брифы | **HOM-114** | Расширить scope (см. §4) и взять в работу |
| 4 | `neighbors_summary` injection для `p4_prompt_expansion` + `p4_beat` + `p4_plan` | — | **Новый тикет** (средний) |
| 5 | Авто-content-review нода (semantic dedup + audio drops) перед Phase 4 | — | **Новый тикет** (средний) |
| 6 | Brand-canon + `episode_intent` + fixed-scene-injection (CTA, intro) | — | **Новый эпик** с дочерними |
| 7 | (фоном) HOM-160 cache replay drops state | **HOM-160** | Брать параллельно — ортогонально, но без него поток HOM-154 не стабилизируется |
| 8 | (фоном) `RetryPolicy.retry_on=(BackendTimeout,)` мёртвый код | — | **Микро-тикет** (правка одной строки + тест) |

HOM-78 (HITL `user_review` после Studio) и HOM-77 / HOM-137 / HOM-155 / HOM-156 (Phase 4 canonical gaps) — НЕ перекрываются с этой работой; идут своими треками.

## 2. Детальный план — шесть потоков

### Поток 1: Restore Converse + `narrative_context` state slot

**Что делаем:** добавляем новую ноду между `p3_pre_scan` и `p3_strategy`, реализующую канонический Step 3.

**Канонический текст (video-use SKILL.md L87, verbatim):**

> «Converse. Describe what you see in plain English. Ask questions *shaped by the material*. Collect: content type, target length/aspect, aesthetic/brand direction, pacing feel, must-preserve moments, must-cut moments, animation and grade preferences, subtitle needs.»

**Реализация:**

- Новый файл `episodes/<slug>/edit/narrative_context.md` (канон не специфицирует персистенс — мы его выбираем для re-runs / cache).
- Два режима сбора:
  - **Interactive (default для new episodes):** `interrupt()` после pre-scan, оркестратор выводит pre-scan summary + 8-полевую анкету, ждёт ответ человеком.
  - **Pre-filled:** если в `episodes/<slug>/intent.yaml` (см. поток 6) уже есть `narrative_context` — пропустить interrupt.
- Новый state-slot `state["edit"]["narrative_context"]: str` (свободный markdown, не Pydantic-объект).
- Прокидывается в `p3_strategy` brief как блок INPUTS и в `p3_edl_select` brief как блок INPUTS (канон требует именно во второй).

**Канонический контракт editor INPUTS** (video-use SKILL.md L130–137, verbatim):

```
INPUTS:
  - takes_packed.md
  - Product/narrative context: <2 sentences from the user>
  - Speaker(s): <name, role, delivery style note>
  - Expected structure: <pick an archetype or invent one>
  - Verbal slips to avoid: <list from the pre-scan pass>
  - Target runtime: <seconds>
```

Сейчас editor получает: takes_packed_path ✓, Product context ✗ (DROPPED), Speakers — частично (только S0/S1 IDs) ✗, Expected structure — частично, через Strategy ✗, Verbal slips ✓, Target runtime ✓. Поток 1 закрывает три ✗ через `narrative_context`.

**DoD:** smoke на Haiku, p3_topology тест обновлён, в `_CACHE_VERSION` бамп p3_strategy + p3_edl_select.

### Поток 2: Loosen creative-state schemas

**Что делаем:** убираем `extra="forbid"` со схем `Strategy`, `Plan`, `DesignSystem`. Добавляем свободно-текстовые поля для прозового обоснования.

- `schemas/p3_strategy.py` — добавить `rationale: str` (~3-6 предложений, прозой) и `taste_notes: str` (свободно). Снять `extra="forbid"` на Strategy.
- Аналогично `schemas/p4_design_system.py`, `schemas/p4_plan.py` — `rationale: str` + `cross_scene_logic: str`.
- Эти поля пропускаются в downstream-брифы прозой, **рядом** со структурными полями, не вместо.

**Почему важно:** сейчас strategy-агент думает, рожает прозу, мы её парсим в 5 string-слотов и теряем 80% мысли. EDL-агент видит «shape: hook-problem-solution-cta» вместо «hook должен сильно зацепить — у спикера есть 3 эмоциональных момента в первой минуте, любой из них тянет открытие».

**DoD:** schema migration, тест что поля прокидываются, smoke что издержки на токенах не взорвались.

### Поток 3: Pre-load canon sections (HOM-114, расширенный scope)

**Что есть в HOM-114 сейчас:**

- `_canon_loader.py` с `load_skill_section(skill_path, anchor)` — markdown-парсер по тексту H2-заголовка.
- Snapshot-тесты, smoke без `Read` SKILL.md.

**Что добавляем поверх:**

1. **Three-layer loader:** loader понимает три источника — `skill_canon` (read-only upstream), `brand_canon` (наш `brand/`, см. поток 6), `episode_intent` (`episodes/<slug>/intent.yaml`). API: `assemble_brief_context(skill_anchors=[(path, anchor)], brand_sections=[...], intent_keys=[...])`.
2. **Поддержка sub-list-item extraction** для случаев когда канон-секция — это пункт списка внутри `## The process` (как Step 3 «Converse» в video-use SKILL.md L87 — нет своего H2-якоря).
3. **Cache-key включает sha256 каждого подгруженного блока** — обновился канон, инвалидировалась только нода, чьи якоря изменились (улучшение над текущим ручным `_CACHE_VERSION` бампом).
4. **Snapshot-тесты на каждый используемый якорь** обоих скиллов.

**Конкретные якоря per-нода:**

- **`p3_pre_scan`:** video-use SKILL.md `## The process` (Step 1, 2), `## Cut craft (techniques)`.
- **`p3_strategy`:** video-use SKILL.md `## The process` (Step 3 + Step 4), `## Hard Rules (production correctness — non-negotiable)`.
- **`p3_edl_select`:** video-use SKILL.md `## Editor sub-agent brief (for multi-take selection)` (verbatim), `## Cut craft (techniques)`, `## EDL format`, `## Hard Rules`.
- **`p3_self_eval`:** video-use SKILL.md `## The process` (Step 7).
- **`p4_design_system`:** hyperframes SKILL.md `### Step 1: Design system`; full `house-style.md` (~74 lines, дешевле чем парсить).
- **`p4_prompt_expansion`:** hyperframes SKILL.md `### Step 2: Prompt expansion`; full `references/prompt-expansion.md` (~69 lines); `references/beat-direction.md ## Per-Beat Direction` + `## Rhythm Planning`.
- **`p4_plan`:** hyperframes SKILL.md `### Step 3: Plan`; `references/transitions.md ## Energy → Primary Transition` + `## Mood → Transition Type` + `## Narrative Position`; `references/beat-direction.md`.
- **`p4_beat`:** hyperframes SKILL.md `## Layout Before Animation`, `## Rules (Non-Negotiable)`, `## Scene Transitions (Non-Negotiable)`, `## Animation Guardrails`; `references/motion-principles.md ## Load-Bearing GSAP Rules` (full, ~60 lines — это ровно то, что HOM-154 retro нашёл пропавшим из per-beat брифа).
- **`p4_captions_layer`:** `references/captions.md ## Caption Exit Guarantee` + `## Text Overflow Prevention` + `## Positioning` + `## Constraints`.

**Anchorability check:** обе SKILL.md и все referenced files имеют unique-text H2 заголовки в пределах файла — anchorable без disambiguation. Проверено на 2026-05-07.

**Каноническое обоснование mechanical-inline подхода:** `references/motion-principles.md` L142 (verbatim): *«don't summarize or shorten them»*. Канон сам требует не пересказывать load-bearing rules — паста идёт verbatim.

### Поток 4: `neighbors_summary` injection

**Что делаем:** в `p4_prompt_expansion` и `p4_beat` (и `p4_plan` опционально) прокидываем сводку соседних сцен, чтобы closed-context fan-out мог соблюдать кросс-сценные канон-правила.

**Канонические места, требующие соседского контекста (verbatim, hyperframes):**

- SKILL.md L249–252, Scene Transitions Non-Negotiable Rule 3: *«NEVER use exit animations except on the final scene… The transition IS the exit.»* — beat не может знать, что он final, без injection.
- `transitions.md` L22: *«Pick ONE primary (60-70% of scene changes) + 1-2 accents. Never use a different transition for every scene.»*
- `transitions.md` L40-49 (Narrative Position): требует знания, что текущая сцена — opening / climax / outro.
- `beat-direction.md` L88-96 (Rhythm Planning): требует глобальной строки ритма «fast-fast-SLOW-fast-SHADER-hold».
- `beat-direction.md` L54: *«1-2 shader transitions (the hero reveal + the CTA)»* — кросс-сценный budget.
- `video-composition.md` L52-54: *«Vary motion per scene — don't repeat the same ambient pattern.»*

**Реализация — поле `_beat_dispatch.neighbors_summary`:**

```python
{
    "scene_index": 3,
    "total_scenes": 6,
    "is_opening": False,
    "is_final": False,
    "is_climax": True,
    "rhythm_position": "PEAK",  # из p4_plan
    "rhythm_string": "hook-build-PEAK-breathe-CTA",
    "planned_transition_in": {"kind": "shader", "name": "wave"},
    "planned_transition_out": {"kind": "css", "name": "blur-fade"},
    "sibling_ambient_motions": ["radial-glow-breathe", "ghost-type-drift", ...],
    "sibling_entrance_directions": ["left", "up", "scale", ...],
}
```

**Ответственный за заполнение:** `p4_dispatch_beats` (детерминированная нода, она и так уже формирует `Send` payload — логично туда же).

**DoD:** обновить `briefs/p4_beat.j2` чтобы цитировал `neighbors_summary`, обновить smoke на одну beat-ноду, проверить что cache-key учитывает соседский summary (бамп `_CACHE_VERSION`).

### Поток 5: Auto content-review node

**Что делаем:** новая LLM-нода `p3_content_review` после `p3_render_segments`, перед `p3_self_eval` (или параллельно).

**Brief (черновик):**

```
INPUTS:
  - edl_path
  - final_transcript_path (post-cut)
  - takes_packed_path (pre-cut, для сравнения)

TASK:
Прочитай EDL и финальный транскрипт. Это taste-проверка ПОСЛЕ того
как timing-математика прошла p3_self_eval — гейты с тайминговой
точностью уже зелёные, но контент мог проскочить с явными косяками.

Найди ровно три класса проблем:
  1. Cross-range semantic duplication — одна и та же мысль/фраза
     дословно или почти дословно прозвучала в двух разных range.
     Пример: «we don't want to lose customers» в range 0:12-0:18
     и снова в 1:34-1:40.
  2. Audio drops на boundaries — обрыв на середине слова, проглоченное
     окончание, фантомный echo.
  3. Сохранившиеся явные false-starts — спикер начал, поправил себя
     прямо в кадре, обе версии остались в EDL.

Output schema: {issues: [...], passed: bool}
Если issues.length > 0 → passed=false, для каждой issue укажи
range (timestamp), цитату, severity (high/medium/low).
```

**Routing на failure:**

- `passed=false` AND `severity=high` exists → `p3_edl_redispatch` (новый condional edge на `p3_edl_select` с `revisions=issues`). Cap=2.
- После cap=2 → `edl_failure_interrupt` (уже существует в графе).
- `passed=true` → нормально к `p3_self_eval`.

**Почему отдельная нода, а не правило в `p3_self_eval`:** разный mental model. `p3_self_eval` — timing math + waveform PNG, `p3_content_review` — таste/семантика. Разные брифы, разные cache keys, разные failure modes.

**DoD:** smoke (~$0.05 на Haiku, ~$0.30 на Sonnet — фактический контроль taste стоит smart-tier), topology test, бамп `_CACHE_VERSION`.

### Поток 6: Brand-canon + episode_intent + fixed-scene-injection (новый эпик)

Архитектурный слой поверх канонической базы. Подробнее ниже в §3 — здесь только границы эпика.

**Дочерние тикеты:**

- 6.1 — структура каталога `brand/` + пустые шаблоны (brand.md, palette.yaml, defaults.yaml, templates/).
- 6.2 — pickup-нода читает `brand/` + `episodes/<slug>/intent.yaml` → state `brand` + `intent`.
- 6.3 — `_canon_loader` интеграция (расширение HOM-114): brand-секции и intent-поля доступны в брифах через те же якорные подстановки.
- 6.4 — детерминированная нода `p4_inject_cta_scene` + шаблон `brand/templates/cta_scene.html`.
- 6.5 — `p4_plan` brief обновляется чтобы видеть `fixed_scenes` в state и НЕ перепланировать их.
- 6.6 — design-adherence content gate (см. §4 — каноническая дыра).

**Когда исполнять:** ПОСЛЕ того как baseline (потоки 1–5) догонит чистую сессию по EDL-качеству. Иначе тюнинг двух unknown одновременно.

## 3. Архитектура трёх слоёв канона

```
final brief =
  ├─ skill_canon        (read-only upstream)         поток 3 / HOM-114
  ├─ brand_canon        (наш brand/, persistent)     поток 6
  ├─ episode_intent     (intent.yaml, optional)      потоки 1+6
  └─ state_from_prior_nodes                          текущая работа графа
```

Это НЕ форк канона: skill-канон по-прежнему read-only. Brand-канон не пересказывает skill-канон, а добавляет инварианты поверх (палитра, логотип, CTA-сцена). При формальном конфликте brand-канон выигрывает (он ближе к выводу).

**Файловая раскладка:**

```
brand/
  brand.md                  ← человеко-читаемый бренд-канон
  palette.yaml              ← структурированные цвета/типографика
  defaults.yaml             ← дефолты для grade/pacing/animation density
  assets/
    logo.svg
    symbol-lime.svg
  templates/
    cta_scene.html          ← деттерминированный CTA-блок
    intro_scene.html        ← опционально

episodes/<slug>/
  intent.yaml               ← опциональные пер-эпизод правки
  raw.<ext>
  edit/
    narrative_context.md    ← заполняется потоком 1, может быть pre-filled из intent.yaml
  ...
```

`intent.yaml` (все поля опциональные):

```yaml
narrative_context: |
  Episode about X. Must preserve the demo at 02:15.
  Must cut the false start at 0:00-0:08.
target_runtime_s: 90
must_preserves: [...]
must_cuts: [...]
animation_wishes: |
  Slightly more aggressive than default.
grade_overrides:
  warmth: +5
beat_overrides: {}
```

Пустой `intent.yaml` → дефолты бренда → канон. Заполненный — рычаг отклониться.

## 4. Скилл-аудит — что нашли

### 4.1. video-use canon (`~/.claude/skills/video-use/SKILL.md`)

- **Anchor extractability: GREEN.** Все H2-секции unique-text, anchorable.
- **Канонический шаг «Converse»** (Step 3) живёт **только пунктом списка** внутри `## The process` (L87) — нет своего H2-якоря. Loader должен поддержать sub-list-item extraction (см. §2 поток 3 пункт 2).
- **Editor INPUTS contract** (L130-137) — три из шести полей у нас сейчас MISSING/PARTIAL/DROPPED. Поток 1 закрывает.
- **Soft modals — почти нет.** Канон дисциплинирован, HR1-HR12 несут must-do нагрузку. Единственный явный «Prefer» в editor RULES (L152, *«Prefer silences ≥400ms as cut targets»*) — стоит harden в нашем брифе до «Cut on silences ≥400ms when available; document in `reason` when forced to cut tighter.»
- **Семантический дедуп / «не оставляй мысль, проговорённую дважды»: НЕ зафиксировано в каноне.** Это пробел в самом video-use SKILL.md. Два варианта: (а) **добавить таste-правило в наш brief assembly** локально, (б) **открыть upstream PR в video-use** с предложением дополнить `## Cut craft` строкой типа: *«Semantic dedup: if the same idea is voiced in multiple ranges, keep the version with cleaner delivery and discard the other. If the speaker corrects themselves mid-take, never keep the pre-correction phrasing.»* Ставлю (а)+(б).
- **Helpers:** проверить что граф использует `transcribe_batch.py` (parallel), а не `transcribe.py`. И что `timeline_view.py` действительно вызывается на pre-scan Step 1 (канон: «sample one or two `timeline_view`s for a visual first impression»).

### 4.2. hyperframes canon (`~/.agents/skills/hyperframes/`)

- **Anchor extractability: GREEN** для SKILL.md и всех `references/`. Подробный список якорей per-нода — в §2 поток 3.
- **Hard-kill / boundary rules** (`motion-principles.md` L135-140) — это ровно те правила, которые HOM-154 retro нашёл пропавшими из per-beat брифа. Mechanical-inline через HOM-114 решает это структурно.
- **Brand-asset contract:** канон ожидает что brand-данные приходят через **`design.md`** (SKILL.md L27, L29, L37; `video-composition.md` L6-11; `house-style.md` L4). Наш brand-канон-слой должен инжектить через `design.md` (расширение / merge), НЕ изобретать новый attribute. Это важно — иначе fork-canon risk.
- **CTA-template / fixed-scene патtern: нет в каноне.** `templates/` содержит только `design-picker.html`. CTA упоминается семантически (rhythm `hook-PUNCH-hold-CTA`, `beat-direction.md` L54: *«1-2 shader transitions (the hero reveal + the CTA)»*) но нет HTML-шаблона. Это **net-new orchestrator territory**, не дублирование канона. Хук — добавить CTA-beat в rhythm-string в `p4_prompt_expansion` (или post-process) с `is_final=true`, и вставить наш HTML verbatim. Финальная-сцена-fade покрывается каноническим Rule 4.
- **Quality-checks gap — design-adherence content check** (`SKILL.md` L348): канон описывает ручной agent-level чек *«every hex value in the composition appears in design.md's palette»*. У нас **нет соответствующего gate**. Это новый контент-уровневый гейт (механический грэп hex-значений в `index.html` против `design.md`). Берём как часть потока 6 (поток brand-canon естественно требует этот гейт для бренд-фиделити).
- **Soft modals в hyperframes — больше**. Конкретные «consider» / «if applicable» / «follow» которые исторически кусались (см. ретро 2026-05-01, 2026-05-02):
  - SKILL.md L23 *«consider offering 2-3 variations»* — harden до «DO offer N variations when prompt.exploratory==true».
  - SKILL.md L51 *«Read references/beat-direction.md for rhythm templates»* — phrased как helper, требуется в Step 2/3. Brief должен явно «READ this file».
  - SKILL.md L56 *«propose them — don't add them»* — soft propose. Hard-gate на `expanded_prompt.scenes` count.
  - SKILL.md L283 *«follow house-style.md for aesthetic defaults»* — soft follow. House-style L34 (декоративы Background Layer 2-5) — каноническая floor, не suggestion. Память `feedback_design_md_opt_outs` уже это покрывает.

### 4.3. Cheatsheets

`docs/cheatsheets/video-use.md` и `docs/cheatsheets/hyperframes.md` корректно отражают канонические 8 шагов и data-атрибуты соответственно. Но shape Step 3 в video-use cheatsheet (L23, *«Converse — тип, длительность, аспект, эстетика, темп, must-keep, must-cut»*) короче канонической 8-полевой формулы (`aesthetic/brand direction, pacing feel, must-preserve moments, must-cut moments, animation and grade preferences, subtitle needs`). Обновить cheatsheet синхронно с потоком 1.

## 5. Sequencing

**Спринт 1 (1 неделя — стабилизация baseline):**

1. Поток 1 — Converse + narrative_context (high impact, средний объём).
2. Поток 2 — снять `extra="forbid"`, добавить rationale-поля (мелкий).
3. HOM-114 — pre-load skill-канон секций (готов к старту, 3 points).
4. Микро-фикса `RetryPolicy.retry_on=(BackendTimeout,)`.

После спринта 1 — повторный E2E на стабильном эпизоде, сравнение качества EDL и Phase 4 с чистой сессией. Эта точка — go/no-go для остальной работы.

**Спринт 2 (если baseline догнал чистую сессию):**

5. Поток 5 — content-review нода.
6. Поток 4 — neighbors_summary.
7. HOM-160 — cache-replay фикса (если ещё актуален после спринта 1).

**Спринт 3 (после стабильного baseline):**

8. Поток 6 эпик — brand-canon + intent.yaml + fixed-scenes.
9. Design-adherence гейт.

**Параллельно (фоном, async):**

- Upstream PR в video-use с semantic-dedup taste rule (§4.1).
- Cheatsheet updates (§4.3).

## 6. Открытые вопросы

1. **Interactive Converse vs file-based intent.yaml.** Сейчас спека предлагает оба пути. Default-режим взять interactive (через `interrupt()`) или file-first? Аргумент за file-first: автоматизация цели «бросил в inbox → получил рендер». Аргумент за interactive: 80% эпизодов это «не знаю заранее всех нюансов, отвечу на вопросы». Решение: default = file-first; если `intent.yaml` отсутствует или поле `narrative_context` пустое → fallback в `interrupt()`.
2. **Где лежит `narrative_context.md`** — внутри `edit/` (где video-use артефакты) или на уровне `episodes/<slug>/`? Аргумент за `edit/`: канон-совместимо, video-use ожидает все артефакты в `<videos_dir>/edit/` (HR12). Аргумент за корень эпизода: используется и Phase 3, и Phase 4. Решение: `edit/narrative_context.md` (Hard Rule побеждает).
3. **`RetryPolicy` — починить таргет на `AllBackendsExhausted` или удалить retry?** Сейчас retry_on=(BackendTimeout,) — мёртвый код. Нужно понять, нужен ли вообще auto-retry для creative-нод (где LLM-faiulre обычно означает что промпт сломан, а не транзиентная сеть). Вынести в отдельный мини-тикет с обсуждением.
4. **Upstream PR в video-use vs локальный таste-rule.** Стоит сделать **оба**: локально не ждать upstream merge, upstream чтобы канон стал точкой правды. Нужна готовность поддерживать локальный rule до merge — и снять после.
5. **Нужен ли отдельный `p3_redispatch_edl` нод или роутинг переиспользует `p3_edl_select` с revisions-payload?** По аналогии с `p4_redispatch_beat` — отдельный лучше (cap-логика чище, отдельный bump cache).

## 7. Не входит в эту спеку

- Phase 4 canonical gaps (HOM-77 / HOM-137 / HOM-155 / HOM-156) — самостоятельный трек.
- HOM-78 (HITL user_review после Studio) — комплементарно, не блокирует.
- HOM-79 cutover в thin-client — после стабилизации baseline.
- Phase 1/2 (audio-isolation / pickup) — закрыты ранее, не пересматриваем.

## 8. Definition of done на уровне всей спеки

После спринтов 1-2 критерий «работает не хуже чистой сессии» проверяется так:

1. Один и тот же raw-эпизод прогоняется через `/edit-episode` (граф) и через свежую `claude` сессию с промптом `«Используя скилл /video-use обработай видео»`.
2. Оба `final.mp4` смотрит человек.
3. Acceptance: количество явных taste-косяков в graph-output ≤ количество в clean-session-output (обычно 0-1). Длительность в пределах ±10%. Семантических дублей нет ни там, ни там.

Если не достигнуто — возврат в Phase 1 systematic-debugging, не «ещё одна правка поверх».
