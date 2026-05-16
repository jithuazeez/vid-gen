"use client";
import * as React from "react";

// ────────────────────────────────────────────────────────────────────
// Button
// ────────────────────────────────────────────────────────────────────
type Variant = "default" | "secondary" | "outline" | "ghost" | "destructive" | "link";
type Size = "sm" | "md" | "lg" | "icon" | "icon-sm";

const sizeStyles: Record<Size, React.CSSProperties> = {
  sm: { height: 32, padding: "0 12px", fontSize: 13 },
  md: { height: 36, padding: "0 14px", fontSize: 14 },
  lg: { height: 42, padding: "0 18px", fontSize: 15 },
  icon: { height: 32, width: 32, padding: 0 },
  "icon-sm": { height: 28, width: 28, padding: 0 },
};

const variantStyles: Record<Variant, React.CSSProperties> = {
  default: { background: "var(--primary)", color: "var(--primary-foreground)", borderColor: "var(--primary)" },
  secondary: { background: "var(--secondary)", color: "var(--secondary-foreground)", borderColor: "var(--border)" },
  outline: { background: "transparent", color: "var(--foreground)", borderColor: "var(--border)" },
  ghost: { background: "transparent", color: "var(--foreground)", borderColor: "transparent" },
  destructive: { background: "var(--destructive)", color: "var(--destructive-foreground)", borderColor: "var(--destructive)" },
  link: { background: "transparent", color: "var(--foreground)", borderColor: "transparent", textDecoration: "underline", textUnderlineOffset: 4 },
};

export function Button({
  children, variant = "default", size = "md", disabled = false,
  onClick, style = {}, type = "button", title, ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  const [hover, setHover] = React.useState(false);
  const [pressed, setPressed] = React.useState(false);

  let hoverStyle: React.CSSProperties = {};
  if (hover && !disabled) {
    if (variant === "default") hoverStyle = { background: "hsl(0 0% 18%)" };
    else if (["secondary", "outline", "ghost"].includes(variant)) hoverStyle = { background: "var(--accent)" };
    else if (variant === "destructive") hoverStyle = { background: "hsl(0 72% 45%)" };
  }

  return (
    <button
      type={type}
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setHover(false); setPressed(false); }}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
      title={title}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6,
        fontFamily: "var(--font-sans)", fontWeight: 500, lineHeight: 1,
        whiteSpace: "nowrap", cursor: disabled ? "not-allowed" : "pointer", userSelect: "none",
        border: "1px solid transparent", borderRadius: "var(--radius)",
        transition: "background-color 120ms, border-color 120ms, color 120ms, opacity 120ms, box-shadow 120ms",
        outline: "none",
        ...sizeStyles[size],
        ...variantStyles[variant],
        ...hoverStyle,
        opacity: disabled ? 0.5 : 1,
        transform: pressed && !disabled ? "translateY(0.5px)" : "none",
        ...style,
      }}
      {...rest}
    >
      {children}
    </button>
  );
}

// ────────────────────────────────────────────────────────────────────
// Card
// ────────────────────────────────────────────────────────────────────
export function Card({
  children, style = {}, hoverable = false, onClick, selected = false,
}: React.PropsWithChildren<{ style?: React.CSSProperties; hoverable?: boolean; onClick?: () => void; selected?: boolean }>) {
  const [hover, setHover] = React.useState(false);
  const interactive = !!onClick || hoverable;
  return (
    <div
      onClick={onClick}
      onMouseEnter={interactive ? () => setHover(true) : undefined}
      onMouseLeave={interactive ? () => setHover(false) : undefined}
      style={{
        background: "var(--card)", color: "var(--card-foreground)",
        border: `1px solid ${selected ? "var(--foreground)" : "var(--border)"}`,
        borderRadius: "var(--radius)",
        boxShadow: hover && interactive ? "var(--shadow-md)" : "var(--shadow-sm)",
        transition: "box-shadow 160ms, border-color 120ms, transform 160ms",
        transform: hover && interactive ? "translateY(-1px)" : "none",
        cursor: interactive ? "pointer" : "default",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Input / Textarea
// ────────────────────────────────────────────────────────────────────
const fieldBase: React.CSSProperties = {
  width: "100%", display: "block",
  background: "var(--background)", color: "var(--foreground)",
  border: "1px solid var(--input)", borderRadius: "var(--radius)",
  padding: "8px 12px", fontSize: 14, lineHeight: 1.5,
  outline: "none",
  transition: "border-color 120ms, box-shadow 120ms, background 120ms",
};

export function Input({ style = {}, ...rest }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      style={{ ...fieldBase, height: 36, ...style }}
      onFocus={(e) => { e.currentTarget.style.borderColor = "var(--ring)"; e.currentTarget.style.boxShadow = "0 0 0 3px hsl(0 0% 50% / 0.12)"; }}
      onBlur={(e) => { e.currentTarget.style.borderColor = "var(--input)"; e.currentTarget.style.boxShadow = "none"; }}
      {...rest}
    />
  );
}

export function Textarea({ style = {}, ...rest }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      style={{ ...fieldBase, minHeight: 80, resize: "vertical", ...style }}
      onFocus={(e) => { e.currentTarget.style.borderColor = "var(--ring)"; e.currentTarget.style.boxShadow = "0 0 0 3px hsl(0 0% 50% / 0.12)"; }}
      onBlur={(e) => { e.currentTarget.style.borderColor = "var(--input)"; e.currentTarget.style.boxShadow = "none"; }}
      {...rest}
    />
  );
}

// ────────────────────────────────────────────────────────────────────
// Badge
// ────────────────────────────────────────────────────────────────────
type BadgeVariant = "default" | "secondary" | "outline" | "success" | "warning" | "info";
const badgeMap: Record<BadgeVariant, { bg: string; fg: string; bd: string }> = {
  default: { bg: "var(--primary)", fg: "var(--primary-foreground)", bd: "var(--primary)" },
  secondary: { bg: "var(--secondary)", fg: "var(--secondary-foreground)", bd: "var(--border)" },
  outline: { bg: "transparent", fg: "var(--foreground)", bd: "var(--border)" },
  success: { bg: "hsl(142 71% 96%)", fg: "hsl(142 71% 24%)", bd: "hsl(142 71% 86%)" },
  warning: { bg: "hsl(38 92% 96%)", fg: "hsl(38 92% 30%)", bd: "hsl(38 92% 86%)" },
  info: { bg: "hsl(217 91% 96%)", fg: "hsl(217 91% 35%)", bd: "hsl(217 91% 86%)" },
};

export function Badge({ children, variant = "secondary", style = {} }: React.PropsWithChildren<{ variant?: BadgeVariant; style?: React.CSSProperties }>) {
  const v = badgeMap[variant];
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 8px", borderRadius: 6,
      fontSize: 11, fontWeight: 500, lineHeight: 1.4,
      background: v.bg, color: v.fg, border: `1px solid ${v.bd}`,
      whiteSpace: "nowrap",
      ...style,
    }}>{children}</span>
  );
}

// ────────────────────────────────────────────────────────────────────
// Chip
// ────────────────────────────────────────────────────────────────────
export function Chip({
  children, onClick, selected = false, disabled = false, icon, style = {}, title,
}: React.PropsWithChildren<{ onClick?: () => void; selected?: boolean; disabled?: boolean; icon?: React.ReactNode; style?: React.CSSProperties; title?: string }>) {
  const [hover, setHover] = React.useState(false);
  return (
    <button
      type="button"
      title={title}
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "6px 12px", height: 30,
        borderRadius: 999, border: "1px solid var(--border)",
        background: selected ? "var(--primary)" : (hover ? "var(--accent)" : "var(--background)"),
        color: selected ? "var(--primary-foreground)" : "var(--foreground)",
        fontSize: 13, fontWeight: 500, lineHeight: 1,
        whiteSpace: "nowrap",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "background-color 120ms, border-color 120ms, color 120ms",
        outline: "none",
        ...style,
      }}
    >
      {icon}
      {children}
    </button>
  );
}

// ────────────────────────────────────────────────────────────────────
// Tabs
// ────────────────────────────────────────────────────────────────────
export function Tabs<T extends string>({
  value, onChange, items, style = {}, fullWidth = false,
}: { value: T; onChange: (v: T) => void; items: { value: T; label: string; icon?: React.ReactNode }[]; style?: React.CSSProperties; fullWidth?: boolean }) {
  return (
    <div style={{
      display: fullWidth ? "flex" : "inline-flex",
      width: fullWidth ? "100%" : "auto",
      padding: 3, gap: 2,
      background: "var(--muted)", borderRadius: "var(--radius)",
      ...style,
    }}>
      {items.map((it) => {
        const active = it.value === value;
        return (
          <button
            key={it.value}
            type="button"
            onClick={() => onChange(it.value)}
            style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 5,
              padding: "6px 8px", height: 28,
              flex: fullWidth ? "1 1 0" : "initial",
              minWidth: 0,
              border: "1px solid transparent", borderRadius: 6,
              background: active ? "var(--background)" : "transparent",
              color: active ? "var(--foreground)" : "var(--muted-foreground)",
              boxShadow: active ? "var(--shadow-sm)" : "none",
              fontWeight: 500, fontSize: 13, lineHeight: 1,
              cursor: "pointer", outline: "none",
              whiteSpace: "nowrap",
              transition: "background-color 120ms, color 120ms",
            }}
          >
            {it.icon}{it.label}
          </button>
        );
      })}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Dialog
// ────────────────────────────────────────────────────────────────────
export function Dialog({ open, onOpenChange, children, width = 460 }: { open: boolean; onOpenChange: (v: boolean) => void; children: React.ReactNode; width?: number }) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onOpenChange(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);
  if (!open) return null;
  return (
    <div
      onClick={() => onOpenChange(false)}
      style={{
        position: "fixed", inset: 0, zIndex: 50,
        background: "rgba(10,10,10,0.5)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 20,
        animation: "fadeIn 160ms ease-out both",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="anim-scale"
        style={{
          width, maxWidth: "100%",
          background: "var(--card)", color: "var(--card-foreground)",
          border: "1px solid var(--border)", borderRadius: 12,
          boxShadow: "var(--shadow-xl)",
          overflow: "hidden",
        }}
      >{children}</div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// RadioGroup
// ────────────────────────────────────────────────────────────────────
export function RadioGroup<T extends string>({
  value, onChange, options, style = {},
}: { value: T; onChange: (v: T) => void; options: { value: T; label: string; hint?: string }[]; style?: React.CSSProperties }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, ...style }}>
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            style={{
              display: "flex", alignItems: "flex-start", gap: 10,
              padding: 12,
              background: active ? "var(--accent)" : "transparent",
              border: `1px solid ${active ? "var(--foreground)" : "var(--border)"}`,
              borderRadius: "var(--radius)",
              textAlign: "left", cursor: "pointer",
              transition: "background-color 120ms, border-color 120ms",
              outline: "none",
            }}
          >
            <div style={{
              width: 14, height: 14, borderRadius: "50%",
              border: `1.5px solid ${active ? "var(--foreground)" : "var(--muted-foreground)"}`,
              flexShrink: 0, marginTop: 3,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              {active && <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--foreground)" }} />}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: "var(--foreground)" }}>{opt.label}</span>
              {opt.hint && <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>{opt.hint}</span>}
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Progress + Avatar + Mono + Label + Separator
// ────────────────────────────────────────────────────────────────────
export function Progress({ value = 0, style = {} }: { value?: number; style?: React.CSSProperties }) {
  return (
    <div style={{ height: 6, background: "var(--muted)", borderRadius: 999, overflow: "hidden", width: "100%", ...style }}>
      <div style={{
        height: "100%",
        width: `${Math.max(0, Math.min(100, value))}%`,
        background: "var(--foreground)",
        borderRadius: 999,
        transition: "width 400ms ease",
      }} />
    </div>
  );
}

export function Mono({ children, size = 12, dim = false, style = {} }: React.PropsWithChildren<{ size?: number; dim?: boolean; style?: React.CSSProperties }>) {
  return <span style={{ fontFamily: "var(--font-mono)", fontSize: size, color: dim ? "var(--muted-foreground)" : "inherit", ...style }}>{children}</span>;
}

export function Label({ children, style = {} }: React.PropsWithChildren<{ style?: React.CSSProperties }>) {
  return <span style={{ fontSize: 12, fontWeight: 500, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: 0.3, ...style }}>{children}</span>;
}

export function Separator({ vertical = false, style = {} }: { vertical?: boolean; style?: React.CSSProperties }) {
  return (
    <div style={{
      ...(vertical
        ? { width: 1, alignSelf: "stretch", borderLeft: "1px solid var(--border)" }
        : { height: 1, borderTop: "1px solid var(--border)", width: "100%" }),
      ...style,
    }} />
  );
}
