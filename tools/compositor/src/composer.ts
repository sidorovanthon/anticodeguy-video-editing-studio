import { writeFileSync } from "node:fs";
import path from "node:path";
import type { SeamPlan, Seam, Transcript } from "./types.js";
import { loadTokensCss } from "./tokens.js";
import { loadBaseCss, loadComponentTemplate, fillTemplate } from "./components.js";

export interface ComposeArgs {
  repoRoot: string;
  episodeDir: string;
  plan: SeamPlan;
  transcript: Transcript;
  masterRelPath: string;
}

const ROOT_WIDTH = 1440;
const ROOT_HEIGHT = 2560;
const CAPTION_TRACK_INDEX = 9;

function msToSeconds(ms: number): string {
  return (Math.round(ms) / 1000).toFixed(3);
}

function defaultTokensPath(repoRoot: string): string {
  return path.join(repoRoot, "design-system", "tokens", "tokens.json");
}

export function buildCompositionHtml(args: ComposeArgs): string {
  const css = loadTokensCss(defaultTokensPath(args.repoRoot));
  const base = loadBaseCss();

  const seamsWithGraphics = args.plan.seams.filter((s) => s.graphic);
  const seamFragments = seamsWithGraphics.map((seam, i) =>
    renderSeamFragment(seam, i + 1),
  );

  const captionTpl = loadComponentTemplate("caption-karaoke");
  const captionInner = fillTemplate(captionTpl, {
    words_json: JSON.stringify(args.transcript.words),
  });

  const masterDurationSec = msToSeconds(args.plan.master_duration_ms);

  const captionLayer = `<div class="clip" data-start="0" data-duration="${masterDurationSec}" data-track-index="${CAPTION_TRACK_INDEX}">
${captionInner}
</div>`;

  // GSAP timeline adapter: paused, registered on window.__timelines["main"].
  // HyperFrames runtime drives time via timeline.time(); onUpdate pulses
  // window.__seekTo (defined by caption-karaoke) with ms.
  const timelineScript = `<script>
(function () {
  if (typeof gsap === "undefined") return;
  var tl = gsap.timeline({ paused: true, onUpdate: function () {
    if (window.__seekTo) window.__seekTo(tl.time() * 1000);
  }});
  tl.to({}, { duration: ${masterDurationSec} });
  window.__timelines = window.__timelines || {};
  window.__timelines["main"] = tl;
})();
</script>`;

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
${css}
${base}
</style>
</head>
<body>
<div id="root"
     data-composition-id="main"
     data-start="0"
     data-duration="${masterDurationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}">
<video class="clip"
       data-start="0"
       data-duration="${masterDurationSec}"
       data-track-index="0"
       data-has-audio="true"
       muted
       src="${args.masterRelPath}"></video>
${seamFragments.join("\n")}
${captionLayer}
${timelineScript}
</div>
</body>
</html>`;
}

function renderSeamFragment(seam: Seam, trackIndex: number): string {
  if (!seam.graphic) return "";
  const tpl = loadComponentTemplate(seam.graphic.component);
  const filled = fillTemplate(tpl, seam.graphic.data);
  const startSec = msToSeconds(seam.at_ms);
  const durationSec = msToSeconds(seam.ends_at_ms - seam.at_ms);
  return `<div class="clip"
     data-seam="${seam.index}"
     data-start="${startSec}"
     data-duration="${durationSec}"
     data-track-index="${trackIndex}">
${filled}
</div>`;
}

export function writeCompositionHtml(args: ComposeArgs, outPath: string): void {
  writeFileSync(outPath, buildCompositionHtml(args));
}
