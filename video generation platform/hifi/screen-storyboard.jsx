// Screen 2: Storyboard — scene grid with slide-in detail panel.

// Procedural placeholder thumbnail per scene (gradient + scene number).
function SceneThumb({ scene, height = 144 }) {
  // deterministic gradient per scene id
  const seed = scene.id.charCodeAt(1) || 1;
  const h1 = (seed * 47) % 360;
  const h2 = (h1 + 40) % 360;
  return (
    <div style={{
      width: '100%', height,
      position: 'relative', overflow: 'hidden',
      borderRadius: 6,
      background: `linear-gradient(135deg, hsl(${h1} 18% 18%), hsl(${h2} 22% 12%))`,
      color: 'rgba(255,255,255,0.85)',
    }}>
      {/* faux film grain dots */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: 'radial-gradient(rgba(255,255,255,0.06) 1px, transparent 1px)',
        backgroundSize: '4px 4px',
        opacity: 0.6,
      }} />
      {/* fake aperture composition lines */}
      <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, opacity: 0.18 }} preserveAspectRatio="none">
        <line x1="33%" y1="0" x2="33%" y2="100%" stroke="white" strokeWidth="0.5" />
        <line x1="66%" y1="0" x2="66%" y2="100%" stroke="white" strokeWidth="0.5" />
        <line x1="0" y1="33%" x2="100%" y2="33%" stroke="white" strokeWidth="0.5" />
        <line x1="0" y1="66%" x2="100%" y2="66%" stroke="white" strokeWidth="0.5" />
      </svg>
      <div style={{ position: 'absolute', left: 10, top: 10, fontFamily: 'var(--font-mono)', fontSize: 10, opacity: 0.85, letterSpacing: 1 }}>
        SCENE {String(parseInt(scene.id.slice(1), 10)).padStart(2, '0')}
      </div>
      <div style={{ position: 'absolute', right: 10, top: 10, fontFamily: 'var(--font-mono)', fontSize: 10, opacity: 0.85 }}>
        {fmtTime(scene.start)} — {fmtTime(scene.start + scene.duration)}
      </div>
      <div style={{
        position: 'absolute', left: 12, bottom: 12, right: 12,
        fontFamily: 'var(--font-sans)', fontSize: 13, fontWeight: 500,
        lineHeight: 1.3,
        textShadow: '0 1px 2px rgba(0,0,0,0.6)',
      }}>{scene.title}</div>
    </div>
  );
}

function fmtTime(s) {
  const m = Math.floor(s / 60), r = Math.floor(s % 60);
  return `${m}:${String(r).padStart(2, '0')}`;
}

function StoryboardScreen() {
  const { state, dispatch } = useApp();
  const { scenes, brief, selectedSceneId } = state;
  const selected = scenes.find(s => s.id === selectedSceneId) || null;

  const total = scenes.reduce((a, s) => a + s.duration, 0);

  const onGenerate = () => {
    dispatch({ type: 'SELECT_SCENE', id: null });
    dispatch({ type: 'GOTO', screen: 'progress' });
  };

  return (
    <ProjectShell
      onBack={() => dispatch({ type: 'GOTO', screen: 'chat' })}
      left={<>
        <BrandMark />
        <Separator vertical style={{ height: 20 }} />
        <span style={{ fontSize: 14, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 }}>{brief.topic || state.projectTitle}</span>
        <div style={{ display: 'flex', gap: 6, marginLeft: 2, flexShrink: 0 }}>
          <Badge variant="secondary">{brief.duration || '30s'}</Badge>
          <Badge variant="secondary">{brief.aspect || '9:16'}</Badge>
          <Badge variant="secondary">{brief.language || 'English'}</Badge>
        </div>
      </>}
      right={<>
        <Button variant="outline" size="sm"><ICON.Refresh size={14} /> Regenerate all</Button>
        <Button size="sm" onClick={onGenerate}>
          Generate video <ICON.ArrowRight size={14} />
        </Button>
        <ThemeToggle />
      </>}
    >
      <div data-screen-label="02-storyboard" style={{ display: 'flex', height: 'calc(100vh - 56px)', minHeight: 0, position: 'relative' }}>
        <div style={{ flex: 1, overflowY: 'auto', padding: '28px 40px 40px' }}>
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 20 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: -0.4 }}>Scene plan</h2>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--muted-foreground)' }}>
                  {scenes.length} scenes · {fmtTime(total)} total — click any card to edit
                </p>
              </div>
              <Button variant="outline" size="sm"><ICON.Plus size={14} /> Add scene</Button>
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
              gap: 16,
            }}>
              {scenes.map(scene => (
                <SceneCard
                  key={scene.id}
                  scene={scene}
                  selected={scene.id === selectedSceneId}
                  onClick={() => dispatch({ type: 'SELECT_SCENE', id: scene.id })}
                />
              ))}
              <Card
                style={{ minHeight: 280, display: 'flex', alignItems: 'center', justifyContent: 'center', borderStyle: 'dashed' }}
                hoverable
              >
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, color: 'var(--muted-foreground)' }}>
                  <ICON.Plus size={20} />
                  <span style={{ fontSize: 13 }}>Add scene</span>
                </div>
              </Card>
            </div>
          </div>
        </div>

        {/* Slide-in detail panel */}
        {selected && (
          <SceneDetailPanel
            key={selected.id}
            scene={selected}
            onClose={() => dispatch({ type: 'SELECT_SCENE', id: null })}
            onUpdate={(patch) => dispatch({ type: 'UPDATE_SCENE', id: selected.id, patch })}
          />
        )}
      </div>
    </ProjectShell>
  );
}

function SceneCard({ scene, selected, onClick }) {
  return (
    <Card hoverable selected={selected} onClick={onClick} style={{ overflow: 'hidden', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <SceneThumb scene={scene} height={150} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '0 2px' }}>
        <p style={{
          margin: 0, fontSize: 13, lineHeight: 1.45, color: 'var(--muted-foreground)',
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>{scene.visualPrompt}</p>
        <p style={{
          margin: 0, fontSize: 13, lineHeight: 1.45, fontStyle: 'italic',
          display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>“{scene.script}”</p>
      </div>
      <Separator />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 2px' }}>
        <div style={{ display: 'flex', gap: 6, fontSize: 11, color: 'var(--muted-foreground)' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
            <ICON.Mic size={11} /> {scene.speaker ? 'on camera' : 'voice-over'}
          </span>
          <span>·</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
            <ICON.Sub size={11} /> {scene.subtitle}
          </span>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={(e) => e.stopPropagation()} title="More">
          <ICON.MoreHorizontal size={14} />
        </Button>
      </div>
    </Card>
  );
}

function SceneDetailPanel({ scene, onClose, onUpdate }) {
  return (
    <aside className="anim-slide-right" style={{
      width: 460, flexShrink: 0,
      background: 'var(--background)',
      borderLeft: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      minHeight: 0,
      boxShadow: 'var(--shadow-lg)',
    }}>
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div>
          <Mono dim size={11}>SCENE {String(parseInt(scene.id.slice(1), 10)).padStart(2, '0')} · {fmtTime(scene.start)}–{fmtTime(scene.start + scene.duration)}</Mono>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2, letterSpacing: -0.2 }}>{scene.title}</div>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose} title="Close">
          <ICON.X size={16} />
        </Button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 20px 16px', display: 'flex', flexDirection: 'column', gap: 22 }}>
        <SceneThumb scene={scene} height={220} />

        <Section title="Narration script">
          <Textarea
            value={scene.script}
            onChange={(e) => onUpdate({ script: e.target.value })}
            rows={3}
          />
        </Section>

        <Section title="Visual direction">
          <Textarea
            value={scene.visualPrompt}
            onChange={(e) => onUpdate({ visualPrompt: e.target.value })}
            rows={3}
          />
        </Section>

        <Section title="Characters in scene">
          {scene.chars.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 13, color: 'var(--muted-foreground)' }}>None — voice-over only</span>
              <Button variant="outline" size="sm" onClick={() => onUpdate({ chars: ['New character — describe their look'] })}>
                <ICON.Plus size={12} /> Add character
              </Button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {scene.chars.map((c, i) => (
                <div key={i} style={{
                  display: 'flex', gap: 8, alignItems: 'flex-start',
                  border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 10,
                }}>
                  <Avatar size={28}>{`C${i+1}`}</Avatar>
                  <Input
                    value={c}
                    onChange={(e) => {
                      const next = scene.chars.slice();
                      next[i] = e.target.value;
                      onUpdate({ chars: next });
                    }}
                    style={{ border: 'none', padding: 0, height: 'auto', fontSize: 13 }}
                  />
                  <Button variant="ghost" size="icon-sm" onClick={() => {
                    onUpdate({ chars: scene.chars.filter((_, j) => j !== i) });
                  }}><ICON.X size={12} /></Button>
                </div>
              ))}
              <Button variant="outline" size="sm" style={{ alignSelf: 'flex-start' }}
                onClick={() => onUpdate({ chars: [...scene.chars, 'New character'] })}>
                <ICON.Plus size={12} /> Add character
              </Button>
            </div>
          )}
        </Section>

        <Section title="Speaking on camera">
          <RadioGroup
            value={scene.speaker ? 'on' : 'off'}
            onChange={(v) => onUpdate({ speaker: v === 'on' })}
            options={[
              { value: 'off', label: 'Off', hint: 'Lip-sync will be skipped for this scene.' },
              { value: 'on',  label: 'On',  hint: 'MuseTalk will sync mouth movement to the narration audio.' },
            ]}
          />
        </Section>

        <Section title="Subtitle position">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {['auto', 'top', 'bottom', 'custom'].map(p => (
              <Chip key={p} selected={scene.subtitle === p} onClick={() => onUpdate({ subtitle: p })}>{p}</Chip>
            ))}
          </div>
        </Section>
      </div>

      <div style={{
        padding: '14px 20px',
        borderTop: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', gap: 8,
      }}>
        <Button variant="outline" size="sm"><ICON.Refresh size={14} /> Regenerate scene</Button>
        <div style={{ display: 'flex', gap: 6 }}>
          <Button variant="ghost" size="sm" onClick={onClose}>Done</Button>
        </div>
      </div>
    </aside>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <Label>{title}</Label>
      {children}
    </div>
  );
}

window.StoryboardScreen = StoryboardScreen;
window.SceneThumb = SceneThumb;
window.fmtTime = fmtTime;
