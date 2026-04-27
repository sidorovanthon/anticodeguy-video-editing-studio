import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const COMPONENTS_DIR = path.resolve(__dirname, "../../../design-system/components");

export function loadComponentTemplate(name: string): string {
  return readFileSync(path.join(COMPONENTS_DIR, `${name}.html`), "utf8");
}

export function loadBaseCss(): string {
  return readFileSync(path.join(COMPONENTS_DIR, "_base.css"), "utf8");
}

export function fillTemplate(template: string, data: Record<string, unknown>): string {
  return template.replace(/\{\{([A-Z_]+)\}\}/g, (_, key) => {
    const v = data[key.toLowerCase()];
    if (v === undefined) return "";
    if (typeof v === "string" || typeof v === "number") return String(v);
    return JSON.stringify(v);
  });
}
