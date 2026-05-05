"""studio_launch node — spawn `hyperframes preview` in the background.

Deterministic class-1 node. Wraps `npx hyperframes preview --port <port>` as
a backgrounded `subprocess.Popen`, writing combined stdout/stderr to
`<hf_dir>/.hyperframes/preview.log` and recording the PID at
`<hf_dir>/.hyperframes/preview.pid`. Returns immediately with
`compose.studio_pid` / `compose.preview_log_path` / `compose.preview_port`
on state — `gate:static_guard` then sleeps 5s and scans the log.

Per spec §4.3 / §6.1 (deterministic node taxonomy) and HOM-125 scope.

Idempotency
-----------
On re-run we check the recorded PID; if the process is still alive we keep
it and reuse the existing log. This matters for the LangGraph "re-run with
same slug → resume from first missing artifact" story — a leftover preview
from a prior run is the desired state, not something to restart. Re-running
with a different port, or with a stale PID file, falls through to a fresh
launch (the previous process, if alive, would still be holding its old port
— that's an operator concern, not ours).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..gates._base import _bundled_hf_cli, hyperframes_dir


DEFAULT_PORT = 3002


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str) -> dict:
    return {
        "errors": [
            {"node": "studio_launch", "message": message, "timestamp": _now()},
        ]
    }


def _is_pid_alive(pid: int) -> bool:
    """Cross-platform liveness check. Returns False on any uncertainty."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # POSIX: process owned by another user exists with this PID —
        # alive enough that we shouldn't respawn.
        return True
    except OSError:
        return False
    return True


def _resolve_cli(hf_dir: Path) -> tuple[list[str], str | None]:
    """Return (argv prefix, error). Prefer bundled CLI; fall back to npx."""
    bundled = _bundled_hf_cli(hf_dir)
    if bundled is not None:
        return [str(bundled)], None
    npx = "npx.cmd" if os.name == "nt" else "npx"
    if shutil.which(npx) is None:
        return [], (
            f"{npx} not found on PATH and no bundled CLI under "
            f"{hf_dir}/node_modules/.bin"
        )
    return [npx, "hyperframes"], None


def _resolved_port(state: dict) -> int:
    """Port precedence: state.compose.preview_port > env > DEFAULT_PORT."""
    compose = state.get("compose") or {}
    port = compose.get("preview_port")
    if port:
        return int(port)
    env_port = os.environ.get("STUDIO_PREVIEW_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass
    return DEFAULT_PORT


def studio_launch_node(state: dict) -> dict:
    hf_dir = hyperframes_dir(state)
    if hf_dir is None:
        return _error("no compose.hyperframes_dir / episode_dir in state")
    if not hf_dir.is_dir():
        return _error(f"hyperframes dir not on disk: {hf_dir}")
    if not (hf_dir / "index.html").is_file():
        return _error(f"index.html not on disk under {hf_dir}")

    state_dir = hf_dir / ".hyperframes"
    state_dir.mkdir(parents=True, exist_ok=True)
    log_path = state_dir / "preview.log"
    pid_path = state_dir / "preview.pid"
    port = _resolved_port(state)

    # Idempotent re-run: if a recorded PID is still alive, reuse it.
    if pid_path.is_file():
        try:
            existing_pid = int(pid_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing_pid = 0
        if existing_pid and _is_pid_alive(existing_pid):
            return {
                "compose": {
                    "studio_pid": existing_pid,
                    "preview_log_path": str(log_path),
                    "preview_port": port,
                    "studio_launched_at": _now(),
                    "studio_reused": True,
                },
            }

    cli_prefix, err = _resolve_cli(hf_dir)
    if err:
        return _error(err)

    # Truncate prior log so the gate's scan window starts clean.
    try:
        log_handle = open(log_path, "w", encoding="utf-8")
    except OSError as exc:
        return _error(f"could not open preview log {log_path}: {exc}")

    cmd = [*cli_prefix, "preview", "--port", str(port)]
    try:
        # Detach stdin so the child doesn't inherit the parent's terminal
        # (otherwise Ctrl-C in the parent shell would also kill preview).
        # On Windows we additionally use CREATE_NEW_PROCESS_GROUP so the
        # child survives parent exit cleanly.
        popen_kwargs: dict = {
            "cwd": str(hf_dir),
            "stdin": subprocess.DEVNULL,
            "stdout": log_handle,
            "stderr": subprocess.STDOUT,
            "shell": False,
        }
        if sys.platform == "win32":
            # DETACHED_PROCESS is the Windows analogue to POSIX
            # start_new_session — without it, the child still shares the
            # parent's console session and a parent-console close would
            # send CTRL_CLOSE_EVENT to the preview server. CREATE_NEW_PROCESS_GROUP
            # additionally isolates Ctrl-C signalling.
            popen_kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
                | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
            )
        else:
            popen_kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **popen_kwargs)
    except FileNotFoundError as exc:
        return _error(f"executable not found: {exc}")
    except OSError as exc:
        return _error(f"failed to spawn preview: {exc}")
    finally:
        # Popen now owns the fd; drop our handle. Tolerate a double-close
        # raised as ValueError ("I/O operation on closed file") — happens
        # if the OS already cleaned up on a spawn failure.
        try:
            log_handle.close()
        except (OSError, ValueError):
            pass

    pid_path.write_text(str(proc.pid), encoding="utf-8")

    return {
        "compose": {
            "studio_pid": proc.pid,
            "preview_log_path": str(log_path),
            "preview_port": port,
            "studio_launched_at": _now(),
            "studio_reused": False,
        },
    }
