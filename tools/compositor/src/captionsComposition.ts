import type { MasterBundle } from "./types.js";
import type { TokenTree } from "./designMd.js";
import { resolveToken } from "./designMd.js";
import { groupWords } from "./groupWords.js";

export interface CaptionsArgs {
  bundle: MasterBundle;
  tree: TokenTree;
}

const MAX_WORDS_PER_GROUP = 5;
const BREAK_AFTER_PAUSE_MS = 120;

export function buildCaptionsCompositionHtml(args: CaptionsArgs): string {
  const totalSec = (Math.round(args.bundle.master.durationMs) / 1000).toFixed(3);
  const words = args.bundle.transcript.words;

  const fontFamily      = resolveToken(args.tree, "type.family.caption");
  const fontSize        = resolveToken(args.tree, "type.size.caption");
  const fontWeight      = resolveToken(args.tree, "type.weight.bold");
  const colorActive     = resolveToken(args.tree, "color.caption.active");
  const colorInactive   = resolveToken(args.tree, "color.caption.inactive");
  const safezoneSide    = resolveToken(args.tree, "safezone.side");
  const safezoneBottom  = resolveToken(args.tree, "safezone.bottom");

  if (words.length === 0) {
    return `<template id="captions-template">
<div data-composition-id="captions" data-start="0" data-duration="${totalSec}" data-width="1440" data-height="2560">
  <!-- no transcript words; captions sub-composition emits no timeline -->
</div>
</template>`;
  }

  const groups = groupWords(
    words.map((w) => ({ text: w.text, startMs: w.startMs, endMs: w.endMs })),
    { maxWordsPerGroup: MAX_WORDS_PER_GROUP, breakAfterPauseMs: BREAK_AFTER_PAUSE_MS },
  );

  const groupsForRuntime = groups.map((g) => ({
    id: g.id,
    startSec: g.startMs / 1000,
    endSec: g.endMs / 1000,
  }));

  const groupDivs = groups
    .map((g) => {
      const inner = g.words.map((w) => `<span class="caption-word">${escapeHtml(w.text)}</span>`).join(" ");
      return `<div class="caption-group" data-group-id="${g.id}">${inner}</div>`;
    })
    .join("\n  ");

  const fontSizePx = parseFontSizePx(fontSize);

  // Build per-group tween statements with literal numeric time positions so the
  // emitted JS is self-contained and the self-lint regex tests can match literals.
  const groupTweens = groups
    .map((g) => {
      const startSec = (g.startMs / 1000).toFixed(3);
      const endSec   = (g.endMs   / 1000).toFixed(3);
      return [
        `      // Group ${g.id}: [${startSec}s – ${endSec}s]`,
        `      (function () {`,
        `        var el = root.querySelector('[data-group-id="${g.id}"]');`,
        `        tl.from(el, { autoAlpha: 0, y: 24, duration: 0.32, ease: "power3.out" }, ${startSec});`,
        `        tl.set(el, { autoAlpha: 0 }, ${endSec});`,
        `        if (fit) { tl.call(function () { window.__hyperframes.fitTextFontSize(el, { maxFontSize: ${fontSizePx}, minFontSize: 28 }); }, [], ${startSec}); }`,
        `      })();`,
      ].join("\n");
    })
    .join("\n");

  return `<template id="captions-template">
<div data-composition-id="captions" data-start="0" data-duration="${totalSec}" data-width="1440" data-height="2560">
  <style>
    [data-composition-id="captions"] {
      width: 100%; height: 100%; position: relative;
      background-color: rgba(0,0,0,0);
    }
    [data-composition-id="captions"] .caption-group {
      position: absolute;
      left: ${safezoneSide}; right: ${safezoneSide};
      bottom: ${safezoneBottom};
      text-align: center;
      font-family: ${fontFamily};
      font-size: ${fontSize};
      font-weight: ${fontWeight};
      line-height: 1.2;
      color: ${colorActive};
      visibility: hidden;
      opacity: 0;
    }
    [data-composition-id="captions"] .caption-word {
      display: inline-block;
      margin: 0 0.18em;
    }
    [data-composition-id="captions"] .caption-group.muted .caption-word {
      color: ${colorInactive};
    }
  </style>
  ${groupDivs}
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    (function () {
      var root = document.querySelector('[data-composition-id="captions"]');
      window.__timelines = window.__timelines || {};
      var tl = gsap.timeline({ paused: true });
      var fit = (window.__hyperframes && window.__hyperframes.fitTextFontSize) || null;

${groupTweens}

      tl.to({}, { duration: ${totalSec} }, 0);
      window.__timelines["captions"] = tl;

      // Self-lint: every group must have an entry tween and a hard-kill set.
      var children = tl.getChildren();
      var GROUPS = ${JSON.stringify(groupsForRuntime)};
      GROUPS.forEach(function (g) {
        var hasEntry = children.some(function (c) { return Math.abs(c.startTime() - g.startSec) < 1e-3 && c.vars && c.vars.duration; });
        var hasKill  = children.some(function (c) { return Math.abs(c.startTime() - g.endSec)   < 1e-3 && c.vars && c.vars.autoAlpha === 0 && !c.vars.duration; });
        if (!hasEntry || !hasKill) {
          throw new Error("captions self-lint failed for group " + g.id + ": entry=" + hasEntry + " kill=" + hasKill);
        }
      });
    })();
  </script>
</div>
</template>`;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));
}

function parseFontSizePx(token: string): number {
  const m = token.match(/^(\d+(?:\.\d+)?)px$/);
  return m ? Number(m[1]) : 64;
}
