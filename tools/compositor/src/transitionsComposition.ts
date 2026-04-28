import type { Seam } from "./types.js";
import type { TransitionConfig } from "./designMd.js";

export interface TransitionsArgs {
  seams: Seam[];
  totalDurationMs: number;
  transition: TransitionConfig;
}

export function buildTransitionsHtml(args: TransitionsArgs): string {
  const totalSec = (Math.round(args.totalDurationMs) / 1000).toFixed(3);

  if (args.seams.length < 2) {
    return `<template id="transitions-template">
<div data-composition-id="transitions" data-start="0" data-duration="${totalSec}" data-width="1440" data-height="2560">
  <!-- single-seam composition: no transitions emitted -->
</div>
</template>`;
  }

  const halfMs = (args.transition.duration * 1000) / 2;
  const totalSecNum = Math.round(args.totalDurationMs) / 1000;
  const boundaries = args.seams.slice(0, -1).map((s, i) => ({
    index: i,
    boundaryMs: s.ends_at_ms,
    startSec: Math.max(0, (s.ends_at_ms - halfMs) / 1000),
  }));

  const boundaryComments = boundaries
    .map((b) => `      /* transition at boundary ${b.index} (seam ${b.index} -> seam ${b.index + 1}) at ${b.boundaryMs}ms */`)
    .join("\n");

  const tlCalls = boundaries
    .map((b) => {
      // Defensive clamp: a degenerate seam ending at totalSec would push the second tween
      // past timeline duration. planSeams should not produce that today; insurance is two chars.
      const secondStart = Math.min(b.startSec + args.transition.duration / 2, totalSecNum - args.transition.duration);
      return `      tl.fromTo(maskEl, { autoAlpha: 0 }, { autoAlpha: 1, duration: ${args.transition.duration / 2}, ease: "${args.transition.easing}" }, ${b.startSec.toFixed(3)});\n      tl.to(maskEl,   { autoAlpha: 0, duration: ${args.transition.duration / 2}, ease: "${args.transition.easing}" }, ${secondStart.toFixed(3)});`;
    })
    .join("\n");

  return `<template id="transitions-template">
<div data-composition-id="transitions" data-start="0" data-duration="${totalSec}" data-width="1440" data-height="2560">
  <style>
    [data-composition-id="transitions"] { position: absolute; inset: 0; pointer-events: none; }
    [data-composition-id="transitions"] .transition-mask {
      position: absolute; inset: 0;
      background-color: #000;
      visibility: hidden;
      opacity: 0;
    }
  </style>
  <div class="transition-mask" id="transitions-mask"></div>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    (function () {
      var maskEl = document.getElementById("transitions-mask");
      window.__timelines = window.__timelines || {};
      var tl = gsap.timeline({ paused: true });
${boundaryComments}
${tlCalls}
      tl.to({}, { duration: ${totalSec} }, 0);
      window.__timelines["transitions"] = tl;
    })();
  </script>
</div>
</template>`;
}
