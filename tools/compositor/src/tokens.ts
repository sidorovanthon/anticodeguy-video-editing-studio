import { readFileSync } from "node:fs";

export type TokenTree = { [k: string]: TokenTree | string | number };

function flatten(
  obj: TokenTree,
  prefix: string,
  out: Record<string, string | number>,
): void {
  for (const [key, value] of Object.entries(obj)) {
    const name = prefix ? `${prefix}-${key}` : key;
    if (value !== null && typeof value === "object") {
      flatten(value as TokenTree, name, out);
    } else {
      out[name] = value as string | number;
    }
  }
}

export function tokensToCss(tokens: TokenTree): string {
  const flat: Record<string, string | number> = {};
  flatten(tokens, "", flat);
  const lines = [":root {"];
  for (const [name, value] of Object.entries(flat)) {
    lines.push(`  --${name}: ${value};`);
  }
  lines.push("}");
  lines.push("");
  return lines.join("\n");
}

export function loadTokensCss(filePath: string): string {
  const raw = readFileSync(filePath, "utf8");
  const tokens = JSON.parse(raw) as TokenTree;
  return tokensToCss(tokens);
}
