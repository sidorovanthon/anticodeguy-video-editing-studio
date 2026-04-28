import { readFileSync } from "node:fs";

export type TokenTree = { [k: string]: TokenTree | string | number };

const FENCE_RE = /```json\s+hyperframes-tokens\s*\n([\s\S]*?)\n```/m;

export function parseDesignMd(markdown: string): TokenTree {
  const match = markdown.match(FENCE_RE);
  if (!match) {
    throw new Error("DESIGN.md: no fenced `hyperframes-tokens` JSON block found");
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(match[1]);
  } catch (e) {
    throw new Error(`DESIGN.md: hyperframes-tokens block is not valid JSON: ${(e as Error).message}`);
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("DESIGN.md: hyperframes-tokens block must be a JSON object");
  }
  return parsed as TokenTree;
}

export function loadDesignMd(filePath: string): TokenTree {
  return parseDesignMd(readFileSync(filePath, "utf8"));
}

function flatten(obj: TokenTree, prefix: string, out: Record<string, string | number>): void {
  for (const [key, value] of Object.entries(obj)) {
    const name = prefix ? `${prefix}-${key}` : key;
    if (value !== null && typeof value === "object") {
      flatten(value as TokenTree, name, out);
    } else {
      out[name] = value as string | number;
    }
  }
}

export function designMdToCss(tree: TokenTree): string {
  const flat: Record<string, string | number> = {};
  flatten(tree, "", flat);
  const lines = [":root {"];
  for (const [name, value] of Object.entries(flat)) {
    lines.push(`  --${name}: ${value};`);
  }
  lines.push("}");
  lines.push("");
  return lines.join("\n");
}

export function resolveToken(tree: TokenTree, dottedPath: string): string {
  const parts = dottedPath.split(".");
  let cursor: TokenTree | string | number = tree;
  for (const part of parts) {
    if (cursor === null || typeof cursor !== "object" || Array.isArray(cursor)) {
      throw new Error(`resolveToken: '${dottedPath}' missing — '${part}' has no parent object`);
    }
    if (!(part in (cursor as TokenTree))) {
      throw new Error(`resolveToken: '${dottedPath}' not found in DESIGN.md tokens`);
    }
    cursor = (cursor as TokenTree)[part];
  }
  if (cursor !== null && typeof cursor === "object") {
    throw new Error(`resolveToken: '${dottedPath}' resolves to a subtree, not a leaf value`);
  }
  return String(cursor);
}
