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
  const normalizedWords = normalizeWords(args.transcript.words);
  const captionInner = fillTemplate(captionTpl, {
    words_json: JSON.stringify(normalizedWords),
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

/**
 * Normalize transcript words to the canonical `{text, start_ms, end_ms}` shape
 * the caption component expects. Accepts either `start_ms`/`end_ms` (ms) or
 * `start`/`end` (seconds, ElevenLabs-native). Throws if neither is present.
 */
function normalizeWords(
  words: ReadonlyArray<Record<string, unknown>>,
): Array<{ text: string; start_ms: number; end_ms: number }> {
  return words.map((w) => {
    const startMsRaw = w.start_ms;
    const endMsRaw = w.end_ms;
    const startSecRaw = w.start;
    const endSecRaw = w.end;

    let start_ms: number | undefined;
    let end_ms: number | undefined;

    if (typeof startMsRaw === "number" && Number.isFinite(startMsRaw)) {
      start_ms = startMsRaw;
    } else if (typeof startSecRaw === "number" && Number.isFinite(startSecRaw)) {
      start_ms = Math.round(startSecRaw * 1000);
    }

    if (typeof endMsRaw === "number" && Number.isFinite(endMsRaw)) {
      end_ms = endMsRaw;
    } else if (typeof endSecRaw === "number" && Number.isFinite(endSecRaw)) {
      end_ms = Math.round(endSecRaw * 1000);
    }

    if (start_ms === undefined || end_ms === undefined) {
      throw new Error(`Word missing timing: ${JSON.stringify(w)}`);
    }

    return { text: String(w.text ?? ""), start_ms, end_ms };
  });
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
