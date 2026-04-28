export interface GroupWordsInput {
  text: string;
  startMs: number;
  endMs: number;
}

export interface CaptionGroup {
  id: string;
  startMs: number;
  endMs: number;
  words: GroupWordsInput[];
}

export interface GroupWordsOptions {
  maxWordsPerGroup: number;
  breakAfterPauseMs: number;
}

export function groupWords(words: GroupWordsInput[], opts: GroupWordsOptions): CaptionGroup[] {
  const groups: CaptionGroup[] = [];
  let current: GroupWordsInput[] = [];

  const flush = (): void => {
    if (current.length === 0) return;
    groups.push({
      id: `g${groups.length}`,
      startMs: current[0].startMs,
      endMs: current[current.length - 1].endMs,
      words: current,
    });
    current = [];
  };

  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    current.push(w);
    const next = words[i + 1];
    const reachedCap = current.length >= opts.maxWordsPerGroup;
    const pauseAfter = next ? next.startMs - w.endMs > opts.breakAfterPauseMs : false;
    if (reachedCap || pauseAfter || !next) {
      flush();
    }
  }

  return groups;
}
