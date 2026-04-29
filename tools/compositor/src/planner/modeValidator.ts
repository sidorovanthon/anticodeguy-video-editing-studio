// tools/compositor/src/planner/modeValidator.ts
import type { SeamPlan, GraphicSource } from "./types.js";

export function validateSeamPlan(plan: SeamPlan, seamsInsideByScene: Map<number, number>): void {
  for (let i = 0; i < plan.scenes.length; i++) {
    const s = plan.scenes[i];
    const dur = s.endMs - s.startMs;
    const seams = seamsInsideByScene.get(i) ?? 0;

    if (seams > 1 && s.mode === "head") {
      throw new Error(`scene ${i + 1}: seamsInside=${seams} but mode=head; head requires ≤1 seam`);
    }
    if (s.narrativePosition === "outro") {
      const ok = s.graphic.kind === "catalog" && s.graphic.name === "subscribe-cta";
      if (s.mode !== "overlay" || !ok) {
        throw new Error(`scene ${i + 1}: outro must be mode=overlay + graphic=catalog/subscribe-cta`);
      }
    }
    if (dur < 1500 && s.mode !== "head" && s.mode !== "overlay") {
      throw new Error(`scene ${i + 1}: short scene (${dur}ms) must be head or overlay`);
    }
    if ((s.mode === "split" || s.mode === "broll" || s.mode === "overlay") &&
        s.graphic.kind === "none") {
      throw new Error(`scene ${i + 1}: ${s.mode} requires a graphic (got source=none)`);
    }
    if (i === 0) continue;
    const prev = plan.scenes[i - 1];

    if (prev.mode === "head" && s.mode === "head") {
      throw new Error(`scenes ${i}-${i + 1}: head→head transition forbidden`);
    }
    if ((prev.mode === "head" && s.mode === "overlay") ||
        (prev.mode === "overlay" && s.mode === "head")) {
      throw new Error(`scenes ${i}-${i + 1}: head→overlay/overlay→head forbidden`);
    }
    if (prev.mode === "overlay" && s.mode === "overlay") {
      throw new Error(`scenes ${i}-${i + 1}: overlay→overlay forbidden`);
    }
    if (prev.mode === "split" && s.mode === "split" && graphicEqual(prev.graphic, s.graphic)) {
      throw new Error(`scenes ${i}-${i + 1}: same-graphic split→split forbidden`);
    }
    if (prev.mode === "broll" && s.mode === "broll" && graphicEqual(prev.graphic, s.graphic)) {
      throw new Error(`scenes ${i}-${i + 1}: same-graphic broll→broll forbidden`);
    }
  }
}

function graphicEqual(a: GraphicSource, b: GraphicSource): boolean {
  if (a.kind !== b.kind) return false;
  if (a.kind === "none") return true;
  if (a.kind === "catalog" && b.kind === "catalog") return a.name === b.name;
  if (a.kind === "generative" && b.kind === "generative") return a.brief.trim() === b.brief.trim();
  return false;
}
