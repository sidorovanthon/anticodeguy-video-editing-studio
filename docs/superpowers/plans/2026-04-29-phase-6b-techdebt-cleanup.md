# Phase 6b Tech-Debt Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land crash-safe resumable Stage-2 pipeline state (D19), measured timeout default (D3), upstream-only fixes for catalog selector leakage and flowchart aspect ratio, with a narrow HF-audit gate up front to avoid reinvention.

**Architecture:** Single TypeScript state module + thin CLI under `tools/compositor/`, called from the three Stage-2 bash wrappers. Per-step manifests scoped to `stage-2-composite/`, top-level `state.json` for handoff/overview. Atomic writes via write-temp-rename. Hash-based resume for the expensive `generate` step only; trust-the-operator with explicit `invalidate` command everywhere else. Catalog/lint/flowchart fixes are upstream issues + planner-prompt gating, no local rewriters.

**Tech Stack:** Node 22, TypeScript, vitest, bash. No new runtime dependencies — only Node stdlib (`node:fs`, `node:crypto`, `node:path`).

**Spec:** `docs/superpowers/specs/2026-04-29-phase-6b-techdebt-cleanup-design.md`

---

## File Structure

**New files (under `tools/compositor/src/state/`):**
- `types.ts` — schema-versioned interfaces for `state.json` and `generate.manifest.json`.
- `atomicWrite.ts` — single-purpose helper: `writeJsonAtomic(path, value)`.
- `episodeState.ts` — read/mutate `state.json` and step manifests. Pure functions over a base directory.
- `promptHash.ts` — canonical sha256 over `{prompt, model, allowedTools}`.

**New CLI:**
- `tools/compositor/src/bin/episode-state.ts` — argv parser dispatching to `episodeState.ts`.

**New tests (under `tools/compositor/test/state/`):**
- `atomicWrite.test.ts`
- `episodeState.test.ts`
- `promptHash.test.ts`

**New tooling:**
- `tools/compositor/src/bin/aggregate-generate-wallclocks.ts` — read all `generate.manifest.json` across episodes, print percentiles.

**Modified:**
- `tools/compositor/package.json` — add `bin` entries.
- `tools/compositor/src/planner/generativeDispatcher.ts` — record `wallclockMs` + prompt hash on each scene completion.
- `tools/compositor/src/planner/realDispatcher.ts` — timeout default + comment header (after measurements land).
- `tools/compositor/src/planner/prompts/generative.md` — gate `flowchart` to landscape only.
- `tools/scripts/run-stage2-plan.sh`, `run-stage2-generate.sh`, `run-stage2-compose.sh` — call `episode-state` CLI at start/end.
- `docs/operations/planner-pipeline-fixes/findings.md` — link upstream issues for D15/D21.
- `docs/superpowers/specs/2026-04-29-phase-6b-techdebt-cleanup-design.md` — appended audit findings + recorded issue URLs.

**New spec stub:**
- `docs/superpowers/specs/2026-04-29-hf-reinvention-audit-design.md` — placeholder for §6 follow-up.

---

## Task 1: Narrow HF Audit (§0)

**Files:**
- Modify: `docs/superpowers/specs/2026-04-29-phase-6b-techdebt-cleanup-design.md` — append findings block.

- [ ] **Step 1: Read all six HF doc files**

Read in this order:
- `tools/compositor/node_modules/hyperframes/dist/docs/compositions.md`
- `tools/compositor/node_modules/hyperframes/dist/docs/data-attributes.md`
- `tools/compositor/node_modules/hyperframes/dist/docs/gsap.md`
- `tools/compositor/node_modules/hyperframes/dist/docs/rendering.md`
- `tools/compositor/node_modules/hyperframes/dist/docs/troubleshooting.md`
- `tools/compositor/node_modules/hyperframes/dist/docs/examples.md`

- [ ] **Step 2: Read shared templates and skills**

- `tools/compositor/node_modules/hyperframes/dist/templates/_shared/AGENTS.md`
- `tools/compositor/node_modules/hyperframes/dist/templates/_shared/CLAUDE.md`
- `tools/compositor/node_modules/hyperframes/dist/skills/hyperframes/**` (if any `.md` files exist — `ls -R` first)
- `tools/compositor/node_modules/hyperframes/dist/skills/hyperframes-cli/**`

- [ ] **Step 3: Append findings block to the spec**

After the `## §0 — Narrow HF Audit` section's "Stop condition" line, append:

```markdown

### HF-audit findings (narrow)

- [pertains-to: D19] <summary of what HF has/lacks for episode-state>. Decision: <D19 unchanged | revised as X>.
- [pertains-to: D3] <summary of what HF has/lacks for timeouts>. Decision: <D3 unchanged | revised as X>.
- [pertains-to: D15/D21] <summary of selector conventions in HF docs>. Decision: <upstream issue framing confirmed | revised>.
- [pertains-to: flowchart aspect> <summary of composition-resolution semantics>. Decision: <§4 unchanged | revised>.
```

Replace the `<...>` markers with concrete findings. If a question has no relevant HF feature, write "Not found in audited docs; D-N proceeds as designed."

If any finding requires changes to §1–§4, edit the affected section(s) in the same commit and note the change explicitly: "**§1 amended after audit:** ..."

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-04-29-phase-6b-techdebt-cleanup-design.md
git commit -m "spec(phase-6b): append narrow HF-audit findings"
```

---

## Task 2: State module — types

**Files:**
- Create: `tools/compositor/src/state/types.ts`

- [ ] **Step 1: Write the types file**

```typescript
// tools/compositor/src/state/types.ts
//
// Schema-versioned types for episode state. Bump SCHEMA_VERSION on any
// breaking change; readers must reject unknown versions.

export const STATE_SCHEMA_VERSION = 1 as const;
export const GENERATE_MANIFEST_SCHEMA_VERSION = 1 as const;

export type StepName = "plan" | "generate" | "compose" | "preview";
export type CheckpointId = "CP1" | "CP2" | "CP3" | "CP4";

export interface EpisodeState {
  schemaVersion: typeof STATE_SCHEMA_VERSION;
  episode: string;
  stage: "stage-2";
  lastCheckpoint: CheckpointId | null;
  completedSteps: StepName[];
  inProgressStep: StepName | null;
  stepStartedAt: string | null; // ISO 8601
  fixesApplied: string[];
  lastUpdate: string; // ISO 8601
}

export interface GenerateSceneEntry {
  kind: "generative" | "catalog" | "none";
  outputPath: string;
  promptHash: string; // "sha256:..."
  outputBytes: number;
  wallclockMs: number;
  completedAt: string; // ISO 8601
}

export interface GenerateManifest {
  schemaVersion: typeof GENERATE_MANIFEST_SCHEMA_VERSION;
  scenes: Record<string, GenerateSceneEntry>;
}
```

- [ ] **Step 2: Commit**

```bash
git add tools/compositor/src/state/types.ts
git commit -m "feat(state): schema-versioned types for episode state"
```

---

## Task 3: Atomic write helper

**Files:**
- Create: `tools/compositor/src/state/atomicWrite.ts`
- Test: `tools/compositor/test/state/atomicWrite.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// tools/compositor/test/state/atomicWrite.test.ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { writeJsonAtomic } from "../../src/state/atomicWrite.js";

describe("writeJsonAtomic", () => {
  let dir: string;
  beforeEach(() => { dir = mkdtempSync(path.join(tmpdir(), "atom-")); });
  afterEach(() => { rmSync(dir, { recursive: true, force: true }); });

  it("writes JSON to the target path", () => {
    const target = path.join(dir, "out.json");
    writeJsonAtomic(target, { a: 1 });
    expect(JSON.parse(readFileSync(target, "utf-8"))).toEqual({ a: 1 });
  });

  it("overwrites existing file in-place", () => {
    const target = path.join(dir, "out.json");
    writeJsonAtomic(target, { a: 1 });
    writeJsonAtomic(target, { a: 2 });
    expect(JSON.parse(readFileSync(target, "utf-8"))).toEqual({ a: 2 });
  });

  it("does not leave a .tmp sibling on success", () => {
    const target = path.join(dir, "out.json");
    writeJsonAtomic(target, { a: 1 });
    expect(existsSync(target + ".tmp")).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/state/atomicWrite.test.ts`
Expected: FAIL with "Cannot find module '../../src/state/atomicWrite.js'".

- [ ] **Step 3: Implement**

```typescript
// tools/compositor/src/state/atomicWrite.ts
import { writeFileSync, renameSync } from "node:fs";

/**
 * Write JSON to `targetPath` atomically: write to `targetPath + ".tmp"` then
 * rename. Rename is atomic on NTFS and POSIX, so a crash leaves either the
 * old file or the new one — never a half-written file.
 */
export function writeJsonAtomic(targetPath: string, value: unknown): void {
  const tmpPath = targetPath + ".tmp";
  writeFileSync(tmpPath, JSON.stringify(value, null, 2) + "\n", "utf-8");
  renameSync(tmpPath, targetPath);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/compositor && npx vitest run test/state/atomicWrite.test.ts`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/state/atomicWrite.ts tools/compositor/test/state/atomicWrite.test.ts
git commit -m "feat(state): atomic write-temp-rename JSON helper"
```

---

## Task 4: Prompt hash

**Files:**
- Create: `tools/compositor/src/state/promptHash.ts`
- Test: `tools/compositor/test/state/promptHash.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// tools/compositor/test/state/promptHash.test.ts
import { describe, it, expect } from "vitest";
import { computePromptHash } from "../../src/state/promptHash.js";

describe("computePromptHash", () => {
  const base = { prompt: "hello", model: "claude-opus-4-7", allowedTools: ["Read", "Write"] };

  it("returns sha256: prefixed string", () => {
    const h = computePromptHash(base);
    expect(h).toMatch(/^sha256:[0-9a-f]{64}$/);
  });

  it("is stable across calls with identical input", () => {
    expect(computePromptHash(base)).toBe(computePromptHash(base));
  });

  it("is order-stable across allowedTools permutations", () => {
    const a = computePromptHash({ ...base, allowedTools: ["Read", "Write"] });
    const b = computePromptHash({ ...base, allowedTools: ["Write", "Read"] });
    expect(a).toBe(b);
  });

  it("changes when prompt changes", () => {
    expect(computePromptHash(base)).not.toBe(computePromptHash({ ...base, prompt: "hello!" }));
  });

  it("changes when model changes", () => {
    expect(computePromptHash(base)).not.toBe(computePromptHash({ ...base, model: "claude-sonnet-4-6" }));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/state/promptHash.test.ts`
Expected: FAIL with module-not-found.

- [ ] **Step 3: Implement**

```typescript
// tools/compositor/src/state/promptHash.ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/compositor && npx vitest run test/state/promptHash.test.ts`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/state/promptHash.ts tools/compositor/test/state/promptHash.test.ts
git commit -m "feat(state): canonical prompt hash for resume-cache"
```

---

## Task 5: episodeState — init + read

**Files:**
- Create: `tools/compositor/src/state/episodeState.ts`
- Test: `tools/compositor/test/state/episodeState.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// tools/compositor/test/state/episodeState.test.ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { initState, readState } from "../../src/state/episodeState.js";

describe("episodeState init + read", () => {
  let episodeDir: string;
  beforeEach(() => { episodeDir = mkdtempSync(path.join(tmpdir(), "ep-")); });
  afterEach(() => { rmSync(episodeDir, { recursive: true, force: true }); });

  it("initState creates state.json with empty completedSteps", () => {
    initState(episodeDir, "test-slug");
    const s = readState(episodeDir);
    expect(s.episode).toBe("test-slug");
    expect(s.completedSteps).toEqual([]);
    expect(s.inProgressStep).toBeNull();
    expect(s.lastCheckpoint).toBeNull();
    expect(s.schemaVersion).toBe(1);
  });

  it("initState does not overwrite existing state", () => {
    initState(episodeDir, "test-slug");
    expect(() => initState(episodeDir, "test-slug")).toThrow(/already exists/);
  });

  it("readState rejects unknown schema version", () => {
    const file = path.join(episodeDir, "state.json");
    writeFileSync(file, JSON.stringify({ schemaVersion: 999 }));
    expect(() => readState(episodeDir)).toThrow(/schemaVersion/);
  });

  it("readState throws clear error when missing", () => {
    expect(() => readState(episodeDir)).toThrow(/state\.json not found/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/state/episodeState.test.ts`
Expected: FAIL with module-not-found.

- [ ] **Step 3: Implement init + read**

```typescript
// tools/compositor/src/state/episodeState.ts
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { writeJsonAtomic } from "./atomicWrite.js";
import {
  EpisodeState,
  STATE_SCHEMA_VERSION,
} from "./types.js";

export function statePath(episodeDir: string): string {
  return path.join(episodeDir, "state.json");
}

export function initState(episodeDir: string, episodeSlug: string): EpisodeState {
  const file = statePath(episodeDir);
  if (existsSync(file)) {
    throw new Error(`state.json already exists at ${file}`);
  }
  const now = new Date().toISOString();
  const state: EpisodeState = {
    schemaVersion: STATE_SCHEMA_VERSION,
    episode: episodeSlug,
    stage: "stage-2",
    lastCheckpoint: null,
    completedSteps: [],
    inProgressStep: null,
    stepStartedAt: null,
    fixesApplied: [],
    lastUpdate: now,
  };
  writeJsonAtomic(file, state);
  return state;
}

export function readState(episodeDir: string): EpisodeState {
  const file = statePath(episodeDir);
  if (!existsSync(file)) {
    throw new Error(`state.json not found at ${file}`);
  }
  const parsed = JSON.parse(readFileSync(file, "utf-8"));
  if (parsed.schemaVersion !== STATE_SCHEMA_VERSION) {
    throw new Error(
      `state.json schemaVersion ${parsed.schemaVersion} not supported (expected ${STATE_SCHEMA_VERSION})`
    );
  }
  return parsed as EpisodeState;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/compositor && npx vitest run test/state/episodeState.test.ts`
Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/state/episodeState.ts tools/compositor/test/state/episodeState.test.ts
git commit -m "feat(state): initState and readState"
```

---

## Task 6: episodeState — markStepStarted / markStepDone / recordFix

**Files:**
- Modify: `tools/compositor/src/state/episodeState.ts`
- Modify: `tools/compositor/test/state/episodeState.test.ts`

- [ ] **Step 1: Append failing tests**

Append to `tools/compositor/test/state/episodeState.test.ts`:

```typescript
import { markStepStarted, markStepDone, recordFix } from "../../src/state/episodeState.js";

describe("step transitions", () => {
  let episodeDir: string;
  beforeEach(() => {
    episodeDir = mkdtempSync(path.join(tmpdir(), "ep-"));
    initState(episodeDir, "test-slug");
  });
  afterEach(() => { rmSync(episodeDir, { recursive: true, force: true }); });

  it("markStepStarted sets inProgressStep and stepStartedAt", () => {
    markStepStarted(episodeDir, "plan");
    const s = readState(episodeDir);
    expect(s.inProgressStep).toBe("plan");
    expect(s.stepStartedAt).not.toBeNull();
  });

  it("markStepDone clears inProgressStep, appends to completedSteps, sets checkpoint", () => {
    markStepStarted(episodeDir, "plan");
    markStepDone(episodeDir, "plan", "CP1");
    const s = readState(episodeDir);
    expect(s.inProgressStep).toBeNull();
    expect(s.stepStartedAt).toBeNull();
    expect(s.completedSteps).toEqual(["plan"]);
    expect(s.lastCheckpoint).toBe("CP1");
  });

  it("markStepDone is idempotent — re-calling does not duplicate completedSteps", () => {
    markStepStarted(episodeDir, "plan");
    markStepDone(episodeDir, "plan", "CP1");
    markStepDone(episodeDir, "plan", "CP1");
    const s = readState(episodeDir);
    expect(s.completedSteps).toEqual(["plan"]);
  });

  it("recordFix appends and dedupes", () => {
    recordFix(episodeDir, "D17");
    recordFix(episodeDir, "D21");
    recordFix(episodeDir, "D17");
    const s = readState(episodeDir);
    expect(s.fixesApplied).toEqual(["D17", "D21"]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tools/compositor && npx vitest run test/state/episodeState.test.ts`
Expected: FAIL with import errors for `markStepStarted` etc.

- [ ] **Step 3: Implement the three functions**

Append to `tools/compositor/src/state/episodeState.ts`:

```typescript
import type { StepName, CheckpointId } from "./types.js";

function mutate(episodeDir: string, fn: (s: EpisodeState) => EpisodeState): EpisodeState {
  const current = readState(episodeDir);
  const next = fn(current);
  next.lastUpdate = new Date().toISOString();
  writeJsonAtomic(statePath(episodeDir), next);
  return next;
}

export function markStepStarted(episodeDir: string, step: StepName): EpisodeState {
  return mutate(episodeDir, (s) => ({
    ...s,
    inProgressStep: step,
    stepStartedAt: new Date().toISOString(),
  }));
}

export function markStepDone(
  episodeDir: string,
  step: StepName,
  checkpoint: CheckpointId,
): EpisodeState {
  return mutate(episodeDir, (s) => ({
    ...s,
    inProgressStep: null,
    stepStartedAt: null,
    completedSteps: s.completedSteps.includes(step)
      ? s.completedSteps
      : [...s.completedSteps, step],
    lastCheckpoint: checkpoint,
  }));
}

export function recordFix(episodeDir: string, label: string): EpisodeState {
  return mutate(episodeDir, (s) => ({
    ...s,
    fixesApplied: s.fixesApplied.includes(label)
      ? s.fixesApplied
      : [...s.fixesApplied, label],
  }));
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools/compositor && npx vitest run test/state/episodeState.test.ts`
Expected: PASS, 8 tests total.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/state/episodeState.ts tools/compositor/test/state/episodeState.test.ts
git commit -m "feat(state): step transitions and fix recording"
```

---

## Task 7: episodeState — generate manifest read/record

**Files:**
- Modify: `tools/compositor/src/state/episodeState.ts`
- Modify: `tools/compositor/test/state/episodeState.test.ts`

- [ ] **Step 1: Append failing tests**

Append to `tools/compositor/test/state/episodeState.test.ts`:

```typescript
import {
  readGenerateManifest,
  recordSceneCompleted,
  isSceneSatisfied,
} from "../../src/state/episodeState.js";
import { mkdirSync, writeFileSync as fsWriteFileSync } from "node:fs";

describe("generate manifest", () => {
  let episodeDir: string;
  let stageDir: string;
  beforeEach(() => {
    episodeDir = mkdtempSync(path.join(tmpdir(), "ep-"));
    stageDir = path.join(episodeDir, "stage-2-composite");
    mkdirSync(stageDir, { recursive: true });
    initState(episodeDir, "test-slug");
  });
  afterEach(() => { rmSync(episodeDir, { recursive: true, force: true }); });

  it("readGenerateManifest returns empty when missing", () => {
    const m = readGenerateManifest(episodeDir);
    expect(m.scenes).toEqual({});
  });

  it("recordSceneCompleted persists scene entry", () => {
    recordSceneCompleted(episodeDir, "B-1", {
      kind: "generative",
      outputPath: "compositions/scene-B-1.html",
      promptHash: "sha256:abc",
      outputBytes: 4096,
      wallclockMs: 250000,
    });
    const m = readGenerateManifest(episodeDir);
    expect(m.scenes["B-1"].promptHash).toBe("sha256:abc");
    expect(m.scenes["B-1"].wallclockMs).toBe(250000);
  });

  it("isSceneSatisfied true when hash matches and file exists at >= 256 B", () => {
    const outRel = "compositions/scene-B-1.html";
    const outAbs = path.join(stageDir, outRel);
    mkdirSync(path.dirname(outAbs), { recursive: true });
    fsWriteFileSync(outAbs, "x".repeat(4096));
    recordSceneCompleted(episodeDir, "B-1", {
      kind: "generative",
      outputPath: outRel,
      promptHash: "sha256:abc",
      outputBytes: 4096,
      wallclockMs: 100,
    });
    expect(isSceneSatisfied(episodeDir, "B-1", "sha256:abc")).toBe(true);
  });

  it("isSceneSatisfied false on hash mismatch", () => {
    recordSceneCompleted(episodeDir, "B-1", {
      kind: "generative",
      outputPath: "compositions/scene-B-1.html",
      promptHash: "sha256:abc",
      outputBytes: 4096,
      wallclockMs: 100,
    });
    expect(isSceneSatisfied(episodeDir, "B-1", "sha256:DIFFERENT")).toBe(false);
  });

  it("isSceneSatisfied false when output file missing", () => {
    recordSceneCompleted(episodeDir, "B-1", {
      kind: "generative",
      outputPath: "compositions/missing.html",
      promptHash: "sha256:abc",
      outputBytes: 4096,
      wallclockMs: 100,
    });
    expect(isSceneSatisfied(episodeDir, "B-1", "sha256:abc")).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tools/compositor && npx vitest run test/state/episodeState.test.ts`
Expected: FAIL with import errors.

- [ ] **Step 3: Implement manifest functions**

Append to `tools/compositor/src/state/episodeState.ts`:

```typescript
import { statSync } from "node:fs";
import {
  GenerateManifest,
  GenerateSceneEntry,
  GENERATE_MANIFEST_SCHEMA_VERSION,
} from "./types.js";

const MIN_SCENE_BYTES = 256;

export function generateManifestPath(episodeDir: string): string {
  return path.join(episodeDir, "stage-2-composite", "generate.manifest.json");
}

export function readGenerateManifest(episodeDir: string): GenerateManifest {
  const file = generateManifestPath(episodeDir);
  if (!existsSync(file)) {
    return { schemaVersion: GENERATE_MANIFEST_SCHEMA_VERSION, scenes: {} };
  }
  const parsed = JSON.parse(readFileSync(file, "utf-8"));
  if (parsed.schemaVersion !== GENERATE_MANIFEST_SCHEMA_VERSION) {
    throw new Error(
      `generate.manifest.json schemaVersion ${parsed.schemaVersion} not supported`
    );
  }
  return parsed as GenerateManifest;
}

export function recordSceneCompleted(
  episodeDir: string,
  sceneId: string,
  entry: Omit<GenerateSceneEntry, "completedAt">,
): GenerateManifest {
  const m = readGenerateManifest(episodeDir);
  m.scenes[sceneId] = { ...entry, completedAt: new Date().toISOString() };
  writeJsonAtomic(generateManifestPath(episodeDir), m);
  return m;
}

/**
 * True iff the manifest has a recorded scene with matching prompt hash AND
 * the recorded output file still exists with size >= MIN_SCENE_BYTES.
 * Used by the dispatcher to skip already-generated scenes on resume.
 */
export function isSceneSatisfied(
  episodeDir: string,
  sceneId: string,
  expectedHash: string,
): boolean {
  const m = readGenerateManifest(episodeDir);
  const entry = m.scenes[sceneId];
  if (!entry) return false;
  if (entry.promptHash !== expectedHash) return false;
  const abs = path.join(episodeDir, "stage-2-composite", entry.outputPath);
  if (!existsSync(abs)) return false;
  try {
    const sz = statSync(abs).size;
    return sz >= MIN_SCENE_BYTES;
  } catch {
    return false;
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools/compositor && npx vitest run test/state/episodeState.test.ts`
Expected: PASS, 13 tests total.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/state/episodeState.ts tools/compositor/test/state/episodeState.test.ts
git commit -m "feat(state): generate manifest read + record + satisfaction check"
```

---

## Task 8: episodeState — invalidate

**Files:**
- Modify: `tools/compositor/src/state/episodeState.ts`
- Modify: `tools/compositor/test/state/episodeState.test.ts`

- [ ] **Step 1: Append failing test**

Append to `tools/compositor/test/state/episodeState.test.ts`:

```typescript
import { invalidateStep } from "../../src/state/episodeState.js";

describe("invalidateStep", () => {
  let episodeDir: string;
  beforeEach(() => {
    episodeDir = mkdtempSync(path.join(tmpdir(), "ep-"));
    initState(episodeDir, "test-slug");
  });
  afterEach(() => { rmSync(episodeDir, { recursive: true, force: true }); });

  it("removes step from completedSteps", () => {
    markStepStarted(episodeDir, "compose");
    markStepDone(episodeDir, "compose", "CP3");
    invalidateStep(episodeDir, "compose");
    const s = readState(episodeDir);
    expect(s.completedSteps).not.toContain("compose");
  });

  it("deletes generate.manifest.json when invalidating generate", () => {
    recordSceneCompleted(episodeDir, "B-1", {
      kind: "generative",
      outputPath: "x.html",
      promptHash: "sha256:abc",
      outputBytes: 1024,
      wallclockMs: 100,
    });
    invalidateStep(episodeDir, "generate");
    expect(existsSync(generateManifestPath(episodeDir))).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/state/episodeState.test.ts`
Expected: FAIL with import error.

- [ ] **Step 3: Implement**

Append to `tools/compositor/src/state/episodeState.ts`:

```typescript
import { unlinkSync } from "node:fs";

export function invalidateStep(episodeDir: string, step: StepName): EpisodeState {
  const next = mutate(episodeDir, (s) => ({
    ...s,
    completedSteps: s.completedSteps.filter((n) => n !== step),
    inProgressStep: s.inProgressStep === step ? null : s.inProgressStep,
    stepStartedAt: s.inProgressStep === step ? null : s.stepStartedAt,
  }));
  if (step === "generate") {
    const m = generateManifestPath(episodeDir);
    if (existsSync(m)) unlinkSync(m);
  }
  return next;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/compositor && npx vitest run test/state/episodeState.test.ts`
Expected: PASS, 15 tests total.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/state/episodeState.ts tools/compositor/test/state/episodeState.test.ts
git commit -m "feat(state): invalidateStep operator override"
```

---

## Task 9: CLI wrapper

**Files:**
- Create: `tools/compositor/src/bin/episode-state.ts`
- Modify: `tools/compositor/package.json` — add `bin` entry.

- [ ] **Step 1: Write the CLI**

```typescript
// tools/compositor/src/bin/episode-state.ts
//
// Thin argv parser. All real work lives in ../state/episodeState.ts so it
// can be imported directly by the compositor when wallclock-precise calls
// matter (avoiding a child-process round-trip per scene).

import {
  initState,
  markStepStarted,
  markStepDone,
  recordFix,
  recordSceneCompleted,
  invalidateStep,
  readState,
} from "../state/episodeState.js";
import type { StepName, CheckpointId } from "../state/types.js";

function arg(name: string, argv: string[]): string | undefined {
  const i = argv.indexOf("--" + name);
  return i >= 0 ? argv[i + 1] : undefined;
}

function required(name: string, argv: string[]): string {
  const v = arg(name, argv);
  if (!v) {
    console.error(`error: --${name} is required`);
    process.exit(2);
  }
  return v;
}

function main(argv: string[]): void {
  const [cmd, ...rest] = argv;
  switch (cmd) {
    case "init": {
      const ep = required("episode-dir", rest);
      const slug = required("slug", rest);
      initState(ep, slug);
      return;
    }
    case "mark-step-started": {
      markStepStarted(required("episode-dir", rest), required("step", rest) as StepName);
      return;
    }
    case "mark-step-done": {
      markStepDone(
        required("episode-dir", rest),
        required("step", rest) as StepName,
        required("checkpoint", rest) as CheckpointId,
      );
      return;
    }
    case "record-fix": {
      recordFix(required("episode-dir", rest), required("label", rest));
      return;
    }
    case "record-scene": {
      recordSceneCompleted(required("episode-dir", rest), required("scene", rest), {
        kind: (arg("kind", rest) as "generative" | "catalog" | "none") ?? "generative",
        outputPath: required("output-path", rest),
        promptHash: required("prompt-hash", rest),
        outputBytes: Number(required("output-bytes", rest)),
        wallclockMs: Number(required("wallclock-ms", rest)),
      });
      return;
    }
    case "invalidate": {
      invalidateStep(required("episode-dir", rest), required("step", rest) as StepName);
      return;
    }
    case "read": {
      const s = readState(required("episode-dir", rest));
      process.stdout.write(JSON.stringify(s, null, 2) + "\n");
      return;
    }
    default:
      console.error(
        "usage: episode-state <init|mark-step-started|mark-step-done|record-fix|record-scene|invalidate|read> [args]"
      );
      process.exit(2);
  }
}

main(process.argv.slice(2));
```

- [ ] **Step 2: Add bin entry to package.json**

Edit `tools/compositor/package.json` — add a `bin` block above `scripts`:

```json
  "bin": {
    "episode-state": "./dist/bin/episode-state.js"
  },
```

- [ ] **Step 3: Sanity-test CLI via tsx**

Run from `tools/compositor`:
```bash
mkdir -p /tmp/cli-smoke && rm -rf /tmp/cli-smoke/*
npx tsx src/bin/episode-state.ts init --episode-dir /tmp/cli-smoke --slug test
npx tsx src/bin/episode-state.ts mark-step-started --episode-dir /tmp/cli-smoke --step plan
npx tsx src/bin/episode-state.ts mark-step-done --episode-dir /tmp/cli-smoke --step plan --checkpoint CP1
npx tsx src/bin/episode-state.ts read --episode-dir /tmp/cli-smoke
```

Expected: final `read` prints state JSON with `completedSteps: ["plan"]`, `lastCheckpoint: "CP1"`.

- [ ] **Step 4: Build and confirm dist artifact exists**

Run: `cd tools/compositor && npm run build`
Expected: `dist/bin/episode-state.js` exists.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/bin/episode-state.ts tools/compositor/package.json
git commit -m "feat(state): episode-state CLI"
```

---

## Task 10: Wire dispatcher to record scenes

**Files:**
- Modify: `tools/compositor/src/planner/generativeDispatcher.ts`
- Modify: `tools/compositor/src/planner/realDispatcher.ts` (export model id for hashing)

- [ ] **Step 1: Read current dispatcher code**

Read `tools/compositor/src/planner/generativeDispatcher.ts` end-to-end. Identify:
- Where `generateOne` invokes the subagent (the call wrapped by D7's file-existence early-return).
- Where `generateAll` orchestrates `Promise.all`.
- How the prompt text is constructed.

Goal of edit: replace the file-existence early-return with the manifest-based `isSceneSatisfied` check, and on success call `recordSceneCompleted` with prompt hash + wallclock.

- [ ] **Step 2: Modify `generateOne`**

Replace the early-return block:

```typescript
import { computePromptHash } from "../state/promptHash.js";
import {
  isSceneSatisfied,
  recordSceneCompleted,
} from "../state/episodeState.js";

// inside generateOne, after promptText is built:
const promptHash = computePromptHash({
  prompt: promptText,
  model: opts.model ?? "claude-opus-4-7",
  allowedTools: opts.allowedTools ?? ["Read", "Write", "Bash"],
});

if (isSceneSatisfied(opts.episodeDir, scene.id, promptHash)) {
  return { ok: true, sceneId: scene.id, skipped: true };
}

const startedAt = Date.now();
const result = await dispatcher.run(promptText);
const wallclockMs = Date.now() - startedAt;

// after result is written to disk and validated:
recordSceneCompleted(opts.episodeDir, scene.id, {
  kind: "generative",
  outputPath: relativeOutputPath, // path.relative(stage2Dir, outAbs)
  promptHash,
  outputBytes: writtenBytes,
  wallclockMs,
});
```

Adapt variable names to whatever the existing function uses. Preserve all existing behavior outside resume + recording.

- [ ] **Step 3: Add `episodeDir`, `model`, `allowedTools` to `GenerateAllOptions`**

If the options interface doesn't already have them, add:

```typescript
episodeDir: string;            // required for state access
model?: string;                // default "claude-opus-4-7"
allowedTools?: string[];       // default ["Read", "Write", "Bash"]
```

Thread through from `generateAll` → `generateOne`.

- [ ] **Step 4: Run existing planner tests**

Run: `cd tools/compositor && npx vitest run test/planner/`
Expected: PASS (no regression). If a test invokes `generateAll`/`generateOne` directly, update the call site to pass `episodeDir` (use a tmpdir + `initState`).

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/planner/generativeDispatcher.ts
git commit -m "feat(state): dispatcher records scenes via manifest, hash-based resume"
```

---

## Task 11: Wire `run-stage2-plan.sh`

**Files:**
- Modify: `tools/scripts/run-stage2-plan.sh`

- [ ] **Step 1: Read current wrapper**

Read `tools/scripts/run-stage2-plan.sh` to find the script header (where args are parsed) and the success exit point.

- [ ] **Step 2: Add state hooks**

Insert near the top, after `EPISODE_DIR` is resolved:

```bash
EPISODE_STATE_BIN="$REPO_ROOT/tools/compositor/dist/bin/episode-state.js"
if [ ! -f "$EPISODE_STATE_BIN" ]; then
  echo "error: $EPISODE_STATE_BIN not found; run 'npm run build' in tools/compositor" >&2
  exit 1
fi
EPISODE_SLUG="$(basename "$EPISODE_DIR")"

# Initialize state.json if missing
if [ ! -f "$EPISODE_DIR/state.json" ]; then
  node "$EPISODE_STATE_BIN" init --episode-dir "$EPISODE_DIR" --slug "$EPISODE_SLUG"
fi

node "$EPISODE_STATE_BIN" mark-step-started --episode-dir "$EPISODE_DIR" --step plan
```

Insert just before successful `exit 0` (or end of script if no explicit exit):

```bash
node "$EPISODE_STATE_BIN" mark-step-done --episode-dir "$EPISODE_DIR" --step plan --checkpoint CP1
```

- [ ] **Step 3: Smoke-test against current episode**

Run from repo root:
```bash
EP=episodes/2026-04-29-desktop-software-licensing-it-turns-out
rm -f "$EP/state.json"
bash tools/scripts/run-stage2-plan.sh "$EP"  # adapt arg form to script
cat "$EP/state.json"
```

Expected: `state.json` exists with `completedSteps: ["plan"]`, `lastCheckpoint: "CP1"`.

- [ ] **Step 4: Commit**

```bash
git add tools/scripts/run-stage2-plan.sh
git commit -m "feat(state): run-stage2-plan.sh writes state.json"
```

---

## Task 12: Wire `run-stage2-generate.sh`

**Files:**
- Modify: `tools/scripts/run-stage2-generate.sh`

- [ ] **Step 1: Read current wrapper**

Read `tools/scripts/run-stage2-generate.sh` end-to-end.

- [ ] **Step 2: Add state hooks**

Same `EPISODE_STATE_BIN` resolution as Task 11. Then:

```bash
node "$EPISODE_STATE_BIN" mark-step-started --episode-dir "$EPISODE_DIR" --step generate
```

before the dispatcher invocation, and:

```bash
node "$EPISODE_STATE_BIN" mark-step-done --episode-dir "$EPISODE_DIR" --step generate --checkpoint CP2
```

after the dispatcher succeeds.

The dispatcher itself records per-scene manifest entries (Task 10); the wrapper only marks step-level boundaries.

- [ ] **Step 3: Smoke-test resume**

Run twice on the current episode (manually deleting one scene file mid-way to confirm only that scene regenerates):

```bash
EP=episodes/2026-04-29-desktop-software-licensing-it-turns-out
bash tools/scripts/run-stage2-generate.sh "$EP"
# Inspect: cat "$EP/stage-2-composite/generate.manifest.json"
rm "$EP/stage-2-composite/compositions/scene-B-1-*.html"  # one scene
bash tools/scripts/run-stage2-generate.sh "$EP"
# Expected: only the deleted scene was regenerated; manifest unchanged for others.
```

- [ ] **Step 4: Commit**

```bash
git add tools/scripts/run-stage2-generate.sh
git commit -m "feat(state): run-stage2-generate.sh writes state.json"
```

---

## Task 13: Wire `run-stage2-compose.sh`

**Files:**
- Modify: `tools/scripts/run-stage2-compose.sh`

- [ ] **Step 1: Read current wrapper**

Read `tools/scripts/run-stage2-compose.sh`.

- [ ] **Step 2: Add state hooks**

```bash
node "$EPISODE_STATE_BIN" mark-step-started --episode-dir "$EPISODE_DIR" --step compose
```

before the compose step starts, and:

```bash
node "$EPISODE_STATE_BIN" mark-step-done --episode-dir "$EPISODE_DIR" --step compose --checkpoint CP3
```

after compose succeeds.

If the same wrapper also drives preview rendering, add another pair:

```bash
node "$EPISODE_STATE_BIN" mark-step-started --episode-dir "$EPISODE_DIR" --step preview
# ... preview render ...
node "$EPISODE_STATE_BIN" mark-step-done --episode-dir "$EPISODE_DIR" --step preview --checkpoint CP4
```

- [ ] **Step 3: Smoke-test full chain**

```bash
EP=episodes/2026-04-29-desktop-software-licensing-it-turns-out
bash tools/scripts/run-stage2-plan.sh "$EP"
bash tools/scripts/run-stage2-generate.sh "$EP"
bash tools/scripts/run-stage2-compose.sh "$EP"
node tools/compositor/dist/bin/episode-state.js read --episode-dir "$EP"
```

Expected: `completedSteps` contains `plan`, `generate`, `compose`, and (if preview is in this wrapper) `preview`.

- [ ] **Step 4: Commit**

```bash
git add tools/scripts/run-stage2-compose.sh
git commit -m "feat(state): run-stage2-compose.sh writes state.json"
```

---

## Task 14: Wallclock aggregator + env-var override (D3 plumbing)

**Files:**
- Create: `tools/compositor/src/bin/aggregate-generate-wallclocks.ts`
- Modify: `tools/scripts/run-stage2-generate.sh` — read `HF_GENERATIVE_TIMEOUT_MS` and pass through.

- [ ] **Step 1: Write the aggregator**

```typescript
// tools/compositor/src/bin/aggregate-generate-wallclocks.ts
//
// Reads every episode's generate.manifest.json under episodes/, prints
// p50/p95/p99 of wallclockMs across all recorded scenes. Used to calibrate
// realDispatcher.timeoutMs.

import { readdirSync, existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import type { GenerateManifest } from "../state/types.js";

const repoRoot = process.argv[2] ?? process.cwd();
const episodesDir = path.join(repoRoot, "episodes");

function* allManifests(): Generator<GenerateManifest> {
  if (!existsSync(episodesDir)) return;
  for (const name of readdirSync(episodesDir)) {
    const m = path.join(episodesDir, name, "stage-2-composite", "generate.manifest.json");
    if (existsSync(m) && statSync(m).isFile()) {
      yield JSON.parse(readFileSync(m, "utf-8")) as GenerateManifest;
    }
  }
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = Math.min(sorted.length - 1, Math.floor(sorted.length * p));
  return sorted[idx];
}

const samples: number[] = [];
for (const m of allManifests()) {
  for (const id of Object.keys(m.scenes)) {
    samples.push(m.scenes[id].wallclockMs);
  }
}
samples.sort((a, b) => a - b);

console.log(`samples: ${samples.length}`);
if (samples.length === 0) {
  console.log("no data — run generate on at least one episode first");
  process.exit(0);
}
console.log(`p50: ${percentile(samples, 0.5)} ms`);
console.log(`p95: ${percentile(samples, 0.95)} ms`);
console.log(`p99: ${percentile(samples, 0.99)} ms`);
console.log(`max: ${samples[samples.length - 1]} ms`);
console.log(`recommended timeoutMs (p99 * 1.5, clamped 180000..720000): ${
  Math.max(180000, Math.min(720000, Math.round(percentile(samples, 0.99) * 1.5)))
}`);
```

- [ ] **Step 2: Wire env-var override into wrapper**

In `tools/scripts/run-stage2-generate.sh`, near the dispatcher invocation, ensure the env var passes through:

```bash
# Allow operator to override default 4-minute per-scene timeout.
# Override is also picked up by realDispatcher.ts via opts.timeoutMs.
export HF_GENERATIVE_TIMEOUT_MS="${HF_GENERATIVE_TIMEOUT_MS:-}"
```

In `tools/compositor/src/planner/realDispatcher.ts`, near the existing `timeoutMs = opts.timeoutMs ?? 4 * 60 * 1000;` line, change to:

```typescript
const envOverride = process.env.HF_GENERATIVE_TIMEOUT_MS;
const timeoutMs = opts.timeoutMs
  ?? (envOverride && /^\d+$/.test(envOverride) ? Number(envOverride) : undefined)
  ?? 4 * 60 * 1000;
```

- [ ] **Step 3: Sanity-run aggregator**

```bash
cd tools/compositor && npm run build
node dist/bin/aggregate-generate-wallclocks.js ../..
```

Expected: prints sample count + percentiles (will be 0 samples until at least one episode runs with the new dispatcher; that's fine).

- [ ] **Step 4: Commit**

```bash
git add tools/compositor/src/bin/aggregate-generate-wallclocks.ts \
        tools/compositor/src/planner/realDispatcher.ts \
        tools/scripts/run-stage2-generate.sh
git commit -m "feat(d3): wallclock aggregator + HF_GENERATIVE_TIMEOUT_MS env-var override"
```

---

## Task 15: D3 — calibration procedure documented

**Files:**
- Modify: `tools/compositor/src/planner/realDispatcher.ts` — calibration comment header.

- [ ] **Step 1: Add a calibration block at the top of `realDispatcher.ts`**

Append after the existing file-header comment:

```typescript
/**
 * Calibration procedure for `timeoutMs`:
 *   1. Run `node tools/compositor/dist/bin/aggregate-generate-wallclocks.js` from repo root.
 *   2. Take the printed "recommended timeoutMs" value.
 *   3. Update the default below (the `4 * 60 * 1000` literal) and add a
 *      comment line: `// last calibrated YYYY-MM-DD over N samples; p99=X ms`.
 * Re-run after every ~10 episodes or after model swap.
 *
 * Last calibrated: not yet (default is a guess; see D3 in
 * docs/operations/planner-pipeline-fixes/findings.md).
 */
```

This is intentionally a doc-only change — actual recalibration happens after enough episodes accumulate, and is a one-line edit by the next operator following the procedure above.

- [ ] **Step 2: Commit**

```bash
git add tools/compositor/src/planner/realDispatcher.ts
git commit -m "docs(d3): document timeoutMs calibration procedure"
```

---

## Task 16: §3 — open upstream issues for catalog selectors

**Files:**
- None (work happens on GitHub).
- Modify: `docs/superpowers/specs/2026-04-29-phase-6b-techdebt-cleanup-design.md` — record issue URLs.
- Modify: `docs/operations/planner-pipeline-fixes/findings.md` — link issues, retire the "consider composer-side rewrite" line.

- [ ] **Step 1: Audit catalog blocks for the anti-pattern**

```bash
grep -rn 'data-composition-id=' tools/compositor/node_modules/hyperframes/dist/templates/ \
  | grep -E '\[data-composition-id'
```

Capture the full list of catalog blocks/files using attribute selectors targeting their own id. Include this list in the issue body.

- [ ] **Step 2: Open issue 1 — catalog block authoring**

Use `gh issue create --repo heygen-com/hyperframes --title "..." --body-file -`. Title:

> Catalog blocks use attribute selectors that conflict under nested-composition reuse

Body (`<<EOF` template):
- Repro: minimal nested composition embedding `flowchart` twice; CSS rules from one instance match the other's DOM.
- Affected blocks: list from Step 1.
- Recommended fix: replace `[data-composition-id="<own-id>"]` with `#<own-id>` in catalog block CSS/HTML, or class-scoped selectors.
- Cross-reference: real-world incident D21 in this repo's `docs/operations/planner-pipeline-fixes/findings.md`.

- [ ] **Step 3: Open issue 2 — `hyperframes lint` rule**

Title:
> `hyperframes lint`: warn on `[data-composition-id="<self>"]` selectors in catalog blocks

Body:
- Rationale: prevents the regression in issue 1 from recurring as new blocks are authored.
- Suggested check: parse CSS in each catalog block, flag attribute selectors whose value matches the block's own composition id.
- Severity: warning (not error) to allow legitimate cross-block targeting.

- [ ] **Step 4: Record URLs in spec**

In `docs/superpowers/specs/2026-04-29-phase-6b-techdebt-cleanup-design.md`, in §3 deliverable list, replace "Issue numbers recorded in this spec at implementation time" with:
```
- Issue 1 (selector authoring): <URL>
- Issue 2 (lint rule): <URL>
```

- [ ] **Step 5: Update findings.md**

In `docs/operations/planner-pipeline-fixes/findings.md`, find the D15/D21 sections. Replace any "consider a composer-side rewrite" forward-looking line with:

```
> Resolution path: upstream-only. See issues <URL1>, <URL2>. No local rewriter
> in this repo per HF-native methodology.
```

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-04-29-phase-6b-techdebt-cleanup-design.md \
        docs/operations/planner-pipeline-fixes/findings.md
git commit -m "docs(d15-d21): link upstream issues for catalog selector leakage"
```

---

## Task 17: §4 — flowchart aspect ratio (issue + planner gating)

**Files:**
- Modify: `tools/compositor/src/planner/prompts/generative.md`
- Modify: `docs/superpowers/specs/2026-04-29-phase-6b-techdebt-cleanup-design.md` — record issue URL.

- [ ] **Step 1: Open catalog issue for portrait variant**

`gh issue create --repo heygen-com/hyperframes` (or whatever repo hosts the catalog).

Title:
> Catalog: add portrait `flowchart-vertical` (1440×2560) variant

Body:
- Use case: vertical short-form episodes can't use the existing 1920×1080 `flowchart` block (letterbox/stretch).
- Concrete request: a new catalog block authored for 1440×2560 with the same data-binding API as the landscape block.
- Cross-reference: this repo (anticodeguy-video-editing-studio), 2026-04-29 episode that hit the mismatch.

Record URL.

- [ ] **Step 2: Find the catalog allowlist in planner prompts**

```bash
grep -n 'flowchart\|catalog\|allowed' tools/compositor/src/planner/prompts/generative.md
```

Identify where catalog blocks are listed/described to the planner.

- [ ] **Step 3: Gate flowchart on landscape only**

In `tools/compositor/src/planner/prompts/generative.md`, where `flowchart` appears in any allowed-catalog list, add:

> **Note:** `flowchart` is authored at 1920×1080. For vertical episodes (target dimensions starting with `1440x2560` or any portrait aspect), do NOT reference `flowchart`; emit a `generative` scene instead.

If the prompt receives target dimensions as a variable, condition the catalog list on landscape vs portrait explicitly.

- [ ] **Step 4: Record issue URL in spec**

In `docs/superpowers/specs/2026-04-29-phase-6b-techdebt-cleanup-design.md`, §4 deliverable list, replace any placeholder with the issue URL.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/planner/prompts/generative.md \
        docs/superpowers/specs/2026-04-29-phase-6b-techdebt-cleanup-design.md
git commit -m "docs(d-aspect): gate flowchart on landscape only; link upstream portrait-variant issue"
```

---

## Task 18: §6 — companion audit spec stub

**Files:**
- Create: `docs/superpowers/specs/2026-04-29-hf-reinvention-audit-design.md`

- [ ] **Step 1: Write the stub spec**

```markdown
# HF Reinvention Audit — Design

**Date:** 2026-04-29
**Status:** Stub — to be filled in after `2026-04-29-phase-6b-techdebt-cleanup` lands.
**Parent spec:** `2026-04-29-phase-6b-techdebt-cleanup-design.md` §6

## Goal

Audit the entire pipeline (`tools/compositor/`, `tools/scripts/`, `standards/`,
prompt templates, custom wrappers around HF) for places where we have built or
maintained functionality that HyperFrames already provides. Output is a findings
document plus N follow-up tickets, not a single-feature design.

## Method (to be expanded)

1. Catalog every "thing we wrote." Group by subsystem.
2. For each, identify the closest HF feature.
3. Tag as: `aligned` / `parallel-manifest` / `gap` / `unclear`.
4. For `parallel-manifest`: open a follow-up ticket to migrate to HF API.
5. For `gap`: confirm gap with HF docs; consider upstream feature request.

## Scope to be defined

- Reading list (HF source, docs, skills)
- Per-subsystem checklist (compositor, planner, scripts, standards)
- Stop condition

## Deliverables

- This document filled in with findings.
- Follow-up tickets in this repo's issue tracker (or specs) per `parallel-manifest` finding.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-04-29-hf-reinvention-audit-design.md
git commit -m "spec(audit): stub for full HF reinvention audit (follow-up to phase-6b cleanup)"
```

---

## Final verification

- [ ] **Step 1: Full test suite**

```bash
cd tools/compositor && npm test
```

Expected: all tests pass, including new state tests (15+ in `test/state/episodeState.test.ts`, 3 in `atomicWrite.test.ts`, 5 in `promptHash.test.ts`).

- [ ] **Step 2: Type-check**

```bash
cd tools/compositor && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: End-to-end smoke on the current episode**

```bash
EP=episodes/2026-04-29-desktop-software-licensing-it-turns-out
rm -f "$EP/state.json" "$EP/stage-2-composite/generate.manifest.json"
bash tools/scripts/run-stage2-plan.sh "$EP"
bash tools/scripts/run-stage2-generate.sh "$EP"
# Interrupt with Ctrl-C mid-generate, then rerun:
bash tools/scripts/run-stage2-generate.sh "$EP"
# Expected: only unfinished scenes regenerate; manifest preserves the rest.
bash tools/scripts/run-stage2-compose.sh "$EP"
node tools/compositor/dist/bin/episode-state.js read --episode-dir "$EP"
```

Expected: `completedSteps` includes `plan`, `generate`, `compose` (and `preview` if compose wrapper drives it). `generate.manifest.json` has 9 entries with non-zero `wallclockMs`.

- [ ] **Step 4: Acceptance-criteria sign-off**

Verify each box in the spec's "Acceptance criteria" list is satisfied. Specifically:
- §0 audit findings appended to spec ✓
- `episode-state` CLI installed, current episode has valid `state.json` ✓
- `realDispatcher.ts` calibration comment present ✓
- Two upstream issues opened (selectors, lint) with URLs in spec ✓
- One catalog issue opened (portrait flowchart) + planner prompt gated ✓
- Companion audit spec stub committed ✓

End of plan.
