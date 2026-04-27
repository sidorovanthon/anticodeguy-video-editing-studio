import type { Seam, SeamPlan, SceneMode } from "./types.js";

const HEADER_RE = /^#\s*Seam plan:\s*(\S+)\s*\(duration=(\d+)ms\)\s*$/;
const SEAM_RE =
  /^SEAM\s+(\d+)\s+at_ms=(\d+)\s+scene:\s*(head|split|full|overlay)\s+ends_at_ms=(\d+)\s*$/;
const GRAPHIC_RE = /^\s+graphic:\s*(\S+)\s*$/;
const DATA_RE = /^\s+data:\s*(.+)$/;

export function writeSeamPlan(plan: SeamPlan): string {
  const lines: string[] = [];
  lines.push(`# Seam plan: ${plan.episode_slug} (duration=${plan.master_duration_ms}ms)`);
  lines.push("");
  for (const seam of plan.seams) {
    lines.push(
      `SEAM ${seam.index} at_ms=${seam.at_ms} scene: ${seam.scene} ends_at_ms=${seam.ends_at_ms}`,
    );
    if (seam.graphic) {
      lines.push(`  graphic: ${seam.graphic.component}`);
      lines.push(`  data: ${JSON.stringify(seam.graphic.data)}`);
    }
  }
  lines.push("");
  return lines.join("\n");
}

export function readSeamPlan(md: string): SeamPlan {
  const lines = md.split(/\r?\n/);
  let episode_slug = "";
  let master_duration_ms = 0;
  const seams: Seam[] = [];
  let current: Seam | null = null;

  for (const line of lines) {
    const headerMatch = HEADER_RE.exec(line);
    if (headerMatch) {
      episode_slug = headerMatch[1];
      master_duration_ms = Number(headerMatch[2]);
      continue;
    }
    const seamMatch = SEAM_RE.exec(line);
    if (seamMatch) {
      if (current) seams.push(current);
      current = {
        index: Number(seamMatch[1]),
        at_ms: Number(seamMatch[2]),
        scene: seamMatch[3] as SceneMode,
        ends_at_ms: Number(seamMatch[4]),
      };
      continue;
    }
    const graphicMatch = GRAPHIC_RE.exec(line);
    if (graphicMatch && current) {
      current.graphic = {
        component: graphicMatch[1],
        data: current.graphic?.data ?? {},
      };
      continue;
    }
    const dataMatch = DATA_RE.exec(line);
    if (dataMatch && current) {
      const parsed = JSON.parse(dataMatch[1]) as Record<string, unknown>;
      if (current.graphic) {
        current.graphic.data = parsed;
      } else {
        current.graphic = { component: "", data: parsed };
      }
      continue;
    }
  }
  if (current) seams.push(current);

  return { episode_slug, master_duration_ms, seams };
}
