// Screen 0: Welcome — single CTA landing.
function WelcomeScreen() {
  const { dispatch } = useApp();

  const onStart = () => {
    dispatch({ type: 'GOTO', screen: 'chat' });
  };

  return (
    <div data-screen-label="00-welcome" style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      background: 'var(--background)', color: 'var(--foreground)',
    }}>
      <header style={{ height: 56, display: 'flex', alignItems: 'center', padding: '0 20px', justifyContent: 'space-between' }}>
        <BrandMark />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Button variant="ghost" size="sm">Examples</Button>
          <Button variant="ghost" size="sm">Docs</Button>
          <ThemeToggle />
        </div>
      </header>

      <div className="anim-fade" style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '40px 24px',
      }}>
        <div style={{ maxWidth: 640, textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 24 }}>
          <Badge variant="outline" style={{ padding: '4px 10px', fontSize: 12 }}>
            <ICON.Sparkles size={12} style={{ marginRight: 2 }} /> Conversational · 5 languages · scene-aware
          </Badge>

          <h1 style={{
            margin: 0,
            fontFamily: 'var(--font-sans)', fontWeight: 600,
            fontSize: 56, lineHeight: 1.05, letterSpacing: -1.2,
          }}>
            Tell us about your&nbsp;video.<br />
            <span style={{ color: 'var(--muted-foreground)' }}>We&apos;ll figure out the rest.</span>
          </h1>

          <p style={{
            margin: 0,
            fontSize: 16, lineHeight: 1.55, color: 'var(--muted-foreground)',
            maxWidth: 520,
          }}>
            Describe your idea in plain language. We plan the scenes, generate the visuals, narrate it in your language, and render it ready to share.
          </p>

          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <Button size="lg" onClick={onStart}>
              <ICON.Plus size={15} /> Start a new video
            </Button>
            <Button size="lg" variant="outline">
              <ICON.Folder size={15} /> Open recent
            </Button>
          </div>

          <div style={{
            marginTop: 36,
            display: 'flex', alignItems: 'center', gap: 32, flexWrap: 'wrap', justifyContent: 'center',
            color: 'var(--muted-foreground)', fontSize: 13,
          }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
              <ICON.MessageSquare size={14} /> Chat-led brief
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
              <ICON.Video size={14} /> Cinematic scenes
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
              <ICON.Globe size={14} /> EN · HI · MR · TA · PA
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
              <ICON.Sub size={14} /> Live subtitles
            </span>
          </div>
        </div>
      </div>

      <footer style={{
        padding: '20px 24px',
        borderTop: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between',
        color: 'var(--muted-foreground)', fontSize: 12,
      }}>
        <Mono dim size={11} style={{ whiteSpace: 'nowrap' }}>v0.1 · prototype</Mono>
        <Mono dim size={11} style={{ whiteSpace: 'nowrap' }}>↵ to start</Mono>
      </footer>
    </div>
  );
}

window.WelcomeScreen = WelcomeScreen;
