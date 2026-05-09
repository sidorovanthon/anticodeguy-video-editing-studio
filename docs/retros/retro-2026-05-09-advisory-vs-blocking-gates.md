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
