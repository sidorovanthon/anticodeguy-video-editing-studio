# Spikes

Empirical results dumped by one-off measurement scripts. Filenames follow
`hom-<n>-results.json`; the script that produces each lives under
`scripts/spike_hom<n>.py`.

Spikes are paid runs — operator authorisation is required before invocation.
The script is committed alongside the schema/brief change so the result is
reproducible; the JSON output is committed in a follow-up commit (or the
operator's hand) once the run completes.

## HOM-243

- Script: `scripts/spike_hom243.py`
- Result: `docs/spikes/hom-243-results.json` (populated post-run).
- Spec: `docs/superpowers/specs/2026-05-10-state-first-artifacts.md` §10
  Step 0.
- Acceptance: 5/5 dispatches succeed, every `html_chars >= 5_000`, every
  `retry_count == 0`. On pass, HOM-231..242 unblock. On fail, pivot to
  LangGraph BaseStore (spec §6.0).
