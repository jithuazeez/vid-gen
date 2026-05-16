// Root app — composes the design canvas, tweaks panel, and the wireframe sections.

const ABW = 1280;   // artboard width
const ABH = 760;    // artboard height

function DesignSystemCard() {
  return (
    <div style={{
      width: ABW, height: 520,
      background: wfTokens.paper,
      padding: 32,
      fontFamily: wfTokens.fPrint,
      display: 'flex', flexDirection: 'column', gap: 18,
    }}>
      <Row justify="space-between" align="flex-start">
        <Col gap={4}>
          <span style={{ fontFamily: wfTokens.fHand, fontSize: 44, lineHeight: 1 }}>video.studio</span>
          <Mono dim>conversational multilingual AI video platform · low-fi wireframes</Mono>
        </Col>
        <Sticky rot={2}>3 directions →</Sticky>
      </Row>

      <Divider />

      <Row gap={24} align="flex-start">
        {/* type */}
        <Col gap={8} style={{ flex: 1.2 }}>
          <SectionLabel>type</SectionLabel>
          <Col gap={2}>
            <span style={{ fontFamily: wfTokens.fHand, fontSize: 34, lineHeight: 1 }}>Caveat — headings</span>
            <Mono size={10} dim>display · handwritten · accents</Mono>
          </Col>
          <Col gap={2}>
            <span style={{ fontFamily: wfTokens.fPrint, fontSize: 16 }}>Kalam — body & ui labels</span>
            <Mono size={10} dim>print · conversational copy · buttons</Mono>
          </Col>
          <Col gap={2}>
            <span style={{ fontFamily: wfTokens.fMono, fontSize: 13 }}>JetBrains Mono — data</span>
            <Mono size={10} dim>mono · timecodes · meta · system</Mono>
          </Col>
        </Col>

        {/* palette */}
        <Col gap={8} style={{ flex: 1 }}>
          <SectionLabel>palette</SectionLabel>
          <Row gap={10}>
            {[
              { c: 'var(--paper)',    n: 'paper' },
              { c: 'var(--paper-2)',  n: 'paper-2' },
              { c: 'var(--ink)',      n: 'ink' },
              { c: 'var(--ink-2)',    n: 'ink-2' },
              { c: 'var(--accent)',   n: 'accent' },
              { c: 'var(--accent-2)', n: 'accent-2' },
            ].map(s => (
              <Col key={s.n} gap={4}>
                <div className="wobble" style={{ width: 48, height: 48, background: s.c, border: `1.5px solid ${wfTokens.ink}` }} />
                <Mono size={10} dim>{s.n}</Mono>
              </Col>
            ))}
          </Row>
          <Mono size={10} dim>cream paper · dark ink · 1 highlighter + 1 marker accent</Mono>
        </Col>

        {/* tone */}
        <Col gap={8} style={{ flex: 1.1 }}>
          <SectionLabel>aesthetic notes</SectionLabel>
          <span style={{ fontSize: 13, lineHeight: 1.45, color: wfTokens.ink2 }}>
            Sketch-paper wireframes. Hand-drawn outlines (svg jitter), dashed dividers, mono data, handwriting headings. When this matures to hi-fi: <em>Linear/Vercel minimal monochrome</em> — keep the same structural decisions, swap the typography to a neutral sans, drop the wobble, keep the accent.
          </span>
        </Col>
      </Row>

      <Divider />

      {/* atoms */}
      <Col gap={8}>
        <SectionLabel>atoms</SectionLabel>
        <Row gap={14} align="center" style={{ flexWrap: 'wrap' }}>
          <Btn>button</Btn>
          <Btn primary>primary</Btn>
          <Btn ghost small>ghost</Btn>
          <Chip>chip</Chip>
          <Chip on>chip · on</Chip>
          <Tag>tag</Tag>
          <Avatar ch="GR" />
          <Bubble from="ai">message</Bubble>
          <Bubble from="user">reply</Bubble>
          <Box pad={8}>boxed content</Box>
          <Box pad={8} dashed>dashed</Box>
          <MediaPlaceholder label="scene" w={120} h={68} />
          <Waveform w={120} h={20} />
          <Sticky>note!</Sticky>
        </Row>
      </Col>
    </div>
  );
}

function App() {
  // Tweaks: language switch
  const TWEAKS = /*EDITMODE-BEGIN*/{
    "lang": "EN",
    "theme": "light"
  }/*EDITMODE-END*/;

  const [t, setTweak] = useTweaks(TWEAKS);

  // apply theme to body
  React.useEffect(() => {
    document.body.classList.toggle('theme-dark', t.theme === 'dark');
  }, [t.theme]);

  const lang = t.lang || 'EN';

  return (
    <React.Fragment>
      <DesignCanvas>
        <DCSection id="ds" title="design system" subtitle="type · palette · atoms">
          <DCArtboard id="ds-main" label="design system" width={ABW} height={520}>
            <DesignSystemCard />
          </DCArtboard>
        </DCSection>

        <DCSection id="hero" title="chat + preview · hero" subtitle="the main surface — three layout philosophies">
          <DCArtboard id="hero-a" label="A · document" width={ABW} height={ABH}>
            <ChatPreviewA lang={lang} />
          </DCArtboard>
          <DCArtboard id="hero-b" label="B · studio" width={ABW} height={ABH}>
            <ChatPreviewB lang={lang} />
          </DCArtboard>
          <DCArtboard id="hero-c" label="C · stage" width={ABW} height={ABH}>
            <ChatPreviewC lang={lang} />
          </DCArtboard>
        </DCSection>

        <DCSection id="storyboard" title="scene plan / storyboard" subtitle="reviewing the AI's proposed scenes before generation">
          <DCArtboard id="story-a" label="A · document" width={ABW} height={ABH}>
            <StoryboardA lang={lang} />
          </DCArtboard>
          <DCArtboard id="story-b" label="B · studio" width={ABW} height={ABH}>
            <StoryboardB lang={lang} />
          </DCArtboard>
          <DCArtboard id="story-c" label="C · stage" width={ABW} height={ABH}>
            <StoryboardC lang={lang} />
          </DCArtboard>
        </DCSection>

        <DCSection id="timeline" title="timeline editor + subtitles" subtitle="dynamic subtitle positioning, animated captions, CTA overlays">
          <DCArtboard id="tl-a" label="A · document" width={ABW} height={ABH}>
            <TimelineA lang={lang} />
          </DCArtboard>
          <DCArtboard id="tl-b" label="B · studio" width={ABW} height={ABH}>
            <TimelineB lang={lang} />
          </DCArtboard>
          <DCArtboard id="tl-c" label="C · stage" width={ABW} height={ABH}>
            <TimelineC lang={lang} />
          </DCArtboard>
        </DCSection>

        <DCSection id="supporting" title="supporting screens" subtitle="generation · language · export · library">
          <DCArtboard id="gen" label="generation progress" width={ABW} height={ABH}>
            <Generation lang={lang} />
          </DCArtboard>
          <DCArtboard id="lang" label="language switch" width={ABW} height={ABH}>
            <Language lang={lang} />
          </DCArtboard>
          <DCArtboard id="export" label="export" width={ABW} height={ABH}>
            <Export lang={lang} />
          </DCArtboard>
          <DCArtboard id="library" label="library" width={ABW} height={ABH}>
            <Library lang={lang} />
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
