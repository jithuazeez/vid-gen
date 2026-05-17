"use client";
import * as React from "react";
import { Button, Mono } from "../UI";
import { Pause, Play, Volume } from "../Icons";
import { fmtTimecode } from "./EditorScreen";

interface Props {
  playing: boolean;
  currentTime: number;
  totalDur: number;
  onTogglePlay: () => void;
  onSeek: (t: number) => void;
}

export function EditorPlayerBar({
  playing, currentTime, totalDur, onTogglePlay, onSeek,
}: Props) {
  return (
    <div style={{
      padding: "10px 20px",
      display: "flex", alignItems: "center", gap: 12,
      borderTop: "1px solid var(--border)",
      background: "var(--background)",
    }}>
      <Button variant="default" size="icon-sm" onClick={onTogglePlay}
              title={playing ? "Pause" : "Play"}>
        {playing ? <Pause size={14} /> : <Play size={14} />}
      </Button>
      <Mono size={12} style={{ minWidth: 96 }}>
        {fmtTimecode(currentTime)} <span style={{ color: "var(--muted-foreground)" }}>
          / {fmtTimecode(totalDur)}
        </span>
      </Mono>
      <Scrubber currentTime={currentTime} totalDur={totalDur} onSeek={onSeek} />
      <Button variant="ghost" size="icon-sm" title="Volume"><Volume size={15} /></Button>
    </div>
  );
}

function Scrubber({
  currentTime, totalDur, onSeek,
}: { currentTime: number; totalDur: number; onSeek: (t: number) => void }) {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const [drag, setDrag] = React.useState(false);

  const handle = React.useCallback((e: { clientX: number }) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    onSeek((x / rect.width) * totalDur);
  }, [onSeek, totalDur]);

  React.useEffect(() => {
    if (!drag) return;
    const move = (e: PointerEvent) => handle(e);
    const up = () => setDrag(false);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [drag, handle]);

  const pct = totalDur > 0 ? (currentTime / totalDur) * 100 : 0;
  return (
    <div ref={ref}
      onPointerDown={(e) => { setDrag(true); handle(e); }}
      style={{ flex: 1, height: 14, display: "flex", alignItems: "center",
               cursor: "pointer", position: "relative" }}>
      <div style={{ width: "100%", height: 4, background: "var(--muted)",
                     borderRadius: 999, position: "relative" }}>
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0,
                       width: `${pct}%`, background: "var(--foreground)",
                       borderRadius: 999 }} />
        <div style={{
          position: "absolute", left: `${pct}%`, top: "50%",
          transform: "translate(-50%, -50%)",
          width: 12, height: 12, borderRadius: "50%",
          background: "var(--foreground)",
          boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
        }} />
      </div>
    </div>
  );
}
