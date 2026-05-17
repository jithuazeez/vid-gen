"use client";
import * as React from "react";
import { Badge, Button, Chip, Input, Label, Mono, Progress, Textarea } from "../UI";
import { Check, Refresh, Spinner, Sub, Mic, Video, X } from "../Icons";
import { Project, Scene, Subtitle } from "@/lib/api";
import { LogEntry, SceneAssets, Selection, fmtTime } from "./EditorScreen";

interface Props {
  project: Project;
  scenes: Scene[];
  sceneAssets: Record<string, SceneAssets>;
  subtitlesByScene: Record<string, Subtitle | null>;
  selected: Selection;
  allDone: boolean;
  overallPct: number;
  doneAssets: number;
  totalAssets: number;
  log: LogEntry[];
  onClearSelected: () => void;
  onRegenerateScene: (sceneId: string) => Promise<void> | void;
  onUpdateScene: (sceneId: string, patch: Partial<Scene>) => Promise<void> | void;
  onRegenerateLanguage: (lang: string) => Promise<void> | void;
}

const ALL_LANGUAGES: { code: string; label: string }[] = [
  { code: "en", label: "EN · English" },
  { code: "hi", label: "HI · Hindi" },
  { code: "mr", label: "MR · Marathi" },
  { code: "ta", label: "TA · Tamil" },
  { code: "pa", label: "PA · Punjabi" },
];

export function EditorRightPanel(props: Props) {
  return (
    <aside style={{
      background: "var(--background)",
      display: "flex", flexDirection: "column", minHeight: 0,
    }}>
      {!props.selected && <PipelinePanel {...props} />}
      {props.selected?.kind === "scene" && (
        <SceneEditPanel
          sceneId={props.selected.sceneId}
          scenes={props.scenes}
          sceneAssets={props.sceneAssets}
          onClose={props.onClearSelected}
          onRegenerate={props.onRegenerateScene}
          onUpdate={props.onUpdateScene}
        />
      )}
      {props.selected?.kind === "sub" && (
        <SubtitleEditPanel
          sceneId={props.selected.sceneId}
          cueIndex={props.selected.cueIndex}
          subtitlesByScene={props.subtitlesByScene}
          onClose={props.onClearSelected}
        />
      )}
    </aside>
  );
}

function PipelinePanel({
  project, scenes, sceneAssets, subtitlesByScene, allDone, overallPct, log,
  onRegenerateLanguage,
}: Props) {
  const sceneDone = scenes.filter((s) => sceneAssets[s.id]?.scene_video?.status === "ready").length;
  const speakerScenes = scenes.filter((s) => s.has_speaker);
  const voiceDone = speakerScenes.filter((s) => sceneAssets[s.id]?.voice?.status === "ready").length;
  const subsDone = speakerScenes.filter((s) => sceneAssets[s.id]?.subtitle_srt?.status === "ready").length;

  return (
    <>
      <div style={{ padding: "20px 20px 16px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, letterSpacing: -0.2 }}>
              {allDone ? "Render complete" : "Rendering pipeline"}
            </h3>
            <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--muted-foreground)" }}>
              {allDone
                ? "Review the timeline, then generate the final cut."
                : "Assets stream in as they finish. Click any tile to edit."}
            </p>
          </div>
          <Mono size={14} style={{ fontWeight: 600 }}>{overallPct}%</Mono>
        </div>
        <Progress value={overallPct} style={{ marginTop: 12 }} />
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        <Section title={`Scenes (${sceneDone}/${scenes.length})`}>
          {scenes.map((s, i) => (
            <Row key={s.id}
              icon={<Video size={12} />}
              label={`Scene ${String(i + 1).padStart(2, "0")}`}
              sub={`${fmtTime(0)}–${fmtTime(Number(s.duration_seconds))}`}
              state={sceneAssets[s.id]?.scene_video} />
          ))}
        </Section>

        {speakerScenes.length > 0 && (
          <Section title={`Voice-over (${voiceDone}/${speakerScenes.length})`}>
            {speakerScenes.map((s, i) => (
              <Row key={`v:${s.id}`}
                icon={<Mic size={12} />}
                label={`Scene ${String(scenes.indexOf(s) + 1).padStart(2, "0")} narration`}
                sub={truncate(s.narration_script, 60)}
                state={sceneAssets[s.id]?.voice} />
            ))}
          </Section>
        )}

        {speakerScenes.length > 0 && (
          <Section title={`Subtitles (${subsDone}/${speakerScenes.length})`}>
            {speakerScenes.map((s) => {
              const sub = subtitlesByScene[s.id];
              return (
                <Row key={`s:${s.id}`}
                  icon={<Sub size={12} />}
                  label={`Scene ${String(scenes.indexOf(s) + 1).padStart(2, "0")}`}
                  sub={
                    sub
                      ? `${sub.cues.length} cues · ${sub.source === "whisper" ? "aligned" : "estimated"}`
                      : "pending"
                  }
                  state={sceneAssets[s.id]?.subtitle_srt}
                />
              );
            })}
          </Section>
        )}

        <LanguageSection
          project={project}
          onRegenerateLanguage={onRegenerateLanguage}
        />

        <Section title="Activity log">
          <div style={{
            display: "flex", flexDirection: "column", gap: 4,
            padding: "0 20px 20px",
          }}>
            {log.length === 0 && <Mono dim size={11}>Nothing yet.</Mono>}
            {log.slice().reverse().slice(0, 60).map((entry, i) => (
              <div key={i} style={{
                display: "flex", gap: 8, fontSize: 11, lineHeight: 1.5,
                alignItems: "baseline",
              }}>
                <Mono dim size={10} style={{ width: 38, flexShrink: 0 }}>
                  +{entry.t.toFixed(1)}s
                </Mono>
                <span style={{
                  color: entry.kind === "err" ? "hsl(0 70% 55%)"
                       : entry.kind === "done" ? "var(--foreground)"
                       : "var(--muted-foreground)",
                }}>
                  {entry.kind === "done" && (
                    <Check size={10} strokeWidth={3}
                      style={{ marginRight: 4, color: "hsl(142 71% 40%)" }} />
                  )}
                  {entry.msg}
                </span>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </>
  );
}

function LanguageSection({
  project,
  onRegenerateLanguage,
}: {
  project: Project;
  onRegenerateLanguage: (lang: string) => Promise<void> | void;
}) {
  const activeLanguage = project.active_language || project.primary_language || "en";
  const available = project.available_languages || [];
  const [pending, setPending] = React.useState<string | null>(null);

  const handleLang = async (code: string) => {
    if (code === activeLanguage || pending) return;
    setPending(code);
    try {
      await onRegenerateLanguage(code);
    } finally {
      setPending(null);
    }
  };

  return (
    <div>
      <div style={{ padding: "14px 20px 8px" }}><Label>Language</Label></div>
      <div style={{ padding: "0 20px 6px", display: "flex", flexWrap: "wrap", gap: 6 }}>
        {ALL_LANGUAGES.map(({ code, label }) => {
          const isActive = code === activeLanguage;
          const isAvailable = available.includes(code);
          const isLoading = pending === code;
          return (
            <button
              key={code}
              onClick={() => handleLang(code)}
              disabled={!!pending}
              style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                padding: "4px 10px", borderRadius: 999,
                border: isActive
                  ? "1.5px solid var(--foreground)"
                  : isAvailable
                  ? "1px solid var(--border)"
                  : "1px dashed var(--border)",
                background: isActive ? "var(--foreground)" : "var(--card)",
                color: isActive ? "var(--background)" : "var(--foreground)",
                fontSize: 11, fontWeight: isActive ? 600 : 400,
                cursor: pending ? "not-allowed" : isActive ? "default" : "pointer",
                opacity: pending && !isLoading ? 0.5 : 1,
              }}
            >
              {isLoading && <Spinner size={10} />}
              {label}
              {!isAvailable && !isActive && !isLoading && (
                <span style={{ fontSize: 10, color: "var(--muted-foreground)" }}>+</span>
              )}
            </button>
          );
        })}
      </div>
      {pending && (
        <div style={{ padding: "0 20px 8px" }}>
          <Mono dim size={11}>Generating {ALL_LANGUAGES.find(l => l.code === pending)?.label} render…</Mono>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: React.PropsWithChildren<{ title: string }>) {
  return (
    <div>
      <div style={{ padding: "14px 20px 8px" }}><Label>{title}</Label></div>
      <div style={{
        padding: title.startsWith("Activity") ? 0 : "0 20px 6px",
        display: "flex", flexDirection: "column", gap: 6,
      }}>{children}</div>
    </div>
  );
}

function Row({
  icon, label, sub, state,
}: {
  icon: React.ReactNode;
  label: string;
  sub?: string;
  state: { status: string; progress: number } | null | undefined;
}) {
  const status = state?.status || "queued";
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "8px 10px",
      borderRadius: "var(--radius)",
      border: "1px solid var(--border)",
      background: "var(--card)",
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: 6,
        background: "var(--muted)", color: "var(--muted-foreground)",
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }}>{icon}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden",
                       textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {label}
        </div>
        {sub && <div style={{ fontSize: 11, color: "var(--muted-foreground)" }}>{sub}</div>}
      </div>
      {status === "ready" && <Badge variant="success"><Check size={10} strokeWidth={3} /> done</Badge>}
      {status === "generating" && (
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 36 }}>
            <Progress value={state?.progress || 0} style={{ height: 4 }} />
          </div>
          <Mono dim size={10}>{Math.round(state?.progress || 0)}%</Mono>
        </div>
      )}
      {status === "failed"  && <Badge variant="warning">failed</Badge>}
      {status === "queued"  && <Badge variant="outline">queued</Badge>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Scene edit panel
// ─────────────────────────────────────────────────────────────────────
function SceneEditPanel({
  sceneId, scenes, sceneAssets, onClose, onRegenerate, onUpdate,
}: {
  sceneId: string;
  scenes: Scene[];
  sceneAssets: Record<string, SceneAssets>;
  onClose: () => void;
  onRegenerate: (sceneId: string) => Promise<void> | void;
  onUpdate: (sceneId: string, patch: Partial<Scene>) => Promise<void> | void;
}) {
  const scene = scenes.find((s) => s.id === sceneId);
  if (!scene) return null;
  const idx = scenes.indexOf(scene);
  const state = sceneAssets[sceneId]?.scene_video;
  const regenerating = state?.status === "generating";

  const [prompt, setPrompt] = React.useState(scene.visual_prompt);
  const [script, setScript] = React.useState(scene.narration_script);
  React.useEffect(() => {
    setPrompt(scene.visual_prompt);
    setScript(scene.narration_script);
  }, [scene.visual_prompt, scene.narration_script]);

  const dirty = prompt !== scene.visual_prompt || script !== scene.narration_script;

  return (
    <>
      <div style={{
        padding: "16px 20px",
        borderBottom: "1px solid var(--border)",
        display: "flex", justifyContent: "space-between",
        alignItems: "flex-start", gap: 10,
      }}>
        <div>
          <Mono dim size={11}>
            SCENE {String(idx + 1).padStart(2, "0")} · {fmtTime(Number(scene.duration_seconds))}
          </Mono>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2, letterSpacing: -0.2 }}>
            Edit scene
          </div>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose} title="Close">
          <X size={16} />
        </Button>
      </div>

      <div style={{
        flex: 1, overflowY: "auto", padding: 20,
        display: "flex", flexDirection: "column", gap: 18,
      }}>
        <div style={{ position: "relative",
                       height: 180, borderRadius: 6,
                       background: "linear-gradient(135deg, hsl(220 25% 25%), hsl(220 25% 12%))" }}>
          {regenerating && (
            <div style={{
              position: "absolute", inset: 0, borderRadius: 6,
              background: "rgba(10,10,10,0.55)", backdropFilter: "blur(2px)",
              display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center", gap: 8,
              color: "white",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
                <Spinner size={12} /> Re-rendering scene…
              </div>
              <div style={{ width: "60%" }}>
                <Progress value={state?.progress || 0} style={{ height: 3 }} />
              </div>
            </div>
          )}
        </div>

        <Field label="Visual direction">
          <Textarea rows={3} value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={regenerating} />
        </Field>

        <Field label="Narration script">
          <Textarea rows={2} value={script}
            onChange={(e) => setScript(e.target.value)}
            disabled={regenerating} />
        </Field>

        <Field label="Subtitle position">
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {["auto", "top", "bottom", "custom"].map((p) => (
              <Chip key={p} selected={scene.subtitle_position === p}
                onClick={() => onUpdate(sceneId, { subtitle_position: p } as any)}
                disabled={regenerating}>{p}</Chip>
            ))}
          </div>
        </Field>

        <Field label="Speaking on camera">
          <div style={{ display: "flex", gap: 6 }}>
            <Chip selected={!scene.has_speaker}
              onClick={() => onUpdate(sceneId, { has_speaker: false } as any)}
              disabled={regenerating}>Off</Chip>
            <Chip selected={scene.has_speaker}
              onClick={() => onUpdate(sceneId, { has_speaker: true } as any)}
              disabled={regenerating}>On (lip-sync)</Chip>
          </div>
        </Field>
      </div>

      <div style={{
        padding: "14px 20px", borderTop: "1px solid var(--border)",
        display: "flex", gap: 8, justifyContent: "space-between",
      }}>
        <Button variant="ghost" size="sm" onClick={onClose}>Back</Button>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {dirty && !regenerating && <Badge variant="warning">unsaved</Badge>}
          <Button size="sm" disabled={regenerating} onClick={async () => {
            if (dirty) await onUpdate(sceneId, {
              visual_prompt: prompt, narration_script: script,
            } as any);
            await onRegenerate(sceneId);
          }}>
            {regenerating
              ? <><Spinner size={14} /> Re-rendering</>
              : <><Refresh size={14} /> Regenerate scene</>}
          </Button>
        </div>
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Subtitle edit panel
// ─────────────────────────────────────────────────────────────────────
function SubtitleEditPanel({
  sceneId, cueIndex, subtitlesByScene, onClose,
}: {
  sceneId: string;
  cueIndex: number;
  subtitlesByScene: Record<string, Subtitle | null>;
  onClose: () => void;
}) {
  const sub = subtitlesByScene[sceneId];
  const cue = sub?.cues[cueIndex];
  const [text, setText] = React.useState(cue?.text || "");
  React.useEffect(() => { setText(cue?.text || ""); }, [cue?.text]);
  if (!sub || !cue) return null;

  return (
    <>
      <div style={{
        padding: "16px 20px",
        borderBottom: "1px solid var(--border)",
        display: "flex", justifyContent: "space-between",
        alignItems: "flex-start", gap: 10,
      }}>
        <div>
          <Mono dim size={11}>
            SUBTITLE CUE {String(cueIndex + 1).padStart(2, "0")} · {fmtTime(cue.start)} → {fmtTime(cue.end)}
          </Mono>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2, letterSpacing: -0.2 }}>
            Edit caption
          </div>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose}><X size={16} /></Button>
      </div>

      <div style={{
        flex: 1, overflowY: "auto", padding: 20,
        display: "flex", flexDirection: "column", gap: 18,
      }}>
        <Field label="Caption text">
          <Textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} />
        </Field>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Field label="Start">
            <Input value={fmtTime(cue.start)} readOnly />
          </Field>
          <Field label="End">
            <Input value={fmtTime(cue.end)} readOnly />
          </Field>
        </div>

        <Field label="Style">
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <Chip selected>Burned in</Chip>
            <Chip>Outlined</Chip>
            <Chip>Karaoke</Chip>
          </div>
        </Field>

        <div style={{
          padding: 12, borderRadius: "var(--radius)",
          border: "1px solid var(--border)", background: "var(--muted)",
          display: "flex", flexDirection: "column", gap: 4,
        }}>
          <Label>Preview</Label>
          <div style={{
            background: "rgba(0,0,0,0.85)", color: "white",
            padding: "8px 14px", borderRadius: 6,
            fontSize: 14, fontWeight: 500, lineHeight: 1.3,
            alignSelf: "center", textAlign: "center",
            marginTop: 4,
          }}>{text || "—"}</div>
        </div>
      </div>

      <div style={{
        padding: "14px 20px", borderTop: "1px solid var(--border)",
        display: "flex", justifyContent: "space-between", gap: 8,
      }}>
        <Button variant="ghost" size="sm" onClick={onClose}>Back</Button>
        <Button size="sm" onClick={async () => {
          // Patch the cue inline via /subtitles/:id with the cues array
          // mutated. Server is authoritative for the next render.
          const next = sub.cues.slice();
          next[cueIndex] = { ...cue, text };
          try {
            const { api } = await import("@/lib/api");
            await api.patchSubtitle(sub.id, { cues: next } as any);
            onClose();
          } catch (e) {
            console.error(e);
          }
        }}>
          <Check size={14} /> Apply changes
        </Button>
      </div>
    </>
  );
}

function Field({ label, children }: React.PropsWithChildren<{ label: string }>) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function truncate(s: string | null | undefined, n: number): string {
  if (!s) return "";
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
