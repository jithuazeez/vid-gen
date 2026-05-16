"use client";
import * as React from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { BrandMark, ProjectShell, ThemeToggle } from "@/components/Shell";
import { Badge, Button, Card, Mono, Progress, Separator } from "@/components/UI";
import { Check, Spinner, Video } from "@/components/Icons";
import { api, subscribeJobEvents, type Project, type Scene } from "@/lib/api";

const STAGES = [
  { key: "scenes",        label: "Visual scenes",      hint: "LTX-Video I2V per scene" },
  { key: "music",         label: "Background music",   hint: "ACE-Step 1.5" },
  { key: "voice",         label: "Voice narration",    hint: "Sarvam Bulbul-v2" },
  { key: "lipsync",       label: "Lip-sync",           hint: "MuseTalk (gated)" },
  { key: "subtitles",     label: "Subtitles",          hint: "Whisper large-v3" },
  { key: "composite",     label: "Compositing",        hint: "FFmpeg per scene" },
  { key: "export",        label: "Final export",       hint: "FFmpeg concat + encode" },
];


export default function ProgressPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const initialJobId = search.get("job");

  const [project, setProject] = React.useState<Project | null>(null);
  const [jobId, setJobId] = React.useState<string | null>(initialJobId);
  const [stage, setStage] = React.useState<string>("queued");
  const [percent, setPercent] = React.useState(0);
  const [doneScenes, setDoneScenes] = React.useState<Set<string>>(new Set());
  const [log, setLog] = React.useState<string[]>([]);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    void api.getProject(id).then(setProject).catch(console.error);
  }, [id]);

  React.useEffect(() => {
    if (!jobId) return;
    return subscribeJobEvents(jobId, (e) => {
      const t = new Date().toLocaleTimeString();
      switch (e.event) {
        case "stage_change":
          if (e.data?.stage) setStage(String(e.data.stage));
          setLog((l) => [`${t} → stage: ${e.data?.stage}`, ...l].slice(0, 80));
          break;
        case "progress":
          if (typeof e.data?.percent === "number") setPercent(e.data.percent);
          break;
        case "scene_ready":
          if (e.data?.scene_id) {
            setDoneScenes((prev) => new Set([...prev, e.data.scene_id]));
            setLog((l) => [`${t} ✓ scene ${e.data.scene_id?.slice(0, 8)} ${e.data.kind || ""}`, ...l].slice(0, 80));
          }
          break;
        case "asset_progress":
          setLog((l) => [`${t}   ${e.data?.asset_type} · ${e.data?.scene_id?.slice(0, 8) || "—"}`, ...l].slice(0, 80));
          break;
        case "done":
          setStage("done");
          setPercent(100);
          setLog((l) => [`${t} ✓ render complete`, ...l].slice(0, 80));
          // Bounce to review.
          setTimeout(() => router.push(`/${id}/review`), 800);
          break;
        case "error":
          setError(String(e.data?.message || "Render failed"));
          break;
      }
    });
  }, [jobId, id, router]);

  // If we landed without a job_id, kick one off automatically.
  React.useEffect(() => {
    if (jobId || !project) return;
    if (project.status !== "rendering" && project.status !== "ready") {
      api.generate(id).then((r) => setJobId(r.job_id)).catch((e) => setError(String(e)));
    } else if (project.latest_job?.id) {
      setJobId(project.latest_job.id);
    }
  }, [project, id, jobId]);

  const stageIdx = Math.max(0, STAGES.findIndex((s) => s.key === stage));

  return (
    <ProjectShell
      onBack={() => router.push(`/${id}/storyboard`)}
      left={<>
        <BrandMark />
        <Separator vertical style={{ height: 20 }} />
        <span style={{ fontSize: 14, fontWeight: 500 }}>{project?.title || "Untitled"}</span>
        <Badge variant="info">Generating</Badge>
      </>}
      right={<ThemeToggle />}
    >
      <div style={{
        padding: "32px 32px 48px", maxWidth: 1080, margin: "0 auto",
        display: "grid", gap: 24, gridTemplateColumns: "minmax(0, 1fr) 380px",
      }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: -0.4 }}>
            Rendering your video
          </h2>
          <Mono dim size={12}>
            {project?.duration_seconds ?? "—"}s · {project?.aspect_ratio ?? "—"} ·
            language: {project?.primary_language ?? "—"}
          </Mono>

          <div>
            <Progress value={percent || (stageIdx + 1) * (100 / STAGES.length)} />
            <div style={{ marginTop: 6, display: "flex", justifyContent: "space-between" }}>
              <Mono size={11} dim>stage: {stage}</Mono>
              <Mono size={11} dim>{percent.toFixed(0)}%</Mono>
            </div>
          </div>

          <Card style={{ padding: 18 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {STAGES.map((s, i) => {
                const reached = i <= stageIdx;
                const current = i === stageIdx && stage !== "done";
                return (
                  <div key={s.key} style={{
                    display: "grid", gridTemplateColumns: "24px 1fr auto",
                    gap: 10, alignItems: "center",
                    opacity: reached ? 1 : 0.45,
                  }}>
                    <span style={{
                      width: 22, height: 22, borderRadius: "50%",
                      display: "inline-flex", alignItems: "center", justifyContent: "center",
                      background: reached ? "var(--foreground)" : "var(--muted)",
                      color: reached ? "var(--background)" : "var(--muted-foreground)",
                    }}>
                      {current ? <Spinner size={12} /> : reached ? <Check size={13} /> : i + 1}
                    </span>
                    <span style={{ fontSize: 14, fontWeight: 500 }}>{s.label}</span>
                    <Mono size={11} dim>{s.hint}</Mono>
                  </div>
                );
              })}
            </div>
          </Card>

          {project?.scenes?.length ? (
            <SceneStrip scenes={project.scenes} doneIds={doneScenes} />
          ) : null}

          {error && (
            <Card style={{ padding: 14, borderColor: "var(--destructive)" }}>
              <span style={{ color: "var(--destructive)", fontSize: 13 }}>Error: {error}</span>
            </Card>
          )}
        </div>

        {/* Live log */}
        <Card style={{ padding: 16, alignSelf: "start", maxHeight: 540, overflowY: "auto" }}>
          <Mono size={11} dim>Live log</Mono>
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
            {log.length === 0 && <Mono dim size={12}>Waiting for events…</Mono>}
            {log.map((line, i) => (
              <Mono key={i} size={11}>{line}</Mono>
            ))}
          </div>
        </Card>
      </div>
    </ProjectShell>
  );
}

function SceneStrip({ scenes, doneIds }: { scenes: Scene[]; doneIds: Set<string> }) {
  return (
    <div style={{ display: "grid", gap: 8, gridTemplateColumns: `repeat(${scenes.length}, 1fr)` }}>
      {scenes.map((s) => {
        const done = doneIds.has(s.id);
        return (
          <Card key={s.id} style={{ padding: 0, overflow: "hidden" }}>
            <div style={{
              aspectRatio: "16/9", background: done ? "var(--foreground)" : "var(--muted)",
              color: done ? "var(--background)" : "var(--muted-foreground)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              {done ? <Check size={18} /> : <Video size={16} />}
            </div>
            <div style={{ padding: 8, display: "flex", justifyContent: "space-between" }}>
              <Mono size={11}>scene {s.scene_index}</Mono>
              <Mono size={11} dim>{Number(s.duration_seconds).toFixed(1)}s</Mono>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
