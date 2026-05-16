// Screen 4: Review & Edit — player + multi-track timeline + tabbed right panel.

const TOTAL_DURATION = 30; // seconds

function ReviewScreen() {
  const { state, dispatch } = useApp();
  const { scenes, brief, currentTime, playing, rightTab, language } = state;
  const subs = SUBTITLES_BY_LANG[language] || SUBTITLES_BY_LANG.English;

  // Playback simulation
  React.useEffect(() => {
    if (!playing) return;
    let raf;
    let last = performance.now();
    const loop = (now) => {
      const dt = (now - last) / 1000;
      last = now;
      const next = currentTime + dt;
      if (next >= TOTAL_DURATION) {
        dispatch({ type: 'SET_TIME', t: 0 });
        dispatch({ type: 'TOGGLE_PLAY' });
        return;
      }
      dispatch({ type: 'SET_TIME', t: next });
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing, currentTime, dispatch]);

  // current scene index
  const currentSceneIdx = Math.min(
    scenes.length - 1,
    scenes.findIndex((s, i) => currentTime >= s.start && currentTime < s.start + s.duration)
  );
  const currentScene = scenes[currentSceneIdx >= 0 ? currentSceneIdx : 0];
  // active subtitle cue
  const activeSub = subs.find(c => currentTime >= c.start && currentTime < c.end);

  // language switch — pretend non-EN takes a moment
  const [switchingLang, setSwitchingLang] = React.useState(false);
  const setLang = (lang) => {
    if (lang === language) return;
    if (lang === 'English') {
      dispatch({ type: 'SET_LANG', lang });
    } else {
      setSwitchingLang(true);
      setTimeout(() => {
        dispatch({ type: 'SET_LANG', lang });
        setSwitchingLang(false);
      }, 700);
    }
  };

  return (
    <ProjectShell
      onBack={() => dispatch({ type: 'GOTO', screen: 'storyboard' })}
      left={<>
        <BrandMark />
        <Separator vertical style={{ height: 20 }} />
        <span style={{ fontSize: 14, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 }}>{brief.topic || state.projectTitle}</span>
        <div style={{ display: 'flex', gap: 6, marginLeft: 2, flexShrink: 0 }}>
          <Badge variant="secondary">{brief.duration || '30s'}</Badge>
          <Badge variant="secondary">{brief.aspect || '9:16'}</Badge>
          <Badge variant="success"><ICON.Check size={10} strokeWidth={3} /> ready</Badge>
        </div>
      </>}
      right={<>
        <LanguageDropdown value={language} onChange={setLang} switching={switchingLang} />
        <Button size="sm" onClick={() => dispatch({ type: 'OPEN_EXPORT' })}>
          <ICON.Download size={14} /> Export
        </Button>
        <ThemeToggle />
      </>}
    >
      <div data-screen-label="04-review" style={{
        display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 360px',
        height: 'calc(100vh - 56px)', minHeight: 0,
      }}>
        {/* Left: player + timeline */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, borderRight: '1px solid var(--border)' }}>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, minHeight: 0, minWidth: 0, background: 'var(--muted)', overflow: 'hidden' }}>
            <VideoPlayer
              scene={currentScene}
              activeSub={activeSub}
              brief={brief}
              switchingLang={switchingLang}
              language={language}
            />
          </div>
          <PlayerControls
            playing={playing}
            currentTime={currentTime}
            onTogglePlay={() => dispatch({ type: 'TOGGLE_PLAY' })}
            onSeek={(t) => dispatch({ type: 'SET_TIME', t })}
          />
          <TimelineCanvas
            scenes={scenes}
            subs={subs}
            currentTime={currentTime}
            onSeek={(t) => dispatch({ type: 'SET_TIME', t })}
          />
        </div>

        {/* Right: tabs */}
        <RightPanel
          tab={rightTab}
          onTabChange={(v) => dispatch({ type: 'SET_RIGHT_TAB', tab: v })}
          subs={subs}
          scenes={scenes}
          currentTime={currentTime}
        />
      </div>

      <ExportModal />
    </ProjectShell>
  );
}

function VideoPlayer({ scene, activeSub, brief, switchingLang, language }) {
  // Aspect ratio frame
  const aspect = brief.aspect || '9:16';
  const ratio = aspect.startsWith('9:16') ? 9/16
              : aspect.startsWith('16:9') ? 16/9
              : aspect.startsWith('1:1')  ? 1
              : aspect.startsWith('4:5')  ? 4/5
              : 9/16;

  return (
    <div style={{
      aspectRatio: `${ratio}`,
      maxHeight: '100%',
      maxWidth: '100%',
      height: ratio < 1 ? '100%' : 'auto',
      width: ratio >= 1 ? '100%' : 'auto',
      position: 'relative', overflow: 'hidden',
      borderRadius: 10,
      background: '#000',
      boxShadow: 'var(--shadow-xl)',
      transition: 'opacity 200ms ease, filter 200ms ease',
      opacity: switchingLang ? 0.6 : 1,
      filter: switchingLang ? 'blur(2px)' : 'none',
    }}>
      <div style={{ position: 'absolute', inset: 0 }}>
        <SceneThumb scene={scene} height="100%" />
      </div>
      {/* CTA overlay (visible scene 2+) */}
      {scene.start >= 6 && scene.start < 18 && (
        <div style={{
          position: 'absolute', top: 22, right: 18,
          background: 'rgba(255,255,255,0.95)', color: '#0a0a0a',
          padding: '6px 12px', borderRadius: 999,
          fontSize: 12, fontWeight: 600,
          boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
        }}>Buy now →</div>
      )}
      {/* subtitle */}
      {activeSub && (
        <div style={{
          position: 'absolute', left: 0, right: 0, bottom: 28,
          display: 'flex', justifyContent: 'center',
        }}>
          <div style={{
            background: 'rgba(0,0,0,0.78)', color: 'white',
            padding: '6px 14px', borderRadius: 6,
            fontSize: 15, fontWeight: 500, lineHeight: 1.3,
            maxWidth: '85%', textAlign: 'center',
            backdropFilter: 'blur(8px)',
          }}>{activeSub.text}</div>
        </div>
      )}
      {/* lang switch overlay */}
      {switchingLang && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0,0,0,0.4)',
          color: 'white', fontSize: 13, gap: 8,
        }}>
          <ICON.Spinner size={16} /> Regenerating in {language}…
        </div>
      )}
    </div>
  );
}

function PlayerControls({ playing, currentTime, onTogglePlay, onSeek }) {
  return (
    <div style={{
      padding: '10px 20px',
      display: 'flex', alignItems: 'center', gap: 12,
      borderTop: '1px solid var(--border)',
      background: 'var(--background)',
    }}>
      <Button variant="default" size="icon-sm" onClick={onTogglePlay} title={playing ? 'Pause' : 'Play (space)'}>
        {playing ? <ICON.Pause size={14} /> : <ICON.Play size={14} />}
      </Button>
      <Mono size={12} style={{ minWidth: 96 }}>
        {fmtTimecode(currentTime)} <span style={{ color: 'var(--muted-foreground)' }}> / {fmtTimecode(TOTAL_DURATION)}</span>
      </Mono>
      <Scrubber currentTime={currentTime} onSeek={onSeek} />
      <Button variant="ghost" size="icon-sm" title="Volume"><ICON.Volume size={15} /></Button>
    </div>
  );
}

function Scrubber({ currentTime, onSeek }) {
  const ref = React.useRef(null);
  const [drag, setDrag] = React.useState(false);
  const handle = (e) => {
    const rect = ref.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    onSeek((x / rect.width) * TOTAL_DURATION);
  };
  React.useEffect(() => {
    if (!drag) return;
    const move = (e) => handle(e);
    const up = () => setDrag(false);
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    return () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    // eslint-disable-next-line
  }, [drag]);
  const pct = (currentTime / TOTAL_DURATION) * 100;
  return (
    <div
      ref={ref}
      onPointerDown={(e) => { setDrag(true); handle(e); }}
      style={{
        flex: 1, height: 14,
        display: 'flex', alignItems: 'center',
        cursor: 'pointer',
        position: 'relative',
      }}
    >
      <div style={{ width: '100%', height: 4, background: 'var(--muted)', borderRadius: 999, position: 'relative' }}>
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0,
          width: `${pct}%`, background: 'var(--foreground)', borderRadius: 999,
        }} />
        <div style={{
          position: 'absolute', left: `${pct}%`, top: '50%',
          transform: 'translate(-50%, -50%)',
          width: 12, height: 12, borderRadius: '50%',
          background: 'var(--foreground)',
          boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
        }} />
      </div>
    </div>
  );
}

function fmtTimecode(s) {
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  const ms = Math.floor((s - Math.floor(s)) * 100);
  return `${String(m).padStart(2,'0')}:${String(r).padStart(2,'0')}.${String(ms).padStart(2,'0')}`;
}

// ─────────────────────────────────────────────────────────────────
// Timeline — multi-track
// ─────────────────────────────────────────────────────────────────
function TimelineCanvas({ scenes, subs, currentTime, onSeek }) {
  const ref = React.useRef(null);
  const pct = (currentTime / TOTAL_DURATION) * 100;
  const handle = (e) => {
    const rect = ref.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    onSeek((x / rect.width) * TOTAL_DURATION);
  };
  return (
    <div style={{
      padding: '14px 20px 20px',
      borderTop: '1px solid var(--border)',
      background: 'var(--background)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, gap: 8 }}>
        <Label>Timeline</Label>
        <Mono dim size={11} style={{ whiteSpace: 'nowrap' }}>{fmtTime(TOTAL_DURATION)} · 5 scenes</Mono>
      </div>

      <div ref={ref}
        onPointerDown={(e) => handle(e)}
        style={{
          position: 'relative', userSelect: 'none', cursor: 'pointer',
          display: 'flex', flexDirection: 'column', gap: 6,
        }}
      >
        {/* time ruler */}
        <div style={{ position: 'relative', height: 14, marginLeft: 80 }}>
          {[0, 5, 10, 15, 20, 25, 30].map(t => (
            <div key={t} style={{
              position: 'absolute', left: `${(t / TOTAL_DURATION) * 100}%`,
              fontSize: 10, color: 'var(--muted-foreground)', fontFamily: 'var(--font-mono)',
              transform: t === 30 ? 'translateX(-100%)' : 'translateX(-50%)',
            }}>0:{String(t).padStart(2,'0')}</div>
          ))}
        </div>

        <Track icon={<ICON.Video size={11} />} label="Scenes">
          {scenes.map((s, i) => (
            <div key={s.id} style={{
              position: 'absolute',
              left: `${(s.start / TOTAL_DURATION) * 100}%`,
              width: `${(s.duration / TOTAL_DURATION) * 100}%`,
              top: 4, bottom: 4,
              borderRadius: 4,
              background: i % 2 === 0 ? 'hsl(0 0% 18%)' : 'hsl(0 0% 25%)',
              color: 'white',
              padding: '0 8px',
              display: 'flex', alignItems: 'center',
              fontSize: 11, fontWeight: 500,
              overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis',
              border: '1px solid hsl(0 0% 10%)',
            }}>S{i+1} · {s.title}</div>
          ))}
        </Track>

        <Track icon={<ICON.Mic size={11} />} label="Voice">
          <Waveform />
        </Track>

        <Track icon={<ICON.Sub size={11} />} label="Subtitles">
          {subs.map((c, i) => (
            <div key={i} style={{
              position: 'absolute',
              left: `${(c.start / TOTAL_DURATION) * 100}%`,
              width: `${((c.end - c.start) / TOTAL_DURATION) * 100}%`,
              top: 4, bottom: 4,
              borderRadius: 4,
              background: 'var(--background)',
              border: '1px solid var(--border)',
              padding: '0 6px',
              display: 'flex', alignItems: 'center',
              fontSize: 10,
              overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis',
            }}>{c.text}</div>
          ))}
        </Track>

        <Track icon={<ICON.Wand size={11} />} label="Overlays">
          <div style={{
            position: 'absolute',
            left: `${(8 / TOTAL_DURATION) * 100}%`,
            width: `${(5 / TOTAL_DURATION) * 100}%`,
            top: 4, bottom: 4, borderRadius: 4,
            background: 'hsl(43 96% 90%)', color: 'hsl(43 96% 25%)',
            border: '1px solid hsl(43 96% 75%)',
            padding: '0 8px', display: 'flex', alignItems: 'center',
            fontSize: 11, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden',
          }}>Buy now →</div>
          <div style={{
            position: 'absolute',
            left: `${(21 / TOTAL_DURATION) * 100}%`,
            width: `${(7 / TOTAL_DURATION) * 100}%`,
            top: 4, bottom: 4, borderRadius: 4,
            background: 'hsl(43 96% 90%)', color: 'hsl(43 96% 25%)',
            border: '1px solid hsl(43 96% 75%)',
            padding: '0 8px', display: 'flex', alignItems: 'center',
            fontSize: 11, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden',
          }}>Try free</div>
        </Track>

        <Track icon={<ICON.Music size={11} />} label="Music">
          <div style={{
            position: 'absolute', left: 0, right: 0, top: 8, bottom: 8,
            borderRadius: 4,
            background: 'repeating-linear-gradient(90deg, var(--muted) 0, var(--muted) 6px, transparent 6px, transparent 9px)',
            border: '1px solid var(--border)',
          }} />
          <Mono dim size={10} style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', whiteSpace: 'nowrap' }}>
            −18 dB
          </Mono>
        </Track>

        {/* Playhead */}
        <div style={{
          position: 'absolute', left: `calc(80px + ${pct}% * (100% - 80px) / 100%)`, top: 14, bottom: 0,
          width: 2, background: 'var(--foreground)', pointerEvents: 'none',
          transform: 'translateX(-1px)',
        }}>
          <div style={{
            position: 'absolute', top: -6, left: -5,
            width: 0, height: 0,
            borderLeft: '6px solid transparent',
            borderRight: '6px solid transparent',
            borderTop: '6px solid var(--foreground)',
          }} />
        </div>
      </div>
    </div>
  );
}

function Track({ icon, label, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'stretch', gap: 8 }}>
      <div style={{
        width: 72, padding: '0 6px',
        display: 'flex', alignItems: 'center', gap: 6,
        fontSize: 11, color: 'var(--muted-foreground)',
        fontFamily: 'var(--font-sans)', fontWeight: 500,
      }}>
        {icon} {label}
      </div>
      <div style={{
        flex: 1, position: 'relative', height: 30,
        background: 'var(--muted)', borderRadius: 'var(--radius)',
        border: '1px solid var(--border)',
        overflow: 'hidden',
      }}>{children}</div>
    </div>
  );
}

function Waveform() {
  // deterministic waveform
  const bars = 80;
  const samples = React.useMemo(() => {
    const arr = [];
    for (let i = 0; i < bars; i++) {
      const v = 0.15 + Math.abs(Math.sin(i * 0.6) * 0.35) + Math.abs(Math.sin(i * 1.3) * 0.3);
      arr.push(Math.min(1, v));
    }
    return arr;
  }, []);
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', padding: '0 6px', gap: 2 }}>
      {samples.map((v, i) => (
        <div key={i} style={{
          flex: 1,
          height: `${v * 80}%`,
          background: 'hsl(0 0% 40%)',
          borderRadius: 1,
          minHeight: 2,
        }} />
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Right panel
// ─────────────────────────────────────────────────────────────────
function RightPanel({ tab, onTabChange, subs, scenes, currentTime }) {
  return (
    <aside style={{ background: 'var(--background)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div style={{ padding: '16px 20px 12px' }}>
        <Tabs
          fullWidth
          value={tab}
          onChange={onTabChange}
          items={[
            { value: 'subtitles', label: 'Subtitles' },
            { value: 'overlays',  label: 'Overlays' },
            { value: 'audio',     label: 'Audio' },
            { value: 'scenes',    label: 'Scenes' },
          ]}
        />
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 20px 20px' }}>
        {tab === 'subtitles' && <SubtitlesTab subs={subs} currentTime={currentTime} />}
        {tab === 'overlays'  && <OverlaysTab />}
        {tab === 'audio'     && <AudioTab />}
        {tab === 'scenes'    && <ScenesTab scenes={scenes} />}
      </div>
    </aside>
  );
}

function SubtitlesTab({ subs, currentTime }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4, gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap' }}>{subs.length} cues</span>
        <Button variant="ghost" size="sm"><ICON.Refresh size={12} /> Regenerate all</Button>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {subs.map((c, i) => {
          const active = currentTime >= c.start && currentTime < c.end;
          return (
            <div key={i} style={{
              padding: 10, borderRadius: 'var(--radius)',
              border: `1px solid ${active ? 'var(--foreground)' : 'var(--border)'}`,
              background: active ? 'var(--accent)' : 'var(--background)',
              display: 'flex', alignItems: 'flex-start', gap: 8,
              transition: 'border-color 120ms ease, background 120ms ease',
            }}>
              <Mono size={11} dim style={{ width: 76, flexShrink: 0, paddingTop: 2 }}>
                {fmtMS(c.start)} – {fmtMS(c.end)}
              </Mono>
              <span style={{ fontSize: 13, lineHeight: 1.4, flex: 1 }}>{c.text}</span>
              <Button variant="ghost" size="icon-sm"><ICON.Edit size={12} /></Button>
            </div>
          );
        })}
        <Button variant="outline" size="sm" style={{ marginTop: 6, alignSelf: 'flex-start' }}>
          <ICON.Plus size={12} /> Add cue
        </Button>
      </div>
    </div>
  );
}

function fmtMS(s) {
  return `0:${String(Math.floor(s)).padStart(2,'0')}`;
}

function OverlaysTab() {
  const overlays = [
    { text: 'Buy now →', start: 8, end: 13, anim: 'fade' },
    { text: 'Try free',  start: 21, end: 28, anim: 'slide up' },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{overlays.length} overlays</span>
        <Button variant="outline" size="sm"><ICON.Plus size={12} /> Add overlay</Button>
      </div>
      {overlays.map((o, i) => (
        <Card key={i} style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div style={{ fontSize: 14, fontWeight: 500 }}>{o.text}</div>
            <Button variant="ghost" size="icon-sm"><ICON.MoreHorizontal size={14} /></Button>
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <Mono dim size={11}>{fmtMS(o.start)} – {fmtMS(o.end)}</Mono>
            <Badge variant="outline">{o.anim}</Badge>
          </div>
        </Card>
      ))}
    </div>
  );
}

function AudioTab() {
  const [vol, setVol] = React.useState(60);
  const [enabled, setEnabled] = React.useState(true);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, marginTop: 4 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Label>Background music</Label>
          <Chip selected={enabled} onClick={() => setEnabled(!enabled)}>{enabled ? 'enabled' : 'off'}</Chip>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: 'var(--muted-foreground)' }}>Volume</span>
            <Mono size={12}>{Math.round(((vol/100) * 36) - 36)} dB</Mono>
          </div>
          <input type="range" min={0} max={100} value={vol} onChange={(e) => setVol(parseInt(e.target.value))}
            disabled={!enabled}
            style={{ width: '100%', accentColor: 'var(--foreground)' }}
          />
        </div>
        <Button variant="outline" size="sm" style={{ alignSelf: 'flex-start' }}>
          <ICON.Refresh size={12} /> Regenerate music
        </Button>
      </div>

      <Separator />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Label>Narration</Label>
        <p style={{ margin: 0, fontSize: 12, color: 'var(--muted-foreground)', lineHeight: 1.5 }}>
          Per-scene voice levels are locked to the master mix in this preview.
        </p>
      </div>
    </div>
  );
}

function ScenesTab({ scenes }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
      <Label>Quick regenerate</Label>
      <p style={{ margin: 0, fontSize: 12, color: 'var(--muted-foreground)', lineHeight: 1.5, marginBottom: 6 }}>
        Spot a bad scene? Re-render just that one without going back to the storyboard.
      </p>
      {scenes.map((s, i) => (
        <Card key={s.id} style={{ padding: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 56, flexShrink: 0 }}>
            <SceneThumb scene={s} height={40} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>Scene {i+1}</div>
            <div style={{ fontSize: 12, color: 'var(--muted-foreground)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title}</div>
          </div>
          <Button variant="ghost" size="icon-sm" title="Regenerate"><ICON.Refresh size={13} /></Button>
        </Card>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Language dropdown
// ─────────────────────────────────────────────────────────────────
function LanguageDropdown({ value, onChange, switching }) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <Button variant="outline" size="sm" onClick={() => setOpen(!open)}>
        <ICON.Globe size={14} />
        {switching ? <><ICON.Spinner size={12} /> switching…</> : value}
        <ICON.ChevronDown size={13} />
      </Button>
      {open && (
        <div className="anim-scale" style={{
          position: 'absolute', right: 0, top: 'calc(100% + 4px)',
          minWidth: 200,
          background: 'var(--popover)', color: 'var(--popover-foreground)',
          border: '1px solid var(--border)', borderRadius: 'var(--radius)',
          boxShadow: 'var(--shadow-lg)',
          padding: 4, zIndex: 30,
        }}>
          {LANGUAGES.map(l => {
            const active = l.code === value;
            return (
              <button key={l.code} type="button"
                onClick={() => { onChange(l.code); setOpen(false); }}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '8px 10px', borderRadius: 6,
                  border: 'none', background: active ? 'var(--accent)' : 'transparent',
                  color: 'var(--foreground)', cursor: 'pointer',
                  fontFamily: 'var(--font-sans)', fontSize: 13,
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = 'var(--accent)'; }}
                onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent'; }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>{l.code}</span>
                  <span style={{ color: 'var(--muted-foreground)', fontSize: 12 }}>{l.native}</span>
                </span>
                {active && <ICON.Check size={12} strokeWidth={3} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

window.ReviewScreen = ReviewScreen;
window.fmtTimecode = fmtTimecode;
