"use client";
import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { BrandMark, ProjectShell, ThemeToggle } from "@/components/Shell";
import { Badge, Button, Label, Mono, Separator } from "@/components/UI";
import { ArrowRight, Check, Spinner } from "@/components/Icons";
import { Chat } from "@/components/Chat";
import { api, Project } from "@/lib/api";

const SLOT_ORDER: { key: string; label: string }[] = [
  { key: "video_type",       label: "Type" },
  { key: "topic",            label: "Topic" },
  { key: "visual_style",     label: "Style" },
  { key: "duration_seconds", label: "Duration" },
  { key: "aspect_ratio",     label: "Aspect" },
  { key: "primary_language", label: "Language" },
  { key: "narration_tone",   label: "Tone" },
  { key: "has_characters",   label: "People?" },
  { key: "music_enabled",    label: "Music" },
  { key: "subtitles_enabled", label: "Subtitles" },
];

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = React.useState<Project | null>(null);
  const [ready, setReady] = React.useState(false);
  const [kicking, setKicking] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    api.getProject(id).then((p) => {
      if (cancelled) return;
      setProject(p);
      if (p.status !== "draft" && p.status !== "collecting") {
        router.push(`/${id}/${routeForStatus(p.status)}`);
      }
    }).catch(console.error);
    return () => { cancelled = true; };
  }, [id, router]);

  async function onStartPlanning() {
    setKicking(true);
    try {
      const { job_id } = await api.generateStoryboard(id);
      router.push(`/${id}/storyboard?job=${job_id}`);
    } catch (e) {
      console.error(e);
      setKicking(false);
    }
  }

  const filled = countFilled(project?.brief || {});

  return (
    <ProjectShell
      onBack={() => router.push("/")}
      left={<>
        <BrandMark />
        <Separator vertical style={{ height: 20 }} />
        <span style={{ fontSize: 14, fontWeight: 500 }}>{project?.title || "Untitled video"}</span>
        <Badge variant="secondary">{project?.status || "draft"}</Badge>
      </>}
      right={<><ThemeToggle /></>}
    >
      <div style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1fr) 340px",
        height: "calc(100vh - 56px)", minHeight: 0,
      }}>
        {/* Chat column — extracted into a reusable component */}
        <div style={{
          display: "flex", flexDirection: "column", minHeight: 0,
          borderRight: "1px solid var(--border)",
        }}>
          <Chat
            projectId={id}
            onSlotUpdate={(slots) =>
              setProject((p) => p ? { ...p, brief: { ...p.brief, ...slots } } : p)
            }
            onReady={() => setReady(true)}
            composerPlaceholder={ready
              ? "All set — click Start planning above."
              : "Type your reply, or tap a suggestion above…"}
            disabled={ready}
          />
          {ready && (
            <div style={{ padding: "0 40px 16px" }}>
              <div style={{ maxWidth: 680, margin: "0 auto" }}>
                <Button onClick={onStartPlanning} disabled={kicking}>
                  {kicking ? <Spinner size={14} /> : null}
                  Start planning <ArrowRight size={14} />
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Brief summary */}
        <aside style={{ padding: "24px 20px", overflowY: "auto", background: "var(--card)" }}>
          <Label>Your video</Label>
          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 10 }}>
            {SLOT_ORDER.map((slot) => {
              const v = (project?.brief as any)?.[slot.key];
              const filled = v !== undefined && v !== null && v !== "";
              return (
                <div key={slot.key} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  fontSize: 13,
                }}>
                  <span style={{ color: "var(--muted-foreground)" }}>{slot.label}</span>
                  <span style={{
                    fontWeight: filled ? 500 : 400,
                    color: filled ? "var(--foreground)" : "var(--muted-foreground)",
                    display: "inline-flex", alignItems: "center", gap: 6,
                  }}>
                    {filled ? <Check size={12} /> : null}
                    {filled ? prettify(slot.key, v) : "—"}
                  </span>
                </div>
              );
            })}
          </div>
          <Separator style={{ margin: "18px 0" }} />
          <Mono dim size={11}>{filled} of {SLOT_ORDER.length} collected</Mono>
        </aside>
      </div>
    </ProjectShell>
  );
}


function countFilled(brief: Record<string, any>): number {
  return SLOT_ORDER.filter((s) => brief[s.key] !== undefined && brief[s.key] !== null && brief[s.key] !== "").length;
}

function prettify(key: string, v: any): string {
  if (key === "duration_seconds") return `${v}s`;
  if (key === "has_characters") return v ? "On camera" : "Voice-over";
  if (key === "music_enabled" || key === "subtitles_enabled") return v ? "On" : "Off";
  if (typeof v === "string") return v.replace(/_/g, " ");
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return String(v);
}

function routeForStatus(status: string): string {
  switch (status) {
    case "planning": return "storyboard";
    case "rendering": return "progress";
    case "ready":
    case "completed": return "review";
    default: return "chat";
  }
}
