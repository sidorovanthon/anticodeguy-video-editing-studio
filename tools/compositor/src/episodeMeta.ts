import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";

export interface EpisodeMetaArgs {
  episodeSlug: string;
  outDir: string;
  createdAt?: string;
}

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
  const createdAt = args.createdAt ?? new Date().toISOString();

  writeFileSync(hyperframesJsonPath, JSON.stringify(HF_PROJECT_CONFIG, null, 2) + "\n");
  writeFileSync(metaJsonPath, JSON.stringify({ id: args.episodeSlug, name: args.episodeSlug, createdAt }, null, 2) + "\n");

  return { hyperframesJsonPath, metaJsonPath };
}
