"""LLMBackend protocol + capability/result types.

Populated in v2 — see spec §7.1 / §7.3. Backends invoke authorized CLIs
(`claude -p`, `codex exec`, `gemini -p`) via subprocess; subscription auth only,
no API keys. Nodes declare requirements (tier, needs_tools, backend preference);
they never name a provider directly.
"""
