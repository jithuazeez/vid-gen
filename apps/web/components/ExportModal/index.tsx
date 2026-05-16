"use client";
import * as React from "react";
// import { Button, Chip, Dialog, Label, Mono, RadioGroup, Spinner } from "../UI";
import { Button, Chip, Dialog, Label, Mono, RadioGroup } from "../UI";
import { Download, Spinner } from "../Icons";
import { api, subscribeJobEvents, type Project } from "@/lib/api";

interface Props {
  project: Project;
  open: boolean;
  onClose: () => void;
}

export function ExportModal({ project, open, onClose }: Props) {
  const [language, setLanguage] = React.useState(project.active_language || project.primary_language || "en");
  const [quality, setQuality] = React.useState<"720p" | "1080p">("1080p");
  const [subs, setSubs] = React.useState<"burned" | "sidecar">("burned");
  const [jobId, setJobId] = React.useState<string | null>(null);
  const [stage, setStage] = React.useState<string | null>(null);
  const [done, setDone] = React.useState<{ asset_id?: string } | null>(null);
  const [downloading, setDownloading] = React.useState(false);

  React.useEffect(() => {
    if (!jobId) return;
    return subscribeJobEvents(jobId, (e) => {
      if (e.event === "stage_change") setStage(String(e.data?.stage || ""));
      if (e.event === "done") {
        const asset = e.data?.export?.asset_id;
        setDone({ asset_id: asset });
      }
    });
  }, [jobId]);

  async function startExport() {
    setDone(null);
    setStage("queued");
    const { job_id } = await api.exportProject(project.id, { language, quality, subtitles: subs });
    setJobId(job_id);
  }

  async function downloadResult() {
    if (!done?.asset_id) return;
    setDownloading(true);
    try {
      const asset = await api.getAsset(done.asset_id);
      const a = document.createElement("a");
      a.href = asset.signed_url;
      a.download = `${project.title || "video"}-${language}-${quality}.mp4`;
      a.click();
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()} width={520}>
      <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
        <div>
          <h3 style={{ margin: 0, fontWeight: 600 }}>Export video</h3>
          <Mono dim size={12}>Final render and download.</Mono>
        </div>

        <div>
          <Label>Language</Label>
          <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
            {(project.available_languages || []).map((code) => (
              <Chip key={code} selected={language === code} onClick={() => setLanguage(code)}>{code}</Chip>
            ))}
          </div>
        </div>

        <div>
          <Label>Quality</Label>
          <RadioGroup
            value={quality}
            onChange={(v) => setQuality(v)}
            options={[
              { value: "1080p", label: "1080p", hint: "Recommended for download/share." },
              { value: "720p",  label: "720p",  hint: "Smaller file, faster encode." },
            ]}
            style={{ marginTop: 6 }}
          />
        </div>

        <div>
          <Label>Subtitles</Label>
          <RadioGroup
            value={subs}
            onChange={(v) => setSubs(v)}
            options={[
              { value: "burned",  label: "Burned-in",  hint: "Always visible — no player support needed." },
              { value: "sidecar", label: "Sidecar SRT", hint: "Toggleable in compatible players." },
            ]}
            style={{ marginTop: 6 }}
          />
        </div>

        {stage && !done && (
          <div style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: 10, background: "var(--muted)", borderRadius: 6,
            fontSize: 13, color: "var(--muted-foreground)",
          }}>
            <Spinner size={14} /> Encoding · {stage}
          </div>
        )}
        {done && (
          <div style={{
            padding: 10, background: "var(--accent)", borderRadius: 6,
            fontSize: 13, color: "var(--foreground)",
          }}>
            ✓ Render complete.
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Button variant="ghost" onClick={onClose}>Close</Button>
          {done?.asset_id ? (
            <Button onClick={downloadResult} disabled={downloading}>
              <Download size={14} /> {downloading ? "Preparing…" : "Download"}
            </Button>
          ) : (
            <Button onClick={startExport} disabled={!!jobId && !done}>
              {jobId ? <Spinner size={14} /> : <Download size={14} />} Render
            </Button>
          )}
        </div>
      </div>
    </Dialog>
  );
}
