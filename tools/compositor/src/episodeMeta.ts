import { writeFileSync, mkdirSync, readFileSync, existsSync } from "node:fs";
import path from "node:path";

export interface EpisodeMetaArgs {
  episodeSlug: string;
  outDir: string;
  createdAt?: string;
}

// $schema and registry URLs are pinned to the contract surface of the
// hyperframes CLI version declared in tools/compositor/package.json.
// They MUST be kept in lockstep with that pin; see
// docs/hyperframes-integration.md for the contract registry.
const HF_PROJECT_CONFIG = {
  $schema: "https://hyperframes.heygen.com/schema/hyperframes.json",
  registry: "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
  paths: {
    blocks: "compositions",
    components: "compositions/components",
    assets: "assets",
  },
} as const;

export function writeEpisodeMeta(args: EpisodeMetaArgs): { hyperframesJsonPath: string; metaJsonPath: string } {
  mkdirSync(args.outDir, { recursive: true });
  const hyperframesJsonPath = path.join(args.outDir, "hyperframes.json");
  const metaJsonPath = path.join(args.outDir, "meta.json");
  // Preserve an existing createdAt so re-runs of `compose` against the
  // same episode do not churn the field on every invocation. Fresh
  // episodes stamp the current time once and keep it.
  let preservedCreatedAt: string | undefined;
  if (!args.createdAt && existsSync(metaJsonPath)) {
    try {
      const existing = JSON.parse(readFileSync(metaJsonPath, "utf8"));
      if (typeof existing?.createdAt === "string") preservedCreatedAt = existing.createdAt;
    } catch { /* ignore malformed file; will be overwritten */ }
  }
  const createdAt = args.createdAt ?? preservedCreatedAt ?? new Date().toISOString();

  writeFileSync(hyperframesJsonPath, JSON.stringify(HF_PROJECT_CONFIG, null, 2) + "\n");
  writeFileSync(metaJsonPath, JSON.stringify({ id: args.episodeSlug, name: args.episodeSlug, createdAt }, null, 2) + "\n");

  return { hyperframesJsonPath, metaJsonPath };
}
