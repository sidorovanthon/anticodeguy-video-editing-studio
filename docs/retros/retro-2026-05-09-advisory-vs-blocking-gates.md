# Retro: advisory vs blocking gates — `gate:animation_map` demotion

Дата: 2026-05-09. Тикеты: HOM-203 (umbrella), HOM-204 (routing change, merged
PR #119), HOM-205 (Studio surface), HOM-206 (brief cleanup), HOM-207 (этот
spec amendment + memory entry).

**Что произошло.** В попытке прокатать чистый E2E на `HOM-154` (после мерджа
HOM-156/201/202) граф халтнул на `gate:animation_map` iter=3 max с тремя
классами violation'ов: caption-strip `collision` (by design — прозрачный текст
поверх контента), hairline-decoration `degenerate` (measurement artifact —
1px-элементы с `opacity:0` entrance дают zero-bbox samples) и end-of-comp
dead-zones >1.0s. LLM-justify ветка из HOM-156 покрывала только
`paced-fast`/`paced-slow`; остальные классы продолжали hard-fail'иться. 415с
recording, $-десятки, ноль реальных дефектов в выходе.

**Корневая причина — canon-deviation.** Аудит четырёх независимых сессий, где
агент использовал глобальный `hyperframes` skill в чистую (`docs/
clean-skills-usage-examples/hyperframes/{0e14ed30,5509a8c6,9cfded3d,
bd562b6c}.jsonl`), показал **0/4 invocations** of `animation-map.mjs`. SKILL.md
§"Quality Checks" §"Animation Map" описывает helper как опциональный QA tool
(*"check every flag — fix or justify"*) — не как blocking gate. Мы повысили
advisory-tooling до blocking-mechanism и получили false-positive retry-loop'ы
именно на тех классах flag'ов, которые canon-author никогда не проверяет.

**Фикс.** HOM-203 (sub-issues 204..207) демотировали `gate:animation_map` до
advisory: helper по-прежнему запускается, JSON парсится, findings пишутся в
`advisory_findings` поле gate-record'а, Studio показывает их оператору — но
router больше не отправляет на `p4_redispatch_beat`. HOM-204 закрыл routing,
HOM-205 — Studio surface, HOM-206 — переписал brief'ы (убрав ложное
"This task is canon"), HOM-207 (этот retro) — закрепил doctrine в spec
§6.2 и memory.

**Урок — design-time check для будущего.** Перед промоцией любого helper'а в
blocking gate: процитировать конкретный Hard Rule в live SKILL.md, который он
энфорсит. Если цитата — это "Quality Checks" / "QA" / "scan" / "may run" /
"fix or justify", gate ДОЛЖЕН быть advisory. Spec §6.2 теперь несёт это правило
явно; memory entry `feedback_advisory_vs_blocking_gates` дублирует для
session-level быстрого pickup'а. Pattern parent — `feedback_external_skill_canon`
("stricter than canon" — это запах).

**Cross-links.** HOM-77 §3 уже подсвечивал ту же форму ("если наш v4 strict-gate
трактует каждый flag как hard fail, мы строже канона"). HOM-156 был первый
half-step. HOM-203 завершил demotion. Соответствующие изменения в spec'е и
memory сделают так, что следующая инстинктивная попытка "давай сделаем gate
для X helper'а" остановится на verification-step ещё до написания routing-кода.

---

## Amendment — HOM-212 per-flag carve-outs (2026-05-09)

**Что добавилось.** HOM-203 wholesale-advisory оказался слишком coarse. Из
`gate:animation_map` findings три семантически разных класса:

* `pending_classify` (paced-fast / paced-slow) — LLM-judgement territory; **advisory** ✅ (это HOM-203 покрыл правильно).
* `always_fix` aggregate — структурно неоднородный: каноническая caption-цепочка
  `#cg-N` (set+fromTo+to+to+set) и chrome-decoratives (entrance + ambient yoyo
  на одном и том же элементе) дают bbox-overlap **по построению** — это
  false-positives, не дефекты авторинга. А вот collision на content-element
  (e.g. `.headline`), `offscreen` и `invisible` — структурные нарушения,
  фиксятся переавторингом сцены.
* `dead_zones` — visible-but-static intervals; ≤ N секунд это намеренный
  pacing beat, > N секунд — провисание. Threshold-based.

**Фикс HOM-212.** Per-flag verdict:

* `collision` blocking ⟺ селектор НЕ caption-canon (`^#cg-\d+$`) И НЕ chrome-
  decorative substring (по умолчанию: `grain`, `glow`, `hairline`, `vignette`,
  `overline`, `corner-mark`, `footer-mark`, `caption-strip`, `margin-tick`).
  Carve-out list — operator-tunable через
  `gates.animation_map.collision_decorative_allowlist` в `graph/config.yaml`.
* `degenerate` blocking ⟺ max(width, height) ≥ 2 px по всем bbox-samples.
  1-2 px hairlines / margin-ticks / underscores carved out by construction.
  Threshold — `gates.animation_map.degenerate_min_bbox_px`, default 2.0.
* `offscreen` / `invisible` — unconditionally blocking. На canonical fixture
  HOM-211 audit'е таких findings нет, FP-класс не идентифицирован, оставляем
  блокирующими (audience элемент не видит — это всегда дефект).
* `dead_zones` blocking ⟺ max duration > threshold. Default 2.0 s, через
  `gates.animation_map.dead_zone_threshold_s`. Routing — **не redispatch**:
  dead-zones живут на root-timeline (composition duration / scene layout),
  это `p4_assemble_index` concern, а не beat-author concern. Dead-zone-only
  blocking → halt с явным notice'ом.

**Routing.** `route_after_animation_map` имеет 4 исхода:

* infrastructure failure → halt
* blocking + beat-actionable (collision/degenerate/offscreen/invisible) + iter<3 → `p4_redispatch_beat`
* blocking + iter≥3 ИЛИ только dead-zone → halt
* pending_classify только → `gate_animation_map_classify`
* clean / advisory only → `gate_snapshot`

Edge `gate_animation_map → p4_redispatch_beat` восстанавливает то, что
HOM-204 убрал wholesale (PR #119). Симметрично, но gated на per-flag
classification — caption canon и chrome decoratives остаются advisory,
как HOM-203 хотел.

**Notice format.** Blocking notices начинаются с `gate:animation_map: BLOCKING — `
(prefix load-bearing для Studio severity routing); advisory остаются
`gate:animation_map: advisory — ` per HOM-205. Infrastructure failure —
`infrastructure failure (...)`. Три prefix'а, три severity tier'а.

**Урок.** Wholesale advisory → wholesale blocking — две ошибочные крайности.
Правильный design point: per-flag classification with named carve-outs that
are config-tunable. HOM-211 reviewer caveat поймал бы это раньше, если бы
HOM-203 audit включал не только "did the canonical author invoke
animation-map.mjs?" но и "*if* they did, *which* findings would they actually
fix?" — на canonical fixture'е ответ был бы: 0 из 109 collision (все на
captions/chrome), 0 из 5 degenerate (все на 1px hairlines). HOM-203's coarse
advisory был эмпирически правильным для тех findings; HOM-212 расширяет
покрытие на ту малую долю findings, которые all-and-only-actionable —
без re-introducing redispatch loop'а.

**Spec/memory cross-link.** Spec §6.2 в `2026-05-02-langgraph-pipeline-design.md`
уже несёт правило "advisory unless canon mandates"; HOM-212 не отменяет это,
а уточняет: gate может быть **advisory by default + per-flag blocking carve-outs**
для подсчитываемо-малого подмножества findings, где canon-author *would*
fix-on-sight (a content-element collision, an offscreen-throughout tween,
а 4-secondный tail dead zone) и где LLM-redispatch может реально починить.
