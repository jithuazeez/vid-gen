"use client";
import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { BrandMark, ProjectShell, ThemeToggle } from "@/components/Shell";
import { Badge, Button, Card, Mono, Separator, Tabs } from "@/components/UI";
import { Download, MessageSquare, Pause, Play, Spinner, Sub, Type, Volume } from "@/components/Icons";
import { api, postChat, subscribeJobEvents, type Overlay, type Project, type Scene, type Subtitle, type SubtitleCue } from "@/lib/api";
import { Timeline } from "@/components/Timeline";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { SubtitleEditor } from "@/components/SubtitleEditor";
import { OverlayTrack } from "@/components/OverlayTrack";
import { ExportModal } from "@/components/ExportModal";

type Tab = "subtitles" | "overlays" | "audio";

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [project, setProject] = React.useState<Project | null>(null);
  const [videoUrl, setVideoUrl] = React.useState<string | null>(null);
  const [subtitlesByScene, setSubtitlesByScene] = React.useState<Subtitle[]>([]);
  const [tab, setTab] = React.useState<Tab>("subtitles");
  const [activeSceneId, setActiveSceneId] = React.useState<string | null>(null);
  const [showExport, setShowExport] = React.useState(false);
  const [showChat, setShowChat] = React.useState(false);
  const [busyLang, setBusyLang] = React.useState<string | null>(null);
  const [musicVolume, setMusicVolume] = React.useState<number>(-18);
  const [currentSec, setCurrentSec] = React.useState(0);

  const refresh = React.useCallback(async () => {
    const p = await api.getProject(id);
    setProject(p);
    if (p.scenes[0]) setActiveSceneId((cur) => cur || p.scenes[0].id);
    setMusicVolume(Number((p.brief?.audio?.music_volume_db ?? -18)));

    const lang = p.active_language || p.primary_language || "en";
    // Fetch subtitles per scene.
    const subs = await Promise.all(p.scenes.map((s) =>
      api.getSubtitle(s.id, lang).catch(() => null)
    ));
    setSubtitlesByScene(subs.filter(Boolean) as Subtitle[]);

    // Resolve the latest final_export asset for the active language.
    try {
      const job = p.latest_job;
      const exportAssetId = (job?.progress as any)?.final_export_asset_id;
      if (exportAssetId) {
        const asset = await api.getAsset(exportAssetId);
        setVideoUrl(asset.signed_url);
      }
    } catch {
      /* no asset yet */
    }
  }, [id]);

  React.useEffect(() => { void refresh(); }, [refresh]);

  async function changeLanguage(code: string) {
    if (!project) return;
    setBusyLang(code);
    try {
      const r = await api.regenerateLanguage(id, code);
      if (r.job_id) {
        const unsub = subscribeJobEvents(r.job_id, async (e) => {
          if (e.event === "done") {
            unsub();
            await refresh();
            setBusyLang(null);
          }
        });
      } else {
        // Cache hit — instant.
        await refresh();
        setBusyLang(null);
      }
    } catch (e) {
      console.error(e);
      setBusyLang(null);
    }
  }

  async function setVolume(db: number) {
    setMusicVolume(db);
    await api.patchAudio(id, db);
  }

  const totalDuration = project?.scenes?.reduce((a, s) => a + Number(s.duration_seconds), 0) || 0;
  const activeSceneSub = subtitlesByScene.find((s) => s.scene_id === activeSceneId) || null;

  return (
    <ProjectShell
      onBack={() => router.push(`/${id}/storyboard`)}
      left={<>
        <BrandMark />
        <Separator vertical style={{ height: 20 }} />
        <span style={{ fontSize: 14, fontWeight: 500 }}>{project?.title || "Untitled"}</span>
        <Badge variant="success">Ready</Badge>
      </>}
      right={<>
        <Button variant="outline" size="sm" onClick={() => setShowChat(true)}>
          <MessageSquare size={14} /> Chat edit
        </Button>
        <Button onClick={() => setShowExport(true)}>
          <Download size={14} /> Export
        </Button>
        <ThemeToggle />
      </>}
    >
      <div style={{
        display: "grid", gridTemplateColumns: "minmax(0, 1fr) 380px",
        height: "calc(100vh - 56px)",
      }}>
        {/* Player + timeline */}
        <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18, minHeight: 0 }}>
          <PlayerCard
            videoUrl={videoUrl}
            onTime={setCurrentSec}
            placeholder={!project || project.status === "rendering"}
          />
          <Card style={{ padding: 14 }}>
            <Timeline
              scenes={project?.scenes || []}
              overlays={(project?.overlays || []) as Overlay[]}
              subtitles={subtitlesByScene.map((s) => ({ sceneId: s.scene_id, cues: s.cues }))}
              durationSec={totalDuration}
              currentSec={currentSec}
              onSelectScene={setActiveSceneId}
            />
          </Card>
        </div>

        {/* Right panel */}
        <aside style={{
          borderLeft: "1px solid var(--border)", padding: "20px 18px",
          display: "flex", flexDirection: "column", gap: 16, overflowY: "auto",
        }}>
          <LanguageSwitch
            active={project?.active_language || null}
            available={project?.available_languages || []}
            busy={busyLang}
            onChange={changeLanguage}
          />

          <Tabs<Tab>
            value={tab}
            onChange={setTab}
            fullWidth
            items={[
              { value: "subtitles", label: "Subtitles", icon: <Sub size={13} /> },
              { value: "overlays",  label: "Overlays",  icon: <Type size={13} /> },
              { value: "audio",     label: "Audio",     icon: <Volume size={13} /> },
            ]}
          />

          {tab === "subtitles" && (
            <SceneSelector
              scenes={project?.scenes || []}
              activeId={activeSceneId}
              onChange={setActiveSceneId}
            />
          )}

          {tab === "subtitles" && (
            <SubtitleEditor
              subtitle={activeSceneSub}
              onSave={async (cues: SubtitleCue[]) => {
                if (!activeSceneSub) return;
                await api.patchSubtitle(activeSceneSub.id, { cues });
                await refresh();
              }}
            />
          )}

          {tab === "overlays" && project && (
            <OverlayTrack
              projectId={project.id}
              overlays={project.overlays || []}
              durationSec={totalDuration}
              onCreate={async (o) => {
                await api.createOverlay({ ...o, project_id: project.id });
                await refresh();
              }}
              onPatch={async (oid, patch) => {
                await api.patchOverlay(oid, patch);
                await refresh();
              }}
              onDelete={async (oid) => {
                await api.deleteOverlay(oid);
                await refresh();
              }}
            />
          )}

          {tab === "audio" && (
            <AudioPanel
              musicEnabled={!!project?.music_enabled}
              musicVolume={musicVolume}
              onVolume={setVolume}
            />
          )}
        </aside>
      </div>

      {project && showExport && (
        <ExportModal project={project} open={showExport} onClose={() => setShowExport(false)} />
      )}
      {showChat && (
        <ChatDrawer projectId={id} onClose={() => setShowChat(false)} onApplied={refresh} />
      )}
    </ProjectShell>
  );
}

// ─── Sub-components ────────────────────────────────────────────────

function PlayerCard({ videoUrl, onTime, placeholder }: { videoUrl: string | null; onTime: (s: number) => void; placeholder: boolean }) {
  const ref = React.useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = React.useState(false);

  React.useEffect(() => {
    const v = ref.current;
    if (!v) return;
    const onUpdate = () => onTime(v.currentTime);
    v.addEventListener("timeupdate", onUpdate);
    return () => v.removeEventListener("timeupdate", onUpdate);
  }, [onTime, videoUrl]);

  function toggle() {
    const v = ref.current;
    if (!v) return;
    if (v.paused) { void v.play(); setPlaying(true); }
    else { v.pause(); setPlaying(false); }
  }

  return (
    <Card style={{ padding: 0, overflow: "hidden" }}>
      <div style={{
        position: "relative", aspectRatio: "16/9",
        background: "#000", display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        {videoUrl ? (
          <video
            ref={ref} src={videoUrl} controls={false}
            style={{ width: "100%", height: "100%" }}
            onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
          />
        ) : (
          <div style={{ color: "var(--muted-foreground)", fontSize: 13, textAlign: "center" }}>
            {placeholder ? <><Spinner size={18} /><div style={{ marginTop: 6 }}>Render in progress…</div></>
                         : "No final export asset yet."}
          </div>
        )}
        {videoUrl && (
          <button
            onClick={toggle}
            style={{
              position: "absolute", inset: 0, background: "transparent",
              border: "none", cursor: "pointer", display: "flex",
              alignItems: "center", justifyContent: "center",
            }}
          >
            <span style={{
              background: "rgba(0,0,0,0.55)", color: "white",
              borderRadius: "50%", width: 56, height: 56,
              display: playing ? "none" : "inline-flex", alignItems: "center", justifyContent: "center",
            }}>
              <Play size={20} />
            </span>
          </button>
        )}
      </div>
    </Card>
  );
}

function SceneSelector({ scenes, activeId, onChange }: { scenes: Scene[]; activeId: string | null; onChange: (id: string) => void }) {
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {scenes.map((s) => (
        <button
          key={s.id}
          onClick={() => onChange(s.id)}
          style={{
            padding: "4px 10px", borderRadius: 6,
            background: activeId === s.id ? "var(--foreground)" : "var(--muted)",
            color: activeId === s.id ? "var(--background)" : "var(--foreground)",
            border: "1px solid var(--border)", cursor: "pointer",
            fontSize: 12, fontWeight: 500,
          }}
        >
          scene {s.scene_index}
        </button>
      ))}
    </div>
  );
}

function AudioPanel({ musicEnabled, musicVolume, onVolume }: { musicEnabled: boolean; musicVolume: number; onVolume: (db: number) => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Mono size={11} dim>Background music</Mono>
      <div style={{
        padding: 12, border: "1px solid var(--border)", borderRadius: 6,
        opacity: musicEnabled ? 1 : 0.5,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 12 }}>
          <span>Volume</span>
          <Mono size={12}>{musicVolume.toFixed(1)} dB</Mono>
        </div>
        <input
          type="range" min={-40} max={6} step={0.5}
          value={musicVolume}
          disabled={!musicEnabled}
          onChange={(e) => onVolume(Number(e.target.value))}
          style={{ width: "100%" }}
        />
        {!musicEnabled && <Mono size={11} dim style={{ marginTop: 6, display: "block" }}>Music disabled in this project.</Mono>}
      </div>
    </div>
  );
}

function ChatDrawer({ projectId, onClose, onApplied }: { projectId: string; onClose: () => void; onApplied: () => void }) {
  const [draft, setDraft] = React.useState("");
  const [log, setLog] = React.useState<{ role: "user" | "assistant"; text: string }[]>([]);
  const [busy, setBusy] = React.useState(false);

  async function send() {
    const text = draft.trim();
    if (!text) return;
    setLog((l) => [...l, { role: "user", text }]);
    setDraft("");
    setBusy(true);
    try {
      let assistant = "";
      for await (const ev of postChat(projectId, text)) {
        if (ev.event === "intent") assistant = ev.data?.preview || assistant;
      }
      if (assistant) setLog((l) => [...l, { role: "assistant", text: assistant }]);
      onApplied();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(10,10,10,0.4)", zIndex: 40 }}>
      <div onClick={(e) => e.stopPropagation()} className="anim-slide-right" style={{
        position: "absolute", top: 0, right: 0, bottom: 0,
        width: 420, background: "var(--card)", borderLeft: "1px solid var(--border)",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--border)" }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>Chat edit</span>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
          {log.length === 0 && <Mono dim size={12}>Try: “Switch to Hindi” · “Move scene 3 subtitles to top” · “Add a CTA at 5s”</Mono>}
          {log.map((m, i) => (
            <div key={i} style={{ alignSelf: m.role === "user" ? "flex-end" : "flex-start", maxWidth: "85%" }}>
              <div style={{
                background: m.role === "user" ? "var(--primary)" : "var(--muted)",
                color: m.role === "user" ? "var(--primary-foreground)" : "var(--foreground)",
                padding: "8px 12px", borderRadius: 10, fontSize: 13,
              }}>{m.text}</div>
            </div>
          ))}
        </div>
        <div style={{ padding: 14, borderTop: "1px solid var(--border)", display: "flex", gap: 8 }}>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void send(); }}
            placeholder="What would you like to change?"
            style={{
              flex: 1, border: "1px solid var(--input)", borderRadius: 8,
              padding: "8px 12px", fontSize: 14, background: "var(--background)",
              color: "var(--foreground)", outline: "none",
            }}
          />
          <Button onClick={send} disabled={busy || !draft.trim()}>Send</Button>
        </div>
      </div>
    </div>
  );
}
