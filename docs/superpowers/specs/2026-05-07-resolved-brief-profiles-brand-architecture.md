# Resolved Episode Brief, Profiles, Brand Layer — context architecture for parity with clean skill sessions

**Дата:** 2026-05-07
**Статус:** Draft, готовится PR
**Supersedes:** `docs/superpowers/specs/2026-05-07-context-continuity-improvements-design.md`, `docs/superpowers/specs/2026-05-07-skill-canon-context-brand-parity-plan.md`
**Контекст-якоря:**
- ретро `docs/retros/retro-2026-05-07-hom-154-clean-e2e-attempt.md` (semantic-дубль фразы в EDL, чёрная HF-композиция, HOM-160 cache replay)
- `CLAUDE.md` — non-negotiable canon-rules + LangGraph-primitives-first + branch+PR workflow
- canon: `~/.claude/skills/video-use/SKILL.md`, `~/.agents/skills/hyperframes/`

---

## 1. Problem statement

LangGraph-оркестратор декомпозирует канонические workflow `video-use` (Phase 3) и `hyperframes` (Phase 4) на атомарные LLM-ноды. Декомпозиция дала контроль и видимость, но потеряла **общий контекст**, который чистая `claude /video-use` сессия держит естественно через conversation history:

- замысел монтажа и тон (что было бы собрано на каноническом шаге **Converse**),
- бренд-идентичность (палитра, типографика, лого, motion language),
- кросс-сценные правила (rhythm string, transition budget, sibling motion variation),
- semantic taste (не оставлять одну и ту же мысль дважды).

Симптомы, поднявшие задачу — HOM-154 E2E-прогон 2026-05-07:

1. EDL оставил `«Yes, maybe it's not as interesting from a business point of view»` дважды подряд через короткую паузу — semantic-дедуп ни в одной ноде не закодирован, `p3_self_eval` пропустил (его mental model — timing math).
2. Phase 4 композиция — без любых бренд-инвариантов и с вырожденным CTA-уровнем (нет финальной сцены подписки, нет лого).
3. Cold-context fan-out (`p4_beat`) не видит соседей и общего ритма.

Корневой класс ошибки: декомпозиция убрала **brief-author**'а (главный агент клина-сессии, держащий конверсацию в рабочей памяти) и заменила его lossy-компрессором канон-фрагментов. Ничего из вышеперечисленного из самого `SKILL.md` не следует — это контекст, который канон собирает в рантайме через Converse + дальнейший разговор.

## 2. Цель и нон-цели

**Цель:** ввести формальный **context-resolution слой** перед Phase 3, через который канон, профиль (видео-класс), бренд-кит, музыкальная библиотека и per-episode intent сводятся в детерминированный `brief.resolved.yaml`. Все creative-ноды получают этот brief как INPUT и **только** этот brief как источник «не-канонического» контекста. Cache-keys creative-нод включают brief fingerprint (HOM-157 уже даёт механику для config-fingerprint; распространяется на brief).

**Нон-цели в этой спеке:**
- Reliability cluster (HOM-160 cross-thread cache replay; HOM-158 follow-up `RetryPolicy.retry_on`; gate:lint iter cap; preventive `p4_beat` guards) — закрывается в backlog'е по обычному порядку.
- HF Phase 4 black-screen investigation (retro #2) — отдельный bare-repro тикет.
- HOM-77 children (HOM-137 root transitions, HOM-155 beat_kills, HOM-156 animation-map fix-or-justify) — самостоятельный трек, комплементарно.
- HOM-78 HITL Studio review — комплементарно.
- Phase 1/2 (audio-isolation, pickup) — закрыты, не пересматриваем.

## 3. Архитектурная модель — четыре слоя контекста

```
final brief consumed by node =
  ├─ skill_canon         (read-only upstream, in-place anchor extraction)
  ├─ profile             (видео-класс — first-class slot)
  ├─ brand_kit           (бренд-канон + music library)
  ├─ episode_intent      (optional per-episode override)
  └─ pipeline_state      (артефакты от upstream-нод)
```

**Профиль — first-class абстракция, не bool-флаг.** Каждый профиль фиксирует видео-класс: `talking-head-portrait`, `explainer`, `long-form`, `horizontal-product-promo`, …. У профиля свои дефолты pacing'а, structural archetype, rhythm template, captions-стратегии, плотности анимации, музыкального бренча (allowed mood, default mix-volume). `canonical` — пустой профиль для regression-режима: чистый канон без бренд- и класс-опинионов.

**Brand-канон — не форк skill-канона.** Skill-канон по-прежнему read-only. Бренд-слой добавляет инварианты ПОВЕРХ канона (палитра, типографика, лого, motion language, music library, CTA template). При формальном конфликте brand-канон выигрывает (он ближе к выводу).

**Это не пересказ канона.** Per-node анкорный список (см. §10) грузит канон-секции дословно — бренд-слой занимает только то, что канон сам оставляет на conversation/style-guide.

## 4. Файловая раскладка

```
profiles/
  canonical/
    profile.yaml                      # пустой override — только skill_canon
  talking-head-portrait/
    profile.yaml                      # pacing, archetype, rhythm template
    house-style.md                    # video-class-specific guidance
  explainer/
    profile.yaml
    house-style.md
  …

brand/
  anticodeguy/
    brand.md                          # brand voice, тон, narrative principles
    palette.yaml                      # colors, typography, contrast pairs
    defaults.yaml                     # motion language, caption style, CTA, grade
    assets/
      logo.svg
      symbol-lime.svg
    templates/
      cta_scene.html                  # детерминированный CTA-блок (статический HTML-template; НЕ hyperframes-registry component)
      intro_scene.html                # опционально
    music/
      tracks/
        editorial-warm-1.mp3
        editorial-warm-1.meta.yaml    # bpm, mood, length, license, lufs, loop_safe
        tutorial-clean-2.mp3
        tutorial-clean-2.meta.yaml
        ...
      defaults.yaml                   # default trackId, per-profile preferences, fixed mix-volume

episodes/<slug>/
  intent.yaml                         # optional per-episode override
  brief.resolved.yaml                 # ← deterministic resolution output
  raw.<ext>
  edit/
    narrative_context.md              # Converse output (interrupt-ветка)
    final.mp4
    transcripts/
      raw.json
  hyperframes/
    index.html
    package.json
```

`profiles/canonical/profile.yaml`:

```yaml
profile_id: canonical
human_label: "Canonical (regression)"
pacing: skill_default
structural_archetype: skill_default
rhythm_template: skill_default
captions:
  enabled: false
animation_density: skill_default
music:
  enabled: false
cta:
  enabled: false
```

`profiles/talking-head-portrait/profile.yaml` (пример):

```yaml
profile_id: talking-head-portrait
human_label: "Talking head — portrait short"
output:
  width: 1080
  height: 1920
  fps: 60
pacing: tight_conversational
structural_archetype: hook_problem_solution_cta
rhythm_template: "hook-build-PEAK-breathe-CTA"
captions:
  enabled: true
  mode: karaoke
  safe_zone: lower_third_avoid_face
animation_density: medium
music:
  enabled: true
  default_mix_db: -18           # фикс mix-volume vs voice; canonical mix без sidechain
cta:
  enabled: true
  placement: final_scene
edit:
  remove:
    - false_starts
    - corrected_phrases
    - dead_air
    - cross_range_semantic_duplicates
  padding:
    head_ms: 50
    tail_ms: 80
```

`brand/anticodeguy/music/defaults.yaml`:

```yaml
default_track_id: editorial-warm-1
volume_db: -18                # фиксированный mix; конвертится в data-volume через 10**(db/20)
fade_in_s: 0.5                # GSAP-tween на свойство volume; опционально
fade_out_s: 1.0
per_profile:
  talking-head-portrait: editorial-warm-1
  explainer:            tutorial-clean-2
  long-form:            doc-bed-3
license_required: true
```

`<track>.meta.yaml`:

```yaml
track_id: editorial-warm-1
title: "Editorial Warm 1"
artist: "Anticodeguy library"
license: "BY 4.0"
license_note: "© 2025 Anticodeguy. CC BY 4.0."
length_s: 142
bpm: 96
mood: ["warm", "editorial", "uplift"]
lufs_integrated: -16.0
loop_safe: true
```

`episodes/<slug>/intent.yaml` (все поля опциональные):

```yaml
profile_id: talking-head-portrait
brand_id: anticodeguy

narrative_context: |
  Episode about X. Must preserve the demo at 02:15.
  Must cut the false start at 0:00–0:08.
target_runtime_s: 90
must_preserves: [...]
must_cuts: [...]

music:
  track_id: tutorial-clean-2
  volume_db: -16

animation_wishes: |
  Slightly more aggressive than default.
grade_overrides:
  warmth: +5
beat_overrides: {}
```

Пустой `intent.yaml` → дефолты профиля → дефолты бренда → канон. Заполненный — рычаг отклониться.

## 5. State namespace `brief`

Новое поле в `state.brief`:

```python
brief = {
    "profile_id": str,                       # 'talking-head-portrait'
    "brand_id": str,                         # 'anticodeguy' | None для canonical
    "resolved_brief_path": str,              # episodes/<slug>/brief.resolved.yaml
    "narrative_context": str | None,         # markdown
    "music": {
        "track_id": str,
        "asset_path": str,
        "volume_db": float,           # → data-volume через 10**(db/20)
        "fade_in_s": float,
        "fade_out_s": float,
        "license_note": str,
        "lufs_integrated": float,
    } | None,
    "fingerprint": str,                      # sha256 over canonicalized resolved brief
}
```

Прокидывается во все creative ноды: `p3_pre_scan`, `p3_strategy`, `strategy_confirmed_interrupt`, `p3_edl_select`, `p3_self_eval`, `p4_design_system`, `p4_prompt_expansion`, `p4_plan`, `p4_beat`, `p4_captions_layer`, `p4_assemble_index`, `p4_inject_music` (новая, см. §11), все P4-гейты.

`brief.fingerprint` подмешивается в `_cache_key` через `make_llm_key` (HOM-157). Изменение трека / палитры / профиля / intent.yaml инвалидирует ровно те ноды, чей brief действительно сменился.

## 6. Новая нода `resolve_episode_brief`

Deterministic, в графе между `pickup` и `p3_inventory` (до начала любых LLM-нод).

**Inputs:**
- source metadata (`pickup` output);
- selection inputs: CLI override (через RunConfig), `intent.yaml`, defaults;
- file system: `profiles/<profile_id>/`, `brand/<brand_id>/`, `brand/<brand_id>/music/`.

**Resolution priority (high → low):** CLI override → `intent.yaml.<key>` → `profile.yaml.<key>` → `brand/<id>/defaults.yaml.<key>` → skill canon default.

**Selection rules:**
- `profile_id`: CLI > intent.yaml > project default (`graph/config.yaml.default_profile_id`, дефолт `talking-head-portrait`).
- `brand_id`: CLI > intent.yaml > project default (`anticodeguy`). Для `profile_id == canonical` — `brand_id == None` принудительно, бренд-слой не подключается.
- `music.track_id`: CLI > intent.yaml > brand `music/defaults.yaml.per_profile[<profile_id>]` > brand `default_track_id`. Если `profile.music.enabled == false` — `brief.music = None`.

**Validation (резолвер падает с понятным сообщением, не пропускает в LLM):**
- profile/brand директории существуют, обязательные файлы на месте;
- `music.asset_path` существует, `<track>.meta.yaml` парсится;
- `license_note` непустой при `license_required: true` и `brand_id != None`;
- output orientation/fps согласован между profile и intent overrides;
- если `intent.yaml` ссылается на ассет — он есть на диске.

**Outputs:**
- `episodes/<slug>/brief.resolved.yaml` — канонично сериализованный (sorted keys, нормализованные пути) для воспроизводимого fingerprint'а;
- `state.brief.*` (см. §5).

**Кэш:** `make_key` (детерминированная нода, не LLM). Ключ = sha256 над всеми прочитанными файлами + resolution priority result.

## 7. Schema loosening для creative state

Сейчас `Strategy`/`Plan`/`DesignSystem` Pydantic-схемы имеют `extra="forbid"` и узкие поля. Стратег-агент рожает прозу, парсер выкидывает 80% мысли в 5 string-слотов.

**Изменения:**

- `schemas/p3_strategy.py`: снять `extra="forbid"`, добавить:
  - `rationale: str` — 3–6 предложений прозой, обоснование.
  - `taste_notes: str` — свободный markdown.
- `schemas/p4_design_system.py`: добавить `rationale: str` + `cross_scene_logic: str`.
- `schemas/p4_plan.py`: добавить `rationale: str` + `cross_scene_logic: str`.

Эти поля прокидываются в downstream-брифы прозой **рядом** со структурными полями, не вместо. Токенный оверхед оценивается ~5–10% per node, оправдан качеством передачи.

## 8. Converse — опциональный interrupt

**File-first default:**
1. Если `brief.resolved.narrative_context` уже заполнен (через `intent.yaml`) — Converse-нода — no-op, идём на `p3_strategy`.
2. Иначе после `p3_pre_scan` — нода `p3_converse` делает `interrupt({...})` с pre-scan summary + 8-полевой анкетой канонического Step 3 (`video-use SKILL.md ## The process` → list-item «Converse», verbatim):

> «Converse. Describe what you see in plain English. Ask questions *shaped by the material*. Collect: content type, target length/aspect, aesthetic/brand direction, pacing feel, must-preserve moments, must-cut moments, animation and grade preferences, subtitle needs.»

Ответ человека пишется в `episodes/<slug>/edit/narrative_context.md` (свободный markdown) и в `state.brief.narrative_context`. Состояние brief после Converse — пересохраняется в `brief.resolved.yaml`, fingerprint бампается.

**Канонический контракт editor INPUTS** (`video-use SKILL.md ## Editor sub-agent brief (for multi-take selection)` → блок начинающийся с «INPUTS:», verbatim):
```
INPUTS:
  - takes_packed.md
  - Product/narrative context: <2 sentences from the user>
  - Speaker(s): <name, role, delivery style note>
  - Expected structure: <pick an archetype or invent one>
  - Verbal slips to avoid: <list from the pre-scan pass>
  - Target runtime: <seconds>
```

Сейчас editor получает: takes_packed_path ✓, Product context ✗ (DROPPED), Speakers — частично ✗, Expected structure — частично через Strategy ✗, Verbal slips ✓, Target runtime ✓. После §6+§8 три ✗ закрываются: Product context — из `narrative_context`; Speakers — из `narrative_context` либо `intent.yaml`; Expected structure — из `profile.structural_archetype` плюс strategy `rationale`.

## 9. Расширение HOM-114 — three-source canon loader

**Что есть в HOM-114 сейчас (Backlog):**
- `_canon_loader.py` с `load_skill_section(skill_path, anchor)`, markdown-парсер по тексту H2-заголовка.
- Snapshot-тесты, smoke без `Read` SKILL.md.

**Что добавляется:**

1. **Three-source API:**
   ```python
   assemble_brief_context(
       skill_anchors: list[tuple[Path, str]],
       profile_sections: list[tuple[Path, str]],
       brand_sections: list[tuple[Path, str]],
       intent_keys: list[str],
       state_excerpts: dict,
   ) -> str
   ```
   Возвращает структурированный markdown-блок для Jinja2-брифа. Каждый источник помечен `## SOURCE: skill_canon`, `## SOURCE: profile`, `## SOURCE: brand`, `## SOURCE: episode_intent`.

2. **Sub-list-item extraction.** Step 3 «Converse» в `video-use SKILL.md ## The process` — пункт списка без своего H2-якоря. Loader извлекает markdown-list-item по startswith-тексту первых 1-2 слов («Converse.», «Self-eval»). Index-based extraction явно запрещён — fragile к перенумерации канонических шагов.

3. **Heading match через `startswith`, не full-string equality.** `## Hard Rules (production correctness — non-negotiable)` матчится через `startswith("## Hard Rules")` чтобы пунктуация хедера не ломала загрузку при upstream churn. Регистрируем мин-длину префикса (~10 chars) чтобы исключить false-positive.

4. **Cache-key включает sha256 каждого подгруженного блока** — обновился канон, инвалидировалась только нода, чьи якоря изменились. **Цена: cache-key включает sha256 содержимого якоря, НЕ имени.** sha256 пустой строки стабилен, поэтому пункт 5 ниже обязателен — иначе silent-empty + warm cache = LLM крутится без канона.

5. **Hard-fail на пустую экстракцию.** Если `load_skill_section(...)` возвращает пустую строку (heading не найден / sub-list-item не найден / referenced файл удалён) — поднимается `CanonAnchorMissing(skill_path, anchor)` с понятным сообщением «канон обновился, ниже якорь больше не существует, проверь diff». Никаких silent-empty fallback'ов в LLM brief.

6. **Startup integrity check `verify_anchors()`.** При build времени графа (один раз per process) walk'аем все registered tuples `(skill_path, anchor)` через все ноды и все `(profile, brand)`-секции; fail loud если хоть один якорь не резолвится. Cheap, deterministic, ловит upstream rename до запуска любых LLM-нод.

7. **Helper-script версионирование.** `pickup` и `p3_pre_scan` `key_func` включают sha256 содержимого ключевых canon-helpers (`transcribe_batch.py`, `pack_transcripts.py`, `timeline_view.py`, `render.py` из `~/.claude/skills/video-use/helpers/`) — иначе обновление helper'а с тем же путём не инвалидирует кэш и пайплайн крутится на deprecated logic.

8. **Snapshot-тесты на каждый используемый якорь** обоих скиллов и каждой brand/profile-секции.

**Anchorability check:** обе SKILL.md и referenced files имеют unique-text H2 заголовки в пределах файла — anchorable без disambiguation. Проверено 2026-05-07; поддерживаем актуальность через п.6 startup check.

**Per-нода anchor list (verbatim из родительских спек, переносится без изменений):**

- **`p3_pre_scan`:** video-use SKILL.md `## The process` (Step 1, 2), `## Cut craft (techniques)`.
- **`p3_strategy`:** video-use SKILL.md `## The process` (Step 3 + Step 4), `## Hard Rules (production correctness — non-negotiable)`; profile `house-style.md` (`## Pacing`, `## Structural archetype`); brand `brand.md` (`## Voice`).
- **`p3_edl_select`:** video-use SKILL.md `## Editor sub-agent brief (for multi-take selection)` (verbatim), `## Cut craft (techniques)`, `## EDL format`, `## Hard Rules`; profile `house-style.md` (`## Edit rules`, including `cross_range_semantic_duplicates`).
- **`p3_self_eval`:** video-use SKILL.md `## The process` (Step 7).
- **`p4_design_system`:** hyperframes SKILL.md `### Step 1: Design system`; full `house-style.md`; brand `palette.yaml` (рендерится в markdown-таблицу), `brand.md` (`## Visual identity`).
- **`p4_prompt_expansion`:** hyperframes SKILL.md `### Step 2: Prompt expansion`; `references/prompt-expansion.md`; `references/beat-direction.md` (`## Per-Beat Direction`, `## Rhythm Planning`); profile `house-style.md` (`## Rhythm template`).
- **`p4_plan`:** hyperframes SKILL.md `### Step 3: Plan`; `references/transitions.md` (`## Energy → Primary Transition`, `## Mood → Transition Type`, `## Narrative Position`); `references/beat-direction.md`; brand `defaults.yaml.transitions`.
- **`p4_beat`:** hyperframes SKILL.md `## Layout Before Animation`, `## Rules (Non-Negotiable)`, `## Scene Transitions (Non-Negotiable)`, `## Animation Guardrails`; `references/motion-principles.md ## Load-Bearing GSAP Rules` (full, verbatim — канон сам требует *«don't summarize or shorten them»*); brand `defaults.yaml.motion_language`.
- **`p4_captions_layer`:** `references/captions.md` (`## Caption Exit Guarantee`, `## Text Overflow Prevention`, `## Positioning`, `## Constraints`); brand `defaults.yaml.captions`.

**Каноническое обоснование mechanical-inline подхода:** `references/motion-principles.md ## Load-Bearing GSAP Rules` содержит фразу *«don't summarize or shorten them»*. Канон сам требует не пересказывать load-bearing rules — паста идёт verbatim.

## 10. `neighbors_summary` injection

В `p4_prompt_expansion`, `p4_beat`, `p4_plan` (опционально) прокидывается сводка соседних сцен, чтобы closed-context fan-out соблюдал кросс-сценные канон-правила.

**Канонические места, требующие соседского контекста (hyperframes, anchor-cited):**
- `SKILL.md ## Scene Transitions (Non-Negotiable)` Rule 3: *«NEVER use exit animations except on the final scene… The transition IS the exit.»* — beat не знает что он final без injection.
- `references/transitions.md` примерно строка с «Pick ONE primary (60-70% of scene changes) + 1-2 accents.» — кросс-сценный transition budget.
- `references/transitions.md ## Narrative Position` — требует знания opening / climax / outro.
- `references/beat-direction.md ## Rhythm Planning` — глобальная строка ритма «fast-fast-SLOW-fast-SHADER-hold».
- `references/beat-direction.md ## Per-Beat Direction` фраза «1-2 shader transitions (the hero reveal + the CTA)» — кросс-сценный budget.
- `references/video-composition.md` фраза «Vary motion per scene — don't repeat the same ambient pattern.» — motion variation.

**Поле `_beat_dispatch.neighbors_summary`:**

```python
{
    "scene_index": 3,
    "total_scenes": 6,
    "is_opening": False,
    "is_final": False,
    "is_climax": True,
    "rhythm_position": "PEAK",
    "rhythm_string": "hook-build-PEAK-breathe-CTA",
    "planned_transition_in": {"kind": "shader", "name": "wave"},
    "planned_transition_out": {"kind": "css", "name": "blur-fade"},
    "sibling_ambient_motions": ["radial-glow-breathe", "ghost-type-drift", ...],
    "sibling_entrance_directions": ["left", "up", "scale", ...],
}
```

**Ответственный за заполнение:** `p4_dispatch_beats` (детерминированная нода, она и так формирует `Send` payload). Cache-key `p4_beat` учитывает соседский summary (бамп `_CACHE_VERSION`).

## 11. Music — selection и application

**Музыка — нативный HF-механизм, никаких custom-runtime'ов.** Канон: `SKILL.md ## Video and Audio` — `<audio>` элемент с `data-track-index`, `data-volume`, `data-start`, `data-duration`. HF capture engine сам микширует треки по `data-volume`. Голос (из `final.mp4`) и музыка — два отдельных `<audio>` элемента с разными `data-volume` и разными track-index'ами. Никаких `window.__hfAudio`, никаких ducking-runtime-скриптов: фиксированный микс громкостей покрывает 95% talking-head shorts.

**Selection at resolve-time** (см. §6). Brief гарантирует наличие `music.asset_path`, валидной license_note, измеренного LUFS.

**Application — детерминированная нода `p4_inject_music`** между `p4_assemble_index` и `gate:design_adherence`:

- Читает `state.brief.music`.
- Пишет `<audio>` верстатимом в root `index.html`:
  ```html
  <audio
    id="music-bed"
    data-start="0"
    data-duration="<final_mp4_duration_s>"
    data-track-index="2"
    data-volume="<volume_0_to_1>"
    src="../assets/music/<track_id>.mp3"
  ></audio>
  ```
- `data-volume` — конвертация из brief.music.volume_db (`-18 dB → ~0.25`, `-12 dB → ~0.5` через `10**(db/20)`).
- Fade in/out (опционально) — GSAP-tween на свойство `volume` через timeline; канон запрещает анимировать только `play()`/`visibility`/`display`, animating `volume` допустимо.
- На `gate:music_present` failure — нода-pre-flight в самой `p4_inject_music` падает с прескриптивным сообщением.

**Альтернатива A (через `p4_assemble_index` brief).** Рассмотрена и отклонена: LLM может «забыть» точные параметры volume/track-index, потребуется gate с corrective loop, удорожает токены без выигрыша. Деттерминированная инъекция короче (~10 строк генерации html + write).

**Volume normalization.** Треки нормализуются на ingest вручную (LUFS измеряется и записывается в `<track>.meta.yaml`). `gate:music_present` валидирует `lufs_integrated` в окне `[-18, -14]` LUFS (источник: EBU R128 / ITU-R BS.1770 streaming targets); вне окна — failure с инструкцией нормализовать через `ffmpeg -af loudnorm` или Audacity.

**Если когда-нибудь понадобится sidechain ducking** (динамическое притухание музыки под voice peaks) — это будет отдельный custom adapter поверх HF (HF-канон сегодня не даёт sidechain primitive), либо upstream HF feature request. Не входит в эту спеку. Memory `feedback_external_skill_canon` запрещает форки канона; sidechain — orchestrator-house добавление, не подмена.

## 12. Content-quality gates

### 12.1 `gate:edl_semantic_ok` (детерминированный, новый)

После `p3_edl_select`. Алгоритм:
- Берётся выбранный transcript-substring per range из EDL.
- Нормализация: lowercase, схлопнуть whitespace, убрать пунктуацию.
- Скользящие 4–8 word shingles, hash-set.
- Если две range содержат пересекающийся shingle (≥6 слов) И находятся в пределах 15 секунд output timeline — flag.
- Sentence-start match (первые 5 слов range vs первые 5 слов следующего range, ≥4 совпадения) — flag.
- Если есть `script.txt` — diff selected sequence против script, помечаем missing/extra phrases.

**Output:** `gate_results[]` запись `{passed: bool, violations: [{range_a, range_b, shared_phrase, severity}], summary: str}`.

**Routing on failure:** `severity=high` exists → `p3_edl_redispatch` (новый conditional edge на `p3_edl_select` с `revisions=violations`, cap=2) → `edl_failure_interrupt`. По аналогии с `p4_redispatch_beat`.

Этот гейт ловит ровно класс HOM-154 (semantic-дубль фразы между range 2 и 3).

### 12.2 `p3_content_review` (LLM, опциональная defence-in-depth)

После `p3_render_segments`, перед `p3_self_eval`. Brief — taste-проверка ПОСЛЕ того как timing-математика прошла: cross-range semantic duplication (резервная линия за §12.1, на случай если шингл не сработал на парафраз), audio drops на boundaries, сохранившиеся явные false-starts.

Output schema: `{issues: [...], passed: bool, severity}`. Routing на failure — тот же `p3_edl_redispatch`.

**Mental-model boundary** — почему отдельная нода, а не правило в `p3_self_eval`: `p3_self_eval` — timing math + waveform PNG, `p3_content_review` — taste/семантика. Разные брифы, разные cache keys, разные failure modes.

### 12.3 `gate:brand_adherence` (детерминированный)

После `p4_assemble_index`. Каждый hex-цвет в композиции присутствует в `palette.yaml`; каждый `font-family` ссылается на разрешённую типографику (или fallback chain из brand kit). Канон-обоснование: `hyperframes SKILL.md ## Quality Checks → ### Design Adherence` описывает ручной agent-level чек *«every hex value in the composition appears in design.md's palette»* — формализуем как deterministic gate.

### 12.4 `gate:cta_present` (детерминированный)

Если `profile.cta.enabled == true`:
- финальная сцена существует;
- referenced лого-asset существует на диске;
- CTA-сцена попадает в финальные N секунд (из brand defaults);
- CTA не overlap с captions safe-zone и face-safe zone.

### 12.5 `gate:seam_policy` (детерминированный)

Каждая EDL cut boundary либо:
- покрыта transition'ом из `compose.plan.transitions[]` (HOM-137 будет производить root-level transitions);
- либо visually acceptable (cut-on-action / silence cut);
- либо явно waived в brief с reason.

В пайплайне до HOM-137 этот гейт может быть в режиме warn-only.

### 12.6 `gate:music_present` (детерминированный, см. §11)

## 13. Production-creative model guard

Для production-режима (`profile_id != canonical`):
- список creative-нод: `p3_strategy`, `p3_edl_select`, `p3_content_review`, `p4_design_system`, `p4_prompt_expansion`, `p4_plan`, `p4_beat`, `p4_captions_layer`.
- На старте графа `_llm.py` резолвит NodeConfig для каждой и проверяет `tier`. Если резолвится в cheap — fail-fast с явным сообщением.
- Override: `intent.yaml.allow_cheap_creative: true` для smoke на конкретном эпизоде.

Memory `feedback_creative_nodes_flagship_tier` уже фиксирует политику; этот guard — её формальный пресечь-механизм.

**LangGraph primitive check (per CLAUDE.md «search docs first»):** проверена документация LangGraph Python (CachePolicy/RetryPolicy/Pregel reference) — нативного node-config-validation хука на graph-build-time нет. Tier policy — orchestrator-house concern (не graph-runtime), поэтому собственный guard в `_llm.py` `resolve_node_config()` оправдан.

## 14. HITL semantics

В non-canonical режиме:
- `p3_review_interrupt` — empty submit ≠ approve. Требуется явное `{approved: true}` в resume payload.
- Payload расширен: `final.mp4` path, EDL summary, semantic-dup gate result, cut-boundary verify artifact paths (генерируется в `p3_self_eval`).
- Approval запись: `{brief_fingerprint, edl_hash, approved_at, approver}` в `state.review.approvals[]`.

В canonical-режиме старое поведение (empty submit → approve) сохраняется — нужно для regression-runs.

## 15. Linear ticket map

**Существующие, линкуются:**

| Тикет | Статус | Связь |
|---|---|---|
| HOM-114 | Backlog | Расширяется до three-source loader (§9) |
| HOM-132 | Done | Дает CachePolicy infra (база §5 fingerprint) |
| HOM-157 | Done | Config fingerprint в LLM cache (база для brief fingerprint) |
| HOM-160 | Backlog, High | Не блокер этой спеки, но §17.acceptance требует |
| HOM-77 | Backlog | Parent для HOM-137/155/156, комплементарно |
| HOM-78 | Backlog | HITL Studio review, комплементарно |
| HOM-154 | In Progress, High | Текущий E2E, симптомы которого закрывает эта спека |

**Новые тикеты под parent epic «Resolved Brief & Profile Architecture» (заводим этот epic в Linear):**

1. **Brief substrate** — state namespace `brief`, `resolve_episode_brief` нода, schema loosening (§5+§6+§7). DoD: smoke на Haiku, topology тест, fingerprint в `make_llm_key` для всех creative-нод.
2. **Profile + brand layer skeleton** — каталоги `profiles/` + `brand/anticodeguy/` + `canonical` profile + `talking-head-portrait` profile (§4). DoD: пустые шаблоны на месте, `resolve_episode_brief` парсит без падения.
3. **HOM-114 расширение** до three-source loader + sub-list-item extraction (§9). DoD: snapshot-тесты на каждый якорь, `_CACHE_VERSION` уходит из ручных бампов в auto-fingerprint.
4. **Converse interrupt + narrative_context wiring** (§8) — `p3_converse` нода, file-first логика, прокидка в `p3_strategy` + `p3_edl_select` brief. DoD: smoke с заполненным `intent.yaml.narrative_context` (no-op путь) и пустым (interrupt путь).
5. **`neighbors_summary` инъекция** (§10) — заполнение в `p4_dispatch_beats`, проброс в `p4_prompt_expansion`/`p4_beat`. DoD: smoke на одну beat-ноду, бамп `_CACHE_VERSION`.
6. **`gate:edl_semantic_ok`** (§12.1) + `p3_edl_redispatch` routing (cap=2). DoD: unit-тесты на shingle-детектор (positive + negative), topology обновлён.
7. **`p3_content_review` нода** (§12.2) — defence-in-depth. DoD: smoke на Haiku, integration с redispatch routing.
8. **`gate:brand_adherence` + `gate:cta_present` + `gate:seam_policy`** (§12.3-12.5). DoD: unit-тесты, smoke на референс-композиции.
9. **Music library substrate** — `brand/<id>/music/` каталог + `<track>.meta.yaml` schema + LUFS validation utility (§4+§11). DoD: 2-3 трека-плейсхолдера в библиотеке, схемы парсятся.
10. **Music selection в resolve_episode_brief + `gate:music_present`** (§6+§11). DoD: priority chain тестируется (CLI > intent > per_profile > default).
11. **`p4_inject_music` нода** (§11). Деттерминированный `<audio>`-write поверх `index.html`; `data-volume` конвертируется из `volume_db`. Опциональный fade через GSAP-tween на `volume`. DoD: smoke композиция проигрывает music + voice одновременно в HF Studio со штатным микшированием HF capture engine.
12. **Production-creative model guard** (§13). DoD: тест что cheap-tier на production падает; canonical-режим не падает.
13. **HITL approval tightening** (§14). DoD: тест что empty submit в non-canonical не approve.

## 16. Sequencing — по Linear milestones

Существующие milestones проекта `LangGraph pipeline migration`:

| ID | Name | Progress | Включает |
|---|---|---|---|
| M1 | Deterministic graph runs end-to-end | 100% | Done |
| M2 | LLM-driven Phase 3 parity | 100% | Done |
| **M3** | Phase 4 composition + per-beat resilience | 90.38% | HOM-77 + HOM-137 + HOM-155 + HOM-156 |
| **M4** | Production cutover | 0% | HOM-78 + HOM-79 |
| **M5** | Phase 3 decomposition hardening | 72.73% | HOM-114 + HOM-115 + HOM-117 |

Архитектурная работа этой спеки в существующие milestones чисто не укладывается — это новый pre-cutover слой между M3/M5 и M4. **Заводим новую `M6 — Resolved Brief & Profile Architecture`** в Linear под 13 тикетов §15.

### M5 close (cleanup и pre-architecture стабилизация)

**M5 уже частично содержит pre-cutover polish** («post-cutover polish and architectural follow-ups», но фактически M5 идёт перед M4 — заходит в работу через HOM-114 и подобные). Дозагружаем M5 cleanup-тикетами, которые блокируют acceptance §17 архитектурной работы:

| Тикет | Что | Принадлежность |
|---|---|---|
| **HOM-160** (High, существует) | Cross-thread cache replay channel-writes hydrate | Перевести в M5. Без него acceptance §17 на fresh-thread не воспроизводится. |
| **HOM-158 follow-up** (новый, S) | `RetryPolicy.retry_on` → `AllBackendsExhausted` или re-raise `BackendTimeout` из `_llm.py` | Завести в M5. Сейчас retry мёртв. |
| **gate_results reducer fix** (новый, S) | `gate_results: Annotated[list, add]` → custom reducer с clear-on-replay семантикой ([LangGraph reducer API](https://langchain-ai.github.io/langgraph/concepts/low_level/) §"Reducers" — `Annotated[list, custom_reducer]`) | Завести в M5. Без него `update_state(as_node=...)` rewind заблокирован — fallback acceptance §17 при незакрытом HOM-160. |
| **HF Phase 4 black-screen** (новый, M) | Bare-repro в чистом `npx hyperframes init`, локализовать слой, fix или upstream issue | Завести в M5. Без playable HF композиции §17 не проверить. |
| **`p4_beat` preventive guards** (новый, S) | В brief — запреты gsap `Math.ceil` repeat overshoot и caption-exit-without-kill | Завести в M5. Сходимость gate:lint loop ~1 fix/iter — preventive окупается каждым прогоном. |
| **HOM-114** (Med, существует) | Pre-load SKILL.md sections | **Расширить scope** до three-source loader (см. §9). Тикет переезжает в M6 как часть архитектуры; в M5 закрывается комментарием «scope merged into M6 ticket #3». |
| **HOM-115** (Low, существует) | Tier-mapping consolidation | Оставить в M5, закрыть когда удобно. После §13 production-creative-guard станет менее критично. |
| **HOM-117** (Low, существует) | 24fps re-encode investigation | Оставить в M5, cosmetic. Не блокирует. |

**M5 acceptance:** на тестовом эпизоде fresh dispatch на прогретом cache даёт cache hits (HOM-160); transient timeout вызывает Pregel retry (HOM-158-fu); rewind через update_state клирует stale gate_results; HF Studio проигрывает реальную нашу композицию; смок Phase 4 не дёргает gate:lint redispatch на двух классах ошибок (preventive guards).

### M3 close (после M5, параллельно с M6 либо до)

HOM-77 family может закрываться **параллельно** с M6, поскольку никаких архитектурных зависимостей между ними нет. Прагматически: HOM-137 нужен для `gate:seam_policy` enforce-mode (M6 ticket §12.5 шипится в warn-only без HOM-137).

| Тикет | Что | Связь с M6 |
|---|---|---|
| **HOM-137** (High) | Root transitions | Разблокирует `gate:seam_policy` enforce-mode (M6 §12.5). Желательно закрыть до или во время M6. |
| **HOM-155** (Medium) | beat_kills auto-inserter | Дополняет `p4_beat` preventive guards из M5. Закрывать когда удобно. |
| **HOM-156** (Medium) | animation-map fix-or-justify | Снижает false-fail на gate:animation_map. Не блокирует M6. |

**M3 закрывается** когда HOM-137 + HOM-155 + HOM-156 закрыты, и HOM-77 (parent) переводится в Done.

### M6 — Resolved Brief & Profile Architecture (новый milestone, **заводим в Linear**)

13 тикетов §15. Внутри M6 — четыре волны (просто порядок исполнения, не отдельные milestones):

**Wave 1 — Brief substrate (тикеты §15.1+§15.2+§15.3).** State namespace `brief`, `resolve_episode_brief` нода, schema loosening, расширение HOM-114 до three-source loader, profile/brand skeleton. **Wave acceptance:** смена палитры в `brand/anticodeguy/palette.yaml` инвалидирует `p4_design_system` и нижестоящие; чистый `canonical`-прогон проходит как раньше; brief fingerprint в LLM cache keys.

**Wave 2 — Per-node context fan-out (§15.4+§15.5).** Converse interrupt + `narrative_context`; `neighbors_summary` инъекция. **Wave acceptance:** HOM-154-подобный re-run → `p3_strategy.rationale` явно ссылается на тон Converse; `p4_beat` видит `is_final=true` через neighbors_summary.

**Wave 3 — Content-quality gates (§15.6+§15.8).** `gate:edl_semantic_ok` (детерминированный shingle), `gate:brand_adherence`, `gate:cta_present`, `gate:seam_policy` (warn-only до HOM-137). **Wave acceptance:** EDL с phrase duplication → `gate:edl_semantic_ok` failed → `p3_edl_redispatch` → fixed.

**Wave 4 — Defence-in-depth + music (§15.7+§15.9+§15.10+§15.11).** LLM `p3_content_review`; music library substrate + selection + `p4_inject_music` + `gate:music_present`. **Wave acceptance:** HF композиция проигрывает background music + voice одновременно через нативный HF audio-mix; смена `intent.yaml.music.track_id` инвалидирует ровно `p4_inject_music`.

**Параллельно с любой волной (после wave 1):** §15.12 (production-creative model guard) + §15.13 (HITL approval tightening).

**Profile expansion (§15.14)** — добавление второго профиля (`explainer`) как доказательство расширяемости. Заводится sub-issue только после закрытия waves 1-4 и acceptance §17. **M6 закрывается** когда §17 acceptance проходит на минимум двух профилях.

### M4 — Production cutover (после M6)

| Тикет | Что | Зависимость |
|---|---|---|
| **HOM-78** (Low) | HITL user_review + feedback routing + final_render | Использует новые поля payload из M6 §14: `semantic_dup_result`, `brief_fingerprint`, `brand_adherence_result`. До закрытия M6 не имеет смысла начинать. |
| **HOM-79** (Low) | `/edit-episode` thin-client cutover | Финальная веха epic'а. Должна экспонировать новый brief-resolution layer (CLI override `--profile`, `--brand`, `--music-track`). |

## 16.1. Полный ticket map по milestones

| Milestone | Status | Тикеты |
|---|---|---|
| M1 | Done | — |
| M2 | Done | — |
| **M5** (close) | 72% | HOM-160 (move-in), HOM-158-fu (new), gate_results-reducer-fix (new), hf-black-screen (new), p4_beat-preventive-guards (new), HOM-114 (scope-merged-into-M6), HOM-115 (low pri), HOM-117 (low pri) |
| **M3** (close) | 90% | HOM-77 (parent), HOM-137, HOM-155, HOM-156 |
| **M6** (NEW) | 0% | §15.1 brief-substrate, §15.2 profile+brand-skeleton, §15.3 HOM-114-extended-three-source, §15.4 converse-narrative_context, §15.5 neighbors_summary, §15.6 gate:edl_semantic_ok, §15.7 p3_content_review, §15.8 brand+cta+seam-gates, §15.9 music-library-substrate, §15.10 music-selection-gate, §15.11 p4_inject_music, §15.12 prod-creative-guard, §15.13 hitl-tightening, §15.14 profile-expansion |
| **M4** | 0% | HOM-78, HOM-79 |

**Linear-операции, которые заводим этой спекой:**

1. **Завести M6** «Resolved Brief & Profile Architecture» в проекте `LangGraph pipeline migration`.
2. **Создать 14 sub-issues** в M6 (13 архитектурных + profile-expansion) с parent ID нового epic-issue под M6.
3. **Создать 4 cleanup тикета** в M5: `HOM-158-fu`, `gate_results-reducer-fix`, `hf-black-screen-investigation`, `p4_beat-preventive-guards`. Parent — HOM-154 либо отдельные с label `cleanup`.
4. **Перевести HOM-160 в M5** (сейчас без milestone, parent HOM-132).
5. **Расширить scope HOM-114** комментарием — переезжает в M6 как §15.3.

## 17. Acceptance criteria на уровне всей спеки

После закрытия M6 waves 1-4 критерий «работает не хуже чистой сессии» проверяется так:

1. Один и тот же raw-эпизод прогоняется через `/edit-episode` (граф) и через свежую `claude` сессию с промптом `«Используя скилл /video-use обработай видео»`.
2. Оба `final.mp4` и оба HF-результата смотрит человек.
3. **Acceptance:**
   - количество явных taste-косяков в graph-output ≤ количество в clean-session-output (обычно 0–1);
   - длительность в пределах ±10%;
   - семантических дублей нет ни там, ни там;
   - брэнд-палитра видна в Phase 4 graph-output, в clean-session — не требуется;
   - CTA-сцена с лого присутствует в graph-output (если `profile.cta.enabled`);
   - background music играет с фиксированным mix-volume под voice (нативный HF audio-mix);
   - editing `intent.yaml.music.track_id` инвалидирует ровно `p4_inject_music` (и ничего лишнего);
   - editing `brand/anticodeguy/palette.yaml` инвалидирует `p4_design_system` и нижестоящие;
   - editing `brief.resolved.narrative_context` инвалидирует `p3_strategy` + `p3_edl_select`.

**Зависимость от HOM-160.** Acceptance §17.3 требует чтобы fresh-thread на прогретом кэше не терял state channel-writes. Если HOM-160 ещё не закрыт — acceptance проверяется на одном непрерывном thread (resume через `update_state(as_node=...)`), не на cold dispatch.

**Поправка диагноза HOM-160 (2026-05-08).** Original ticket intuited cache-replay channel-writes loss; investigation showed langgraph 1.1.10 cache-replay applies all cached writes correctly cross-thread. Real root cause: `route_after_preflight` short-circuits Phase 3 when `final.mp4` exists (per CLAUDE.md "Idempotency" §, intentional), but Phase 4 cache keys (e.g. `p4_design_system._cache_key` extras) fingerprint `state.edit.strategy` — which is empty on a fresh thread because Phase 3 never ran. Fix: persist `<edit>/strategy.json` from `p3_strategy`; insert deterministic `rehydrate_skip_phase3` node on the skip edge to reload it. Architectural direction matches M6 (`brief.resolved.yaml` is on-disk source-of-truth). Implementation lands in this same PR family (HOM-160 branch); §17 acceptance harness can rely on rehydrate semantics.

Если acceptance не достигнуто — возврат в systematic-debugging, не «ещё одна правка поверх».

## 18. Open questions

1. **Profile selection — CLI override vs intent.yaml.** Решение: оба, CLI > intent.yaml. CLI для smoke / regression / one-off; intent.yaml для воспроизводимости эпизода.
2. **Brand kit version-pinning в `intent.yaml` для воспроизводимости старых эпизодов.** Brand-kit может эволюционировать, старые эпизоды должны быть rerunnable. Опции: (а) git-sha бренд-каталога в `brief.resolved.yaml`, (б) копия применённого brand snapshot в `episodes/<slug>/brand_snapshot/` на момент первого прогона. Recommend (а) — дешевле, восстанавливается через `git checkout`.
3. **Smart-pick трека по `narrative_context`.** LLM-нода читает mood/pacing из intent + meta-yaml треков, выбирает по семантике. MVP — детерминированный выбор; smart-pick — feature backlog.
4. **`license_note` enforcement.** Recommend: hard-fail в `resolve_episode_brief` для любого `brand_id != None`. Бренд = коммерческий контекст; пустая лицензия — orchestrator-bug.
5. **`canonical` profile и music.** Музыка — это орчестратор-house feature, не канон. В `canonical` профиле music отключена принудительно. Recommend: оставить как есть.
6. **Per-class music override hierarchy.** Сейчас `brand/<id>/music/defaults.yaml.per_profile[<profile_id>]` — простой словарь. Разрастётся при добавлении профилей. На сейчас оставляем простую форму; рефакторим на namespaced-yaml если станет неудобно.

## 19. Не входит в эту спеку

См. §2 (нон-цели). Дополнительно:
- Phase 4 canonical gaps (HOM-77 / HOM-137 / HOM-155 / HOM-156) — самостоятельный трек.
- HOM-78 (HITL user_review после Studio) — комплементарно.
- HOM-79 cutover в thin-client — после стабилизации baseline.
- Phase 1/2 (audio-isolation / pickup) — закрыты ранее, не пересматриваем.
- Upstream PRs в `video-use` (semantic-dedup taste rule) и `hyperframes` — async, делаются отдельно от этой работы.

## 20. Связь с CLAUDE.md / memories

Следует:
- `feedback_external_skill_canon` — никаких пересказов канона; per-node anchor list (§9) грузит секции дословно.
- `feedback_graph_decomposition_brief_references_canon` — брифы ссылаются на якоря `SKILL.md`, а не embed'ят канон. Brand-слой не дублирует канон, дополняет.
- `feedback_creative_nodes_flagship_tier` — формализуется в §13 production-guard.
- `feedback_topology_wiring_per_ticket` — каждый из 13 тикетов §15 требует topology wiring в том же PR.
- `feedback_branch_pr_workflow` — implementation тикетов через worktree → PR → review → merge.
- `feedback_langgraph_native_primitives` — `interrupt()` для Converse, `Send` для neighbors_summary через `p4_dispatch_beats`, `CachePolicy` для нод, `update_state(as_node=...)` для midpoint-resume в HOM-160 acceptance.

Спека написана с учётом ретро HOM-154; конкретные симптомы (semantic-дубль, отсутствие бренд-идентичности, cold fan-out beat) закрываются M6 waves 2-4 соответственно.
