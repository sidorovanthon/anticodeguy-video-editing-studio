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

import { execFileSync } from "node:child_process";
import path from "node:path";
import type { SubagentDispatcher } from "./segmenter.js";

export interface RealDispatcherOptions {
  repoRoot: string;
  /** Override the `claude` binary path; defaults to `claude` on PATH. */
  claudeBin?: string;
  /** Override the allowed tool list. Defaults to Read/Write/Bash. */
  allowedTools?: string[];
  /** Optional working directory for the subagent process. */
  cwd?: string;
}

export function makeRealSubagentDispatcher(opts: RealDispatcherOptions): SubagentDispatcher {
  const claudeBin = opts.claudeBin ?? "claude";
  const allowedTools = opts.allowedTools ?? ["Read", "Write", "Bash"];
  const repoRoot = path.resolve(opts.repoRoot);
  return {
    async run(promptText: string): Promise<string> {
      const args = [
        "-p", promptText,
        "--add-dir", repoRoot,
        "--allowedTools", ...allowedTools,
        "--permission-mode", "acceptEdits",
        "--output-format", "text",
      ];
      const out = execFileSync(claudeBin, args, {
        cwd: opts.cwd,
        stdio: ["ignore", "pipe", "inherit"],
        maxBuffer: 64 * 1024 * 1024,
      });
      return out.toString("utf-8");
    },
  };
}
