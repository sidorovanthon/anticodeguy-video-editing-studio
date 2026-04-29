// tools/compositor/src/bin/episode-state.ts
//
// Thin argv parser. All real work lives in ../state/episodeState.ts so it
// can be imported directly by the compositor when wallclock-precise calls
// matter (avoiding a child-process round-trip per scene).

import {
  initState,
  markStepStarted,
  markStepDone,
  recordFix,
  recordSceneCompleted,
  invalidateStep,
  readState,
} from "../state/episodeState.js";
import type { StepName, CheckpointId } from "../state/types.js";

function arg(name: string, argv: string[]): string | undefined {
  const i = argv.indexOf("--" + name);
  return i >= 0 ? argv[i + 1] : undefined;
}

function required(name: string, argv: string[]): string {
  const v = arg(name, argv);
  if (!v) {
    console.error(`error: --${name} is required`);
    process.exit(2);
  }
  return v;
}

function main(argv: string[]): void {
  const [cmd, ...rest] = argv;
  switch (cmd) {
    case "init": {
      const ep = required("episode-dir", rest);
      const slug = required("slug", rest);
      initState(ep, slug);
      return;
    }
    case "mark-step-started": {
      markStepStarted(required("episode-dir", rest), required("step", rest) as StepName);
      return;
    }
    case "mark-step-done": {
      markStepDone(
        required("episode-dir", rest),
        required("step", rest) as StepName,
        required("checkpoint", rest) as CheckpointId,
      );
      return;
    }
    case "record-fix": {
      recordFix(required("episode-dir", rest), required("label", rest));
      return;
    }
    case "record-scene": {
      recordSceneCompleted(required("episode-dir", rest), required("scene", rest), {
        kind: (arg("kind", rest) as "generative" | "catalog" | "none") ?? "generative",
        outputPath: required("output-path", rest),
        promptHash: required("prompt-hash", rest),
        outputBytes: Number(required("output-bytes", rest)),
        wallclockMs: Number(required("wallclock-ms", rest)),
      });
      return;
    }
    case "invalidate": {
      invalidateStep(required("episode-dir", rest), required("step", rest) as StepName);
      return;
    }
    case "read": {
      const s = readState(required("episode-dir", rest));
      process.stdout.write(JSON.stringify(s, null, 2) + "\n");
      return;
    }
    default:
      console.error(
        "usage: episode-state <init|mark-step-started|mark-step-done|record-fix|record-scene|invalidate|read> [args]"
      );
      process.exit(2);
  }
}

main(process.argv.slice(2));
