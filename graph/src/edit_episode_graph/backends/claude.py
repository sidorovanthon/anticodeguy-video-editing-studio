"""ClaudeCodeBackend — `claude -p "<task>" --output-format stream-json --model <id>`.

Populated in v2 — see spec §7.2. Subscription auth only.

Windows note (spec §7.7): `claude.exe` is a `.cmd` shim and `subprocess.run` with
`shell=False` may yield EINVAL — implementation must use the explicit `.exe` path or
`shell=True` with proper quoting. See `feedback_bundled_helper_path.md`.
"""
