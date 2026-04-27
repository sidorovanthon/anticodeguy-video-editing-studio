import { describe, it, expect } from "vitest";
import { loadTranscript } from "../src/transcript.js";
import path from "node:path";

describe("loadTranscript", () => {
  it("parses sample transcript", () => {
    const t = loadTranscript(path.resolve(__dirname, "fixtures/transcript.sample.json"));
    expect(t.words).toHaveLength(3);
    expect(t.words[0].text).toBe("Hello");
    expect(t.duration_ms).toBe(1500);
  });
  it("rejects empty words array", () => {
    expect(() => loadTranscript("")).toThrow();
  });
  it("accepts ElevenLabs-style audio_duration_secs and normalizes to duration_ms", () => {
    const t = loadTranscript(
      path.resolve(__dirname, "fixtures/transcript.audio_duration_secs.json"),
    );
    expect(t.duration_ms).toBe(Math.round(1.2345 * 1000));
  });
  it("throws when neither duration_ms nor audio_duration_secs is present", () => {
    expect(() =>
      loadTranscript(path.resolve(__dirname, "fixtures/transcript.no_duration.json")),
    ).toThrow(/duration/);
  });
  it("prefers duration_ms when both fields are present", () => {
    const t = loadTranscript(
      path.resolve(__dirname, "fixtures/transcript.both_durations.json"),
    );
    expect(t.duration_ms).toBe(1500);
  });
});
