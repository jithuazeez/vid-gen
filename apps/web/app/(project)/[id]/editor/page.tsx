"use client";
import * as React from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { BrandMark, ProjectShell } from "@/components/Shell";
import { EditorScreen } from "@/components/Editor/EditorScreen";
import { api, Project, subscribeJobEvents, SSEEvent } from "@/lib/api";

export default function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const queryJob = search.get("job");

  const [project, setProject] = React.useState<Project | null>(null);
  const [jobId, setJobId] = React.useState<string | null>(queryJob);
  // Surface every SSE event the editor cares about as a state update so
  // children stay declarative.
  const [events, setEvents] = React.useState<SSEEvent[]>([]);

  const refresh = React.useCallback(async () => {
    const p = await api.getProject(id);
    setProject(p);
    // Discover the live job if the URL didn't carry one (e.g. a reload).
    if (!queryJob && p.latest_job?.id) setJobId(p.latest_job.id);
  }, [id, queryJob]);

  React.useEffect(() => { void refresh(); }, [refresh]);

  React.useEffect(() => {
    if (!jobId) return;
    return subscribeJobEvents(jobId, (e) => {
      setEvents((prev) => {
        // Keep the buffer small — children replay from the latest assets snapshot
        // on snapshot events anyway.
        const next = prev.length > 200 ? prev.slice(-150) : prev;
        return [...next, e];
      });
      // Re-fetch project on terminal events so server-side state is the
      // source of truth at completion.
      if (e.event === "done" || e.event === "error") void refresh();
    });
  }, [jobId, refresh]);

  if (!project) {
    return (
      <ProjectShell left={<BrandMark />}>
        <div style={{ padding: 40, color: "var(--muted-foreground)" }}>Loading…</div>
      </ProjectShell>
    );
  }

  return (
    <EditorScreen
      project={project}
      events={events}
      onBack={() => router.push(`/${id}/storyboard`)}
      onReloadProject={refresh}
      onNewJob={setJobId}
    />
  );
}
