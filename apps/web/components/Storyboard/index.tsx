"use client";
/**
 * Storyboard — reusable scene-grid + scene-detail-drawer + edit-chat-drawer.
 *
 * The page (`app/(project)/[id]/storyboard/page.tsx`) handles routing and
 * data loading; this component owns the rendering. Architecture.md §5,
 * §13 (chat drawer drives Screen 2 edits).
 */
import * as React from "react";
import { Button, Card, Chip, Label, Mono, RadioGroup, Textarea } from "@/components/UI";
import {
  Edit, Image as ImageIcon, Mic, Wand, X,
} from "@/components/Icons";
import { Chat } from "@/components/Chat";
import { api, type Scene } from "@/lib/api";


export interface StoryboardGridProps {
  scenes: Scene[];
  onOpenScene: (s: Scene) => void;
  onToggleSpeaker: (s: Scene) => void;
}

export function StoryboardGrid({ scenes, onOpenScene, onToggleSpeaker }: StoryboardGridProps) {
  return (
    <div style={{
      display: "grid", gap: 16,
      gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
    }}>
      {scenes.map((s) => (
        <SceneCard
          key={s.id}
          scene={s}
          onOpen={() => onOpenScene(s)}
          onToggleSpeaker={() => onToggleSpeaker(s)}
        />
      ))}
    </div>
  );
}


export function SceneCard({
  scene, onOpen, onToggleSpeaker,
}: { scene: Scene; onOpen: () => void; onToggleSpeaker: () => void }) {
  const [thumbUrl, setThumbUrl] = React.useState<string | null>(null);
  React.useEffect(() => {
    let cancelled = false;
    setThumbUrl(null);
    if (!scene.thumbnail_asset_id) return;
    api.getAsset(scene.thumbnail_asset_id)
      .then((a) => { if (!cancelled) setThumbUrl(a.signed_url); })
      .catch(() => { /* leave placeholder */ });
    return () => { cancelled = true; };
  }, [scene.thumbnail_asset_id]);
  return (
    <Card hoverable onClick={onOpen} style={{ padding: 0, display: "flex", flexDirection: "column" }}>
      <div style={{
        aspectRatio: "16 / 9",
        background: "var(--muted)",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "var(--muted-foreground)",
        borderBottom: "1px solid var(--border)",
        overflow: "hidden",
      }}>
        {thumbUrl ? (
          <img src={thumbUrl} alt={`Scene ${scene.scene_index}`}
               style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <ImageIcon size={24} />
        )}
      </div>
      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>Scene {scene.scene_index}</span>
          <Mono dim size={11}>{Number(scene.duration_seconds).toFixed(1)}s</Mono>
        </div>
        <div style={{
          fontSize: 12, color: "var(--muted-foreground)",
          display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
        }}>
          {scene.visual_prompt}
        </div>
        <div style={{
          fontSize: 12, fontStyle: "italic", color: "var(--foreground)",
          display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
        }}>
          “{scene.narration_script}”
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 4 }}>
          <Chip
            selected={!!scene.has_speaker}
            icon={<Mic size={12} />}
            style={{ height: 26, fontSize: 12 }}
            title={scene.has_speaker ? "Speaker on camera (lip-synced)" : "Voice-over only"}
          >
            {scene.has_speaker ? "On camera" : "Voice-over"}
          </Chip>
          <Mono dim size={11}>subs: {scene.subtitle_position}</Mono>
        </div>
      </div>
    </Card>
  );
}


export function SceneDetailPanel({
  scene, onClose, onSave,
}: { scene: Scene; onClose: () => void; onSave: (patch: Partial<Scene>) => void }) {
  const [script, setScript] = React.useState(scene.narration_script);
  const [prompt, setPrompt] = React.useState(scene.visual_prompt);
  const [speaker, setSpeaker] = React.useState<"on" | "off">(scene.has_speaker ? "on" : "off");
  const [sub, setSub] = React.useState<"auto" | "top" | "bottom">(
    (scene.subtitle_position as any) || "auto"
  );
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(10,10,10,0.4)", zIndex: 40 }}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="anim-slide-right"
        style={{
          position: "absolute", top: 0, right: 0, bottom: 0,
          width: 520, background: "var(--card)", color: "var(--card-foreground)",
          borderLeft: "1px solid var(--border)",
          padding: 24, overflowY: "auto",
          display: "flex", flexDirection: "column", gap: 16,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0, fontWeight: 600, fontSize: 16 }}>
            Scene {scene.scene_index} · {Number(scene.duration_seconds).toFixed(1)}s
          </h3>
          <Button variant="ghost" size="icon-sm" onClick={onClose}><X size={14} /></Button>
        </div>

        <div>
          <Label>Narration script</Label>
          <Textarea value={script} onChange={(e) => setScript(e.target.value)}
                    style={{ marginTop: 6, minHeight: 90 }} />
        </div>

        <div>
          <Label>Visual direction</Label>
          <Textarea value={prompt} onChange={(e) => setPrompt(e.target.value)}
                    style={{ marginTop: 6, minHeight: 110 }} />
        </div>

        <div>
          <Label>Speaking on camera</Label>
          <RadioGroup
            value={speaker}
            onChange={(v) => setSpeaker(v as "on" | "off")}
            options={[
              { value: "off", label: "Off", hint: "Voice-over only — no lip-sync pass." },
              { value: "on", label: "On", hint: "Lip-sync the voice track onto the scene's face." },
            ]}
            style={{ marginTop: 6 }}
          />
        </div>

        <div>
          <Label>Subtitle position</Label>
          <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
            {(["auto", "top", "bottom"] as const).map((p) => (
              <Chip key={p} selected={sub === p} onClick={() => setSub(p)}>{p}</Chip>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: "auto" }}>
          <Button variant="outline" onClick={() => api.regenerateScene(scene.id)}>
            <Wand size={14} /> Regenerate
          </Button>
          <Button style={{ marginLeft: "auto" }} onClick={() => onSave({
            narration_script: script,
            visual_prompt: prompt,
            has_speaker: speaker === "on",
            subtitle_position: sub,
          })}>
            <Edit size={14} /> Save changes
          </Button>
        </div>
      </div>
    </div>
  );
}


export function EditChatDrawer({
  projectId, onClose, onApplied,
}: { projectId: string; onClose: () => void; onApplied: () => void }) {
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(10,10,10,0.4)", zIndex: 40 }}>
      <div onClick={(e) => e.stopPropagation()} className="anim-slide-right" style={{
        position: "absolute", top: 0, right: 0, bottom: 0,
        width: 420, background: "var(--card)", borderLeft: "1px solid var(--border)",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{
          padding: "14px 18px", borderBottom: "1px solid var(--border)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>Chat edit</span>
          <Button variant="ghost" size="icon-sm" onClick={onClose}><X size={14} /></Button>
        </div>
        <Chat
          projectId={projectId}
          variant="drawer"
          greeting="Try: “Make scene 2 a sunset” · “Switch to Hindi” · “Regenerate scene 4”"
          composerPlaceholder="What would you like to change?"
          onIntent={(d) => { if (d?.applied || d?.queued) onApplied(); }}
        />
      </div>
    </div>
  );
}
