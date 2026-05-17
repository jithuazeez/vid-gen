"use client";
import * as React from "react";
import { Label, Mono } from "../UI";
import { Mic, Spinner, Sub, Video } from "../Icons";
import { Scene, Subtitle } from "@/lib/api";
import { SceneAssets, Selection, fmtTime } from "./EditorScreen";

interface Props {
  scenes: Scene[];
  sceneStarts: { sceneId: string; start: number; end: number }[];
  sceneAssets: Record<string, SceneAssets>;
  subtitlesByScene: Record<string, Subtitle | null>;
  totalDur: number;
  currentTime: number;
  selected: Selection;
  onSeek: (t: number) => void;
  onSelect: (s: Selection) => void;
}

const LABEL_GUTTER = 80;

export function EditorTimeline({
  scenes, sceneStarts, sceneAssets, subtitlesByScene,
  totalDur, currentTime, selected, onSeek, onSelect,
}: Props) {
  const ref = React.useRef<HTMLDivElement | null>(null);

  const handleRulerDown = (e: React.PointerEvent) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = Math.max(LABEL_GUTTER, Math.min(rect.width, e.clientX - rect.left)) - LABEL_GUTTER;
    onSeek((x / (rect.width - LABEL_GUTTER)) * totalDur);
  };

  const pct = totalDur > 0 ? (currentTime / totalDur) * 100 : 0;

  // Total cues count for the header subtitle.
  const cueCount = Object.values(subtitlesByScene).reduce(
    (n, s) => n + (s?.cues.length || 0), 0,
  );

  const ticks = React.useMemo(() => {
    const step = totalDur > 60 ? 10 : 5;
    const arr: number[] = [];
    for (let t = 0; t <= totalDur; t += step) arr.push(t);
    if (arr[arr.length - 1] !== Math.round(totalDur)) arr.push(Math.round(totalDur));
    return arr;
  }, [totalDur]);

  return (
    <div style={{
      padding: "14px 20px 20px",
      borderTop: "1px solid var(--border)",
      background: "var(--background)",
    }}>
      <div style={{ display: "flex", alignItems: "center",
                     justifyContent: "space-between", marginBottom: 10, gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Label>Timeline</Label>
          <Mono dim size={11} style={{ whiteSpace: "nowrap" }}>
            click any tile to edit · drag to seek
          </Mono>
        </div>
        <Mono dim size={11}>
          {fmtTime(totalDur)} · {scenes.length} scenes · {cueCount} cues
        </Mono>
      </div>

      <div ref={ref} style={{
        position: "relative", userSelect: "none",
        display: "flex", flexDirection: "column", gap: 6,
      }}>
        {/* Time ruler */}
        <div onPointerDown={handleRulerDown}
             style={{ position: "relative", height: 14,
                       marginLeft: LABEL_GUTTER, cursor: "pointer" }}>
          {ticks.map((t) => (
            <div key={t} style={{
              position: "absolute", left: `${(t / totalDur) * 100}%`,
              fontSize: 10, color: "var(--muted-foreground)",
              fontFamily: "var(--font-mono)",
              transform: t >= totalDur ? "translateX(-100%)" : "translateX(-50%)",
            }}>0:{String(Math.round(t)).padStart(2, "0")}</div>
          ))}
        </div>

        {/* Scenes track */}
        <Track icon={<Video size={11} />} label="Scenes">
          {scenes.map((s, i) => {
            const span = sceneStarts.find((x) => x.sceneId === s.id);
            if (!span) return null;
            const left = (span.start / totalDur) * 100;
            const width = ((span.end - span.start) / totalDur) * 100;
            const state = sceneAssets[s.id]?.scene_video;
            const isSel = selected?.kind === "scene" && selected.sceneId === s.id;
            return (
              <Block key={s.id} left={left} width={width}
                state={state} selected={isSel}
                onClick={() => state?.status === "ready" && onSelect({ kind: "scene", sceneId: s.id })}
                label={`S${i + 1} · ${truncate(s.visual_prompt, 30)}`}
                tone="dark"
                index={i}
              />
            );
          })}
        </Track>

        {/* Voice track */}
        <Track icon={<Mic size={11} />} label="Voice">
          {scenes.filter((s) => s.has_speaker).map((s) => {
            const span = sceneStarts.find((x) => x.sceneId === s.id);
            if (!span) return null;
            const left = (span.start / totalDur) * 100;
            const width = ((span.end - span.start) / totalDur) * 100;
            const state = sceneAssets[s.id]?.voice;
            return (
              <Block key={`v:${s.id}`} left={left} width={width}
                state={state}
                label="voice"
                tone="light"
                index={0}
                onClick={() => {}}
              />
            );
          })}
        </Track>

        {/* Subtitles track */}
        <Track icon={<Sub size={11} />} label="Subtitles">
          {scenes.map((s) => {
            const span = sceneStarts.find((x) => x.sceneId === s.id);
            if (!span) return null;
            const sub = subtitlesByScene[s.id];
            const subState = sceneAssets[s.id]?.subtitle_srt;
            if (!sub || !sub.cues.length) {
              if (!s.has_speaker) return null;
              // Show one queued placeholder for the scene's subtitle slot.
              const left = (span.start / totalDur) * 100;
              const width = ((span.end - span.start) / totalDur) * 100;
              return (
                <Block key={`sub:${s.id}`} left={left} width={width}
                  state={subState} label="queued cues" tone="light" index={0}
                  onClick={() => {}}
                />
              );
            }
            return sub.cues.map((c, idx) => {
              const start = span.start + c.start;
              const end   = span.start + c.end;
              const left  = (start / totalDur) * 100;
              const width = Math.max(0.5, ((end - start) / totalDur) * 100);
              const isSel = selected?.kind === "sub"
                && selected.sceneId === s.id && selected.cueIndex === idx;
              return (
                <Block key={`sub:${s.id}:${idx}`}
                  left={left} width={width}
                  state={subState} selected={isSel}
                  label={truncate(c.text, 28)} tone="light" index={idx}
                  onClick={() => subState?.status === "ready"
                    && onSelect({ kind: "sub", sceneId: s.id, cueIndex: idx })}
                />
              );
            });
          })}
        </Track>

        {/* Playhead — only over the track area, not the ruler labels */}
        <div style={{
          position: "absolute",
          left: `calc(${LABEL_GUTTER}px + ${pct} * (100% - ${LABEL_GUTTER}px) / 100)`,
          top: 14, bottom: 0,
          width: 2, background: "var(--foreground)", pointerEvents: "none",
          transform: "translateX(-1px)",
        }}>
          <div style={{
            position: "absolute", top: -6, left: -5,
            width: 0, height: 0,
            borderLeft: "6px solid transparent",
            borderRight: "6px solid transparent",
            borderTop: "6px solid var(--foreground)",
          }} />
        </div>
      </div>
    </div>
  );
}

function Track({
  icon, label, children,
}: React.PropsWithChildren<{ icon: React.ReactNode; label: string }>) {
  return (
    <div style={{ display: "flex", alignItems: "stretch", gap: 8 }}>
      <div style={{
        width: 72, padding: "0 6px",
        display: "flex", alignItems: "center", gap: 6,
        fontSize: 11, color: "var(--muted-foreground)",
        fontFamily: "var(--font-sans)", fontWeight: 500,
      }}>{icon} {label}</div>
      <div style={{
        flex: 1, position: "relative", height: 30,
        background: "var(--muted)", borderRadius: "var(--radius)",
        border: "1px solid var(--border)",
        overflow: "hidden",
      }}>{children}</div>
    </div>
  );
}

function Block({
  left, width, state, selected, onClick, label, tone, index,
}: {
  left: number; width: number;
  state: { status: string; progress: number } | null | undefined;
  selected?: boolean;
  onClick: () => void;
  label: string;
  tone: "dark" | "light";
  index: number;
}) {
  const status = state?.status || "queued";
  const isDark = tone === "dark";
  let body: React.ReactNode;
  if (status === "queued") {
    body = (
      <div style={{
        position: "absolute", inset: 4, borderRadius: 4,
        border: "1.5px dashed var(--border)",
        background: "transparent",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <Mono dim size={10}>queued</Mono>
      </div>
    );
  } else if (status === "generating") {
    body = (
      <div style={{
        position: "absolute", inset: 4, borderRadius: 4,
        background: isDark
          ? "linear-gradient(110deg, hsl(0 0% 18%) 8%, hsl(0 0% 30%) 18%, hsl(0 0% 18%) 33%)"
          : "linear-gradient(110deg, var(--muted) 8%, var(--background) 18%, var(--muted) 33%)",
        backgroundSize: "200% 100%",
        animation: "shimmer 1500ms linear infinite",
        border: `1px solid ${isDark ? "hsl(0 0% 10%)" : "var(--border)"}`,
        display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
        color: isDark ? "rgba(255,255,255,0.78)" : "var(--muted-foreground)",
      }}>
        <Spinner size={10} />
        <span style={{ fontSize: 10, fontWeight: 500 }}>
          {Math.round(state?.progress || 0)}%
        </span>
      </div>
    );
  } else if (status === "failed") {
    body = (
      <div style={{
        position: "absolute", inset: 4, borderRadius: 4,
        background: "hsl(0 60% 30%)", color: "white",
        padding: "0 8px",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 10, fontWeight: 600,
      }}>failed</div>
    );
  } else {
    body = (
      <div style={{
        position: "absolute", inset: 4, borderRadius: 4,
        background: isDark
          ? (index % 2 === 0 ? "hsl(0 0% 18%)" : "hsl(0 0% 25%)")
          : "var(--background)",
        color: isDark ? "white" : "var(--foreground)",
        padding: "0 8px",
        display: "flex", alignItems: "center",
        fontSize: 11, fontWeight: 500,
        overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis",
        border: `1px solid ${selected ? "var(--ring)" : (isDark ? "hsl(0 0% 10%)" : "var(--border)")}`,
        boxShadow: selected ? "0 0 0 2px var(--background), 0 0 0 3px var(--ring)" : "none",
        cursor: "pointer",
        animation: "fadeIn 200ms ease-out",
      }}>{label}</div>
    );
  }
  return (
    <div
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      style={{
        position: "absolute",
        left: `${left}%`, width: `${width}%`,
        top: 0, bottom: 0,
        cursor: status === "ready" ? "pointer" : "default",
      }}
    >{body}</div>
  );
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
