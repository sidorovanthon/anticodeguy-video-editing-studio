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

**Профиль — first-class абстракция, не bool-флаг.** Каждый профиль фиксирует видео-класс: `talking-head-portrait`, `explainer`, `long-form`, `horizontal-product-promo`, …. У профиля свои дефолты pacing'а, structural archetype, rhythm template, captions-стратегии, плотности анимации, музыкального бренча (ducking aggressiveness, allowed mood). `canonical` — пустой профиль для regression-режима: чистый канон без бренд- и класс-опинионов.

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
      cta_scene.html                  # детерминированный CTA-блок
      intro_scene.html                # опционально
    music/
      tracks/
        editorial-warm-1.mp3
        editorial-warm-1.meta.yaml    # bpm, mood, length, license, lufs, loop_safe
        tutorial-clean-2.mp3
        tutorial-clean-2.meta.yaml
        ...
      defaults.yaml                   # default trackId, per-profile preferences, ducking
      _runtime/
        ducking.js                    # HF-runtime hook template (если нужно ducking)

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
  ducking_aggressiveness: medium
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
volume_db: -18
fade_in_s: 0.5
fade_out_s: 1.0
ducking:
  enabled: true
  target_db: -28
  attack_ms: 120
  release_ms: 400
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
        "volume_db": float,
        "fade_in_s": float,
        "fade_out_s": float,
        "ducking": dict,
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
2. Иначе после `p3_pre_scan` — нода `p3_converse` делает `interrupt({...})` с pre-scan summary + 8-полевой анкетой канонического Step 3 (video-use SKILL.md L87, verbatim):

> «Converse. Describe what you see in plain English. Ask questions *shaped by the material*. Collect: content type, target length/aspect, aesthetic/brand direction, pacing feel, must-preserve moments, must-cut moments, animation and grade preferences, subtitle needs.»

Ответ человека пишется в `episodes/<slug>/edit/narrative_context.md` (свободный markdown) и в `state.brief.narrative_context`. Состояние brief после Converse — пересохраняется в `brief.resolved.yaml`, fingerprint бампается.

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

2. **Sub-list-item extraction.** Step 3 «Converse» в video-use SKILL.md L87 — пункт списка внутри `## The process`, без своего H2-якоря. Loader умеет извлекать markdown-list-item по index или по startswith-тексту.

3. **Cache-key включает sha256 каждого подгруженного блока** — обновился канон, инвалидировалась только нода, чьи якоря изменились (улучшение над ручным `_CACHE_VERSION` бампом).

4. **Snapshot-тесты на каждый используемый якорь** обоих скиллов и каждой brand/profile-секции.

**Anchorability check:** обе SKILL.md и referenced files имеют unique-text H2 заголовки в пределах файла — anchorable без disambiguation. Проверено 2026-05-07.

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

**Каноническое обоснование mechanical-inline подхода:** `references/motion-principles.md` L142 (verbatim): *«don't summarize or shorten them»*. Канон сам требует не пересказывать load-bearing rules — паста идёт verbatim.

## 10. `neighbors_summary` injection

В `p4_prompt_expansion`, `p4_beat`, `p4_plan` (опционально) прокидывается сводка соседних сцен, чтобы closed-context fan-out соблюдал кросс-сценные канон-правила.

**Канонические места, требующие соседского контекста (verbatim, hyperframes):**
- SKILL.md L249–252, Scene Transitions Non-Negotiable Rule 3: *«NEVER use exit animations except on the final scene… The transition IS the exit.»*
- `transitions.md` L22: *«Pick ONE primary (60-70% of scene changes) + 1-2 accents.»*
- `transitions.md` L40-49 (Narrative Position).
- `beat-direction.md` L88-96 (Rhythm Planning).
- `beat-direction.md` L54: *«1-2 shader transitions (the hero reveal + the CTA)»*.
- `video-composition.md` L52-54: *«Vary motion per scene — don't repeat the same ambient pattern.»*

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

## 11. Music — selection, application, ducking

**Selection at resolve-time** (см. §6). Brief гарантирует наличие `music.asset_path`, валидной license_note, измеренного LUFS.

**Application — новая детерминированная нода `p4_inject_music`** между `p4_assemble_index` и `gate:design_adherence`:

- Читает `state.brief.music`.
- Пишет `<audio>` слой в `index.html` верстатимом (timeline-зарегистрированный, seek-driven, как требует HF-канон).
- Если `ducking.enabled` — подключает `brand/<brand_id>/music/_runtime/ducking.js` и регистрирует hook на `window.__hfAudio` через паттерн HF audio-adapter'а (см. waapi/three skills для аналогичных runtime-hook-паттернов).
- На `gate:music_present` failure — нода-pre-flight в самой `p4_inject_music` падает с прескриптивным сообщением, что чинить.

**Альтернатива A (через `p4_assemble_index` brief).** Рассмотрена и отклонена: LLM может «забыть» ducking/fade параметры, потребуется gate с corrective loop, удорожает токены без выигрыша. Деттерминированная инъекция чище.

**Volume normalization.** Треки нормализуются на ingest вручную (LUFS измеряется и записывается в `<track>.meta.yaml`). `gate:music_present` валидирует `lufs_integrated` в окне `[-18, -14]` LUFS; вне окна — failure с инструкцией нормализовать.

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

После `p4_assemble_index`. Каждый hex-цвет в композиции присутствует в `palette.yaml`; каждый `font-family` ссылается на разрешённую типографику (или fallback chain из brand kit). Канон-обоснование: hyperframes SKILL.md L348 описывает ручной agent-level чек *«every hex value in the composition appears in design.md's palette»* — формализуем.

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
11. **`p4_inject_music` нода + ducking runtime template** (§11). DoD: smoke композиция реально проигрывает аудио в HF Studio с ducking'ом.
12. **Production-creative model guard** (§13). DoD: тест что cheap-tier на production падает; canonical-режим не падает.
13. **HITL approval tightening** (§14). DoD: тест что empty submit в non-canonical не approve.

## 16. Sequencing — milestones

**Milestone A — Brief substrate (тикеты 1+2+3).** Без него остальное не закрепляется. Acceptance: смена палитры в `brand/anticodeguy/palette.yaml` инвалидирует `p4_design_system` и нижестоящие; чистый `canonical`-прогон проходит как раньше.

**Milestone B — Per-node context fan-out (тикеты 4+5).** Converse + narrative_context, neighbors_summary. Acceptance: HOM-154 повтор → `p3_strategy.rationale` явно ссылается на тон Converse; `p4_beat` видит `is_final=true` без посторонних подсказок.

**Milestone C — Content-quality gates (тикеты 6+8).** Detect-and-route на content-уровне. Acceptance: подсунутый EDL с phrase duplication → `gate:edl_semantic_ok` failed → redispatch → fixed.

**Milestone D — Defence-in-depth + music (тикеты 7+9+10+11).** LLM content-review поверх детерминированных гейтов; music library и инъекция. Acceptance: финальная HF композиция проигрывает background music с ducking'ом под голос.

**Milestone E — Profile expansion (тикет = эпик-extension).** Добавляем второй профиль (например `explainer`) как доказательство расширяемости. Не пишем, пока MVP единственного профиля не работает.

**Параллельно (vendor-tier, любой момент после Milestone A):** тикеты 12+13.

## 17. Acceptance criteria на уровне всей спеки

После Milestone'ов A+B+C+D критерий «работает не хуже чистой сессии» проверяется так:

1. Один и тот же raw-эпизод прогоняется через `/edit-episode` (граф) и через свежую `claude` сессию с промптом `«Используя скилл /video-use обработай видео»`.
2. Оба `final.mp4` и оба HF-результата смотрит человек.
3. **Acceptance:**
   - количество явных taste-косяков в graph-output ≤ количество в clean-session-output (обычно 0–1);
   - длительность в пределах ±10%;
   - семантических дублей нет ни там, ни там;
   - брэнд-палитра видна в Phase 4 graph-output, в clean-session — не требуется;
   - CTA-сцена с лого присутствует в graph-output (если `profile.cta.enabled`);
   - background music играет с заданным ducking'ом;
   - editing `intent.yaml.music.track_id` инвалидирует ровно `p4_inject_music` (и ничего лишнего);
   - editing `brand/anticodeguy/palette.yaml` инвалидирует `p4_design_system` и нижестоящие;
   - editing `brief.resolved.narrative_context` инвалидирует `p3_strategy` + `p3_edl_select`.

**Зависимость от HOM-160.** Acceptance §17.3 требует чтобы fresh-thread на прогретом кэше не терял state channel-writes. Если HOM-160 ещё не закрыт — acceptance проверяется на одном непрерывном thread (resume через `update_state(as_node=...)`), не на cold dispatch.

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

Спека написана с учётом ретро HOM-154; конкретные симптомы (semantic-дубль, отсутствие бренд-идентичности, cold fan-out beat) закрываются Milestone'ами B+C+D соответственно.
