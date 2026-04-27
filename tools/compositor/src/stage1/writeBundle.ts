import { writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { loadTranscript } from "../transcript.js";
import { loadEdl, remapWordsToMaster } from "../edl.js";
import type {
  BundleBoundary,
  BundleMaster,
  BundleWord,
  MasterBundle,
} from "../types.js";

export interface BuildBundleArgs {
  slug: string;
  transcriptPath: string;
  edlPath: string;
  masterPath: string;
  /** Injectable for tests; in production omit and ffprobe is invoked. */
  probeMaster?: (masterPath: string) => BundleMaster;
}

export function buildBundle(args: BuildBundleArgs): MasterBundle {
  const transcript = loadTranscript(args.transcriptPath);
  const edl = loadEdl(args.edlPath);
  const master = (args.probeMaster ?? probeMasterWithFfprobe)(args.masterPath);

  const boundaries: BundleBoundary[] = [{ atMs: 0, kind: "start" }];
  let acc = 0;
  for (let i = 0; i < edl.ranges.length - 1; i++) {
    acc += (edl.ranges[i].end - edl.ranges[i].start) * 1000;
    boundaries.push({ atMs: Math.round(acc), kind: "seam" });
  }
  boundaries.push({ atMs: master.durationMs, kind: "end" });

  const remapped = remapWordsToMaster(transcript.words, edl);
  const words: BundleWord[] = remapped.map((w) => ({
    text: w.text,
    startMs: w.start_ms,
    endMs: w.end_ms,
  }));

  return {
    schemaVersion: 1,
    slug: args.slug,
    master,
    boundaries,
    transcript: { language: "en", words },
  };
}

export function writeBundleFile(bundle: MasterBundle, outPath: string): void {
  writeFileSync(outPath, JSON.stringify(bundle, null, 2));
}

function probeMasterWithFfprobe(masterPath: string): BundleMaster {
  const res = spawnSync(
    "ffprobe",
    [
      "-v", "error",
      "-select_streams", "v:0",
      "-show_entries", "stream=width,height,r_frame_rate:format=duration",
      "-of", "json",
      masterPath,
    ],
    { encoding: "utf8" },
  );
  if (res.status !== 0) {
    throw new Error(`ffprobe failed for ${masterPath}: ${res.stderr}`);
  }
  const probed = JSON.parse(res.stdout) as {
    streams?: Array<{ width?: number; height?: number; r_frame_rate?: string }>;
    format?: { duration?: string };
  };
  const stream = probed.streams?.[0];
  if (!stream || stream.width === undefined || stream.height === undefined) {
    throw new Error(`ffprobe did not return width/height for ${masterPath}`);
  }
  const fpsParts = (stream.r_frame_rate ?? "60/1").split("/");
  const fps = Math.round(Number(fpsParts[0]) / Number(fpsParts[1] ?? "1"));
  const durationSec = Number(probed.format?.duration ?? "0");
  if (!durationSec) {
    throw new Error(`ffprobe did not return duration for ${masterPath}`);
  }
  return {
    durationMs: Math.round(durationSec * 1000),
    width: stream.width,
    height: stream.height,
    fps,
  };
}
