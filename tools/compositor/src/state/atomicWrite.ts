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
