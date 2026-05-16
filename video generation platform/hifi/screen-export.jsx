// Screen 5: Export modal — configure → rendering → done.

function ExportModal() {
  const { state, dispatch } = useApp();
  const { exportOpen, exportState, exportProgress, exportOptions, language, brief } = state;

  // Simulated render progress
  React.useEffect(() => {
    if (exportState !== 'rendering') return;
    let raf;
    const start = performance.now();
    const TOTAL = 4500;
    const tick = (now) => {
      const t = now - start;
      const p = Math.min(100, Math.round((t / TOTAL) * 100));
      dispatch({ type: 'SET_EXPORT_PROG', value: p });
      if (p >= 100) {
        setTimeout(() => dispatch({ type: 'SET_EXPORT_STATE', value: 'done' }), 300);
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line
  }, [exportState]);

  const close = () => {
    dispatch({ type: 'CLOSE_EXPORT' });
    // reset state so reopening is fresh
    setTimeout(() => {
      dispatch({ type: 'SET_EXPORT_STATE', value: 'configure' });
      dispatch({ type: 'SET_EXPORT_PROG', value: 0 });
    }, 200);
  };

  const startExport = () => {
    dispatch({ type: 'SET_EXPORT_STATE', value: 'rendering' });
    dispatch({ type: 'SET_EXPORT_PROG', value: 0 });
  };

  return (
    <Dialog open={exportOpen} onOpenChange={() => close()} width={480}>
      {exportState === 'configure' && (
        <ConfigureView
          options={exportOptions}
          language={language}
          brief={brief}
          onChange={(patch) => dispatch({ type: 'SET_EXPORT_OPT', patch })}
          onCancel={close}
          onStart={startExport}
        />
      )}
      {exportState === 'rendering' && (
        <RenderingView progress={exportProgress} onClose={close} />
      )}
      {exportState === 'done' && (
        <DoneView options={exportOptions} language={language} brief={brief} onClose={close} />
      )}
    </Dialog>
  );
}

function ConfigureView({ options, language, brief, onChange, onCancel, onStart }) {
  return (
    <>
      <div style={{ padding: '20px 24px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600, letterSpacing: -0.3 }}>Export video</h3>
          <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--muted-foreground)' }}>
            Render a final file for download or sharing.
          </p>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onCancel}><ICON.X size={16} /></Button>
      </div>

      <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 18 }}>
        <Row label="Language">
          <Badge variant="secondary"><ICON.Globe size={11} /> {language}</Badge>
          <span style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>(from review)</span>
        </Row>
        <Row label="Format">
          <Chip selected>MP4</Chip>
          <Mono dim size={11}>more formats soon</Mono>
        </Row>
        <Row label="Quality">
          <div style={{ display: 'flex', gap: 6 }}>
            {['720p', '1080p'].map(q => (
              <Chip key={q} selected={options.quality === q} onClick={() => onChange({ quality: q })}>{q}</Chip>
            ))}
          </div>
        </Row>
        <Row label="Aspect">
          <Badge variant="secondary">{brief.aspect || '9:16'}</Badge>
          <span style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>(locked from brief)</span>
        </Row>
        <Row label="Subtitles">
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <Chip selected={options.subtitles === 'burned'}  onClick={() => onChange({ subtitles: 'burned' })}>Burned in</Chip>
            <Chip selected={options.subtitles === 'sidecar'} onClick={() => onChange({ subtitles: 'sidecar' })}>Sidecar .srt</Chip>
            <Chip selected={options.subtitles === 'both'}    onClick={() => onChange({ subtitles: 'both' })}>Both</Chip>
          </div>
        </Row>
        <Separator />
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 13, color: 'var(--muted-foreground)' }}>Estimated size</span>
          <Mono size={13}>~ {options.quality === '720p' ? '7.8' : '14.2'} MB</Mono>
        </div>
      </div>

      <div style={{ padding: '14px 24px', display: 'flex', justifyContent: 'flex-end', gap: 8, borderTop: '1px solid var(--border)' }}>
        <Button variant="ghost" size="md" onClick={onCancel}>Cancel</Button>
        <Button size="md" onClick={onStart}>
          <ICON.Download size={14} /> Start export
        </Button>
      </div>
    </>
  );
}

function Row({ label, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ width: 100, fontSize: 13, color: 'var(--muted-foreground)' }}>{label}</div>
      <div style={{ flex: 1, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>{children}</div>
    </div>
  );
}

function RenderingView({ progress, onClose }) {
  const stageText = progress < 25 ? 'Muxing audio…'
                  : progress < 60 ? 'Burning subtitles…'
                  : progress < 90 ? 'Encoding video…'
                  : 'Finalising file…';
  return (
    <>
      <div style={{ padding: '20px 24px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)' }}>
        <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Exporting…</h3>
        <Button variant="ghost" size="icon-sm" onClick={onClose}><ICON.X size={16} /></Button>
      </div>
      <div style={{ padding: '24px 24px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 14, color: 'var(--muted-foreground)' }}>{stageText}</span>
          <Mono size={14}>{progress}%</Mono>
        </div>
        <Progress value={progress} />
        <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--muted-foreground)', lineHeight: 1.5 }}>
          You can close this window — we'll keep going in the background and notify you when it's done.
        </p>
      </div>
    </>
  );
}

function DoneView({ options, language, brief, onClose }) {
  const filename = `northbean_${language.toLowerCase()}_${options.quality}.mp4`;
  const size = options.quality === '720p' ? '7.8' : '14.2';
  return (
    <>
      <div style={{ padding: '20px 24px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 28, height: 28, borderRadius: '50%',
            background: 'hsl(142 71% 45%)', color: 'white',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}><ICON.Check size={16} strokeWidth={3} /></div>
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Export ready</h3>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose}><ICON.X size={16} /></Button>
      </div>
      <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: 12, borderRadius: 'var(--radius)', border: '1px solid var(--border)',
          background: 'var(--muted)',
        }}>
          <div style={{
            width: 40, height: 40, borderRadius: 6,
            background: 'var(--background)', border: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <ICON.Video size={18} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{filename}</div>
            <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
              {size} MB · {brief.aspect || '9:16'} · {options.subtitles === 'burned' ? 'burned subs' : options.subtitles === 'sidecar' ? 'sidecar .srt' : 'subs + .srt'} · {language}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button style={{ flex: 1 }}><ICON.Download size={14} /> Download</Button>
          <Button variant="outline" style={{ flex: 1 }}><ICON.Copy size={14} /> Copy link</Button>
        </div>
        <p style={{ margin: 0, fontSize: 11, color: 'var(--muted-foreground)', textAlign: 'center' }}>
          Signed link expires in 1 hour.
        </p>
      </div>
    </>
  );
}

window.ExportModal = ExportModal;
