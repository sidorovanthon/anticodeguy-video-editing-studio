# scripts/bare_repros/

Bare-reproduction scripts for known-blocked upstream bugs tracked in user
memory (`feedback_hf_*.md`, `feedback_lint_regex_*.md`, etc.).

Each script scaffolds a clean external-skill project (`npx hyperframes init`
or equivalent), reproduces the canonical pattern that triggers the bug, and
exits with a tri-state code:

| exit | meaning                                              |
| ---- | ---------------------------------------------------- |
| 0    | bug still reproduces — memory entry remains accurate |
| 1    | bug NOT reproduced — upstream may have fixed it; needs human review before clearing the memory entry |
| 2    | inconclusive (timeout, missing tool, parse failure)  |

Run the orchestrating graph node (`preflight_canon`) to dispatch every script
whose memory entry is older than 7 days. Or run a single script manually:

```powershell
python scripts/bare_repros/feedback_hf_subcomp_loader_data_composition_src.py
```

The companion sidecar `state.json` (gitignored) stores per-bug
`{last_verified, last_status}` so the node can skip fresh entries and avoid
spending 30–60s on repros every run.

See CLAUDE.md §"Investigation methodology — bare-repro before upstream-blame"
for the rule this automates.
