// Supporting screens — Generation Progress · Language Switch · Export · Library
// One tight wireframe per supporting screen.

const SSUP = {};

// ─── Generation Progress ──────────────────────────────────────
SSUP.Generation = function Generation({ lang = 'EN' }) {
  const steps = [
    { k: 'plan',      label: 'scene planning',       state: 'done',    note: '4 scenes · 0:28' },
    { k: 'video',     label: 'video generation',     state: 'done',    note: '4 / 4 scenes' },
    { k: 'voice',     label: 'voice generation',     state: 'running', note: `${lang} · 2 / 4 lines` },
    { k: 'lipsync',   label: 'lip sync',             state: 'queued',  note: 'GPU queue: 3rd' },
    { k: 'subs',      label: 'subtitle render',      state: 'queued',  note: lang },
    { k: 'overlay',   label: 'overlay + text',       state: 'queued',  note: 'logo · CTA' },
    { k: 'compose',   label: 'timeline composite',   state: 'queued',  note: '—' },
    { k: 'export',    label: 'export · 1:1 · mp4',   state: 'queued',  note: '—' },
  ];
  return (
    <Frame url="video.studio/c/diwali-tea-ad/render">
      <Col gap={0} style={{ height: '100%', padding: '20px 36px' }}>
        <Row justify="space-between" style={{ marginBottom: 14 }}>
          <Col gap={2}>
            <H size={28}>Rendering…</H>
            <Mono dim>est. 02:48 remaining · job #r-7421</Mono>
          </Col>
          <Row gap={8}>
            <Btn small ghost>cancel</Btn>
            <Btn small>render in background</Btn>
          </Row>
        </Row>

        <Row gap={20} align="flex-start">
          {/* preview */}
          <Col gap={8} style={{ width: 360 }}>
            <MediaPlaceholder label="rendering scene 02 · kitchen" w={360} h={360} />
            <Row gap={6}>
              <Tag>1:1</Tag><Tag>mp4</Tag><Tag>{lang}</Tag>
            </Row>
          </Col>

          {/* step list */}
          <Col gap={8} style={{ flex: 1 }}>
            <SectionLabel>pipeline</SectionLabel>
            {steps.map((s, i) => {
              const isDone = s.state === 'done';
              const isRun  = s.state === 'running';
              return (
                <Row key={s.k} gap={10} align="center">
                  <div style={{ width: 18, height: 18, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {isDone ? <Icon kind="check" size={14} /> : isRun ? <Icon kind="spark" size={14} /> : <Icon kind="circle" size={12} color={wfTokens.ink3}/>}
                  </div>
                  <Mono size={12} style={{ width: 160, color: isRun ? wfTokens.ink : wfTokens.ink2 }}>{s.label}</Mono>
                  <div style={{ flex: 1, height: 10, border: `1.25px solid ${isRun ? wfTokens.ink : wfTokens.ink2}`, borderRadius: 6, position: 'relative', overflow: 'hidden' }} className={isRun ? 'wobble' : ''}>
                    <div style={{ position: 'absolute', inset: 0, width: isDone ? '100%' : isRun ? '52%' : '0%', background: isDone ? wfTokens.ink2 : wfTokens.accent }} />
                  </div>
                  <Mono dim size={11} style={{ width: 120, textAlign: 'right' }}>{s.note}</Mono>
                </Row>
              );
            })}

            <Box pad={10} dashed style={{ marginTop: 10 }}>
              <Row gap={8}>
                <Sticky rot={-2}>switching language?</Sticky>
                <span style={{ fontSize: 13, color: wfTokens.ink2, lineHeight: 1.4 }}>
                  Visual scenes stay. Only voice, lip-sync, subtitles & overlays regenerate.
                </span>
              </Row>
            </Box>
          </Col>
        </Row>
      </Col>
    </Frame>
  );
};

// ─── Language Switch ──────────────────────────────────────────
SSUP.Language = function Language({ lang = 'EN' }) {
  const langs = [
    { code: 'EN', name: 'English',  native: 'English' },
    { code: 'HI', name: 'Hindi',    native: 'हिन्दी' },
    { code: 'MR', name: 'Marathi',  native: 'मराठी' },
    { code: 'TA', name: 'Tamil',    native: 'தமிழ்' },
    { code: 'PA', name: 'Punjabi',  native: 'ਪੰਜਾਬੀ' },
  ];
  const regen = [
    { k: 'voice',   on: true,  label: 'narration' },
    { k: 'sub',     on: true,  label: 'subtitles' },
    { k: 'lip',     on: true,  label: 'lip sync' },
    { k: 'overlay', on: true,  label: 'text overlays' },
    { k: 'video',   on: false, label: 'visual scenes (skipped)' },
  ];
  return (
    <Frame url="video.studio/c/diwali-tea-ad/language">
      <Col gap={0} style={{ height: '100%', padding: '24px 36px' }}>
        <Col gap={4}>
          <H size={28}>Change language</H>
          <Mono dim>visual scenes are reused — only audio + text regenerate</Mono>
        </Col>

        <Row gap={20} style={{ marginTop: 20, flex: 1, alignItems: 'flex-start' }}>
          {/* picker */}
          <Col gap={8} style={{ flex: 1 }}>
            <SectionLabel>target language</SectionLabel>
            {langs.map(l => {
              const on = l.code === lang;
              return (
                <Box key={l.code} pad={12} style={{ background: on ? wfTokens.accent : 'transparent', cursor: 'pointer' }}>
                  <Row justify="space-between">
                    <Row gap={10}>
                      <Mono size={12} style={{ width: 28 }}>{l.code}</Mono>
                      <span style={{ fontSize: 15 }}>{l.name}</span>
                      <span style={{ fontFamily: wfTokens.fHand, fontSize: 18, color: wfTokens.ink2 }}>{l.native}</span>
                    </Row>
                    {on && <Icon kind="check" size={14}/>}
                  </Row>
                </Box>
              );
            })}
          </Col>

          {/* what regenerates */}
          <Col gap={10} style={{ flex: 1 }}>
            <SectionLabel>what will regenerate</SectionLabel>
            {regen.map(r => (
              <Row key={r.k} gap={10}>
                <Icon kind={r.on ? 'check' : 'circle'} size={14} color={r.on ? wfTokens.ink : wfTokens.ink3}/>
                <span style={{ fontSize: 14, color: r.on ? wfTokens.ink : wfTokens.ink3, textDecoration: r.on ? 'none' : 'line-through' }}>{r.label}</span>
              </Row>
            ))}
            <Box pad={10} dashed style={{ marginTop: 10 }}>
              <Row gap={8} justify="space-between">
                <Mono>est. time</Mono>
                <Mono>~ 1:40</Mono>
              </Row>
              <Row gap={8} justify="space-between">
                <Mono>credits</Mono>
                <Mono>− 18</Mono>
              </Row>
            </Box>
            <Row gap={8} style={{ marginTop: 6 }}>
              <Btn small ghost>cancel</Btn>
              <Btn small primary>regenerate in {lang} →</Btn>
            </Row>
          </Col>
        </Row>
      </Col>
    </Frame>
  );
};

// ─── Export ───────────────────────────────────────────────────
SSUP.Export = function Export({ lang = 'EN' }) {
  return (
    <Frame url="video.studio/c/diwali-tea-ad/export">
      <Col gap={0} style={{ height: '100%', padding: '24px 36px' }}>
        <Row justify="space-between" style={{ marginBottom: 14 }}>
          <Col gap={2}>
            <H size={28}>Export</H>
            <Mono dim>diwali-tea-ad · {lang} · 0:28</Mono>
          </Col>
          <Btn primary><Icon kind="download" size={14}/> render & download</Btn>
        </Row>

        <Row gap={24} style={{ flex: 1, alignItems: 'flex-start' }}>
          <Col gap={10} style={{ flex: 1.2 }}>
            <MediaPlaceholder label="final preview · 1:1" w={'100%'} h={360} style={{ width: '100%' }} />
            <Row gap={8}><Tag>{lang}</Tag><Tag>subs · burned</Tag><Tag>CTA at 0:26</Tag></Row>
          </Col>

          <Col gap={14} style={{ flex: 1 }}>
            <Col gap={6}>
              <SectionLabel>aspect ratio</SectionLabel>
              <Row gap={6}>
                <Chip on>1:1</Chip><Chip>9:16</Chip><Chip>16:9</Chip><Chip>4:5</Chip>
              </Row>
            </Col>

            <Col gap={6}>
              <SectionLabel>format</SectionLabel>
              <Row gap={6}><Chip on>mp4 · h264</Chip><Chip>mov</Chip><Chip>webm</Chip><Chip>gif</Chip></Row>
            </Col>

            <Col gap={6}>
              <SectionLabel>quality</SectionLabel>
              <Row gap={6}><Chip>720p</Chip><Chip on>1080p</Chip><Chip>2k</Chip></Row>
            </Col>

            <Col gap={6}>
              <SectionLabel>subtitles</SectionLabel>
              <Row gap={6}><Chip on>burned in</Chip><Chip>separate .srt</Chip><Chip>off</Chip></Row>
            </Col>

            <Col gap={6}>
              <SectionLabel>also export in</SectionLabel>
              <Row gap={6} style={{ flexWrap: 'wrap' }}>
                <Chip>+ EN</Chip><Chip>+ HI</Chip><Chip>+ MR</Chip><Chip>+ TA</Chip><Chip>+ PA</Chip>
              </Row>
              <Mono dim>reuses scenes · only audio + text regenerate</Mono>
            </Col>
          </Col>
        </Row>
      </Col>
    </Frame>
  );
};

// ─── Library ──────────────────────────────────────────────────
SSUP.Library = function Library({ lang = 'EN' }) {
  const projects = [
    { name: 'diwali tea ad',      meta: '0:28 · 1:1 · 5 langs', state: 'rendered',  updated: '2 min ago' },
    { name: 'monsoon promo',      meta: '0:15 · 9:16 · EN',     state: 'rendering', updated: 'now' },
    { name: 'product launch v2',  meta: '1:12 · 16:9 · EN/HI',  state: 'draft',     updated: 'yesterday' },
    { name: 'employee anniv reel', meta: '0:45 · 1:1 · EN',     state: 'rendered',  updated: '3d ago' },
    { name: 'kid story · pilot',   meta: '2:08 · 16:9 · MR',    state: 'draft',     updated: 'last week' },
    { name: 'investor update',     meta: '1:30 · 16:9 · EN',    state: 'rendered',  updated: '2w ago' },
  ];
  return (
    <Frame url="video.studio">
      <Col gap={0} style={{ height: '100%' }}>
        <Row style={{ padding: '14px 28px', borderBottom: `1.5px dashed ${wfTokens.ink}`, justifyContent: 'space-between' }}>
          <Row gap={12}>
            <Icon kind="spark" size={18}/>
            <span style={{ fontFamily: wfTokens.fHand, fontSize: 22 }}>video.studio</span>
          </Row>
          <Row gap={8}>
            <Btn small ghost><Icon kind="folder" size={12}/> all projects</Btn>
            <Btn small primary><Icon kind="plus" size={12}/> new video</Btn>
          </Row>
        </Row>

        <Col gap={12} style={{ flex: 1, padding: '20px 28px', overflow: 'hidden' }}>
          <Row justify="space-between">
            <H size={26}>your videos</H>
            <Row gap={6}>
              <Chip on>all</Chip><Chip>drafts</Chip><Chip>rendering</Chip><Chip>rendered</Chip>
            </Row>
          </Row>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
            {projects.map((p, i) => (
              <Box key={p.name} pad={12} style={{ background: i === 0 ? wfTokens.paper2 : 'transparent' }}>
                <Col gap={8}>
                  <MediaPlaceholder label={p.name} w={'100%'} h={120} style={{ width: '100%' }} />
                  <Row justify="space-between" align="flex-start">
                    <Col gap={2}>
                      <span style={{ fontFamily: wfTokens.fHand, fontSize: 20, lineHeight: 1 }}>{p.name}</span>
                      <Mono size={10} dim>{p.meta}</Mono>
                    </Col>
                    <Tag>{p.state}</Tag>
                  </Row>
                  <Row justify="space-between">
                    <Mono size={10} dim>{p.updated}</Mono>
                    <Row gap={6}>
                      <Icon kind="play" size={12}/>
                      <Icon kind="edit" size={12}/>
                      <Icon kind="download" size={12}/>
                    </Row>
                  </Row>
                </Col>
              </Box>
            ))}
          </div>
        </Col>
      </Col>
    </Frame>
  );
};

Object.assign(window, SSUP);
