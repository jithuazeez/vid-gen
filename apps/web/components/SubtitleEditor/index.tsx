"use client";
import * as React from "react";
import { Button, Chip, Mono, Textarea } from "../UI";
import type { Subtitle, SubtitleCue } from "@/lib/api";

interface Props {
  subtitle: Subtitle | null;
  onSave: (cues: SubtitleCue[]) => void | Promise<void>;
  busy?: boolean;
}

export function SubtitleEditor({ subtitle, onSave, busy }: Props) {
  const [cues, setCues] = React.useState<SubtitleCue[]>(subtitle?.cues || []);

  React.useEffect(() => {
    setCues(subtitle?.cues || []);
  }, [subtitle?.id, subtitle?.cues]);

  function updateCue(i: number, patch: Partial<SubtitleCue>) {
    setCues((arr) => arr.map((c, idx) => idx === i ? { ...c, ...patch } : c));
  }

  function deleteCue(i: number) {
    setCues((arr) => arr.filter((_, idx) => idx !== i));
  }

  function addCue() {
    const last = cues[cues.length - 1];
    const start = last ? Number(last.end) : 0;
    setCues((arr) => [...arr, { start, end: start + 1.5, text: "New caption" }]);
  }

  if (!subtitle) {
    return (
      <div style={{ padding: 16, color: "var(--muted-foreground)", fontSize: 13 }}>
        No subtitles for this scene yet — they appear after Whisper alignment finishes.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Mono size={11} dim>{cues.length} cue{cues.length === 1 ? "" : "s"} · {subtitle.language}</Mono>
        <div style={{ display: "flex", gap: 6 }}>
          <Chip onClick={addCue}>+ cue</Chip>
          <Button size="sm" disabled={busy} onClick={() => onSave(cues)}>Save</Button>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 320, overflowY: "auto" }}>
        {cues.map((c, i) => (
          <div key={i} style={{
            display: "grid",
            gridTemplateColumns: "70px 70px 1fr auto",
            gap: 6, alignItems: "start",
            padding: 8, border: "1px solid var(--border)", borderRadius: 6,
          }}>
            <input
              type="number" step={0.05} value={Number(c.start).toFixed(2)}
              onChange={(e) => updateCue(i, { start: Number(e.target.value) })}
              style={inputStyle}
            />
            <input
              type="number" step={0.05} value={Number(c.end).toFixed(2)}
              onChange={(e) => updateCue(i, { end: Number(e.target.value) })}
              style={inputStyle}
            />
            <Textarea
              value={c.text}
              onChange={(e) => updateCue(i, { text: e.target.value })}
              style={{ minHeight: 30, fontSize: 13 }}
            />
            <Button variant="ghost" size="icon-sm" onClick={() => deleteCue(i)}>×</Button>
          </div>
        ))}
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  height: 30, padding: "0 6px",
  fontSize: 12, fontFamily: "var(--font-mono)",
  border: "1px solid var(--input)", borderRadius: 4,
  background: "var(--background)", color: "var(--foreground)",
  outline: "none",
};
