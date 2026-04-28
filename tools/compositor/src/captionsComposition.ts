import type { MasterBundle } from "./types.js";

export interface CaptionsArgs {
  bundle: MasterBundle;
}

export function buildCaptionsCompositionHtml(args: CaptionsArgs): string {
  const totalSec = (Math.round(args.bundle.master.durationMs) / 1000).toFixed(3);
  const wordsForRuntime = args.bundle.transcript.words.map((w) => ({
    text: w.text,
    start_ms: w.startMs,
    end_ms: w.endMs,
  }));
  return `<template id="captions-template">
<div data-composition-id="captions" data-width="1440" data-height="2560">
  <style>
    [data-composition-id="captions"] { width: 100%; height: 100%; position: relative; }
    [data-composition-id="captions"] .caption-row {
      position: absolute;
      left: var(--safezone-side, 6%);
      right: var(--safezone-side, 6%);
      bottom: var(--safezone-bottom, 22%);
      text-align: center;
      font-family: var(--type-family-caption, system-ui);
      font-size: var(--type-size-caption, 64px);
      font-weight: var(--type-weight-bold, 700);
      line-height: 1.2;
    }
    [data-composition-id="captions"] .word {
      display: inline-block;
      margin: 0 0.18em;
      color: var(--color-caption-inactive, rgba(255,255,255,0.55));
    }
    [data-composition-id="captions"] .word.active {
      color: var(--color-caption-active, #FFFFFF);
    }
  </style>
  <div class="caption-row" id="captions-row"></div>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    (function () {
      var WORDS = ${JSON.stringify(wordsForRuntime)};
      var row = document.getElementById("captions-row");
      WORDS.forEach(function (w, i) {
        var span = document.createElement("span");
        span.className = "word";
        span.dataset.start = w.start_ms;
        span.dataset.end = w.end_ms;
        span.textContent = w.text;
        row.appendChild(span);
      });
      window.__timelines = window.__timelines || {};
      var tl = gsap.timeline({ paused: true });
      WORDS.forEach(function (w, i) {
        var sel = ".word:nth-child(" + (i + 1) + ")";
        tl.set(sel, { className: "+=active" }, w.start_ms / 1000);
        tl.set(sel, { className: "-=active" }, w.end_ms / 1000);
      });
      tl.to({}, { duration: ${totalSec} }, 0);
      window.__timelines["captions"] = tl;
    })();
  </script>
</div>
</template>`;
}
