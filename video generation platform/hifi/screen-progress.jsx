// Screen 3: Generation Progress — animated pipeline + per-scene cards.

function ProgressScreen() {
  const { state, dispatch } = useApp();
  const { scenes, brief } = state;

  // Simulated render: walks through stages over ~14s, advancing scenes too.
  const [stage, setStage] = React.useState(0);            // 0..STAGES.length
  const [sceneProg, setSceneProg] = React.useState(
    scenes.map(() => ({ status: 'waiting', percent: 0 }))
  );
  const [elapsed, setElapsed] = React.useState(0);
  const TOTAL_MS = 14000;

  React.useEffect(() => {
    const start = performance.now();
    let raf;
    const tick = () => {
      const t = performance.now() - start;
      setElapsed(t);
      // stage progression
      const stageProgress = Math.min(1, t / TOTAL_MS);
      const stageIdx = Math.min(STAGES.length - 1, Math.floor(stageProgress * STAGES.length));
      setStage(stageIdx);

      // scene-level: each scene completes at staggered times
      setSceneProg((prev) => prev.map((sp, i) => {
        // Each scene starts at (i * 1500)ms and takes 3500ms to complete
        const sceneStart = i * 1500;
        const sceneEnd = sceneStart + 3500;
        if (t < sceneStart) return { status: 'waiting', percent: 0 };
        if (t < sceneEnd - 1200) {
          const p = ((t - sceneStart) / (sceneEnd - sceneStart - 1200)) * 100;
          return { status: 'generating', percent: Math.min(95, p) };
        }
        if (t < sceneEnd) return { status: 'lipsync', percent: 100 };
        return { status: 'done', percent: 100 };
      }));

      if (t >= TOTAL_MS) {
        // Done — push to review
        setTimeout(() => {
          dispatch({ type: 'GOTO', screen: 'review' });
        }, 700);
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line
  }, []);

  const overallPct = Math.min(100, Math.round((elapsed / TOTAL_MS) * 100));
  const eta = Math.max(0, Math.round((TOTAL_MS - elapsed) / 1000));

  return (
    <ProjectShell
      onBack={() => dispatch({ type: 'GOTO', screen: 'storyboard' })}
      left={<>
        <BrandMark />
        <Separator vertical style={{ height: 20 }} />
        <span style={{ fontSize: 14, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 }}>{brief.topic || state.projectTitle}</span>
        <Badge variant="info" style={{ flexShrink: 0 }}>rendering</Badge>
      </>}
      right={<>
        <Button variant="outline" size="sm">Cancel</Button>
        <ThemeToggle />
      </>}
    >
      <div data-screen-label="03-progress" style={{ padding: '32px 40px 40px', maxWidth: 1200, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 24 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, letterSpacing: -0.5 }}>
              Generating your video
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--muted-foreground)' }}>
              About {eta}s remaining · job <Mono size={12}>r-7421</Mono>
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: -0.5, fontFamily: 'var(--font-mono)' }}>{overallPct}%</div>
            <div style={{ fontSize: 12, color: 'var(--muted-foreground)' }}>complete</div>
          </div>
        </div>

        <Progress value={overallPct} style={{ marginBottom: 32 }} />

        {/* Pipeline stepper */}
        <Card style={{ padding: 24, marginBottom: 24 }}>
          <Label style={{ marginBottom: 16, display: 'block' }}>Pipeline</Label>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, position: 'relative' }}>
            {/* connecting line */}
            <div style={{
              position: 'absolute', top: 14, left: '6%', right: '6%',
              height: 1, background: 'var(--border)',
            }} />
            <div style={{
              position: 'absolute', top: 14, left: '6%',
              height: 1,
              background: 'var(--foreground)',
              width: `${(stage / (STAGES.length - 1)) * 88}%`,
              transition: 'width 350ms ease',
            }} />
            {STAGES.map((s, i) => {
              const done = i < stage;
              const active = i === stage;
              return (
                <div key={s.key} style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
                  position: 'relative', zIndex: 1, flex: 1,
                }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%',
                    background: done || active ? 'var(--foreground)' : 'var(--background)',
                    border: `1.5px solid ${done || active ? 'var(--foreground)' : 'var(--border)'}`,
                    color: done || active ? 'var(--background)' : 'var(--muted-foreground)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'all 250ms ease',
                  }}>
                    {done && <ICON.Check size={14} strokeWidth={3} />}
                    {active && <ICON.Spinner size={14} />}
                    {!done && !active && <Mono size={10}>{i + 1}</Mono>}
                  </div>
                  <span style={{
                    fontSize: 12,
                    fontWeight: active ? 600 : 400,
                    color: done || active ? 'var(--foreground)' : 'var(--muted-foreground)',
                  }}>{s.label}</span>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Per-scene grid */}
        <div style={{ marginBottom: 12 }}>
          <Label>Per-scene progress</Label>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 16 }}>
          {scenes.map((scene, i) => {
            const p = sceneProg[i];
            return (
              <Card key={scene.id} style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Mono size={11} dim>SCENE {String(i+1).padStart(2, '0')}</Mono>
                  <SceneStatusBadge status={p.status} />
                </div>
                <div style={{ position: 'relative' }}>
                  <SceneThumb scene={scene} height={120} />
                  {p.status !== 'done' && (
                    <div style={{
                      position: 'absolute', inset: 0, borderRadius: 6,
                      background: 'rgba(10,10,10,0.4)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: 'rgba(255,255,255,0.9)',
                    }}>
                      {p.status === 'waiting' && (
                        <span style={{ fontSize: 12, opacity: 0.8 }}>Waiting…</span>
                      )}
                      {(p.status === 'generating' || p.status === 'lipsync') && (
                        <div style={{ width: '70%' }}>
                          <Progress value={p.percent} style={{ height: 4 }} />
                        </div>
                      )}
                    </div>
                  )}
                  {p.status === 'done' && (
                    <div style={{
                      position: 'absolute', inset: 0, borderRadius: 6,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: 'rgba(255,255,255,0.95)',
                    }}>
                      <ICON.Play size={32} style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }} />
                    </div>
                  )}
                </div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{scene.title}</div>
              </Card>
            );
          })}
        </div>
      </div>
    </ProjectShell>
  );
}

function SceneStatusBadge({ status }) {
  if (status === 'done')       return <Badge variant="success"><ICON.Check size={10} strokeWidth={3} /> done</Badge>;
  if (status === 'generating') return <Badge variant="info"><ICON.Spinner size={10} /> generating</Badge>;
  if (status === 'lipsync')    return <Badge variant="info"><ICON.Spinner size={10} /> lip-sync</Badge>;
  return <Badge variant="outline">waiting</Badge>;
}

window.ProgressScreen = ProgressScreen;
