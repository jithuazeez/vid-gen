// shadcn-style primitives — vanilla CSS-in-JS, no Tailwind.
// Mirrors shadcn variants and sizing where reasonable.

const cx = (...args) => args.filter(Boolean).join(' ');

// ──────────────────────────────────────────────────────────────────
// Button
// ──────────────────────────────────────────────────────────────────
const buttonStyles = {
  base: {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
    fontFamily: 'var(--font-sans)', fontWeight: 500, lineHeight: 1,
    whiteSpace: 'nowrap', cursor: 'pointer', userSelect: 'none',
    border: '1px solid transparent', borderRadius: 'var(--radius)',
    transition: 'background-color 120ms ease, border-color 120ms ease, color 120ms ease, opacity 120ms ease, box-shadow 120ms ease',
    outline: 'none',
  },
  size: {
    sm:   { height: 32, padding: '0 12px', fontSize: 13 },
    md:   { height: 36, padding: '0 14px', fontSize: 14 },
    lg:   { height: 42, padding: '0 18px', fontSize: 15 },
    icon: { height: 32, width: 32, padding: 0 },
    'icon-sm': { height: 28, width: 28, padding: 0 },
  },
  variant: {
    default:   { background: 'var(--primary)', color: 'var(--primary-foreground)', borderColor: 'var(--primary)' },
    secondary: { background: 'var(--secondary)', color: 'var(--secondary-foreground)', borderColor: 'var(--border)' },
    outline:   { background: 'transparent', color: 'var(--foreground)', borderColor: 'var(--border)' },
    ghost:     { background: 'transparent', color: 'var(--foreground)', borderColor: 'transparent' },
    destructive:{ background: 'var(--destructive)', color: 'var(--destructive-foreground)', borderColor: 'var(--destructive)' },
    link:      { background: 'transparent', color: 'var(--foreground)', borderColor: 'transparent', textDecoration: 'underline', textUnderlineOffset: 4 },
  },
};
function Button({ children, variant = 'default', size = 'md', disabled = false, onClick, style = {}, type = 'button', title, ...rest }) {
  const [hover, setHover] = React.useState(false);
  const [pressed, setPressed] = React.useState(false);
  const v = buttonStyles.variant[variant] || buttonStyles.variant.default;
  const s = buttonStyles.size[size] || buttonStyles.size.md;

  let hoverStyle = {};
  if (hover && !disabled) {
    if (variant === 'default') hoverStyle = { background: 'hsl(0 0% 18%)' };
    else if (variant === 'secondary') hoverStyle = { background: 'var(--accent)' };
    else if (variant === 'outline')   hoverStyle = { background: 'var(--accent)' };
    else if (variant === 'ghost')     hoverStyle = { background: 'var(--accent)' };
    else if (variant === 'destructive') hoverStyle = { background: 'hsl(0 72% 45%)' };
  }
  const pressedStyle = pressed && !disabled ? { transform: 'translateY(0.5px)' } : {};
  return (
    <button
      type={type}
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setHover(false); setPressed(false); }}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
      onFocus={(e) => { e.currentTarget.style.boxShadow = '0 0 0 2px var(--background), 0 0 0 4px var(--ring)'; }}
      onBlur={(e) => { e.currentTarget.style.boxShadow = ''; }}
      style={{
        ...buttonStyles.base, ...s, ...v, ...hoverStyle, ...pressedStyle,
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        ...style,
      }}
      title={title}
      {...rest}
    >{children}</button>
  );
}

// ──────────────────────────────────────────────────────────────────
// Card
// ──────────────────────────────────────────────────────────────────
function Card({ children, style = {}, hoverable = false, onClick, selected = false }) {
  const [hover, setHover] = React.useState(false);
  const interactive = !!onClick || hoverable;
  return (
    <div
      onClick={onClick}
      onMouseEnter={interactive ? () => setHover(true) : undefined}
      onMouseLeave={interactive ? () => setHover(false) : undefined}
      style={{
        background: 'var(--card)', color: 'var(--card-foreground)',
        border: `1px solid ${selected ? 'var(--foreground)' : 'var(--border)'}`,
        borderRadius: 'var(--radius)',
        boxShadow: hover && interactive ? 'var(--shadow-md)' : 'var(--shadow-sm)',
        transition: 'box-shadow 160ms ease, border-color 120ms ease, transform 160ms ease',
        transform: hover && interactive ? 'translateY(-1px)' : 'none',
        cursor: interactive ? 'pointer' : 'default',
        ...style,
      }}
    >{children}</div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Input / Textarea
// ──────────────────────────────────────────────────────────────────
const fieldBase = {
  width: '100%', display: 'block',
  background: 'var(--background)', color: 'var(--foreground)',
  border: '1px solid var(--input)', borderRadius: 'var(--radius)',
  padding: '8px 12px', fontSize: 14, lineHeight: 1.5,
  outline: 'none',
  transition: 'border-color 120ms ease, box-shadow 120ms ease, background 120ms ease',
};
function Input({ style = {}, autoFocus, ...rest }) {
  const ref = React.useRef(null);
  React.useEffect(() => { if (autoFocus && ref.current) ref.current.focus(); }, [autoFocus]);
  return (
    <input
      ref={ref}
      style={{ ...fieldBase, height: 36, ...style }}
      onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--ring)'; e.currentTarget.style.boxShadow = '0 0 0 3px hsl(0 0% 50% / 0.12)'; }}
      onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--input)'; e.currentTarget.style.boxShadow = 'none'; }}
      {...rest}
    />
  );
}
function Textarea({ style = {}, autoFocus, ...rest }) {
  const ref = React.useRef(null);
  React.useEffect(() => { if (autoFocus && ref.current) ref.current.focus(); }, [autoFocus]);
  return (
    <textarea
      ref={ref}
      style={{ ...fieldBase, minHeight: 80, resize: 'vertical', ...style }}
      onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--ring)'; e.currentTarget.style.boxShadow = '0 0 0 3px hsl(0 0% 50% / 0.12)'; }}
      onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--input)'; e.currentTarget.style.boxShadow = 'none'; }}
      {...rest}
    />
  );
}

// ──────────────────────────────────────────────────────────────────
// Badge
// ──────────────────────────────────────────────────────────────────
function Badge({ children, variant = 'secondary', style = {} }) {
  const map = {
    default:   { bg: 'var(--primary)', fg: 'var(--primary-foreground)', bd: 'var(--primary)' },
    secondary: { bg: 'var(--secondary)', fg: 'var(--secondary-foreground)', bd: 'var(--border)' },
    outline:   { bg: 'transparent', fg: 'var(--foreground)', bd: 'var(--border)' },
    success:   { bg: 'hsl(142 71% 96%)', fg: 'hsl(142 71% 24%)', bd: 'hsl(142 71% 86%)' },
    warning:   { bg: 'hsl(38 92% 96%)', fg: 'hsl(38 92% 30%)', bd: 'hsl(38 92% 86%)' },
    info:      { bg: 'hsl(217 91% 96%)', fg: 'hsl(217 91% 35%)', bd: 'hsl(217 91% 86%)' },
  };
  const v = map[variant] || map.secondary;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 8px', borderRadius: 6,
      fontSize: 11, fontWeight: 500, lineHeight: 1.4,
      background: v.bg, color: v.fg, border: `1px solid ${v.bd}`,
      fontFamily: 'var(--font-sans)',
      whiteSpace: 'nowrap',
      ...style,
    }}>{children}</span>
  );
}

// ──────────────────────────────────────────────────────────────────
// Chip — tappable suggestion (used heavily in chat)
// ──────────────────────────────────────────────────────────────────
function Chip({ children, onClick, selected = false, disabled = false, icon, style = {} }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '6px 12px', height: 30,
        borderRadius: 999, border: '1px solid var(--border)',
        background: selected ? 'var(--primary)' : (hover ? 'var(--accent)' : 'var(--background)'),
        color: selected ? 'var(--primary-foreground)' : 'var(--foreground)',
        fontFamily: 'var(--font-sans)', fontSize: 13, fontWeight: 500, lineHeight: 1,
        whiteSpace: 'nowrap',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        transition: 'background-color 120ms ease, border-color 120ms ease, color 120ms ease',
        outline: 'none',
        ...style,
      }}
    >
      {icon}
      {children}
    </button>
  );
}

// ──────────────────────────────────────────────────────────────────
// Tabs
// ──────────────────────────────────────────────────────────────────
function Tabs({ value, onChange, items, style = {}, fullWidth = false }) {
  return (
    <div style={{
      display: fullWidth ? 'flex' : 'inline-flex',
      width: fullWidth ? '100%' : 'auto',
      padding: 3, gap: 2,
      background: 'var(--muted)', borderRadius: 'var(--radius)',
      ...style,
    }}>
      {items.map((it) => {
        const active = it.value === value;
        return (
          <button key={it.value} type="button" onClick={() => onChange(it.value)}
            style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              padding: '6px 8px', height: 28,
              flex: fullWidth ? '1 1 0' : 'initial',
              minWidth: 0,
              border: '1px solid transparent', borderRadius: 6,
              background: active ? 'var(--background)' : 'transparent',
              color: active ? 'var(--foreground)' : 'var(--muted-foreground)',
              boxShadow: active ? 'var(--shadow-sm)' : 'none',
              fontFamily: 'var(--font-sans)', fontWeight: 500, fontSize: 13, lineHeight: 1,
              cursor: 'pointer', outline: 'none',
              whiteSpace: 'nowrap',
              transition: 'background-color 120ms ease, color 120ms ease',
            }}>
            {it.icon}{it.label}
          </button>
        );
      })}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Dialog (modal)
// ──────────────────────────────────────────────────────────────────
function Dialog({ open, onOpenChange, children, width = 460, dismissOnBackdrop = true }) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onOpenChange(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onOpenChange]);
  if (!open) return null;
  return (
    <div
      onClick={dismissOnBackdrop ? () => onOpenChange(false) : undefined}
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        background: 'rgba(10,10,10,0.5)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 20,
        animation: 'fadeIn 160ms ease-out both',
      }}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="anim-scale"
        style={{
          width, maxWidth: '100%',
          background: 'var(--card)', color: 'var(--card-foreground)',
          border: '1px solid var(--border)', borderRadius: 12,
          boxShadow: 'var(--shadow-xl)',
          overflow: 'hidden',
        }}>
        {children}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Radio group (vertical, with optional helper text)
// ──────────────────────────────────────────────────────────────────
function RadioGroup({ value, onChange, options, style = {} }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, ...style }}>
      {options.map(opt => {
        const active = opt.value === value;
        return (
          <button key={opt.value} type="button" onClick={() => onChange(opt.value)}
            style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              padding: 12,
              background: active ? 'var(--accent)' : 'transparent',
              border: `1px solid ${active ? 'var(--foreground)' : 'var(--border)'}`,
              borderRadius: 'var(--radius)',
              textAlign: 'left', cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
              transition: 'background-color 120ms ease, border-color 120ms ease',
              outline: 'none',
            }}>
            <div style={{
              width: 14, height: 14, borderRadius: '50%',
              border: `1.5px solid ${active ? 'var(--foreground)' : 'var(--muted-foreground)'}`,
              flexShrink: 0, marginTop: 3,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {active && <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--foreground)' }} />}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--foreground)' }}>{opt.label}</span>
              {opt.hint && <span style={{ fontSize: 12, color: 'var(--muted-foreground)' }}>{opt.hint}</span>}
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Progress bar (determinate)
// ──────────────────────────────────────────────────────────────────
function Progress({ value = 0, style = {} }) {
  return (
    <div style={{
      height: 6, background: 'var(--muted)', borderRadius: 999, overflow: 'hidden',
      width: '100%', ...style,
    }}>
      <div style={{
        height: '100%', width: `${Math.max(0, Math.min(100, value))}%`,
        background: 'var(--foreground)',
        borderRadius: 999,
        transition: 'width 400ms ease',
      }} />
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Avatar (initials or icon)
// ──────────────────────────────────────────────────────────────────
function Avatar({ children, size = 28, style = {} }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: 'var(--muted)', color: 'var(--muted-foreground)',
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: size * 0.42,
      flexShrink: 0,
      ...style,
    }}>{children}</div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Tooltip-ish hover label (lightweight, doesn't need portal)
// ──────────────────────────────────────────────────────────────────
function Hint({ children, label, side = 'top', style = {} }) {
  const [show, setShow] = React.useState(false);
  return (
    <span
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      style={{ position: 'relative', display: 'inline-flex', ...style }}
    >
      {children}
      {show && (
        <span style={{
          position: 'absolute',
          [side === 'top' ? 'bottom' : 'top']: '100%',
          left: '50%', transform: 'translateX(-50%)',
          marginBottom: side === 'top' ? 6 : 0, marginTop: side === 'bottom' ? 6 : 0,
          background: 'var(--primary)', color: 'var(--primary-foreground)',
          fontSize: 11, fontWeight: 500, lineHeight: 1.3,
          padding: '4px 8px', borderRadius: 6, whiteSpace: 'nowrap',
          pointerEvents: 'none', zIndex: 20,
          boxShadow: 'var(--shadow-md)',
        }}>{label}</span>
      )}
    </span>
  );
}

// ──────────────────────────────────────────────────────────────────
// Separator
// ──────────────────────────────────────────────────────────────────
function Separator({ vertical = false, style = {} }) {
  return (
    <div style={{
      ...(vertical
        ? { width: 1, alignSelf: 'stretch', borderLeft: '1px solid var(--border)' }
        : { height: 1, borderTop: '1px solid var(--border)', width: '100%' }),
      ...style,
    }} />
  );
}

// ──────────────────────────────────────────────────────────────────
// Small text helpers
// ──────────────────────────────────────────────────────────────────
function Mono({ children, size = 12, dim = false, style = {} }) {
  return <span style={{ fontFamily: 'var(--font-mono)', fontSize: size, color: dim ? 'var(--muted-foreground)' : 'inherit', ...style }}>{children}</span>;
}
function Label({ children, style = {} }) {
  return <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--muted-foreground)', textTransform: 'uppercase', letterSpacing: 0.3, ...style }}>{children}</span>;
}

Object.assign(window, {
  cx, Button, Card, Input, Textarea, Badge, Chip, Tabs, Dialog, RadioGroup,
  Progress, Avatar, Hint, Separator, Mono, Label,
});
