// Screenflow v2 — committed direction following screenflow.md
const SF_ABW = 1280;
const SF_ABH = 800;

function SystemNote() {
  return (
    <div style={{
      width: SF_ABW, height: 360,
      background: wfTokens.paper,
      padding: 32, display: 'flex', flexDirection: 'column', gap: 14, fontFamily: wfTokens.fPrint,
    }}>
      <Row justify="space-between" align="flex-start">
        <Col gap={4}>
          <span style={{ fontFamily: wfTokens.fHand, fontSize: 40, lineHeight: 1 }}>screenflow · v2</span>
          <Mono dim>one committed direction · 5 screens · agent-driven chat with suggestion chips on every question</Mono>
        </Col>
        <Sticky rot={2}>follows screenflow.md →</Sticky>
      </Row>
      <Divider />

      <Row gap={28} align="flex-start">
        <Col gap={6} style={{ flex: 1 }}>
          <SectionLabel>flow</SectionLabel>
          <Row gap={6} align="center" style={{ flexWrap: 'wrap' }}>
            <Chip>welcome</Chip><Arrow length={16}/>
            <Chip>chat</Chip><Arrow length={16}/>
            <Chip>storyboard</Chip><Arrow length={16}/>
            <Chip>progress</Chip><Arrow length={16}/>
            <Chip>review</Chip><Arrow length={16}/>
            <Chip>export</Chip>
          </Row>
        </Col>
        <Col gap={6} style={{ flex: 1 }}>
          <SectionLabel>chat principles</SectionLabel>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.55, color: wfTokens.ink2 }}>
            <li>agent drives — one question at a time</li>
            <li>every question has chips · tap = send</li>
            <li>typing always wins · chips are shortcuts</li>
            <li>brief summary fills as you go (3/10 → 10/10)</li>
            <li>start planning enables only when ready</li>
          </ul>
        </Col>
        <Col gap={6} style={{ flex: 1 }}>
          <SectionLabel>state map</SectionLabel>
          <Box pad={10} dashed>
            <Col gap={4}>
              {[
                ['draft / collecting', 'chat'],
                ['planning',           'storyboard · skeletons'],
                ['rendering',          'progress · sse driven'],
                ['ready / completed',  'review · edit · export'],
                ['failed',             'inline banner + retry'],
              ].map(([s, w]) => (
                <Row key={s} justify="space-between"><Mono size={10}>{s}</Mono><Mono size={10} dim>{w}</Mono></Row>
              ))}
            </Col>
          </Box>
        </Col>
      </Row>
    </div>
  );
}

function App() {
  const TWEAKS = /*EDITMODE-BEGIN*/{
    "lang": "EN",
    "theme": "light"
  }/*EDITMODE-END*/;

  const [t, setTweak] = useTweaks(TWEAKS);

  React.useEffect(() => {
    document.body.classList.toggle('theme-dark', t.theme === 'dark');
  }, [t.theme]);

  const lang = t.lang || 'EN';

  return (
    <React.Fragment>
      <DesignCanvas>
        <DCSection id="system" title="system" subtitle="agent-driven · chip-suggestion chat · linear 5-screen flow">
          <DCArtboard id="sys" label="overview" width={SF_ABW} height={360}>
            <SystemNote />
          </DCArtboard>
        </DCSection>

        <DCSection id="entry" title="entry" subtitle="single CTA · no list to be empty">
          <DCArtboard id="welcome" label="0 · welcome" width={SF_ABW} height={SF_ABH}>
            <Welcome />
          </DCArtboard>
        </DCSection>

        <DCSection id="chat" title="1 · chat" subtitle="agent drives · chip suggestions on every turn · brief summary on the right">
          <DCArtboard id="chat-mid" label="A · in progress · 3 of 10" width={SF_ABW} height={SF_ABH}>
            <Chat lang={lang} ready={false} />
          </DCArtboard>
          <DCArtboard id="chat-ready" label="B · ready to plan · 10 of 10" width={SF_ABW} height={SF_ABH}>
            <Chat lang={lang} ready={true} />
          </DCArtboard>
        </DCSection>

        <DCSection id="story" title="2 · storyboard" subtitle="approval gate · click a card to open the detail panel">
          <DCArtboard id="story-grid" label="A · grid" width={SF_ABW} height={SF_ABH}>
            <Storyboard lang={lang} openDetail={false} />
          </DCArtboard>
          <DCArtboard id="story-detail" label="B · grid + detail panel open" width={SF_ABW} height={SF_ABH}>
            <Storyboard lang={lang} openDetail={true} />
          </DCArtboard>
        </DCSection>

        <DCSection id="progress" title="3 · progress" subtitle="60–180s render · pipeline stepper + per-scene cards">
          <DCArtboard id="prog" label="generating…" width={SF_ABW} height={SF_ABH}>
            <Progress lang={lang} />
          </DCArtboard>
        </DCSection>

        <DCSection id="review" title="4 · review & edit" subtitle="player + multi-track timeline · right-panel tabs">
          <DCArtboard id="rev-subs" label="A · subtitles tab" width={SF_ABW} height={SF_ABH}>
            <Review lang={lang} tab="subtitles" />
          </DCArtboard>
          <DCArtboard id="rev-overlays" label="B · overlays tab" width={SF_ABW} height={SF_ABH}>
            <Review lang={lang} tab="overlays" />
          </DCArtboard>
          <DCArtboard id="rev-audio" label="C · audio tab" width={SF_ABW} height={SF_ABH}>
            <Review lang={lang} tab="audio" />
          </DCArtboard>
          <DCArtboard id="rev-scenes" label="D · scenes tab" width={SF_ABW} height={SF_ABH}>
            <Review lang={lang} tab="scenes" />
          </DCArtboard>
        </DCSection>

        <DCSection id="export" title="5 · export modal" subtitle="three states · configure → progress → done">
          <DCArtboard id="exp-config" label="A · configure" width={SF_ABW} height={SF_ABH}>
            <ExportScreen lang={lang} state="configure" />
          </DCArtboard>
          <DCArtboard id="exp-prog" label="B · exporting" width={SF_ABW} height={SF_ABH}>
            <ExportScreen lang={lang} state="progress" />
          </DCArtboard>
          <DCArtboard id="exp-done" label="C · ready" width={SF_ABW} height={SF_ABH}>
            <ExportScreen lang={lang} state="done" />
          </DCArtboard>
        </DCSection>
      </DesignCanvas>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Theme">
          <TweakRadio label="mode" value={t.theme} onChange={v => setTweak('theme', v)}
            options={[{value:'light', label:'light'},{value:'dark', label:'dark'}]} />
        </TweakSection>
        <TweakSection label="Language">
          <TweakSelect label="active" value={t.lang} onChange={v => setTweak('lang', v)}
            options={[
              { value: 'EN', label: 'English' },
              { value: 'HI', label: 'हिन्दी · Hindi' },
              { value: 'MR', label: 'मराठी · Marathi' },
              { value: 'TA', label: 'தமிழ் · Tamil' },
              { value: 'PA', label: 'ਪੰਜਾਬੀ · Punjabi' },
            ]} />
        </TweakSection>
      </TweaksPanel>
    </React.Fragment>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
