// Sketchy low-fi wireframe primitives.
// Visual vocab: hand-drawn outlines (SVG turbulence/displacement),
// dashed dividers, marker accents, monospace data, handwriting headings.

const W = {}; // namespace

// Common style objects (named uniquely)
const wfTokens = {
  ink: 'var(--ink)',
  ink2: 'var(--ink-2)',
  ink3: 'var(--ink-3)',
  paper: 'var(--paper)',
  paper2: 'var(--paper-2)',
  accent: 'var(--accent)',
  accent2: 'var(--accent-2)',
  fHand: 'var(--f-hand)',
  fPrint: 'var(--f-print)',
  fMono: 'var(--f-mono)',
};

// ───────────────────────────────────────────────────────────────
// Frame — the artboard chrome (a desktop browser window, sketchy)
// ───────────────────────────────────────────────────────────────
W.Frame = function Frame({ url = "video.studio", children, style = {} }) {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: wfTokens.paper,
      color: wfTokens.ink,
      borderRadius: 6,
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
      fontFamily: wfTokens.fPrint,
      ...style,
    }}>
      <div style={{
        height: 34, flex: '0 0 34px',
        borderBottom: `1.5px dashed ${wfTokens.ink}`,
        display: 'flex', alignItems: 'center', padding: '0 14px', gap: 10,
      }}>
        <span style={dot()} />
        <span style={dot()} />
        <span style={dot()} />
        <div style={{
          flex: 1, marginLeft: 14, height: 18,
          border: `1.5px solid ${wfTokens.ink}`, borderRadius: 9,
          fontFamily: wfTokens.fMono, fontSize: 11,
          display: 'flex', alignItems: 'center', padding: '0 10px',
          color: wfTokens.ink2,
        }}>{url}</div>
      </div>
      <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>{children}</div>
    </div>
  );
  function dot() { return { width: 10, height: 10, borderRadius: '50%', border: `1.5px solid ${wfTokens.ink}` }; }
};

// ───────────────────────────────────────────────────────────────
// Sketchy box — outline with optional wobble filter for hand-drawn feel
// ───────────────────────────────────────────────────────────────
W.Box = function Box({ children, dashed = false, wobble = true, pad = 12, radius = 6, bg, style = {}, ...rest }) {
  return (
    <div
      className={wobble ? 'wobble' : ''}
      style={{
        border: `1.5px ${dashed ? 'dashed' : 'solid'} ${wfTokens.ink}`,
        background: bg || 'transparent',
        borderRadius: radius,
        padding: pad,
        ...style,
      }}
      {...rest}
    >{children}</div>
  );
};

// Box that lays out a row, no wobble (better for compositions)
W.Row = function Row({ children, gap = 10, align = 'center', justify = 'flex-start', style = {} }) {
  return <div style={{ display: 'flex', alignItems: align, justifyContent: justify, gap, ...style }}>{children}</div>;
};
W.Col = function Col({ children, gap = 10, style = {} }) {
  return <div style={{ display: 'flex', flexDirection: 'column', gap, ...style }}>{children}</div>;
};

// ───────────────────────────────────────────────────────────────
// Button (sketchy outline)
// ───────────────────────────────────────────────────────────────
W.Btn = function Btn({ children, primary = false, ghost = false, small = false, style = {} }) {
  return (
    <span className="wobble" style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: small ? '4px 10px' : '6px 14px',
      borderRadius: 999,
      border: `1.5px solid ${wfTokens.ink}`,
      background: primary ? wfTokens.ink : (ghost ? 'transparent' : wfTokens.paper),
      color: primary ? wfTokens.paper : wfTokens.ink,
      fontFamily: wfTokens.fPrint,
      fontSize: small ? 13 : 15,
      lineHeight: 1,
      ...style,
    }}>{children}</span>
  );
};

// Chip — small pill, for tags and chat suggestions
W.Chip = function Chip({ children, on = false, style = {} }) {
  return (
    <span className="wobble" style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '4px 10px',
      borderRadius: 999,
      border: `1.25px solid ${wfTokens.ink}`,
      background: on ? wfTokens.accent : 'transparent',
      fontFamily: wfTokens.fPrint, fontSize: 13, lineHeight: 1.1,
      ...style,
    }}>{children}</span>
  );
};

// Tag — square label (mono)
W.Tag = function Tag({ children, style = {} }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 6px',
      border: `1px solid ${wfTokens.ink}`,
      fontFamily: wfTokens.fMono, fontSize: 10,
      textTransform: 'uppercase', letterSpacing: 0.5,
      ...style,
    }}>{children}</span>
  );
};

// Sticky note — yellow highlight annotation
W.Sticky = function Sticky({ children, rot = -1.5, style = {} }) {
  return (
    <div style={{
      display: 'inline-block',
      background: wfTokens.accent,
      padding: '6px 10px',
      transform: `rotate(${rot}deg)`,
      fontFamily: wfTokens.fHand, fontSize: 16, lineHeight: 1.1,
      boxShadow: '2px 2px 0 rgba(0,0,0,0.15)',
      ...style,
    }}>{children}</div>
  );
};

// Heading — handwritten
W.H = function H({ children, size = 28, style = {} }) {
  return <div style={{ fontFamily: wfTokens.fHand, fontSize: size, lineHeight: 1, ...style }}>{children}</div>;
};

// Mono data line
W.Mono = function Mono({ children, size = 11, dim = false, style = {} }) {
  return <span style={{ fontFamily: wfTokens.fMono, fontSize: size, color: dim ? wfTokens.ink3 : wfTokens.ink2, ...style }}>{children}</span>;
};

// Squiggly underline (for headings, labels)
W.Squiggle = function Squiggle({ w = 80, color }) {
  const c = color || wfTokens.ink;
  return (
    <svg width={w} height="6" viewBox={`0 0 ${w} 6`} aria-hidden="true" style={{ display: 'block' }}>
      <path d={`M 0 3 Q ${w*0.1} 0 ${w*0.2} 3 T ${w*0.4} 3 T ${w*0.6} 3 T ${w*0.8} 3 T ${w} 3`}
            fill="none" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
};

// Arrow (sketchy)
W.Arrow = function Arrow({ dir = 'right', length = 40, color }) {
  const c = color || wfTokens.ink;
  const lengths = { right: [0,0,length,0], down: [0,0,0,length], left: [length,0,0,0], up: [0,length,0,0] };
  const [x1,y1,x2,y2] = lengths[dir];
  const w = Math.max(Math.abs(x2-x1)+12, 16);
  const h = Math.max(Math.abs(y2-y1)+12, 16);
  return (
    <svg className="wobble" width={w} height={h} style={{ display: 'inline-block' }}>
      <line x1={x1+6} y1={y1+6} x2={x2+6} y2={y2+6} stroke={c} strokeWidth="1.5" strokeLinecap="round" />
      {dir === 'right' && <polyline points={`${x2+0},${y2+2} ${x2+6},${y2+6} ${x2+0},${y2+10}`} fill="none" stroke={c} strokeWidth="1.5" strokeLinecap="round" />}
      {dir === 'down' && <polyline points={`${x2+2},${y2+0} ${x2+6},${y2+6} ${x2+10},${y2+0}`} fill="none" stroke={c} strokeWidth="1.5" strokeLinecap="round" />}
    </svg>
  );
};

// Image / video placeholder — diagonal lines + label
W.MediaPlaceholder = function MediaPlaceholder({ label = "scene", ratio, w, h, style = {} }) {
  const width = w || (ratio === '9:16' ? 140 : ratio === '1:1' ? 200 : 280);
  const height = h || (ratio === '9:16' ? 250 : ratio === '1:1' ? 200 : 158);
  return (
    <div className="wobble" style={{
      width, height,
      border: `1.5px solid ${wfTokens.ink}`,
      borderRadius: 4,
      position: 'relative',
      overflow: 'hidden',
      background: wfTokens.paper2,
      ...style,
    }}>
      <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, opacity: 0.6 }}>
        <line x1="0" y1="0" x2="100%" y2="100%" stroke={wfTokens.ink} strokeWidth="0.75" />
        <line x1="100%" y1="0" x2="0" y2="100%" stroke={wfTokens.ink} strokeWidth="0.75" />
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: wfTokens.fMono, fontSize: 10, color: wfTokens.ink2,
        textTransform: 'uppercase', letterSpacing: 1,
      }}>{label}</div>
    </div>
  );
};

// Waveform placeholder
W.Waveform = function Waveform({ w = 200, h = 28, seed = 1, color }) {
  const c = color || wfTokens.ink;
  const bars = 40;
  const rng = (i) => (Math.sin(i * 12.9898 + seed * 78.233) * 43758.5453) % 1;
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      {Array.from({ length: bars }).map((_, i) => {
        const r = Math.abs(rng(i));
        const bh = 4 + r * (h - 6);
        return <rect key={i} x={(i / bars) * w} y={(h - bh) / 2} width={(w / bars) * 0.6} height={bh} fill={c} opacity={0.85} />;
      })}
    </svg>
  );
};

// Chat bubble
W.Bubble = function Bubble({ from = 'ai', children, style = {} }) {
  const isUser = from === 'user';
  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      ...style,
    }}>
      <div className="wobble" style={{
        maxWidth: '85%',
        border: `1.5px solid ${wfTokens.ink}`,
        background: isUser ? wfTokens.paper2 : 'transparent',
        borderRadius: isUser ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
        padding: '8px 12px',
        fontFamily: wfTokens.fPrint, fontSize: 14, lineHeight: 1.3,
      }}>{children}</div>
    </div>
  );
};

// Avatar circle (initials)
W.Avatar = function Avatar({ ch = 'AI', size = 24 }) {
  return (
    <div className="wobble" style={{
      width: size, height: size, borderRadius: '50%',
      border: `1.5px solid ${wfTokens.ink}`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: wfTokens.fMono, fontSize: size * 0.4,
      flex: `0 0 ${size}px`,
    }}>{ch}</div>
  );
};

// Section label — small caps with squiggle
W.SectionLabel = function SectionLabel({ children, style = {} }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, ...style }}>
      <span style={{ fontFamily: wfTokens.fMono, fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: wfTokens.ink2 }}>{children}</span>
    </div>
  );
};

// Dashed divider
W.Divider = function Divider({ vertical = false, style = {} }) {
  if (vertical) return <div style={{ width: 0, alignSelf: 'stretch', borderLeft: `1.5px dashed ${wfTokens.ink}`, opacity: 0.7, ...style }} />;
  return <div style={{ height: 0, borderTop: `1.5px dashed ${wfTokens.ink}`, opacity: 0.7, ...style }} />;
};

// Icon (rough hand-drawn symbol) — minimal set
W.Icon = function Icon({ kind, size = 16, color }) {
  const c = color || wfTokens.ink;
  const props = { width: size, height: size, viewBox: '0 0 16 16', fill: 'none', stroke: c, strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round' };
  switch (kind) {
    case 'play':    return <svg className="wobble" {...props}><polygon points="5,3 13,8 5,13" /></svg>;
    case 'pause':   return <svg className="wobble" {...props}><line x1="5" y1="3" x2="5" y2="13" /><line x1="11" y1="3" x2="11" y2="13" /></svg>;
    case 'plus':    return <svg className="wobble" {...props}><line x1="8" y1="2" x2="8" y2="14" /><line x1="2" y1="8" x2="14" y2="8" /></svg>;
    case 'send':    return <svg className="wobble" {...props}><line x1="2" y1="8" x2="14" y2="8" /><polyline points="10,4 14,8 10,12" /></svg>;
    case 'mic':     return <svg className="wobble" {...props}><rect x="6" y="2" width="4" height="8" rx="2" /><path d="M4 9 a4 4 0 0 0 8 0" /><line x1="8" y1="13" x2="8" y2="15" /></svg>;
    case 'globe':   return <svg className="wobble" {...props}><circle cx="8" cy="8" r="6" /><line x1="2" y1="8" x2="14" y2="8" /><path d="M8 2 Q 4 8 8 14 Q 12 8 8 2" /></svg>;
    case 'download':return <svg className="wobble" {...props}><line x1="8" y1="2" x2="8" y2="10" /><polyline points="4,7 8,11 12,7" /><line x1="3" y1="14" x2="13" y2="14" /></svg>;
    case 'gear':    return <svg className="wobble" {...props}><circle cx="8" cy="8" r="2.5" /><path d="M8 1 v2 M8 13 v2 M1 8 h2 M13 8 h2 M3 3 l1.5 1.5 M11.5 11.5 L13 13 M3 13 l1.5-1.5 M11.5 4.5 L13 3" /></svg>;
    case 'edit':    return <svg className="wobble" {...props}><path d="M3 13 L3 11 L11 3 L13 5 L5 13 Z" /></svg>;
    case 'refresh': return <svg className="wobble" {...props}><path d="M3 8 a5 5 0 0 1 9 -3" /><polyline points="12,2 12,5 9,5" /><path d="M13 8 a5 5 0 0 1 -9 3" /><polyline points="4,14 4,11 7,11" /></svg>;
    case 'check':   return <svg className="wobble" {...props}><polyline points="3,8 7,12 13,4" /></svg>;
    case 'circle':  return <svg className="wobble" {...props}><circle cx="8" cy="8" r="6" /></svg>;
    case 'square':  return <svg className="wobble" {...props}><rect x="3" y="3" width="10" height="10" /></svg>;
    case 'sub':     return <svg className="wobble" {...props}><rect x="2" y="3" width="12" height="10" rx="1" /><line x1="4" y1="9" x2="9" y2="9" /><line x1="4" y1="11" x2="11" y2="11" /></svg>;
    case 'wand':    return <svg className="wobble" {...props}><line x1="3" y1="13" x2="11" y2="5" /><line x1="11" y1="3" x2="11" y2="5" /><line x1="9" y1="3" x2="13" y2="3" /><line x1="13" y1="5" x2="13" y2="7" /></svg>;
    case 'folder':  return <svg className="wobble" {...props}><path d="M2 5 L2 12 L14 12 L14 6 L8 6 L7 4 L2 4 Z" /></svg>;
    case 'spark':   return <svg className="wobble" {...props}><path d="M8 2 L9 7 L14 8 L9 9 L8 14 L7 9 L2 8 L7 7 Z" /></svg>;
    default: return null;
  }
};

// Annotation — hand-drawn arrow pointing at something, with handwriting note
W.Note = function Note({ children, style = {} }) {
  return (
    <div style={{
      fontFamily: wfTokens.fHand,
      fontSize: 18,
      color: wfTokens.ink2,
      transform: 'rotate(-1.5deg)',
      ...style,
    }}>{children}</div>
  );
};

Object.assign(window, W);
Object.assign(window, { wfTokens });
