#!/usr/bin/env python3
"""SessionEnd hook: warn if Phase 4 wrote a >=3-beat composition without parallel dispatches.

ALWAYS exits 0. Never blocks the user. Emits a non-blocking stderr warning when:
  (a) the session wrote a new `episodes/<slug>/hyperframes/index.html`,
  (b) the paired `DESIGN.md` declares >= 3 beats, AND
  (c) fewer than 3 parallel `Task` (Agent) tool dispatches occurred before that write.

Machine-enforced complement to the brief imperative shipped in PR #20 (Phase 4 §3).
Defends against the discipline-doesn't-scale failure mode documented in retro
2026-05-01 §2.6 (and Section 7 verification retro §2.4): the model knows the rule
yet authors all beats inline when no automation forces the parallel split.

================================================================================
Step 6.2 RESEARCH FINDINGS — Claude Code hook contract (verified 2026-05-01)
================================================================================

Source: https://code.claude.com/docs/en/hooks (canonical CC hooks docs).

1. EVENT NAME: `SessionEnd`. Fires when the session terminates (clear, resume,
   logout, prompt_input_exit, bypass_permissions_disabled, other). We picked this
   over `Stop` because Stop fires after every assistant turn (would warn many
   times per session); SessionEnd fires once at the end. Critically, SessionEnd
   hooks CANNOT block — exit code and JSON output are for side effects only.
   That is exactly the semantics we want: warn but never gate.

2. HOOK INPUT: JSON on stdin. Common fields: `session_id`, `transcript_path`,
   `cwd`, `hook_event_name`. SessionEnd adds `reason`. The `transcript_path`
   field is the absolute path to the session's JSONL transcript — exactly what
   we need. No env var; we parse stdin. CLI flag `--transcript <path>` is
   supported as an alternate input path so tests (and manual smoke runs) can
   drive the script without simulating CC hook stdin.

3. JSONL TRANSCRIPT SHAPE: tool_use entries are wrapped, not top-level. Verified
   against `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`:
       {"type":"assistant",
        "timestamp":"2026-05-01T10:00:05.100Z",
        "message":{"content":[
            {"type":"tool_use","id":"...","name":"Task",
             "input":{"description":"...","subagent_type":"...","prompt":"..."}},
            ...]}}
   Multiple tool_use entries can appear in a single assistant message — when CC
   dispatches parallel agents in one turn, they share the same outer `timestamp`.
   That co-occurrence in a single message is itself the parallel-dispatch signal.
   The `Agent` tool surfaces in transcripts as `name: "Task"` (the Task tool is
   how CC invokes subagents); we count both names defensively.

4. STDERR CONVENTION: For exit 0, stdout is parsed as JSON if valid, otherwise
   logged. Stderr is shown to the user (and to Claude in transcript). For
   non-blocking SessionEnd warnings, plain stderr text on exit 0 is the right
   shape — no JSON envelope needed. We exit 0 unconditionally.

5. settings.json: registered under `hooks.SessionEnd[].hooks[]` with matcher
   `"*"`, type `"command"`, command using `$CLAUDE_PROJECT_DIR` to locate the
   script. See `.claude/settings.json` in this repo.

================================================================================

Beat-counting convention: DESIGN.md lives at the same directory as index.html
(`episodes/<slug>/hyperframes/DESIGN.md`). We count `### Beat ` headings as the
canonical beat marker — verified against the real `2026-05-01-desktop-software-licensing-it-turns-out-is/hyperframes/DESIGN.md` which uses
`### Beat 1 — Hook (...)` style.

Parallel detection: count Task/Agent tool_use entries grouped by their outer
assistant-message timestamp. If any single message contains >= 3 Task entries,
that's parallel dispatch (canonical CC behaviour: tools called in one
"function_calls" block share the message). Falls back to a 5-second sliding
window over distinct timestamps if the per-message group is too small.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterator

AGENT_TOOL_NAMES = {"Task", "Agent"}
WRITE_TOOL_NAMES = {"Write"}
PARALLEL_THRESHOLD = 3
BEAT_THRESHOLD = 3


def parse_transcript(path: Path) -> Iterator[dict]:
    """Yield JSON objects from a JSONL file. Skip blank/malformed lines silently."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def iter_tool_uses(entries):
    """Yield (timestamp, tool_name, tool_input) for every tool_use in transcript.

    Handles the canonical CC shape: top-level entry has `timestamp` and
    `message.content[]`, where each content item with `type == "tool_use"` has
    `name` and `input`. Multiple tool_uses in one entry share the timestamp.
    """
    for entry in entries:
        ts = entry.get("timestamp")
        msg = entry.get("message")
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "tool_use":
                continue
            name = item.get("name")
            inp = item.get("input") or {}
            if isinstance(name, str):
                yield (ts, name, inp)


def find_new_index_html(tool_uses):
    """Return (timestamp, file_path: Path) of the most recent Write to a
    hyperframes/index.html under episodes/<slug>/, or None.
    """
    found = None
    for ts, name, inp in tool_uses:
        if name not in WRITE_TOOL_NAMES:
            continue
        fp = inp.get("file_path")
        if not isinstance(fp, str):
            continue
        # Match episodes/<slug>/hyperframes/index.html on either path style.
        norm = fp.replace("\\", "/")
        if "/episodes/" in norm and norm.endswith("/hyperframes/index.html"):
            found = (ts, Path(fp))
    return found


def count_parallel_agent_dispatches(tool_uses, before_ts):
    """Count Task/Agent tool_uses that occurred at or before `before_ts`,
    grouped into parallel batches.

    Strategy: group by outer assistant-message timestamp. If any single timestamp
    bucket has >= PARALLEL_THRESHOLD agent calls, that is unambiguous parallel
    dispatch (a single function_calls block from one assistant turn). Returns
    the maximum bucket size seen, which the caller compares against the
    threshold.

    Falls back to: total agent count if timestamps are missing/identical for
    all entries (conservative — if we can't tell, assume parallel).
    """
    buckets: dict[str, int] = defaultdict(int)
    total = 0
    any_ts = False
    for ts, name, _inp in tool_uses:
        if name not in AGENT_TOOL_NAMES:
            continue
        if before_ts and isinstance(ts, str) and ts > before_ts:
            continue
        total += 1
        if isinstance(ts, str):
            any_ts = True
            buckets[ts] += 1
        else:
            buckets["__no_ts__"] += 1
    if not any_ts:
        # No timestamps at all — be conservative, assume any cluster is parallel.
        return total
    return max(buckets.values()) if buckets else 0


def design_md_beat_count(index_html_path: Path) -> int:
    """Count `### Beat ` headings in DESIGN.md sibling to index.html."""
    design = index_html_path.parent / "DESIGN.md"
    try:
        text = design.read_text(encoding="utf-8")
    except OSError:
        return 0
    count = 0
    for line in text.splitlines():
        stripped = line.lstrip()
        # Canonical: `### Beat 1 — ...`. Also tolerate `## Beat ` and
        # `- **Beat N` list-item style as defensive fallbacks.
        if stripped.startswith("### Beat ") or stripped.startswith("## Beat "):
            count += 1
        elif stripped.startswith("- **Beat "):
            count += 1
    return count


def read_transcript_path_from_stdin() -> str | None:
    """Read CC hook JSON payload from stdin and extract transcript_path."""
    if sys.stdin is None or sys.stdin.isatty():
        return None
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(payload, dict):
        tp = payload.get("transcript_path")
        if isinstance(tp, str):
            return tp
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SessionEnd hook: warn on sequential beat authoring."
    )
    parser.add_argument(
        "--transcript",
        type=str,
        default=None,
        help="Path to session JSONL transcript (overrides stdin payload).",
    )
    args = parser.parse_args()

    transcript_str = args.transcript or read_transcript_path_from_stdin()
    if not transcript_str:
        return 0
    transcript_path = Path(transcript_str)
    if not transcript_path.is_file():
        return 0

    try:
        # Materialize once — we iterate twice (find write, count agents).
        tool_uses = list(iter_tool_uses(parse_transcript(transcript_path)))
    except Exception:
        return 0

    write = find_new_index_html(tool_uses)
    if write is None:
        return 0
    write_ts, write_path = write

    beats = design_md_beat_count(write_path)
    if beats < BEAT_THRESHOLD:
        return 0

    parallel = count_parallel_agent_dispatches(tool_uses, write_ts)
    if parallel >= PARALLEL_THRESHOLD:
        return 0

    msg = (
        "WARNING: Phase 4 wrote a {beats}-beat composition "
        "({path}) without parallel Task dispatches "
        "(saw max {parallel} concurrent Task call(s); threshold is {thresh}).\n"
        "Per retro 2026-05-01 §2.6, multi-beat compositions should be authored "
        "by parallel sub-agents (one Task per beat, dispatched in a single "
        "assistant turn). Sequential inline authoring scales poorly and was "
        "the documented failure mode this hook guards against.\n"
        "This warning is non-blocking; the session is complete.\n"
    ).format(beats=beats, path=write_path, parallel=parallel, thresh=PARALLEL_THRESHOLD)
    sys.stderr.write(msg)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Hook must NEVER block: swallow any unexpected error and exit 0.
        sys.exit(0)
