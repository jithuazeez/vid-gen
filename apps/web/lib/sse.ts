// SSE helpers for the frontend.
// Two flavours:
//   1. EventSource for GET endpoints (`/jobs/:id/events`).
//   2. fetch + ReadableStream for POST SSE endpoints (`/projects/:id/chat`).

const isBrowser = typeof window !== "undefined";

export function apiBase(): string {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) return process.env.NEXT_PUBLIC_API_BASE_URL;
  return isBrowser ? "/api-proxy" : "http://localhost:8000";
}

export interface SSEEvent {
  event: string;
  data: any;
}

// Frontend-known SSE event names. Add to this list when the backend
// publishes a new event type so EventSource picks it up.
export const KNOWN_EVENTS = [
  "snapshot",
  "stage_change",
  "scene_ready",
  "asset_progress",
  "progress",
  "intent",
  "slot_update",
  "question",
  "ready",
  "thinking",
  "token",
  "done",
  "error",
] as const;

export function eventsUrl(jobId: string): string {
  return `${apiBase()}/jobs/${jobId}/events`;
}

/**
 * Subscribe to a job's SSE event stream. Returns a teardown function.
 */
export function subscribeJobEvents(
  jobId: string,
  onEvent: (e: SSEEvent) => void,
): () => void {
  const es = new EventSource(eventsUrl(jobId));
  for (const name of KNOWN_EVENTS) {
    es.addEventListener(name, (raw: any) => {
      let data: any = raw.data;
      try { data = JSON.parse(raw.data); } catch { /* leave raw */ }
      onEvent({ event: name, data });
    });
  }
  es.addEventListener("error", () => {
    // EventSource auto-reconnects; surface a soft event so the UI can
    // show a "reconnecting" indicator if it cares.
    onEvent({ event: "error", data: { reconnecting: true } });
  });
  return () => es.close();
}

/**
 * POST a JSON body and consume an SSE stream from the response. Used by
 * `/projects/:id/chat`, which can't use EventSource (POST + body).
 */
export async function* postSse(
  path: string,
  body: any,
): AsyncIterable<SSEEvent> {
  const r = await fetch(`${apiBase()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
    },
    body: JSON.stringify(body),
  });
  if (!r.body) return;
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    // Normalize \r\n → \n so the parser works regardless of whether
    // sse_starlette sends \r\n\r\n or \n\n as the event boundary.
    buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const lines = frame.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      try {
        yield { event, data: data ? JSON.parse(data) : null };
      } catch {
        yield { event, data };
      }
    }
  }
}
