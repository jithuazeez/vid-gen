"use client";
import * as React from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { BrandMark, ProjectShell, ThemeToggle } from "@/components/Shell";
import { Badge, Button, Mono, Separator } from "@/components/UI";
import { MessageSquare, Refresh, Spinner, Wand } from "@/components/Icons";
import {
  StoryboardGrid, SceneDetailPanel, EditChatDrawer,
} from "@/components/Storyboard";
import { api, Project, Scene, subscribeJobEvents } from "@/lib/api";

export default function StoryboardPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const planningJobId = search.get("job");
  const [project, setProject] = React.useState<Project | null>(null);
  const [scenes, setScenes] = React.useState<Scene[]>([]);
  const [selected, setSelected] = React.useState<Scene | null>(null);
  const [generating, setGenerating] = React.useState(false);
  const [editDrawerOpen, setEditDrawerOpen] = React.useState(false);

  const refresh = React.useCallback(async () => {
    const [p, sb] = await Promise.all([api.getProject(id), api.getStoryboard(id)]);
    setProject(p);
    setScenes(sb.scenes);
  }, [id]);

  React.useEffect(() => { void refresh(); }, [refresh]);

  // If we navigated in with ?job=<storyboard_job_id>, subscribe to its SSE
  // stream so scenes appear the moment the worker publishes them — instead
  // of leaving the user staring at "Planning your scenes…" until they hit
  // refresh manually.
  React.useEffect(() => {
    if (!planningJobId) return;
    return subscribeJobEvents(planningJobId, (e) => {
      if (e.event === "scene_ready" || e.event === "done") {
        void refresh();
      }
    });
  }, [planningJobId, refresh]);

  async function onGenerate() {
    setGenerating(true);
    try {
      const { job_id } = await api.generate(id);
      // The async editor is the new landing — assets stream in as they're
      // rendered; the user can edit any tile in place.
      router.push(`/${id}/editor?job=${job_id}`);
    } catch (e) {
      console.error(e);
      setGenerating(false);
    }
  }

  async function patchScene(scene: Scene, patch: Partial<Scene>) {
    const updated = await api.patchScene(scene.id, patch);
    setScenes((arr) => arr.map((s) => s.id === scene.id ? updated : s));
    if (selected?.id === scene.id) setSelected(updated);
  }

  return (
    <ProjectShell
      onBack={() => router.push(`/${id}/chat`)}
      left={<>
        <BrandMark />
        <Separator vertical style={{ height: 20 }} />
        <span style={{ fontSize: 14, fontWeight: 500 }}>{project?.title || "Untitled"}</span>
        <Badge variant="secondary">Storyboard</Badge>
      </>}
      right={<>
        <Button variant="outline" size="sm" onClick={() => setEditDrawerOpen(true)}>
          <MessageSquare size={14} /> Chat edit
        </Button>
        <Button variant="ghost" size="sm" onClick={refresh} title="Refresh"><Refresh size={14} /></Button>
        <Button onClick={onGenerate} disabled={generating || scenes.length === 0}>
          {generating ? <Spinner size={14} /> : <Wand size={14} />}
          Generate
        </Button>
        <ThemeToggle />
      </>}
    >
      <div style={{ padding: "28px 32px", maxWidth: 1280, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 18 }}>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: -0.4 }}>
            Scenes ({scenes.length})
          </h2>
          <Mono dim size={12}>
            {project?.duration_seconds ?? "—"}s · {project?.aspect_ratio ?? "—"} · {project?.primary_language ?? "—"}
          </Mono>
        </div>

        {scenes.length === 0 ? (
          <div style={{
            border: "1px dashed var(--border)", borderRadius: 12, padding: 40,
            display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
            color: "var(--muted-foreground)",
          }}>
            <Spinner size={20} />
            <span>Planning your scenes…</span>
            <Button size="sm" variant="outline" onClick={refresh}>Refresh</Button>
          </div>
        ) : (
          <StoryboardGrid
            scenes={scenes}
            onOpenScene={setSelected}
            onToggleSpeaker={(s) => patchScene(s, { has_speaker: !s.has_speaker })}
          />
        )}
      </div>

      {selected && (
        <SceneDetailPanel
          scene={selected}
          onClose={() => setSelected(null)}
          onSave={(patch) => patchScene(selected, patch).then(() => setSelected(null))}
        />
      )}

      {editDrawerOpen && (
        <EditChatDrawer projectId={id} onClose={() => setEditDrawerOpen(false)} onApplied={refresh} />
      )}
    </ProjectShell>
  );
}
