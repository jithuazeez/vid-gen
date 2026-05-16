"use client";
import * as React from "react";
import { Aperture, ArrowLeft, Moon, Sun } from "./Icons";
import { Button } from "./UI";

export function ProjectShell({
  left, center, right, children, onBack,
}: React.PropsWithChildren<{
  left?: React.ReactNode; center?: React.ReactNode; right?: React.ReactNode; onBack?: () => void;
}>) {
  return (
    <div style={{
      minHeight: "100vh", display: "flex", flexDirection: "column",
      background: "var(--background)", color: "var(--foreground)",
    }}>
      <header style={{
        height: 56, flexShrink: 0,
        borderBottom: "1px solid var(--border)",
        display: "flex", alignItems: "center", padding: "0 20px", gap: 16,
        background: "var(--background)",
        position: "sticky", top: 0, zIndex: 10,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0, flex: 1 }}>
          {onBack && (
            <Button variant="ghost" size="icon-sm" onClick={onBack} title="Back">
              <ArrowLeft size={16} />
            </Button>
          )}
          {left}
        </div>
        {center && <div style={{ display: "flex", alignItems: "center", gap: 8 }}>{center}</div>}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto", flexShrink: 0 }}>
          {right}
        </div>
      </header>
      <main style={{ flex: 1, minHeight: 0 }}>{children}</main>
    </div>
  );
}

export function BrandMark() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{
        width: 22, height: 22, borderRadius: 6,
        background: "var(--primary)", color: "var(--primary-foreground)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <Aperture size={13} strokeWidth={2} />
      </div>
      <span style={{ fontWeight: 600, fontSize: 14, letterSpacing: -0.2 }}>video.studio</span>
    </div>
  );
}

export function ThemeToggle() {
  const [dark, setDark] = React.useState(false);
  React.useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
  };
  return (
    <Button variant="ghost" size="icon-sm" onClick={toggle} title={dark ? "Light mode" : "Dark mode"}>
      {dark ? <Sun size={15} /> : <Moon size={15} />}
    </Button>
  );
}
