"use client";
import * as React from "react";
// import { Chip, Mono, Spinner } from "../UI";
import { Button, Chip, Dialog, Label, Mono, RadioGroup } from "../UI";
import { Download, Spinner } from "../Icons";

const LANGS: { code: string; label: string }[] = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "mr", label: "मराठी" },
  { code: "ta", label: "தமிழ்" },
  { code: "pa", label: "ਪੰਜਾਬੀ" },
];

interface Props {
  active: string | null;
  available: string[];
  busy?: string | null;             // language currently being rendered
  onChange: (code: string) => void;
}

export function LanguageSwitch({ active, available, busy, onChange }: Props) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <Mono size={11} dim>Language</Mono>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {LANGS.map((l) => {
          const isActive = active === l.code;
          const isCached = available.includes(l.code);
          const isBusy = busy === l.code;
          return (
            <Chip
              key={l.code}
              selected={isActive}
              onClick={() => onChange(l.code)}
              disabled={isBusy}
              icon={isBusy ? <Spinner size={10} /> : undefined}
              style={{
                opacity: isCached ? 1 : 0.7,
                borderStyle: isCached ? "solid" : "dashed",
              }}
              title={isCached
                ? "Cached — instant switch"
                : "Will render — voice + lip-sync + subtitles + composite"}
            >
              {l.label}
            </Chip>
          );
        })}
      </div>
    </div>
  );
}
