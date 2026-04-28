import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import type { SeamPlan, MasterBundle } from "./types.js";
import { loadDesignMd, designMdToCss } from "./designMd.js";
import { buildCaptionsCompositionHtml } from "./captionsComposition.js";

export interface ComposeArgs {
  designMdPath: string;
  plan: SeamPlan;
  bundle: MasterBundle;
  masterRelPath: string;
  existingSeamFiles: Set<number>;
}

const ROOT_WIDTH = 1440;
const ROOT_HEIGHT = 2560;
const TRACK_VIDEO = 0;
const TRACK_CAPTIONS = 1;
const TRACK_AUDIO = 2;
const TRACK_SEAM_BASE = 3;

function msToSeconds(ms: number): string {
  return (Math.round(ms) / 1000).toFixed(3);
}

export function buildRootIndexHtml(args: ComposeArgs): string {
  const tree = loadDesignMd(args.designMdPath);
  const css = designMdToCss(tree);
  const masterDurationSec = msToSeconds(args.bundle.master.durationMs);

  const seamFragments = args.plan.seams
    .filter((s) => args.existingSeamFiles.has(s.index))
    .map((s, i) => {
      const startSec = msToSeconds(s.at_ms);
      const durationSec = msToSeconds(s.ends_at_ms - s.at_ms);
      const trackIndex = TRACK_SEAM_BASE + i;
      return `<div class="clip"
     data-composition-src="compositions/seam-${s.index}.html"
     data-composition-id="seam-${s.index}"
     data-start="${startSec}"
     data-duration="${durationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}"
     data-track-index="${trackIndex}"></div>`;
    });

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
${css}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: ${ROOT_WIDTH}px; height: ${ROOT_HEIGHT}px; background: var(--color-bg-transparent); color: var(--color-text-primary); font-family: var(--type-family-caption); overflow: hidden; }
</style>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
</head>
<body>
<div id="root"
     data-composition-id="root"
     data-start="0"
     data-duration="${masterDurationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}">
<video id="master-video"
       class="clip"
       data-start="0"
       data-duration="${masterDurationSec}"
       data-track-index="${TRACK_VIDEO}"
       data-has-audio="false"
       muted
       playsinline
       src="${args.masterRelPath}"></video>
<audio id="master-audio"
       class="clip"
       data-start="0"
       data-duration="${masterDurationSec}"
       data-track-index="${TRACK_AUDIO}"
       data-volume="1"
       src="${args.masterRelPath}"></audio>
<div class="clip"
     data-composition-src="compositions/captions.html"
     data-composition-id="captions"
     data-start="0"
     data-duration="${masterDurationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}"
     data-track-index="${TRACK_CAPTIONS}"></div>
${seamFragments.join("\n")}
<script>
(function () {
  if (typeof gsap === "undefined") return;
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({ paused: true });
  tl.to({}, { duration: ${masterDurationSec} });
  window.__timelines["root"] = tl;
})();
</script>
</div>
</body>
</html>`;
}

export interface WriteCompositionArgs extends ComposeArgs {
  episodeDir: string;
}

export function writeCompositionFiles(args: WriteCompositionArgs): { indexPath: string; captionsPath: string } {
  const compositeDir = path.join(args.episodeDir, "stage-2-composite");
  const compositionsDir = path.join(compositeDir, "compositions");
  mkdirSync(compositionsDir, { recursive: true });

  const indexPath = path.join(compositeDir, "index.html");
  const captionsPath = path.join(compositionsDir, "captions.html");

  writeFileSync(indexPath, buildRootIndexHtml(args));
  writeFileSync(captionsPath, buildCaptionsCompositionHtml({ bundle: args.bundle }));

  return { indexPath, captionsPath };
}
