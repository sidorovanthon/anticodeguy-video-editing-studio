import { createHash } from "node:crypto";

export interface PromptHashInput {
  prompt: string;
  model: string;
  allowedTools: string[];
}

/**
 * Canonical sha256 over the inputs that determine subagent output. Used for
 * resume-cache invalidation: same hash → safe to skip; different hash →
 * regenerate. allowedTools are sorted for order-stability.
 */
export function computePromptHash(input: PromptHashInput): string {
  const canonical = JSON.stringify({
    prompt: input.prompt,
    model: input.model,
    allowedTools: [...input.allowedTools].sort(),
  });
  return "sha256:" + createHash("sha256").update(canonical).digest("hex");
}
