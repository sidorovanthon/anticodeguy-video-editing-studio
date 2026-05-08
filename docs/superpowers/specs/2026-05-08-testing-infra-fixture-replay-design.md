# Testing infra — fixture-replay harness + per-ticket DoD update

**Дата:** 2026-05-08
**Статус:** Draft, готовится PR
**Контекст-якоря:**
- ретро HOM-154 (semantic-дубль в EDL, чёрная HF-композиция, gate:lint redispatch loop)
- спека M6 `docs/superpowers/specs/2026-05-07-resolved-brief-profiles-brand-architecture.md` §15-§17 (DoD per ticket, acceptance criteria)
- CLAUDE.md §"LangGraph primitives — search docs before rolling custom"
- memory `feedback_creative_nodes_flagship_tier`, `feedback_langgraph_native_primitives`

---

## 1. Problem statement

После закрытия M5 cleanup-волны (HOM-160, HOM-162, HOM-163, HOM-164, HOM-165) M5 effectively готов к закрытию, M6 — большой архитектурной волне — начинается следующим шагом. M6 будет менять брифы, schema'ы и cache-fingerprints у ~10 LLM-нод. Текущий per-ticket DoD CLAUDE.md требует «real-CLI Haiku smoke», что эмпирически создаёт false economy:

- Haiku-output провоцирует gate:lint / gate:design_adherence redispatch loop (HOM-154 ретро finding #5: convergence ~1 fix/iter, 26→25→21 за три итерации); три re-dispatch'а Sonnet'а за один проход обходятся дороже одного успешного Opus-вызова.
- Synthetic state в smoke-скриптах не ловит регрессии, которые поверх реального graph state ловятся: HOM-154 показал что smoke'и на болванках проходили, а реальный эпизод спотыкался на каждом шагу.

Корневой класс проблемы: M6 work хочет валидировать «граф работает корректно», а не «LLM отвечает качественно». Текущая инфраструктура смешивает эти два класса теста и платит за оба каждый прогон. Решение — формальный testing-infra слой, который разделяет:
- **Class A** (структурные регрессии: Jinja brief content, Pydantic schemas, topology, cache fingerprint logic) — ловится бесплатно.
- **Class B** (поведенческие: реальный LLM с новым брифом производит right-shape output, downstream-ноды парсят его) — paid one-shot record + replay.

## 2. Цель и нон-цели

**Цель:** ввести трёхслойную тестирующую пирамиду (L0 cheap structural / L1 fixture-replay / L2 manual wave acceptance), основанную на нативном LangGraph `CachePolicy + SqliteCache` примитиве. Зафиксировать prewarmed `cache.db` для канонического fixture-эпизода в репозитории. Обновить per-ticket DoD в CLAUDE.md: «Haiku smoke» → «fixture-replay на production tier».

**Нон-цели:**
- GitHub Actions / CI integration — non-goal в этой спеке (архитектура CI-ready, добавляется без переделок). Текущая интеграция = `pytest` локально перед `gh pr create` + reviewer-агент проверяет fixture diff в PR.
- Multi-fixture episodes (один portrait talking-head канонический, остальные — добавляются по необходимости).
- Quality assertions на content поверх structural validation (M6 wave 3 gates делают это отдельно — `gate:edl_semantic_ok`, `gate:brand_adherence` etc; testing infra ловит structural breakage, не качество выхода).
- Phase 1/2 fixture details (transcribe + audio-isolate уже cache-друженные через `make_key`; первый прогон fixture-эпизода один раз заплатит ElevenLabs/ffmpeg, потом cache hits).

## 3. Архитектура — три слоя пирамиды

```
L2  manual wave acceptance         paid one-shot, ~$1-3/wave
    full real-tier prod run на fixture, глазная сверка с спека M6 §17
                ↓
L1  fixture-replay graph runs      $0 после первого record
    pytest test_graph_replay.py — node-under-test делает реальный вызов
    (recorded), всё остальное — cache hit из committed cache.db
                ↓
L0  structural / cheap            $0 на каждом push'е
    unit tests, brief snapshot, schema migration, topology test,
    fingerprint invalidation assertion, verify_anchors() startup check
```

**L0 — Structural ($0):**
- Pydantic schema unit tests (включая schema loosening migrations — M6 §7).
- **Brief snapshot tests** — `tests/snapshots/briefs/<node>.txt`; Jinja-render → string compare; PR diff читаемый.
- **Topology test** — node set + edge set assertions. Уже существует (`graph/tests/test_p4_topology.py`); расширяется для каждого нового узла.
- **Fingerprint invalidation assertion** — для каждого creative-нода: helper `assert_fingerprint_changes_when(node, key, mutation)` гарантирует что меняя `brief.fingerprint` или `state.brief.<key>` ключ кэша меняется. Без этой проверки HOM-157 механизм работает теоретически, но не проверяется.
- **`verify_anchors()` startup check** (HOM-114 §9 уже включает) — все canon якоря резолвятся при build времени графа.

**L1 — Fixture-replay ($0 после первого record):**
- Канонический fixture-эпизод; `tests/fixtures/episodes/canonical-portrait-talking-head/cache.db` коммитится.
- `pytest tests/test_graph_replay.py::test_<node>_smoke` копирует fixture cache.db → `graph/.cache/`, запускает граф со slug=`fixture-canonical-portrait-talking-head`, ассертит:
  - 100% нод не-under-test дают cache hit.
  - Node-under-test (если brief/schema/inputs изменились — fingerprint поменялся) делает один реальный production-tier вызов; результат пишется в cache.db; PR diff покажет изменение.
  - Граф достигает halt_llm_boundary без exception.
- Companion CLI `pytest --dump-recordings <slug>` экспортирует cache.db rows → `tests/fixtures/episodes/<slug>/recordings/<node_name>.json` (canonically sorted, human-readable). JSON — primary review surface; cache.db — canonical, binary.

**L2 — Wave acceptance (manual, paid):**
- В конце каждой M6 волны: `HOMESTUDIO_TEST_MODE=record pytest tests/test_graph_replay.py` — full E2E на production tier, real cost.
- Глазная сверка с критериями M6 §17: семантические дубли отсутствуют, brand palette видна, CTA сцена есть, ±10% длительности vs clean skill-session output, cache invalidation корректна (изменив `brand/anticodeguy/palette.yaml` — инвалидируется ровно `p4_design_system` и downstream).
- Записывается retro `docs/retros/retro-YYYY-MM-DD-m6-wave-N-acceptance.md`.
- Приблизительная стоимость: $1-3 на 30-секундный fixture-эпизод на Sonnet-tier нодах + флагманский Opus на p4_design_system / p4_plan / p4_beat (остальные creative-ноды), один раз на волну (4 волны = $4-12 общая стоимость L2 для всего M6).

## 4. Recording mechanism — режимы, инвалидация, stability

**Три режима** управляются через env var `HOMESTUDIO_TEST_MODE`:

- **`replay`** (default для CI и большинства dev-прогонов) — открывает fixture cache.db **read-only**; cache miss = pytest fail с понятным сообщением `«no recording for node X with fingerprint Y; re-record locally via HOMESTUDIO_TEST_MODE=record-on-miss»`. Гарантирует отсутствие неожиданных платных вызовов.
- **`record-on-miss`** (default для local dev пока работаешь над тикетом) — replay'ятся существующие, missed запускаются реально (production tier per `graph/config.yaml` или per-node override), results пишутся обратно в cache.db. После работы один `git diff tests/fixtures/.../cache.db` показывает что обновилось; companion JSON dump пересоздаётся для review.
- **`record`** (явная команда `HOMESTUDIO_TEST_MODE=record pytest --record-fixtures`) — wipe cache.db и full real-prod прогон. Использование редкое: либо первичная инициализация fixture-эпизода (DoD этого тикета), либо ситуация когда крупная схема state поменялась и проще перезаписать всё.

**Cache invalidation:** через существующий `make_llm_key` (HOM-157) — fingerprint включает brief content, NodeConfig (tier/model/timeout), и upstream artifact hashes. Меняешь brief — fingerprint меняется — cache miss для затронутой ноды и всех downstream чьи fingerprints зависят от её output'а (через `key_func` extras chain). Detёрministic ноды (ffmpeg, persist) используют `make_key` без NodeConfig fingerprint — не реагируют на model/tier change.

**Stability concern:** SQLite журналирование может писать non-deterministic timestamp metadata, что вызовет spurious git-diff'ы на каждый prewarmed prerun. Решения по приоритету:
1. Replay-mode открывает cache.db read-only через `sqlite3.connect(uri=True, ...&mode=ro)` — гарантия неизменности на чтение.
2. Record-mode пишет через `VACUUM INTO temp.db` потом atomic rename — детерминированная raw-форма.
3. Если LangGraph `SqliteCache` внутри использует non-deterministic indexing или auto-incrementing ROWID — fallback на JSON-canonical-form storage с custom `BaseCache` adapter (см. langgraph.cache contracts). Эту опцию проверяем при имплементации; не закладываем как required.

**Studio replay (operator runbook — HOM-186):** to walk the recorded
fixture episode through `langgraph dev` Studio at $0 spend:

```powershell
copy tests\fixtures\episodes\canonical-portrait-talking-head\cache.db graph\.cache\langgraph.db
$env:HOMESTUDIO_PROJECT_ROOT = "$PWD\tests\fixtures"
cd graph
.venv\Scripts\langgraph.exe dev --allow-blocking --no-browser
# POST run with slug=canonical-portrait-talking-head; resume both
# interrupts (strategy_confirmed_interrupt, p3_review_interrupt) with
# {"resume":"approved"}.
```

`--allow-blocking` is required because `_caching.py::file_fingerprint`
issues synchronous file reads during graph draw. `HOMESTUDIO_PROJECT_ROOT`
is mandatory so `_paths.project_root()` resolves `episodes/<slug>/`
under the fixture tree, not the gitignored production `episodes/`. HF
render is NOT in the graph (HOM-78 covers `p4_final_render`); after the
graph terminates at `p4_assemble_index` → gate cluster →
`p4_persist_session` → `studio_launch`, run `npx hyperframes render`
manually inside the fixture's `hyperframes/` directory.

**JSON dump CLI** (`pytest --dump-recordings <slug>`):
- Парсит cache.db rows, группирует по node_name.
- Экспортирует в `tests/fixtures/episodes/<slug>/recordings/<node_name>.json` со схемой `{node, fingerprint, channel_writes, recorded_at, recording_meta: {model, tier, response_length}}`.
- JSON канонически отсортирован (sorted keys, normalized whitespace) для воспроизводимого diff'а.
- Обновляется автоматически при `record-on-miss` (хук в pytest fixture после теста); вручную пересоздаётся через CLI.

## 5. Fixture episode — выбор, layout, gitignore

**Выбор:** один реальный portrait talking-head клип ~30-60 сек. **Кандидат:** обрезанный фрагмент из `episodes/2026-05-06-who-else-is-tired-of-endless-monthly/raw.mp4` (HOM-154 episode). Аргумент за: уже эксфилтровал две регрессии (semantic-dup в EDL, HF black-screen), значит реальный, не подтасованный — содержит характеристики которые ловят таки изменения. Альтернатива (отбираем при имплементации, если будут privacy/lengтh concerns): записать новый фрагмент специально.

**Layout:**
```
tests/fixtures/episodes/canonical-portrait-talking-head/
  raw.mp4                      # ~5-10 MB; git-LFS или прямо в git
  intent.yaml                  # profile_id: talking-head-portrait, brand_id: anticodeguy
  cache.db                     # prewarmed LangGraph SqliteCache (binary, canonical)
  recordings/                  # human-readable JSON dump per node для PR review
    p3_pre_scan.json
    p3_strategy.json
    p3_edl_select.json
    p4_design_system.json
    ...
  expected/                    # opt: committed expected outputs для regression
    final.mp4.sha256
    index.html.lint.json
README.md                      # как пользоваться: «pytest tests/test_graph_replay.py» / «pytest --record-fixtures»
```

**Gitignore:** `episodes/` остаётся gitignored для прода. `tests/fixtures/` — committed целиком. Fixture run использует slug `fixture-canonical-portrait-talking-head` (префикс `fixture-` — convention). `_paths.project_root()` уже walks-up; для fixture-mode override через `HOMESTUDIO_PROJECT_ROOT=tests/fixtures` env var на тестовом прогоне — fixture episodes пишутся/читаются изолированно от production episodes/.

**LFS — open question:** raw.mp4 ~5-10MB — можно положить через git-LFS (если репо уже LFS-пользуется) или прямо в git (для приватного репо в этих масштабах не критично). Решаем при имплементации; фалбэк — git напрямую.

## 6. Per-ticket DoD update — что меняется в CLAUDE.md

**Старый DoD (CLAUDE.md §"Decomposition via brief-references-canon" → "Definition of done for LLM-node tickets"):**
1. Real-CLI Haiku smoke.
2. Topology wiring + topology test green.
3. Topology check pass.
4. Update halt_llm_boundary notice.

**Новый DoD (после testing infra шипится):**

**Mandatory (every PR):**
1. **Brief snapshot test (L0)** — `tests/snapshots/briefs/<node>.txt` обновляется в той же PR; reviewer видит текстовый diff брифа.
2. **Topology wiring + topology test green** (без изменений).
3. **Update halt_llm_boundary notice** (без изменений).

**Conditional (depends on PR scope):**
4. **Schema migration test (L0)** — обязательный если PR трогает Pydantic schema. Asserts что old shape всё ещё парсится после loosening.
5. **Fingerprint invalidation assertion (L0)** — обязательный для creative-нод с новыми brief inputs (e.g. Wave 1 brief substrate, Wave 2 neighbors_summary). Помечает «changing input X → cache key changes».
6. **Fixture-replay smoke (L1)** — обязательный если PR трогает creative LLM ноду. `pytest tests/test_graph_replay.py::test_<node>_smoke`. Diff cache.db + `recordings/<node>.json` в PR.

**Removed:**
- «Real-CLI Haiku smoke» — полностью заменяется fixture-replay на production tier. `smoke_hom*.py` файлы (HOM-118, HOM-119, HOM-127, HOM-160, HOM-163, HOM-165) либо удаляются, либо мигрируются в `tests/test_graph_replay.py::test_<node>_smoke`.

**Wave acceptance (L2)** — отдельный шаг при закрытии M6 волны (НЕ per-ticket):
- `HOMESTUDIO_TEST_MODE=record pytest tests/test_graph_replay.py` на production tier.
- Глазная сверка vs M6 §17 acceptance criteria.
- Retro в `docs/retros/`.

**CLAUDE.md update:**
- Раздел «Definition of done for LLM-node tickets» переписывается под новые требования.
- Добавляется новый раздел «Testing infra — fixture replay»: ссылка на эту спеку, описание трёх режимов `HOMESTUDIO_TEST_MODE`, что reviewer-агент должен проверять (cache.db diff present + JSON dump consistency).
- Существующее правило «search docs for native primitives first» — этот спек служит примером (cache.db = native LangGraph CachePolicy + SqliteCache, не parallel-infra).

## 7. CI integration — explicit non-goal сейчас

Текущий стек: `gh pr create` через GitHub, без `.github/workflows/`. Вводить CI в этой спеке — non-goal:
- Кросс-платформа (Windows-host dev / возможно Linux-runners) — добавляет сложность.
- Секреты для record-mode на runner'е — но record-mode не нужен в CI; только replay-mode → API ключи на runner'е НЕ нужны.
- Maintenance overhead (pin Python version, cache pip deps).

**Архитектура CI-ready** в том смысле, что когда захочется добавить:
- `pytest` под `HOMESTUDIO_TEST_MODE=replay` не делает реальных вызовов → `ANTHROPIC_API_KEY` не требуется на runner'е.
- L0 brief snapshot и schema/topology тесты тривиально проходят в любом окружении.
- Только L2 wave acceptance остаётся manual local run (платный — не для CI).

**Сейчас интеграция** = `pytest` локально перед `gh pr create` + reviewer-агент (текущий workflow) ассертит что fixture cache.db / JSON dumps в diff'е PR соответствуют DoD.

## 8. Linear ticket map и зависимости

**Новый M5 тикет (заводим этой спекой):**

**HOM-NEW-A: «Testing infra — fixture-replay harness + DoD update»** (M5, **High**, ~5pt). Состав:

1. Layout `tests/fixtures/episodes/<slug>/` + README.md.
2. Cache.db tooling:
   - Read-only replay mode helper.
   - Record-on-miss режим (writeback в pytest fixture teardown).
   - Record-from-scratch mode (`pytest --record-fixtures`).
   - `HOMESTUDIO_TEST_MODE` env var integration.
   - Stability hardening (read-only mode для replay; VACUUM INTO для record).
3. JSON dump CLI (`pytest --dump-recordings <slug>`).
4. Brief snapshot test framework (`tests/snapshots/briefs/`); первичные снэпшоты для всех existing creative briefs (p3_strategy, p3_edl_select, p4_design_system, p4_prompt_expansion, p4_plan, p4_beat, p4_captions_layer).
5. Fingerprint invalidation assertion helper (`tests/_helpers/fingerprint_assertions.py`).
6. Initial fixture: подготовить и закоммитить один реальный portrait talking-head ~30-60 сек (раскадрованный из HOM-154 episode). Prewarmed cache.db: один-shot record на production tier (acceptance criterion ниже).
7. Migrate existing `smoke_hom*.py` → `tests/test_graph_replay.py::test_<node>_smoke` (или удалить если node не в граф'е больше).
8. CLAUDE.md update — новый DoD блок replaces "Haiku smoke" секцию + новый раздел "Testing infra — fixture replay".

**Acceptance criteria HOM-NEW-A:**
- Все existing creative briefs имеют snapshot tests, проходят в `pytest`.
- `tests/test_graph_replay.py::test_full_replay` выполняется со cache hit на каждой ноде существующего графа (Phase 3 + Phase 4 reachable subset), runtime <60 сек, $0 спендж.
- `pytest --record-fixtures` отрабатывает full real-tier прогон на fixture, обновляет cache.db и recordings/, runtime ~5-10 мин, paid one-shot.
- CLAUDE.md обновлён, новый DoD задокументирован, существующие memory entries (`feedback_creative_nodes_flagship_tier`) обновлены.

**Linear deps цепочка:**

```
HOM-NEW-A (M5 testing infra)
    ↓ blocks
HOM-161 (M6 epic) → HOM-166 (Wave 1 brief substrate) → HOM-167, HOM-114
                                                            ↓
                                                       HOM-168, HOM-169 (Wave 2)
                                                            ↓
                                                       HOM-170, HOM-171 (Wave 3)
                                                            ↓
                                                       HOM-172, HOM-173, HOM-174, HOM-175 (Wave 4)
                                                            ↓
                                                       HOM-178 (M6 close gate — profile expansion)
HOM-176, HOM-177 — параллельно после Wave 1
```

Linear-операции после approve этой спеки:
1. **Завести HOM-NEW-A** в M5 milestone, High pri, ~5pt, label `area:graph` + `Improvement`. Parent — нет (M5 cleanup).
2. **Set blockedBy** для всех M6 sub-issues (HOM-166, HOM-167, HOM-114 explicit; через HOM-161 epic для остальных). Конкретно: `HOM-166 blockedBy HOM-NEW-A`. Остальные M6 тикеты — `relatedTo HOM-NEW-A` (мягкая зависимость; формальная цепочка через HOM-161).
3. **Закрыть M5 formally** после merge HOM-NEW-A: HOM-115/HOM-117 остаются Backlog Low, milestone description обновляется со строкой «testing infra harness landed via HOM-NEW-A».

**Не входит в скоуп этой спеки** (per M6 §19):
- HOM-77 family (HOM-137/155/156) — параллельный M3 close трек; fixture cache.db перерекордится при каждом merge той семьи (normal flow).
- HOM-78, HOM-79 (M4 cutover) — после M6.
- Upstream PRs в video-use/hyperframes — вне репо.

## 9. Open questions

1. **git-LFS vs прямой commit raw.mp4.** ~5-10MB. Recommend: проверить наличие LFS квоты при имплементации; fallback — прямо в git (для приватного репо тривиально).
2. **Stability concern с SqliteCache** — может потребоваться custom JSON-based BaseCache adapter если LangGraph SqliteCache внутренний format non-deterministic. Не закладываем как required; проверяем при имплементации, эскалируем sub-issue если нужен adapter.
3. **`HOMESTUDIO_TEST_MODE` defaults** — для local dev `record-on-miss` (удобно), для не-test pytest runs нужен ли default? Recommend: env var отсутствует = `replay` (safe default; missing recording = fail).
4. **Migration window для smoke_hom*.py** — все ли удалять / мигрировать в одном PR с HOM-NEW-A, или растянуть по тикетам? Recommend: всё в HOM-NEW-A, чтобы DoD update вступил единомоментно.
5. **L2 acceptance — frequency.** Per-wave (4 раза за M6) или per-ticket для critical Wave 1? Recommend: per-wave; per-ticket L2 убил бы экономию L1.

## 10. Связь с CLAUDE.md / memories

Соответствует:
- `feedback_langgraph_native_primitives` — cache.db = native CachePolicy + SqliteCache, не parallel-infra. Этот спек служит примером применения правила.
- `feedback_creative_nodes_flagship_tier` — обновляется: Haiku-tier для production smoke'ов был ошибкой; теперь production tier для всех creative-нод и в replay-mode (deterministic).
- `feedback_topology_wiring_per_ticket` — DoD сохраняет обязательную topology wiring + test.
- `feedback_branch_pr_workflow` — implementation тикета HOM-NEW-A через worktree → PR → review → merge.

Обновляется:
- `CLAUDE.md` §"Definition of done for LLM-node tickets" → новые пункты, drop Haiku smoke.
- `CLAUDE.md` новый раздел §"Testing infra — fixture replay" с описанием режимов и review expectations.
