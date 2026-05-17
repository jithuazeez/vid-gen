// Typed fetch client. SSE helpers live in `lib/sse.ts`.

import { apiBase, postSse, subscribeJobEvents, eventsUrl, type SSEEvent } from "./sse";

export { eventsUrl, subscribeJobEvents };
export type { SSEEvent };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${apiBase()}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`${r.status} ${r.statusText}: ${text || path}`);
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

// ──────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────
export type ProjectStatus =
  | "draft" | "collecting" | "planning" | "rendering"
  | "ready" | "completed" | "failed" | "cancelled";

export interface Scene {
  id: string;
  scene_index: number;
  duration_seconds: number | string;
  visual_prompt: string;
  narration_script: string;
  has_speaker: boolean;
  subtitle_position: string;
  thumbnail_asset_id: string | null;
  scene_video_asset_id: string | null;
}

export interface Overlay {
  id: string;
  overlay_type: string;
  text: string | null;
  start_seconds: number;
  end_seconds: number;
  position: Record<string, any>;
  animation: string;
  style: Record<string, any>;
}

export interface SubtitleCue {
  start: number;
  end: number;
  text: string;
  position?: string | { x: number; y: number };
}

export interface Subtitle {
  id: string;
  scene_id: string;
  language: string;
  cues: SubtitleCue[];
  generated_position: string | null;
  source?: "estimated" | "whisper";
}

export type AssetStatus = "queued" | "generating" | "ready" | "failed";

export type AssetType =
  | "scene_video"
  | "voice"
  | "lipsync_video"
  | "subtitle_srt"
  | "composite";

export interface AssetState {
  id: string;
  scene_id: string | null;
  asset_type: AssetType;
  language: string | null;
  status: AssetStatus;
  progress: number;
}

export interface Project {
  id: string;
  title: string | null;
  status: ProjectStatus;
  brief: Record<string, any>;
  primary_language: string | null;
  active_language: string | null;
  available_languages: string[];
  aspect_ratio: string | null;
  duration_seconds: number | null;
  has_characters: boolean;
  music_enabled: boolean;
  scenes: Scene[];
  overlays: Overlay[];
  subtitles?: Subtitle[];
  assets?: AssetState[];
  latest_job: Job | null;
}

export interface Job {
  id: string;
  project_id: string;
  job_type: string;
  language: string | null;
  status: string;
  current_stage: string | null;
  progress: Record<string, any>;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export type ReferenceKind = "character" | "style" | "environment";

export interface Reference {
  id: string;
  asset_type: string;
  kind: ReferenceKind;
  character_name: string | null;
  storage_key: string;
  mime_type: string | null;
  bytes: number | null;
  descriptors: Record<string, any> | null;
  signed_url: string;
  expires_at: string;
}

export interface SignedAsset {
  id: string;
  asset_type: string;
  language: string | null;
  storage_key: string;
  mime_type: string | null;
  bytes: number | null;
  signed_url: string;
  expires_at: string;
}

// ──────────────────────────────────────────────────────────────
// API surface
// ──────────────────────────────────────────────────────────────
export const api = {
  createProject: (body: { title?: string } = {}) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),

  getProject: (id: string) => request<Project>(`/projects/${id}`),

  patchProject: (id: string, body: Partial<Project>) =>
    request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),

  getStoryboard: (id: string) =>
    request<{ scenes: Scene[] }>(`/projects/${id}/storyboard`),

  generateStoryboard: (id: string) =>
    request<{ job_id: string }>(`/projects/${id}/storyboard/generate`, { method: "POST" }),

  patchScene: (sceneId: string, body: Partial<Scene>) =>
    request<Scene>(`/scenes/${sceneId}`, { method: "PATCH", body: JSON.stringify(body) }),

  regenerateScene: (sceneId: string) =>
    request<{ job_id: string }>(`/scenes/${sceneId}/regenerate`, { method: "POST" }),

  moveScene: (sceneId: string, newIndex: number) =>
    request<{ ok: boolean; new_index: number }>(`/scenes/${sceneId}/move`, {
      method: "POST",
      body: JSON.stringify({ new_index: newIndex }),
    }),

  generate: (id: string) =>
    request<{ job_id: string }>(`/projects/${id}/generate`, { method: "POST" }),

  regenerateLanguage: (id: string, language: string) =>
    request<{ job_id?: string; status?: string; active_language?: string }>(
      `/projects/${id}/regenerate-language`,
      { method: "POST", body: JSON.stringify({ language }) },
    ),

  exportProject: (
    id: string,
    body: { language: string; quality?: string; subtitles?: string },
  ) =>
    request<{ job_id: string }>(`/projects/${id}/export`, {
      method: "POST", body: JSON.stringify(body),
    }),

  getJob: (jobId: string) => request<Job>(`/jobs/${jobId}`),

  getAsset: (assetId: string) => request<SignedAsset>(`/assets/${assetId}`),

  // References (user-uploaded character / style / environment images)
  listReferences: (projectId: string) =>
    request<Reference[]>(`/projects/${projectId}/references`),

  uploadReference: async (
    projectId: string,
    file: File,
    kind: ReferenceKind,
    characterName?: string,
  ): Promise<Reference> => {
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    if (characterName) form.append("character_name", characterName);
    const r = await fetch(`${apiBase()}/projects/${projectId}/references`, {
      method: "POST",
      body: form,
    });
    if (!r.ok) {
      const text = await r.text().catch(() => "");
      throw new Error(`${r.status} ${r.statusText}: ${text}`);
    }
    return r.json() as Promise<Reference>;
  },

  deleteReference: (assetId: string) =>
    request<void>(`/references/${assetId}`, { method: "DELETE" }),

  // Overlays
  createOverlay: (body: Omit<Overlay, "id"> & { project_id: string }) =>
    request<Overlay>("/overlays", { method: "POST", body: JSON.stringify(body) }),
  patchOverlay: (id: string, body: Partial<Overlay>) =>
    request<Overlay>(`/overlays/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteOverlay: (id: string) =>
    request<void>(`/overlays/${id}`, { method: "DELETE" }),

  // Subtitles
  getSubtitle: (sceneId: string, language: string) =>
    request<Subtitle>(`/subtitles/scene/${sceneId}/${language}`),
  patchSubtitle: (id: string, body: Partial<Subtitle>) =>
    request<Subtitle>(`/subtitles/${id}`, {
      method: "PATCH", body: JSON.stringify(body),
    }),

  // Audio
  patchAudio: (projectId: string, music_volume_db: number) =>
    request<{ ok: boolean; music_volume_db: number }>(
      `/projects/${projectId}/audio`,
      { method: "PATCH", body: JSON.stringify({ music_volume_db }) },
    ),

  ping: (id: string) =>
    request<{ job_id: string }>(`/projects/${id}/ping`, { method: "POST" }),
};

// Backwards-compat: chat is just a POST SSE call.
export async function* postChat(projectId: string, message: string) {
  yield* postSse(`/projects/${projectId}/chat`, { message });
}
