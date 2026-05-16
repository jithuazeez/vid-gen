"use client";
import * as React from "react";
import { Button, Chip, Input, Label, Mono } from "../UI";
import type { Overlay } from "@/lib/api";

interface Props {
  projectId: string;
  overlays: Overlay[];
  durationSec: number;
  onCreate: (o: Omit<Overlay, "id">) => void | Promise<void>;
  onPatch: (id: string, patch: Partial<Overlay>) => void | Promise<void>;
  onDelete: (id: string) => void | Promise<void>;
}

export function OverlayTrack({ overlays, durationSec, onCreate, onPatch, onDelete }: Props) {
  const [drafting, setDrafting] = React.useState(false);
  const [draft, setDraft] = React.useState({
    overlay_type: "cta", text: "Subscribe",
    start_seconds: 0, end_seconds: Math.min(3, durationSec),
    animation: "fade",
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Mono size={11} dim>{overlays.length} overlay{overlays.length === 1 ? "" : "s"}</Mono>
        <Button size="sm" onClick={() => setDrafting((v) => !v)}>
          {drafting ? "Cancel" : "+ Add overlay"}
        </Button>
      </div>

      {drafting && (
        <div style={{ padding: 10, border: "1px dashed var(--border)", borderRadius: 6,
                      display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", gap: 6 }}>
            {(["cta", "lower_third", "logo", "animated_text"] as const).map((t) => (
              <Chip key={t} selected={draft.overlay_type === t}
                    onClick={() => setDraft((d) => ({ ...d, overlay_type: t }))}>{t}</Chip>
            ))}
          </div>
          <Input value={draft.text} placeholder="Text"
                 onChange={(e) => setDraft((d) => ({ ...d, text: e.target.value }))} />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            <NumField label="start (s)" value={draft.start_seconds}
                      onChange={(v) => setDraft((d) => ({ ...d, start_seconds: v }))} />
            <NumField label="end (s)" value={draft.end_seconds}
                      onChange={(v) => setDraft((d) => ({ ...d, end_seconds: v }))} />
          </div>
          <Button size="sm" onClick={async () => {
            await onCreate({ ...draft, position: { x: 0.5, y: 0.85 }, style: {} } as any);
            setDrafting(false);
          }}>Create</Button>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {overlays.map((o) => (
          <div key={o.id} style={{
            padding: 10, border: "1px solid var(--border)", borderRadius: 6,
            display: "grid", gridTemplateColumns: "100px 1fr 90px 90px 30px",
            gap: 8, alignItems: "center", fontSize: 13,
          }}>
            <Chip selected>{o.overlay_type}</Chip>
            <Input
              value={o.text || ""}
              onChange={(e) => onPatch(o.id, { text: e.target.value })}
            />
            <NumField label="start" value={o.start_seconds}
                      onChange={(v) => onPatch(o.id, { start_seconds: v })} />
            <NumField label="end" value={o.end_seconds}
                      onChange={(v) => onPatch(o.id, { end_seconds: v })} />
            <Button variant="ghost" size="icon-sm" onClick={() => onDelete(o.id)}>×</Button>
          </div>
        ))}
      </div>
    </div>
  );
}

function NumField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Label style={{ fontSize: 10 }}>{label}</Label>
      <Input
        type="number" step={0.1} value={Number(value).toFixed(2)}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ height: 30, fontFamily: "var(--font-mono)", fontSize: 12 }}
      />
    </div>
  );
}
