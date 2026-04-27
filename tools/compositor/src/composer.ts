import { writeFileSync } from "node:fs";
import path from "node:path";
import type { SeamPlan, Seam, MasterBundle } from "./types.js";
import { loadTokensCss } from "./tokens.js";
import { loadBaseCss, loadComponentTemplate, fillTemplate } from "./components.js";

export interface ComposeArgs {
  repoRoot: string;
  episodeDir: string;
  plan: SeamPlan;
  bundle: MasterBundle;
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
  // Words are already master-aligned in the bundle. Caption components
  // consume start_ms/end_ms (snake_case); convert from camelCase here at
  // the component boundary.
  const wordsForComponent = args.bundle.transcript.words.map((w) => ({
    text: w.text,
    start_ms: w.startMs,
    end_ms: w.endMs,
  }));
  const captionInner = fillTemplate(captionTpl, {
    words_json: JSON.stringify(wordsForComponent),
  });

  const masterDurationSec = msToSeconds(args.bundle.master.durationMs);

  const captionLayer = `<div class="clip" data-start="0" data-duration="${masterDurationSec}" data-track-index="${CAPTION_TRACK_INDEX}">
${captionInner}
</div>`;

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
<script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
</head>
<body>
<div id="root"
     data-composition-id="main"
     data-start="0"
     data-duration="${masterDurationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}">
<video id="master-video"
       class="clip"
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
