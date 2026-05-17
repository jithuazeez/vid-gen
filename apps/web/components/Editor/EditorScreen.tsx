"use client";
import * as React from "react";
import { BrandMark, ProjectShell, ThemeToggle } from "../Shell";
import { Badge, Button, Mono, Separator } from "../UI";
import { Check, Download, Spinner } from "../Icons";
import { ExportModal } from "../ExportModal";
import { api, AssetState, AssetStatus, AssetType, Project, Scene,
         SSEEvent, Subtitle, SubtitleCue } from "@/lib/api";
import { EditorTimeline } from "./EditorTimeline";
import { PreviewPlayer } from "./PreviewPlayer";
import { EditorPlayerBar } from "./EditorPlayerBar";
import { EditorRightPanel } from "./EditorRightPanel";

// Key into the per-asset state map. Voice/lipsync/subs/composite are
// language-scoped; scene_video is not.
export type AssetKey = string;
export function keyOf(
  scene_id: string | null | undefined,
  type: AssetType,
  language?: string | null,
): AssetKey {
  return `${scene_id || ""}|${type}|${language || ""}`;
}

export interface SceneAssets {
  scene_video: AssetState | null;
  voice: AssetState | null;
  lipsync_video: AssetState | null;
  subtitle_srt: AssetState | null;
  composite: AssetState | null;
}

export type Selection =
  | { kind: "scene"; sceneId: string }
  | { kind: "sub";   sceneId: string; cueIndex: number }
  | null;

export interface LogEntry {
  t: number;   // seconds since the editor mounted
  kind: "info" | "done" | "warn" | "err";
  msg: string;
}

interface Props {
  project: Project;
  events: SSEEvent[];
  onBack: () => void;
  onReloadProject: () => Promise<void> | void;
  onNewJob: (jobId: string) => void;
}

export function EditorScreen({ project, events, onBack, onReloadProject, onNewJob }: Props) {
  const language = project.active_language || project.primary_language || "en";
  const scenes = React.useMemo(
    () => [...project.scenes].sort((a, b) => a.scene_index - b.scene_index),
    [project.scenes],
  );

  // ───────── Subtitle state (estimated → whisper) ─────────
  // Source of truth is project.subtitles from REST; SSE 'subtitle.refined'
  // events trigger a project refresh so this state is always fresh.
  const subtitlesByScene = React.useMemo<Record<string, Subtitle | null>>(() => {
    const map: Record<string, Subtitle | null> = {};
    for (const s of scenes) map[s.id] = null;
    for (const sub of project.subtitles || []) {
      if (sub.language === language) map[sub.scene_id] = sub;
    }
    return map;
  }, [scenes, project.subtitles, language]);

  // ───────── Per-asset state map ─────────
  // Hydrated from project.assets (REST), then patched by SSE events as they arrive.
  const [assetState, setAssetState] = React.useState<Record<AssetKey, AssetState>>({});

  // Seed from REST on every project change (this handles initial mount + reload).
  React.useEffect(() => {
    const seeded: Record<AssetKey, AssetState> = {};
    for (const a of project.assets || []) {
      seeded[keyOf(a.scene_id, a.asset_type, a.language)] = a;
    }
    setAssetState((prev) => ({ ...seeded, ...prev }));
    // We intentionally merge prev *on top* of seeded so an SSE update that
    // already landed isn't clobbered by a stale REST snapshot.
    // eslint-disable-next-line
  }, [project.id, project.assets?.length]);

  const mountedAt = React.useRef<number>(performance.now());
  const [log, setLog] = React.useState<LogEntry[]>(() => [
    { t: 0, kind: "info", msg: `Render started · ${scenes.length} scenes` },
  ]);
  const seenSnapshot = React.useRef(false);

  // ───────── Drive state from the SSE event buffer ─────────
  // The page passes us the *full* event buffer; we walk new entries each
  // render. Keeping a high-water-mark index avoids reprocessing.
  const watermark = React.useRef(0);
  React.useEffect(() => {
    if (events.length <= watermark.current) return;
    const fresh = events.slice(watermark.current);
    watermark.current = events.length;
    const t = (performance.now() - mountedAt.current) / 1000;

    setAssetState((prev) => {
      let next = prev;
      let mutated = false;
      const ensure = () => {
        if (!mutated) { next = { ...prev }; mutated = true; }
      };

      for (const e of fresh) {
        if (e.event === "snapshot" && !seenSnapshot.current) {
          seenSnapshot.current = true;
          const arr = (e.data?.assets || []) as AssetState[];
          for (const a of arr) {
            ensure();
            next[keyOf(a.scene_id, a.asset_type, a.language)] = a;
          }
          continue;
        }
        if (e.event.startsWith("asset.")) {
          const d = e.data || {};
          const k = keyOf(d.scene_id, d.asset_type, d.language);
          const cur = next[k];
          const status: AssetStatus =
            e.event === "asset.ready" ? "ready" :
            e.event === "asset.failed" ? "failed" : "generating";
          ensure();
          next[k] = {
            id: d.asset_id || cur?.id || k,
            scene_id: d.scene_id || null,
            asset_type: d.asset_type,
            language: d.language ?? null,
            status,
            progress: status === "ready" ? 100 : (cur?.progress ?? 5),
          };
        }
      }
      return mutated ? next : prev;
    });

    // Append to the activity log for the right panel.
    setLog((prev) => {
      const additions: LogEntry[] = [];
      for (const e of fresh) {
        if (e.event === "asset.ready") {
          const d = e.data || {};
          additions.push({
            t, kind: "done",
            msg: `${labelFor(d.asset_type)}${d.scene_id ? ` · scene ${shortId(d.scene_id, scenes)}` : ""} · ready`,
          });
        } else if (e.event === "asset.started") {
          const d = e.data || {};
          additions.push({
            t, kind: "info",
            msg: `${labelFor(d.asset_type)}${d.scene_id ? ` · scene ${shortId(d.scene_id, scenes)}` : ""} · started`,
          });
        } else if (e.event === "asset.failed") {
          const d = e.data || {};
          additions.push({
            t, kind: "err",
            msg: `${labelFor(d.asset_type)}${d.scene_id ? ` · scene ${shortId(d.scene_id, scenes)}` : ""} · failed`,
          });
        } else if (e.event === "subtitle.refined") {
          const d = e.data || {};
          additions.push({
            t, kind: "info",
            msg: `Subtitles refined · scene ${shortId(d.scene_id, scenes)}`,
          });
          // Refresh the project so cues swap in.
          void onReloadProject();
        } else if (e.event === "stage_change") {
          additions.push({ t, kind: "info", msg: `Stage · ${e.data?.stage}` });
        } else if (e.event === "done") {
          additions.push({ t, kind: "done", msg: "Final render ready" });
        } else if (e.event === "error") {
          additions.push({
            t, kind: "err",
            msg: `${e.data?.stage || "pipeline"} failed: ${e.data?.message || "unknown"}`,
          });
        }
      }
      if (!additions.length) return prev;
      return [...prev, ...additions].slice(-200);
    });
  }, [events, scenes, onReloadProject]);

  const sceneAssets = React.useMemo(() => {
    const m: Record<string, SceneAssets> = {};
    for (const s of scenes) {
      m[s.id] = {
        scene_video:   assetState[keyOf(s.id, "scene_video", null)]   || null,
        voice:         assetState[keyOf(s.id, "voice", language)]     || null,
        lipsync_video: assetState[keyOf(s.id, "lipsync_video", language)] || null,
        subtitle_srt:  assetState[keyOf(s.id, "subtitle_srt", language)]  || null,
        composite:     assetState[keyOf(s.id, "composite", language)] || null,
      };
    }
    return m;
  }, [scenes, assetState, language]);

  // Aggregate "all done" — every per-scene composite is ready. (composite
  // pulls in every upstream artifact, so this is the correct gate.)
  const allDone = scenes.length > 0 && scenes.every(
    (s) => sceneAssets[s.id]?.composite?.status === "ready"
  );
  const totalAssets = scenes.reduce((n, s) => {
    const hs = s.has_speaker;
    return n + 1 /*scene_video*/ + 1 /*composite*/
             + (hs ? 3 : 0); /* voice, lipsync, subtitle */
  }, 0);
  const doneAssets = scenes.reduce((n, s) => {
    const a = sceneAssets[s.id];
    let c = 0;
    if (a.scene_video?.status === "ready") c++;
    if (a.composite?.status === "ready") c++;
    if (s.has_speaker) {
      if (a.voice?.status === "ready") c++;
      if (a.lipsync_video?.status === "ready") c++;
      if (a.subtitle_srt?.status === "ready") c++;
    }
    return n + c;
  }, 0);
  const overallPct = totalAssets ? Math.round((doneAssets / totalAssets) * 100) : 0;

  // ───────── Playback ─────────
  const totalDur = scenes.reduce((n, s) => n + Number(s.duration_seconds || 0), 0) || 30;
  const [currentTime, setCurrentTime] = React.useState(0);
  const [playing, setPlaying] = React.useState(false);
  React.useEffect(() => {
    if (!playing) return;
    let raf: number;
    let last = performance.now();
    const loop = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setCurrentTime((t) => {
        const nx = t + dt;
        if (nx >= totalDur) { setPlaying(false); return 0; }
        return nx;
      });
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing, totalDur]);

  // ───────── Selection ─────────
  const [selected, setSelected] = React.useState<Selection>(null);
  const [exportOpen, setExportOpen] = React.useState(false);

  // ───────── Language regeneration ─────────
  const onRegenerateLanguage = React.useCallback(async (lang: string) => {
    const res = await api.regenerateLanguage(project.id, lang);
    if (res.job_id) onNewJob(res.job_id);
    await onReloadProject();
  }, [project.id, onNewJob, onReloadProject]);

  // ───────── Per-scene regenerate ─────────
  const onRegenerateScene = React.useCallback(async (sceneId: string) => {
    try {
      await api.regenerateScene(sceneId);
      // Reset that scene's assets back to generating in the local map so the
      // tiles immediately re-enter the shimmer state without waiting for SSE.
      setAssetState((prev) => {
        const next = { ...prev };
        for (const at of ["scene_video", "voice", "lipsync_video", "subtitle_srt", "composite"] as AssetType[]) {
          const k = keyOf(sceneId, at, at === "scene_video" ? null : language);
          const cur = next[k];
          if (cur) next[k] = { ...cur, status: "generating", progress: 5 };
        }
        return next;
      });
    } catch (err) {
      console.error(err);
    }
  }, [language]);

  const onUpdateScene = React.useCallback(async (sceneId: string, patch: Partial<Scene>) => {
    await api.patchScene(sceneId, patch as any);
    await onReloadProject();
  }, [onReloadProject]);

  // ───────── Current preview scene + active subtitle ─────────
  const sceneStarts = React.useMemo(() => {
    const arr: { sceneId: string; start: number; end: number }[] = [];
    let cursor = 0;
    for (const s of scenes) {
      const d = Number(s.duration_seconds || 0);
      arr.push({ sceneId: s.id, start: cursor, end: cursor + d });
      cursor += d;
    }
    return arr;
  }, [scenes]);

  const currentScene = React.useMemo(() => {
    const hit = sceneStarts.find(
      (s) => currentTime >= s.start && currentTime < s.end
    );
    return scenes.find((sc) => sc.id === (hit?.sceneId || scenes[0]?.id)) || null;
  }, [currentTime, sceneStarts, scenes]);

  const sceneOffset = React.useMemo(() => {
    return sceneStarts.find((s) => s.sceneId === currentScene?.id)?.start ?? 0;
  }, [sceneStarts, currentScene]);

  const activeSub = React.useMemo<SubtitleCue | null>(() => {
    if (!currentScene) return null;
    const sub = subtitlesByScene[currentScene.id];
    if (!sub) return null;
    const offset = sceneStarts.find((x) => x.sceneId === currentScene.id)?.start ?? 0;
    const local = currentTime - offset;
    return sub.cues.find((c) => local >= c.start && local < c.end) || null;
  }, [currentScene, subtitlesByScene, sceneStarts, currentTime]);

  // ───────── Render ─────────
  return (
    <ProjectShell
      onBack={onBack}
      left={<>
        <BrandMark />
        <Separator vertical style={{ height: 20 }} />
        <span style={{ fontSize: 14, fontWeight: 500, whiteSpace: "nowrap",
                       overflow: "hidden", textOverflow: "ellipsis", minWidth: 0 }}>
          {project.title || "Untitled"}
        </span>
        <div style={{ display: "flex", gap: 6, marginLeft: 2, flexShrink: 0 }}>
          <Badge variant="secondary">{project.duration_seconds ?? 30}s</Badge>
          <Badge variant="secondary">{project.aspect_ratio ?? "9:16"}</Badge>
          {allDone ? (
            <Badge variant="success"><Check size={10} strokeWidth={3} /> all assets ready</Badge>
          ) : (
            <Badge variant="info">
              <Spinner size={10} /> rendering · {doneAssets}/{totalAssets}
            </Badge>
          )}
        </div>
      </>}
      right={<>
        <Mono dim size={11} style={{ whiteSpace: "nowrap" }}>
          job {project.latest_job?.id?.slice(0, 8) || "—"}
        </Mono>
        <Button size="sm" disabled={!allDone} onClick={() => setExportOpen(true)}>
          {allDone
            ? <><Download size={14} /> Generate final video</>
            : <><Spinner size={14} /> Generating…</>}
        </Button>
        <ThemeToggle />
      </>}
    >
      <div data-screen-label="03-editor" style={{
        display: "grid", gridTemplateColumns: "minmax(0, 1fr) 380px",
        height: "calc(100vh - 56px)", minHeight: 0,
      }}>
        <div style={{ display: "flex", flexDirection: "column", minHeight: 0,
                       borderRight: "1px solid var(--border)" }}>
          <div style={{
            flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
            padding: 20, minHeight: 0, background: "var(--muted)",
            overflow: "hidden", position: "relative",
          }}>
            <PreviewPlayer
              scene={currentScene}
              sceneState={currentScene ? sceneAssets[currentScene.id] : null}
              activeSub={activeSub}
              aspect={project.aspect_ratio || "9:16"}
              overallPct={overallPct}
              doneAssets={doneAssets}
              totalAssets={totalAssets}
              playing={playing}
              currentTime={currentTime}
              sceneOffset={sceneOffset}
            />
          </div>

          <EditorPlayerBar
            playing={playing}
            currentTime={currentTime}
            totalDur={totalDur}
            onTogglePlay={() => setPlaying((p) => !p)}
            onSeek={(t) => setCurrentTime(t)}
          />

          <EditorTimeline
            scenes={scenes}
            sceneStarts={sceneStarts}
            sceneAssets={sceneAssets}
            subtitlesByScene={subtitlesByScene}
            totalDur={totalDur}
            currentTime={currentTime}
            selected={selected}
            onSeek={setCurrentTime}
            onSelect={setSelected}
          />
        </div>

        <EditorRightPanel
          project={project}
          scenes={scenes}
          sceneAssets={sceneAssets}
          subtitlesByScene={subtitlesByScene}
          selected={selected}
          allDone={allDone}
          overallPct={overallPct}
          doneAssets={doneAssets}
          totalAssets={totalAssets}
          log={log}
          onClearSelected={() => setSelected(null)}
          onRegenerateScene={onRegenerateScene}
          onUpdateScene={onUpdateScene}
          onRegenerateLanguage={onRegenerateLanguage}
        />
      </div>

      <ExportModal
        project={project}
        open={exportOpen}
        onClose={() => setExportOpen(false)}
      />
    </ProjectShell>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Tiny formatting helpers
// ─────────────────────────────────────────────────────────────────────
function labelFor(asset_type: string): string {
  switch (asset_type) {
    case "scene_video":   return "Scene video";
    case "voice":         return "Voice-over";
    case "lipsync_video": return "Lip-sync";
    case "subtitle_srt":  return "Subtitles";
    case "composite":     return "Composite";
    default:              return asset_type;
  }
}

function shortId(scene_id: string, scenes: Scene[]): string {
  const idx = scenes.findIndex((s) => s.id === scene_id);
  if (idx < 0) return scene_id.slice(0, 6);
  return String(idx + 1).padStart(2, "0");
}

export function fmtTimecode(t: number): string {
  const s = Math.max(0, Math.floor(t));
  const m = Math.floor(s / 60);
  const ss = (s % 60).toString().padStart(2, "0");
  const cs = Math.floor((t - s) * 100).toString().padStart(2, "0");
  return `${m}:${ss}.${cs}`;
}

export function fmtTime(t: number): string {
  const s = Math.max(0, Math.floor(t));
  const m = Math.floor(s / 60);
  return `${m}:${(s % 60).toString().padStart(2, "0")}`;
}
