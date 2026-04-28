import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import type { SeamPlan, MasterBundle } from "./types.js";
import type { TokenTree } from "./designMd.js";
import { loadDesignMd, designMdToCss, resolveToken } from "./designMd.js";
import { buildCaptionsCompositionHtml } from "./captionsComposition.js";
import { buildTransitionsHtml } from "./transitionsComposition.js";
import { readTransitionConfig } from "./designMd.js";

export interface ComposeArgs {
  designMdPath: string;
  plan: SeamPlan;
  bundle: MasterBundle;
  masterRelPath: string;
  musicRelPath?: string;
  existingSeamFiles: Set<number>;
}

const ROOT_WIDTH = 1440;
const ROOT_HEIGHT = 2560;
// Track-index ladder. HF treats track-index purely as an identifier
// (it does NOT affect z-order); these are coordination IDs only.
// Adding a new track? Pick the next unused integer and update this object.
const TRACKS = {
  VIDEO: 0,
  CAPTIONS: 1,
  AUDIO: 2,
  SEAM_BASE: 3,
  TRANSITIONS: 4,
  MUSIC: 5,
} as const;

function msToSeconds(ms: number): string {
  return (Math.round(ms) / 1000).toFixed(3);
}

export function buildRootIndexHtml(args: ComposeArgs, tree?: TokenTree): string {
  const t = tree ?? loadDesignMd(args.designMdPath);
  const css = designMdToCss(t);
  const masterDurationSec = msToSeconds(args.bundle.master.durationMs);
  const bgTransparent = resolveToken(t, "color.bg.transparent");
  const textPrimary  = resolveToken(t, "color.text.primary");
  const fontCaption  = resolveToken(t, "type.family.caption");

  const seamFragments = args.plan.seams
    .filter((s) => args.existingSeamFiles.has(s.index))
    .map((s) => {
      const startSec = msToSeconds(s.at_ms);
      const durationSec = msToSeconds(s.ends_at_ms - s.at_ms);
      return `<div class="clip"
     data-composition-src="compositions/seam-${s.index}.html"
     data-composition-id="seam-${s.index}"
     data-start="${startSec}"
     data-duration="${durationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}"
     data-track-index="${TRACKS.SEAM_BASE}"></div>`;
    });

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
${css}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: ${ROOT_WIDTH}px; height: ${ROOT_HEIGHT}px; background: ${bgTransparent}; color: ${textPrimary}; font-family: ${fontCaption}; overflow: hidden; }
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
       data-track-index="${TRACKS.VIDEO}"
       data-has-audio="false"
       muted
       playsinline
       src="${args.masterRelPath}"></video>
<audio id="master-audio"
       class="clip"
       data-start="0"
       data-duration="${masterDurationSec}"
       data-track-index="${TRACKS.AUDIO}"
       data-volume="1"
       src="${args.masterRelPath}"></audio>
${args.musicRelPath ? `<audio id="music"
       class="clip"
       data-start="0"
       data-duration="${masterDurationSec}"
       data-track-index="${TRACKS.MUSIC}"
       data-volume="0.5"
       src="${args.musicRelPath}"></audio>` : ""}
<div class="clip"
     data-composition-src="compositions/captions.html"
     data-composition-id="captions"
     data-start="0"
     data-duration="${masterDurationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}"
     data-track-index="${TRACKS.CAPTIONS}"></div>
<div class="clip"
     data-composition-src="compositions/transitions.html"
     data-composition-id="transitions"
     data-start="0"
     data-duration="${masterDurationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}"
     data-track-index="${TRACKS.TRANSITIONS}"></div>
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

export function writeCompositionFiles(args: WriteCompositionArgs): { indexPath: string; captionsPath: string; transitionsPath: string } {
  const compositeDir = path.join(args.episodeDir, "stage-2-composite");
  const compositionsDir = path.join(compositeDir, "compositions");
  mkdirSync(compositionsDir, { recursive: true });

  const tree = loadDesignMd(args.designMdPath);
  const indexPath = path.join(compositeDir, "index.html");
  const captionsPath = path.join(compositionsDir, "captions.html");

  writeFileSync(indexPath, buildRootIndexHtml(args, tree));
  writeFileSync(captionsPath, buildCaptionsCompositionHtml({ bundle: args.bundle, tree }));

  const transitionConfig = readTransitionConfig(tree);
  const transitionsPath = path.join(compositionsDir, "transitions.html");
  writeFileSync(transitionsPath, buildTransitionsHtml({
    seams: args.plan.seams,
    totalDurationMs: args.bundle.master.durationMs,
    transition: transitionConfig,
  }));

  return { indexPath, captionsPath, transitionsPath };
}
