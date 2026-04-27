# Components Smoke Test (Task 8)

Smoke test deferred to integration in Task 9 composer test; HyperFrames preview consumes whole compositions, not isolated fragments. Static checks confirm files exist and have no leaked tokens (all `var(--…)` references live inside `<style>` blocks; all six HTML fragments and `_base.css` parse and read successfully via Node `fs.readFileSync`).
