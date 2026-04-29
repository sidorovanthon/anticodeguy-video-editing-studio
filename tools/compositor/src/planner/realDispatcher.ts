// tools/compositor/src/planner/realDispatcher.ts
//
// Real `SubagentDispatcher` that wraps the same Claude headless CLI invocation
// `tools/scripts/run-stage1.sh:159` uses for the EDL author. The shell version
// constructs the command as:
//
//     claude -p "$PROMPT" \
//       --add-dir "$REPO_ROOT" \
//       --allowedTools Read Write Bash \
//       --permission-mode acceptEdits \
//       --output-format text
//
// We mirror that exactly here, but via `execFileSync` with array args (no shell,
// no string concatenation) per the security guidance in the Phase 6b plan.
//
// Calibration procedure for `timeoutMs`:
//   1. Run `node tools/compositor/dist/bin/aggregate-generate-wallclocks.js`
//      from the repo root.
//   2. Take the printed "recommended timeoutMs" value.
//   3. Update the default in `makeRealSubagentDispatcher` (the
//      `4 * 60 * 1000` literal) and replace the line below with:
//      `// last calibrated YYYY-MM-DD over N samples; p99=X ms`.
// Re-run after every ~10 episodes or after a model swap.
//
// Last calibrated: not yet (default is a guess; see D3 in
// docs/operations/planner-pipeline-fixes/findings.md).

import { execFile } from "node:child_process";
import { promisify } from "node:util";
import path from "node:path";
import type { SubagentDispatcher } from "./segmenter.js";

const execFileAsync = promisify(execFile);

export interface RealDispatcherOptions {
  repoRoot: string;
  /** Override the `claude` binary path; defaults to `claude` on PATH. */
  claudeBin?: string;
  /** Override the allowed tool list. Defaults to Read/Write/Bash. */
  allowedTools?: string[];
  /** Optional working directory for the subagent process. */
  cwd?: string;
  /**
   * Hard timeout per subagent invocation, in milliseconds. The child is killed
   * (SIGKILL) when exceeded so a hung claude-cli does not stall the whole
   * Promise.all batch indefinitely. Default 4 min.
   */
  timeoutMs?: number;
}

export function makeRealSubagentDispatcher(opts: RealDispatcherOptions): SubagentDispatcher {
  const claudeBin = opts.claudeBin ?? "claude";
  const allowedTools = opts.allowedTools ?? ["Read", "Write", "Bash"];
  const repoRoot = path.resolve(opts.repoRoot);
  // Precedence: env var first (operator's override surface per spec §2),
  // then explicit option, then default. Inversion would make a hardcoded
  // caller silently shadow the operator's HF_GENERATIVE_TIMEOUT_MS.
  const envOverride = process.env.HF_GENERATIVE_TIMEOUT_MS;
  let envTimeoutMs: number | undefined;
  if (envOverride !== undefined && envOverride !== "") {
    if (/^\d+$/.test(envOverride)) {
      envTimeoutMs = Number(envOverride);
    } else {
      console.warn(
        `[realDispatcher] HF_GENERATIVE_TIMEOUT_MS=${JSON.stringify(envOverride)} is not a positive integer; ignoring and falling back.`,
      );
    }
  }
  const timeoutMs = envTimeoutMs ?? opts.timeoutMs ?? 4 * 60 * 1000;
  return {
    async run(promptText: string): Promise<string> {
      const args = [
        "-p", promptText,
        "--add-dir", repoRoot,
        "--allowedTools", ...allowedTools,
        "--permission-mode", "acceptEdits",
        "--output-format", "text",
      ];
      // execFile (async) — execFileSync would block Node's event loop and
      // serialise sibling subagent runs even when generateAll uses Promise.all.
      const { stdout } = await execFileAsync(claudeBin, args, {
        cwd: opts.cwd,
        maxBuffer: 64 * 1024 * 1024,
        timeout: timeoutMs,
        killSignal: "SIGKILL",
      });
      return stdout;
    },
  };
}
