"use client";
import * as React from "react";
import { Mono, Progress } from "../UI";
import { Spinner } from "../Icons";
import { api, Scene, SubtitleCue } from "@/lib/api";
import { SceneAssets } from "./EditorScreen";

interface Props {
  scene: Scene | null;
  sceneState: SceneAssets | null;
  activeSub: SubtitleCue | null;
  aspect: string;
  overallPct: number;
  doneAssets: number;
  totalAssets: number;
  playing: boolean;
  currentTime: number;
  sceneOffset: number;
}

export function PreviewPlayer({
  scene, sceneState, activeSub, aspect, overallPct, doneAssets, totalAssets,
  playing, currentTime, sceneOffset,
}: Props) {
  const ratio =
    aspect.startsWith("9:16") ? 9 / 16 :
    aspect.startsWith("16:9") ? 16 / 9 :
    aspect.startsWith("1:1")  ? 1 :
    aspect.startsWith("4:5")  ? 4 / 5 : 9 / 16;

  const compositeReady = sceneState?.composite?.status === "ready";
  const sceneVideoReady = sceneState?.scene_video?.status === "ready";

  // Prefer composite (has audio + subtitles burned in), fall back to scene_video
  const primaryAsset = compositeReady
    ? sceneState?.composite
    : sceneVideoReady
    ? sceneState?.scene_video
    : null;

  // For the spinner, track whichever pipeline stage is currently active
  const spinnerAsset = sceneState?.composite?.status === "generating"
    ? sceneState?.composite
    : sceneState?.scene_video;

  const spinnerVisible = !compositeReady;

  // Fetch signed URL whenever the best available asset changes
  const [videoUrl, setVideoUrl] = React.useState<string | null>(null);
  const prevAssetId = React.useRef<string | null>(null);

  React.useEffect(() => {
    if (!primaryAsset || primaryAsset.id === prevAssetId.current) return;
    // Guard: don't try to fetch if the id looks like a key string (no real UUID)
    const looksLikeUuid = /^[0-9a-f-]{36}$/i.test(primaryAsset.id);
    if (!looksLikeUuid) return;
    prevAssetId.current = primaryAsset.id;
    setVideoUrl(null);
    api.getAsset(primaryAsset.id)
      .then((a) => setVideoUrl(a.signed_url))
      .catch(() => { /* signed URL will be null; spinner stays */ });
  }, [primaryAsset?.id]);

  // Clear URL when scene changes so the old video doesn't flash
  const prevSceneId = React.useRef<string | null>(null);
  React.useEffect(() => {
    if (scene?.id !== prevSceneId.current) {
      prevSceneId.current = scene?.id ?? null;
      setVideoUrl(null);
      prevAssetId.current = null;
    }
  }, [scene?.id]);

  const videoRef = React.useRef<HTMLVideoElement>(null);

  // Sync play / pause
  React.useEffect(() => {
    const el = videoRef.current;
    if (!el || !videoUrl) return;
    if (playing) {
      el.play().catch(() => {});
    } else {
      el.pause();
    }
  }, [playing, videoUrl]);

  // Seek when paused (timeline scrubbing) or when scene changes
  React.useEffect(() => {
    const el = videoRef.current;
    if (!el || !videoUrl || playing) return;
    const local = Math.max(0, currentTime - sceneOffset);
    if (Math.abs(el.currentTime - local) > 0.15) {
      el.currentTime = local;
    }
  }, [currentTime, sceneOffset, playing, videoUrl]);

  // Reset to scene start when the asset URL is freshly loaded
  React.useEffect(() => {
    const el = videoRef.current;
    if (!el || !videoUrl) return;
    el.currentTime = Math.max(0, currentTime - sceneOffset);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoUrl]);

  return (
    <div style={{
      aspectRatio: `${ratio}`,
      maxHeight: "100%", maxWidth: "100%",
      height: ratio < 1 ? "100%" : "auto",
      width:  ratio >= 1 ? "100%" : "auto",
      position: "relative", overflow: "hidden",
      borderRadius: 10, background: "#000",
      boxShadow: "var(--shadow-xl)",
    }}>
      {/* Background gradient — fades out once video loads */}
      <div style={{
        position: "absolute", inset: 0,
        opacity: videoUrl ? 0 : 0.25,
        transition: "opacity 300ms ease",
        background:
          "radial-gradient(circle at 30% 30%, hsl(220 30% 30%), hsl(220 30% 12%))",
        pointerEvents: "none",
      }} />

      {/* Video element */}
      {videoUrl && (
        <video
          ref={videoRef}
          src={videoUrl}
          style={{
            position: "absolute", inset: 0,
            width: "100%", height: "100%",
            objectFit: "cover",
          }}
          playsInline
          preload="auto"
        />
      )}

      {/* Spinner overlay while composite is still generating */}
      {spinnerVisible && (
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          gap: 12, color: "rgba(255,255,255,0.92)",
        }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "6px 12px", borderRadius: 999,
            background: "rgba(0,0,0,0.5)", backdropFilter: "blur(8px)",
            fontSize: 12, fontWeight: 500,
          }}>
            <Spinner size={12} />
            {spinnerAsset?.status === "generating"
              ? `Rendering scene ${scene ? sceneLabel(scene) : ""}…`
              : "Waiting in queue"}
          </div>
          <div style={{ width: "60%", maxWidth: 280 }}>
            <Progress value={spinnerAsset?.progress || 0} style={{ height: 3 }} />
          </div>
          <Mono size={11} style={{ color: "rgba(255,255,255,0.65)" }}>
            pipeline · {doneAssets}/{totalAssets} · {overallPct}%
          </Mono>
        </div>
      )}

      {/* Subtitle overlay (for scene_video-only fallback; composite has subs burned in) */}
      {!compositeReady && sceneVideoReady && activeSub && (
        <div style={{
          position: "absolute", left: 0, right: 0, bottom: 28,
          display: "flex", justifyContent: "center",
          pointerEvents: "none",
        }}>
          <div style={{
            background: "rgba(0,0,0,0.78)", color: "white",
            padding: "6px 14px", borderRadius: 6,
            fontSize: 15, fontWeight: 500, lineHeight: 1.3,
            maxWidth: "85%", textAlign: "center",
            backdropFilter: "blur(8px)",
          }}>{activeSub.text}</div>
        </div>
      )}
    </div>
  );
}

function sceneLabel(s: Scene): string {
  return String(s.scene_index).padStart(2, "0");
}
