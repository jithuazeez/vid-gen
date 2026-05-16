"use client";
/**
 * Chat — reusable conversational surface for both:
 *
 *   • collect mode — Screen 1; the orchestrator slot-fills the brief.
 *   • edit mode    — Screens 2 & 4; the edit-router applies scene/overlay/
 *                    language intents.
 *
 * Both modes hit the same backend endpoint (POST /projects/:id/chat) and
 * pick a graph based on project.status. This component just renders the
 * stream — the bubbles, chips, typing indicator, and composer.
 *
 * Architecture.md §13.
 */
import * as React from "react";
import { Button, Chip, Mono } from "@/components/UI";
import { ArrowUp, Mic } from "@/components/Icons";
import { api, postChat, type ReferenceKind, type SSEEvent } from "@/lib/api";

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  chips?: string[];
  ready?: boolean;
  intent?: string;
  applied?: boolean;
  /** Set on assistant bubbles that prompted a reference upload. The UI
   *  swaps the composer chips for a file-picker affordance. */
  expectsUpload?: ReferenceKind | null;
}

export interface ChatProps {
  projectId: string;
  /** Called whenever the orchestrator emits a slot_update (collect mode). */
  onSlotUpdate?: (slots: Record<string, unknown>) => void;
  /** Called when the orchestrator declares ready (collect mode). */
  onReady?: () => void;
  /** Called for any intent event (edit mode). */
  onIntent?: (data: any) => void;
  /** Called for any token chunk (collect mode streaming). */
  onToken?: (text: string) => void;
  /** Greeting bubble seeded before the user types. */
  greeting?: string;
  /** Disable the composer (e.g. while a render is in flight). */
  disabled?: boolean;
  composerPlaceholder?: string;
  className?: string;
  /** Drawer mode renders a tighter layout with no padding around bubbles. */
  variant?: "page" | "drawer";
  initialMessages?: ChatMessage[];
}

export function Chat({
  projectId,
  onSlotUpdate,
  onReady,
  onIntent,
  onToken,
  greeting,
  disabled,
  composerPlaceholder,
  className,
  variant = "page",
  initialMessages,
}: ChatProps) {
  const [messages, setMessages] = React.useState<ChatMessage[]>(
    initialMessages ?? (greeting ? [{ role: "assistant", text: greeting }] : [])
  );
  const [draft, setDraft] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending]);

  async function send(value: string, silent = false) {
    const text = value.trim();
    if (!silent && !text) return;
    if (!silent) {
      setMessages((m) => [...m, { role: "user", text }]);
      setDraft("");
    }
    setSending(true);
    try {
      let aiText = "";
      let chips: string[] = [];
      let ready = false;
      let intent: string | undefined;
      let applied = false;
      let expectsUpload: ReferenceKind | null = null;

      for await (const ev of postChat(projectId, text) as AsyncIterable<SSEEvent>) {
        switch (ev.event) {
          case "token":
            onToken?.(ev.data?.text || "");
            // Append the token to the in-progress assistant bubble.
            aiText += ev.data?.text || "";
            break;
          case "slot_update":
            onSlotUpdate?.(ev.data?.slots || {});
            break;
          case "question":
            aiText = ev.data?.prompt || aiText;
            chips = ev.data?.chips || [];
            if (ev.data?.expects === "upload" && ev.data?.upload_kind) {
              expectsUpload = ev.data.upload_kind as ReferenceKind;
            }
            break;
          case "ready":
            ready = true;
            onReady?.();
            break;
          case "intent":
            intent = ev.data?.intent;
            applied = !!ev.data?.applied;
            if (ev.data?.preview) aiText = ev.data.preview;
            onIntent?.(ev.data);
            break;
          case "error":
            aiText = aiText || (typeof ev.data?.message === "string"
              ? ev.data.message : "Something went wrong.");
            break;
        }
      }
      setMessages((m) => [...m, {
        role: "assistant", text: aiText, chips, ready, intent, applied,
        expectsUpload,
      }]);
    } catch (e) {
      console.error(e);
    } finally {
      setSending(false);
    }
  }

  async function handleFilesPicked(files: FileList | null, kind: ReferenceKind) {
    if (!files || files.length === 0) return;
    const uploaded: string[] = [];
    const failed: string[] = [];

    for (const file of Array.from(files)) {
      let characterName: string | undefined;
      if (kind === "character") {
        // Use a tiny prompt for now; the SDXL refs key on this name.
        const guess = file.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ");
        const name = window.prompt(
          `Who is this? (first name; will be reused across scenes)`,
          guess,
        );
        if (name == null) continue;  // user cancelled
        characterName = name.trim() || undefined;
      }
      try {
        const ref = await api.uploadReference(projectId, file, kind, characterName);
        uploaded.push(
          kind === "character" && ref.character_name
            ? `${ref.character_name}`
            : file.name,
        );
      } catch (err) {
        console.error("reference upload failed", err);
        failed.push(file.name);
      }
    }

    // Surface a synthetic user bubble + advance the conversation. The
    // backend orchestrator sees this turn, marks the prompted flag, and
    // moves on to the next question.
    const parts: string[] = [];
    if (uploaded.length) {
      parts.push(
        kind === "character"
          ? `Uploaded character reference${uploaded.length > 1 ? "s" : ""}: ${uploaded.join(", ")}`
          : `Uploaded ${uploaded.length} ${kind} reference${uploaded.length > 1 ? "s" : ""}`,
      );
    }
    if (failed.length) {
      parts.push(`Failed: ${failed.join(", ")}`);
    }
    const summary = parts.join(" · ") || "Skipped uploads.";
    setMessages((m) => [...m, { role: "user", text: summary }]);
    await send(summary, true);
  }

  const onKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(draft); }
  };

  const padding = variant === "drawer" ? "16px" : "32px 40px 24px";
  const composerPadding = variant === "drawer" ? "10px 14px" : "14px 40px 18px";

  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const pendingKindRef = React.useRef<ReferenceKind | null>(null);

  function openPicker(kind: ReferenceKind) {
    pendingKindRef.current = kind;
    fileInputRef.current?.click();
  }

  // Last assistant bubble decides whether the next reply expects an upload.
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const awaitingUpload: ReferenceKind | null = lastAssistant?.expectsUpload ?? null;

  function handleChip(label: string) {
    if (awaitingUpload && /^upload\b/i.test(label)) {
      openPicker(awaitingUpload);
      return;
    }
    void send(label);
  }

  return (
    <div className={className} style={{
      display: "flex", flexDirection: "column", minHeight: 0, height: "100%",
    }}>
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding }}>
        <div style={{ maxWidth: 680, margin: "0 auto", display: "flex", flexDirection: "column", gap: 18 }}>
          {messages.map((m, i) => (
            <Bubble
              key={i}
              msg={m}
              onChip={handleChip}
              disabledChips={i !== messages.length - 1 || m.role !== "assistant" || sending || !!disabled}
            />
          ))}
          {sending && <Typing />}
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        hidden
        onChange={(e) => {
          const kind = pendingKindRef.current ?? "character";
          pendingKindRef.current = null;
          void handleFilesPicked(e.target.files, kind);
          // Reset so the same file can be picked again later.
          e.target.value = "";
        }}
      />

      <div style={{ borderTop: "1px solid var(--border)", padding: composerPadding }}>
        <div style={{ maxWidth: 680, margin: "0 auto" }}>
          <div style={{
            display: "flex", alignItems: "flex-end", gap: 8,
            border: "1px solid var(--input)", borderRadius: 12,
            padding: 8, background: "var(--background)",
          }}>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={composerPlaceholder ?? "Type your reply, or tap a suggestion above…"}
              disabled={disabled || sending}
              rows={1}
              style={{
                flex: 1, resize: "none", border: "none", outline: "none",
                background: "transparent",
                fontSize: 15, lineHeight: 1.5, padding: "6px 8px",
                fontFamily: "var(--font-sans)", color: "var(--foreground)",
                minHeight: 28, maxHeight: 160,
              }}
            />
            <Button variant="ghost" size="icon-sm" title="Voice"><Mic size={15} /></Button>
            <Button size="icon-sm" onClick={() => send(draft)}
                    disabled={!draft.trim() || sending || disabled}>
              <ArrowUp size={14} />
            </Button>
          </div>
          {variant === "page" && (
            <Mono dim size={11} style={{ marginTop: 8, display: "block" }}>
              ↵ to send · ⇧↵ for newline
            </Mono>
          )}
        </div>
      </div>
    </div>
  );
}


function Bubble({ msg, onChip, disabledChips }: {
  msg: ChatMessage; onChip: (v: string) => void; disabledChips: boolean;
}) {
  const isUser = msg.role === "user";
  return (
    <div className="anim-fade" style={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start" }}>
      <div style={{
        maxWidth: 520,
        background: isUser ? "var(--primary)" : "var(--card)",
        color: isUser ? "var(--primary-foreground)" : "var(--foreground)",
        border: isUser ? "1px solid var(--primary)" : "1px solid var(--border)",
        padding: "12px 14px",
        borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
        boxShadow: "var(--shadow-sm)",
      }}>
        <div style={{ fontSize: 15, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{msg.text}</div>
        {msg.intent && msg.applied && (
          <Mono dim size={11} style={{ marginTop: 8, display: "block" }}>
            ✓ Applied · {msg.intent}
          </Mono>
        )}
        {!!msg.chips?.length && (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
            {msg.chips.map((c, i) => (
              <Chip key={i} onClick={() => onChip(c)} disabled={disabledChips}>
                {c}
              </Chip>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


function Typing() {
  return (
    <div style={{ display: "flex", justifyContent: "flex-start" }}>
      <div style={{
        background: "var(--card)", border: "1px solid var(--border)",
        padding: "10px 14px", borderRadius: "16px 16px 16px 4px",
        display: "inline-flex", gap: 4,
      }}>
        {[0, 1, 2].map((i) => (
          <span key={i} style={{
            width: 6, height: 6, borderRadius: "50%",
            background: "var(--muted-foreground)",
            animation: `bounceDot 1s ease-in-out ${i * 0.15}s infinite both`,
          }} />
        ))}
      </div>
    </div>
  );
}
