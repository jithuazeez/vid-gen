// Shell — top bar shared across in-project screens.

function ProjectShell({ left, center, right, children, onBack }) {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      background: 'var(--background)', color: 'var(--foreground)',
    }}>
      <header style={{
        height: 56, flexShrink: 0,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', padding: '0 20px',
        gap: 16,
        background: 'var(--background)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
          {onBack && (
            <Button variant="ghost" size="icon-sm" onClick={onBack} title="Back">
              <ICON.ArrowLeft size={16} />
            </Button>
          )}
          {left}
        </div>
        {center && <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>{center}</div>}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto', flexShrink: 0 }}>
          {right}
        </div>
      </header>
      <main style={{ flex: 1, minHeight: 0 }}>{children}</main>
    </div>
  );
}

function BrandMark({ size = 16 }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 22, height: 22, borderRadius: 6,
        background: 'var(--primary)', color: 'var(--primary-foreground)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <ICON.Aperture size={13} strokeWidth={2} />
      </div>
      <span style={{ fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: 14, letterSpacing: -0.2 }}>video.studio</span>
    </div>
  );
}

function ThemeToggle() {
  const [dark, setDark] = React.useState(() => document.documentElement.classList.contains('dark'));
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle('dark', next);
  };
  return (
    <Button variant="ghost" size="icon-sm" onClick={toggle} title={dark ? 'Light mode' : 'Dark mode'}>
      {dark ? <ICON.Sun size={15} /> : <ICON.Moon size={15} />}
    </Button>
  );
}

Object.assign(window, { ProjectShell, BrandMark, ThemeToggle });
