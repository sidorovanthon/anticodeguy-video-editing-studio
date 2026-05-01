# Design: Retro 2026-05-01 action items — sequenced plan

**Дата:** 2026-05-01
**Источник retro:** `docs/retros/retro-2026-05-01-liquid-glass-subcomp-loader.md`
**Скоуп:** конвертация 6 retro findings + meta-failures в атомарные единицы работы.

---

## Цель

Закрыть retro findings так, чтобы:

1. Конкретные баги/недочёты Phase 4 были устранены в brief-е, MEMORY и (если подтвердится) в коде scaffold-а.
2. Главные failure mode-ы первичного оркестратора получили **структурную защиту**, а не только разовый патч:
   - inline-execution на parallel-dispatch,
   - canon drift (на этих и будущих находках),
   - overwhelm / chase-by-symptom при пустом выходе Phase 4,
   - premature upstream-blame,
   - drift в новых soft-modal формулировках.
3. План сохранил canon: всё, что мы добавляем в brief/CLAUDE.md/memory, **слоится перед canon как triage или extension**, а не пре-эмптирует его.

## Не-цель

- Не редактируем upstream HF/video-use исходники (CLAUDE.md «External skill canon — non-negotiable»).
- Не файлим upstream issues до Phase 0 investigation.
- Не пытаемся починить orchestrator-side баги до того, как Phase 0 определит, что они orchestrator-side.

---

## Структура работ

### Memory batch (immediate, до всех PR)

Локальные записи в `C:\Users\sidor\.claude\projects\C--Users-sidor-repos-anticodeguy-video-editing-studio\memory\`. Не PR.

**4 записи пишутся сразу:**

| Файл | Тип | Сжатый контент |
|---|---|---|
| `feedback_brief_consider_means_mandatory.md` | feedback | В Phase 4 brief `Consider`/`SHOULD`/`recommended` — sugar для mandatory orchestrator-house mechanics. Verified 2026-05-01: пропустил parallel-dispatch под `Consider` → 2× wall-time. |
| `feedback_studio_player_empty_state.md` | feedback | HF studio показывает «Drop media here» пока композиция не выбрана в sidebar — это default UI. Verify overlay-и через `npx hyperframes snapshot` ДО studio launch. |
| `feedback_text_box_overflow_glyph_bearing.md` | feedback | `data-layout-allow-overflow` (canon escape, SKILL.md §"Visual Inspect") применим также к glyph-bearing artifacts на heavy display fonts. **Phrase as canon-extension, не canon-fix.** |
| `feedback_wcag_headless_opacity_artifact.md` | feedback | Если все WCAG warnings имеют `fg: rgb(0,0,0)` AND CSS задаёт visible color AND elements используют `opacity: 0` в entrance `fromTo` — это headless-screenshot артефакт. Document and proceed. **Triage-step ПЕРЕД canon-итерацией, не вместо.** |

**2 записи откладываются до Phase 0:**

| Файл | Зависит от | Причина hold |
|---|---|---|
| Замена `feedback_multi_beat_sub_compositions.md` (новое имя `feedback_hf_subcomp_loader_*.md` — финал зависит от root cause) | Phase 0 | Не знаем: orchestrator-side bug или upstream. Premature canonization хуже чем no-memory. |
| `feedback_lint_regex_repeat_minus_one_in_comments.md` | Phase 0 | То же — может оказаться, что в bare scaffold lint не triggers, и баг в нашем generated content. |

**Старая запись `feedback_multi_beat_sub_compositions.md`:** не трогаем до Phase 0. После Phase 0 — удалить (или переименовать) и заменить на корректную.

---

### PR-1 `phase4/diagnostics-and-triage`

**Файл:** `.claude/commands/edit-episode.md` (Phase 4 brief).

**Скоуп:**

1. **WCAG headless-artifact triage step.** Добавить ПЕРЕД canon-итерацией по палитре, не заменяя её.

   ```
   Triage step (apply first): if all warnings have fg: rgb(0,0,0)
   AND elements set a visible color in CSS AND elements use opacity: 0
   in entrance fromTo — это headless-screenshot artifact. Document
   the symptom in DESIGN.md → "WCAG Validator — Headless Artifact"
   и proceed. Otherwise apply canon's palette-family iteration
   (HF SKILL.md §"Contrast").
   ```

2. **Snapshot interpretation rule.** Привязать к Beat→Visual Mapping, чтобы не противоречить канону fade-in offset (SKILL.md:276 — 0.1-0.3s).

   ```
   Empty snapshot at a timestamp where DESIGN.md → Beat→Visual Mapping
   указывает visible element = композиция сломана; не proceeed to studio.
   Empty snapshot в первые 0.3s от beat-start — canonical entrance offset,
   не bug. Snapshot is definitive only when checked against expected-visible
   list, not in absolute terms.
   ```

3. **Diagnostic entry-point — Phase 4 output empty/broken.** Структурный фикс против overwhelm/chase-by-symptom. Новая секция в Phase 4 brief.

   ```
   Diagnostic entry-point — when Phase 4 output is unexpectedly empty
   or broken. Before forming any hypothesis, run in this order:
     1. npx hyperframes compositions → verify sub-comp `elements`/`duration`
        non-zero. If `0 elements / 0.0s` for sub-comp listed in
        data-composition-src → mounting failed, do NOT debug content/styles.
     2. npx hyperframes snapshot --at <beat_timestamps from DESIGN.md>
        → verify expected-visible per Beat→Visual Mapping.
     3. Only after (1) and (2) report definite results, form hypotheses.

   Anti-pattern: gradient-descend по симптомам (track-index reshuffles,
   file rename, restart, malformed div) до того как (1) и (2) сделаны.
   Retro 2026-05-01 §2.3 — потерянных 40 мин.
   ```

**Canon-check:** все три добавления — triage/qualifier/diagnostic-ordering. Не replace, не override. Совместимы с SKILL.md §"Contrast", §"Visual Inspect".

**Output Checklist additions:** нет — это диагностические правила, не gate-ы.

**Test plan PR:** пересмотреть Phase 4 brief как целое, убедиться что три добавления не противоречат соседним правилам (например, не дублируют существующий «Visual verification» блок lines 207-214).

---

### PR-2 `phase4/soft-language-audit`

**Файл:** `.claude/commands/edit-episode.md` (весь brief).

**Скоуп — три слоя:**

1. **Preamble convention** (top of Phase 4 brief, либо top of whole file):

   ```
   Conventions for this brief: every directive is mandatory unless
   tagged (optional, skip without consequence). Treat soft modals
   (Consider / SHOULD / recommended / may / might) as bugs to report.
   ```

2. **Mechanical audit + disposition table.**

   - Grep на brief-е: `\b(consider|should|recommend(ed)?|strongly?|may|might|encourage)\b` (case-insensitive).
   - Каждый hit получает один из 3 label-ов:
     - `imperative` — flip body to imperative verb + (если checkable) добавить Output Checklist verifier.
     - `explicit-optional` — tag `(optional, skip without consequence)`.
     - `leave-as-is` — модал не модальный (например «may diverge from the script» — описание факта, не директива).
   - Disposition table показывается user-у на approval ДО любых правок.
   - После применения — re-grep; каждый оставшийся hit либо tagged, либо approved leave-as-is.

3. **Per-flip Output Checklist verifiers (где checkable).** Главный кейс — §2.6 parallel-dispatch:

   ```
   **Beat authoring — parallel-agent dispatch (mandatory for ≥ 3 beats).**
   After DESIGN.md and expanded-prompt.md exist, dispatch one sub-agent
   per beat via the `superpowers:dispatching-parallel-agents` skill.
   Each agent gets the beat's section from expanded-prompt.md and writes
   its compositions/beat-{N}-{slug}.html independently. Main session waits,
   then assembles the root index.html. Do not write beats sequentially
   in the main session.

   Output Checklist: Beats authored by ≥ 3 parallel sub-agents (verifiable
   by checking session transcript for parallel `Agent` tool calls during
   Phase 4 — if zero parallel dispatches in transcript, Phase 4 is incomplete).
   ```

   Канонический mirror: video-use SKILL.md Hard Rule 10 — «Parallel sub-agents for multiple animations. Never sequential.» Cross-skill consistency.

**Canon-check:** soft-language audit — pure orchestrator-house brief polish, не трогает canon. Ссылка на video-use Hard Rule 10 в commit message укрепляет обоснование.

**Risk:** false-flip leave-as-is модала на imperative. Mitigation — disposition table с explicit user approval.

---

### PR-3 `meta/bare-repro-rule`

**Файл:** `CLAUDE.md`.

**Скоуп:** один абзац в секцию «External skill canon» (или новой секцией «Investigation methodology»):

```
**Bare-repro before upstream-blame.** Before claiming any HF or
video-use behavior is an upstream bug or doc-bug, reproduce in
a bare scaffold (`npx hyperframes init` / clean video-use install).
If bare-repro succeeds while our pipeline fails — the bug is
orchestrator-side. Investigate scripts/scaffold_*.py, glue scripts,
and brief deltas before opening upstream issue.

Verified necessary 2026-05-01: three suspected upstream bugs from
retro (sub-comp loader, lint regex on comments, <template> doc-bug)
all required investigation before claim.
```

**Canon-check:** generalizes Phase 0 methodology в постоянное правило. Не трогает canon, защищает canon от premature blame.

---

### PR-4 `hooks/parallel-dispatch-detector`

**Файл:** `.claude/settings.json` (hooks секция) + опционально `scripts/check-parallel-dispatch.py` если логика сложнее inline.

**Скоуп:** PostToolUse или SessionEnd hook.

**Trigger condition:**
- В session transcript-е появился новый `episodes/<slug>/hyperframes/index.html`.
- Этот index.html ссылается на DESIGN.md / expanded-prompt.md с ≥ 3 beats.
- В session transcript-е за время от scaffold до index.html — ноль parallel `Agent` dispatches с описанием beat-authoring.

**Action:** non-blocking warning to user через stderr или user-prompt-submit message:

```
[parallel-dispatch-detector] Phase 4 produced index.html with ≥ 3 beats
but no parallel Agent dispatches were detected in this session.
This may indicate sequential beat authoring (retro 2026-05-01 §2.6).
If intentional (e.g., resumed session), ignore.
```

**Canon-check:** hook — orchestrator-side machine-enforce. Не трогает HF/video-use canon. Mirrors video-use Hard Rule 10 в проверяемой форме.

**Risk:** false positives на resumed/skip-build runs где Phase 4 был пропущен. Mitigation — точная trigger-condition (новый index.html в этой сессии, не существующий).

**Test:** прогон на эпизоде с уже готовым `hyperframes/index.html` (skip-build path) → hook не triggers. Прогон с дисптачем 3 параллельных Agent-ов → не triggers. Прогон с sequential authoring → triggers.

---

### Phase 0 investigation `investigate/subcomp-loader-bare-repro`

**Изолированный worktree** (не PR на main, отдельная исследовательская ветка). Может выполняться параллельно с PR-1..4.

**Цель:** определить root cause трёх retro findings — orchestrator-side или upstream.

**Подготовка (canon respect, обязательно перед bare-репро):**
- Прочитать `~/.agents/skills/hyperframes/SKILL.md` § "Composition Structure" (lines 159-185) — canon-blessed pattern.
- Прочитать `~/.agents/skills/hyperframes/references/motion-principles.md` — load-bearing GSAP rules для sub-comp (referenced from SKILL.md:74 «prefer `gsap.fromTo()` in sub-compositions»).

**Bare-repro setup:**
- Создать `tmp/bare-hf-repro/` (gitignored).
- `npx hyperframes init` без orchestrator scaffold.
- Использовать **canonical `<template>` pattern из SKILL.md:165-183** — не модифицировать.
- Минимальный repro для каждого finding:
  1. **§2.1 sub-comp loader.** Mount `<div data-composition-src="compositions/foo.html" data-start="0" data-duration="5" data-track-index="1">`. Sub-comp с `<template>` + visible static content. Render. Если красный виден — orchestrator-side. Diff `tmp/bare-hf-repro/` vs episode `hyperframes/` после нашего scaffold-а — найти дельту.
  2. **§2.4 lint regex.** Минимальный sub-comp с комментарием `// avoid repeat:-1`. `npx hyperframes lint`. Если triggers в bare — upstream. Если не triggers — что-то в нашем generated content создаёт литерал.
  3. **§2.3 `<template>` в `compositions` CLI.** `npx hyperframes compositions` на bare project. Если sub-comp viден с правильным `elements`/`duration` — наш scaffold ломает; иначе upstream loader edge case.

**Подозреваемые orchestrator-side дельты (для §2.1 main suspect):**
- хардлинк `final.mp4` как одновременно `<video>` и `<audio>` источник.
- `data-has-audio="false"` workaround (upstream #586).
- `hyperframes.json` / `meta.json` overrides из нашего `scripts/scaffold_hyperframes.py`.
- pre-populated `index.html` template — diff с bare-init output.
- GSAP pattern: `tl.from()` vs `tl.fromTo()` в sub-comp (SKILL.md:74).

**Outcomes:**
- **Orchestrator-side:** документировать дельту, PR-5 — фикс в `scripts/scaffold_hyperframes.py` или там, где найдена; brief обновляется реальным root cause; memory entries пишутся с корректным контентом.
- **Upstream:** документировать минимальный bare-repro; PR-5 — brief workaround + GH issues; memory entries как изначально.

---

### PR-5 (post-investigation, scope TBD)

Зависит от Phase 0 outcomes. Два возможных скоупа:

**Если orchestrator-side:**
- Code fix в `scripts/scaffold_hyperframes.py` (или wherever).
- Brief update — убрать «broken in 0.4.41» формулировку, заменить на корректное описание fix-а.
- Memory: написать корректные `feedback_hf_subcomp_loader_*.md` и `feedback_lint_regex_*.md` с реальным root cause (orchestrator-side).
- Старую memory `feedback_multi_beat_sub_compositions.md` — удалить.

**Если upstream:**
- Brief workaround (как изначально предлагал retro).
- GH issues на heygen-com/hyperframes с минимальным bare-repro (готов из Phase 0).
- Memory: `feedback_hf_subcomp_loader_broken.md` (или с другим именем, отражающим upstream nature) + `feedback_lint_regex_repeat_minus_one_in_comments.md`.
- Старую `feedback_multi_beat_sub_compositions.md` — удалить.

---

## Sequencing

```
Memory batch (4 записи)        ────►  immediate
                                       │
PR-1 phase4/diagnostics-and-triage  ─┐│
PR-2 phase4/soft-language-audit     ─┤│  parallel
PR-3 meta/bare-repro-rule           ─┤│
PR-4 hooks/parallel-dispatch-detector┤│
                                     ││
Phase 0 investigation (worktree)    ─┘│  parallel
                                       │
                                       ▼
                              PR-5 (scope from Phase 0)
                                       │
                                       ▼
                              Memory batch (held 2 entries)
                                       │
                                       ▼
                              Удаление старой feedback_multi_beat_sub_compositions.md
```

PR-1..4 независимы и могут merge-иться в любом порядке. Phase 0 — параллельно. PR-5 — последний.

---

## Failure mode coverage (план vs retro)

| Failure mode | Защита |
|---|---|
| Inline-execution на parallel-dispatch | PR-2 (imperative + verifier + preamble) + memory + PR-4 (machine-enforce) |
| Canon drift на конкретных findings | PR-1 (triage formulations) |
| Overwhelm / symptom-chase | PR-1 (diagnostic entry-point) |
| Premature upstream-blame | PR-3 (bare-repro правило) + Phase 0 как методология |
| Drift на NEW soft-modal | PR-2 preamble convention |
| Drift вне soft-modal формулировок | PR convention: каждый PR на edit-episode.md перечисляет SKILL.md секции, против которых проверены изменения (мягкая защита; не отдельный PR, добавляется в PR template или CLAUDE.md один раз) |

---

## Out of scope

- Upstream issues file-инг (откладывается до Phase 0).
- Любые правки в `~/.agents/skills/hyperframes/` или `~/.claude/skills/video-use/` — внешний canon, read-only.
- Расширение `superpowers:dispatching-parallel-agents` skill — этот skill используется как есть.
- Переработка `scripts/pickup.py`, `scripts/isolate_audio.py`, `scripts/remap_transcript.py` — retro их не задевает.

---

## Open questions

- (Минор) Где именно положить preamble convention в PR-2 — top of Phase 4 brief или top of file? Решается при PR-2 implementation, не блокирует план.
- (Минор) PR-4 hook trigger heuristic для «новый index.html в этой сессии» — может потребовать чтения transcript-а через CC machinery; точная форма решается при implementation.
- (Минор) Имя финального memory-файла для §2.1 (после Phase 0) — зависит от root cause.

Все три — implementation-level, не дизайн-level.
