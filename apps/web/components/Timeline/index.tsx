"use client";
import * as React from "react";
import { Mono } from "../UI";
import type { Overlay, Scene, SubtitleCue } from "@/lib/api";

interface TimelineProps {
  scenes: Scene[];
  overlays: Overlay[];
  subtitles: { sceneId: string; cues: SubtitleCue[] }[];
  durationSec: number;
  currentSec: number;
  onSeek?: (sec: number) => void;
  onSelectScene?: (sceneId: string) => void;
}

const ROW_H = 28;
const GAP = 6;

export function Timeline(props: TimelineProps) {
  const { scenes, overlays, subtitles, durationSec, currentSec, onSeek, onSelectScene } = props;
  const trackRef = React.useRef<HTMLDivElement>(null);

  function handleClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!trackRef.current || !onSeek) return;
    const rect = trackRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const sec = (x / rect.width) * durationSec;
    onSeek(Math.max(0, Math.min(durationSec, sec)));
  }

  const cueRows = React.useMemo(() => {
    // Lay subtitle cues onto a single row, anchored relative to scene start.
    let acc = 0;
    const sceneOffsets = new Map<string, number>();
    for (const s of scenes) {
      sceneOffsets.set(s.id, acc);
      acc += Number(s.duration_seconds || 0);
    }
    return subtitles.flatMap((row) => {
      const off = sceneOffsets.get(row.sceneId) || 0;
      return row.cues.map((c, i) => ({
        key: `${row.sceneId}-${i}`,
        start: off + c.start,
        end: off + c.end,
        text: c.text,
      }));
    });
  }, [scenes, subtitles]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: GAP }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <Mono dim size={11}>Timeline</Mono>
        <Mono dim size={11}>{currentSec.toFixed(1)}s / {durationSec.toFixed(1)}s</Mono>
      </div>
      <div
        ref={trackRef}
        onClick={handleClick}
        style={{
          position: "relative",
          width: "100%",
          background: "var(--muted)",
          borderRadius: 6,
          padding: GAP,
          cursor: onSeek ? "pointer" : "default",
        }}
      >
        {/* Scenes track */}
        <Track label="scenes">
          {scenes.map((s, i) => {
            const left = pctOf(scenes.slice(0, i).reduce((a, x) => a + Number(x.duration_seconds), 0), durationSec);
            const w = pctOf(Number(s.duration_seconds), durationSec);
            return (
              <Block
                key={s.id}
                left={`${left}%`}
                width={`${w}%`}
                color="var(--foreground)"
                onClick={() => onSelectScene?.(s.id)}
                label={`${s.scene_index}`}
              />
            );
          })}
        </Track>

        {/* Subtitles track */}
        <Track label="subs">
          {cueRows.map((c) => (
            <Block
              key={c.key}
              left={`${pctOf(c.start, durationSec)}%`}
              width={`${pctOf(c.end - c.start, durationSec)}%`}
              color="hsl(217 91% 60%)"
              label={c.text.length > 18 ? c.text.slice(0, 16) + "…" : c.text}
            />
          ))}
        </Track>

        {/* Overlays track */}
        <Track label="overlay">
          {overlays.map((o) => (
            <Block
              key={o.id}
              left={`${pctOf(o.start_seconds, durationSec)}%`}
              width={`${pctOf(o.end_seconds - o.start_seconds, durationSec)}%`}
              color="hsl(38 92% 55%)"
              label={o.text || o.overlay_type}
            />
          ))}
        </Track>

        {/* Music track (whole timeline) */}
        <Track label="music">
          <Block left="0%" width="100%" color="hsl(142 50% 45%)" label="bgm" />
        </Track>

        {/* Playhead */}
        <div style={{
          position: "absolute", top: 0, bottom: 0,
          left: `${pctOf(currentSec, durationSec)}%`,
          width: 2, background: "var(--foreground)", pointerEvents: "none",
        }} />
      </div>
    </div>
  );
}

function Track({ label, children }: React.PropsWithChildren<{ label: string }>) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      marginBottom: GAP,
    }}>
      <span style={{
        width: 56, fontFamily: "var(--font-mono)", fontSize: 10,
        color: "var(--muted-foreground)", textAlign: "right",
      }}>{label}</span>
      <div style={{
        flex: 1, position: "relative", height: ROW_H,
        background: "var(--background)",
        border: "1px solid var(--border)", borderRadius: 4,
      }}>
        {children}
      </div>
    </div>
  );
}

function Block({ left, width, color, label, onClick }: {
  left: string; width: string; color: string; label: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={(e) => { e.stopPropagation(); onClick?.(); }}
      title={label}
      style={{
        position: "absolute", top: 2, bottom: 2, left, width,
        background: color, opacity: 0.85,
        borderRadius: 3, color: "var(--background)",
        fontSize: 10, lineHeight: `${ROW_H - 4}px`,
        padding: "0 6px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        cursor: onClick ? "pointer" : "default",
      }}
    >{label}</div>
  );
}

function pctOf(part: number, whole: number): number {
  if (whole <= 0) return 0;
  return Math.max(0, Math.min(100, (part / whole) * 100));
}
