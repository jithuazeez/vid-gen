// Screen 3: Timeline Editor (subtitle + overlay editing) — 3 directions

const SCT = {};

const sceneClips = [
  { n: '01', label: 'lamp',     w: 0.18 },
  { n: '02', label: 'kitchen',  w: 0.28 },
  { n: '03', label: 'balcony',  w: 0.30 },
  { n: '04', label: 'product',  w: 0.24 },
];

// Sample subtitle lines by language (very rough, illustrative only)
const subSamples = {
  EN: ['Some traditions', "don't need to be taught —", 'only tasted.', 'Brew the warmth.'],
  HI: ['कुछ परंपराएँ', 'सिखाई नहीं जातीं —', 'सिर्फ़ चखी जाती हैं।', 'गर्माहट चखिए।'],
  MR: ['काही परंपरा', 'शिकवल्या जात नाहीत —', 'फक्त चाखल्या जातात.', 'उबदारपणा चाखा.'],
  TA: ['சில மரபுகள்', 'கற்றுத் தர முடியாது —', 'சுவைக்கத்தான் முடியும்.', 'சூட்டை சுவைக்கவும்.'],
  PA: ['ਕੁਝ ਰਵਾਇਤਾਂ', 'ਸਿਖਾਈਆਂ ਨਹੀਂ ਜਾਂਦੀਆਂ —', 'ਸਿਰਫ ਚਖੀਆਂ ਜਾਂਦੀਆਂ ਹਨ.', 'ਨਿੱਘ ਨੂੰ ਚਖੋ.'],
};

// -------- Direction A — Document --------
// Vertical layout: preview at top, then a single scrollable timeline strip,
// then a "subtitle script" reading like a screenplay
SCT.TimelineA = function TimelineA({ lang = 'EN' }) {
  const subs = subSamples[lang] || subSamples.EN;
  return (
    <Frame url="video.studio/c/diwali-tea-ad/edit">
      <Col gap={0} style={{ height: '100%', padding: '14px 28px' }}>
        <Row justify="space-between" style={{ marginBottom: 10 }}>
          <Row gap={10}><Mono>edit</Mono><Mono dim>· timeline + subtitles</Mono></Row>
          <Row gap={8}>
            <Chip><Icon kind="globe" size={12} /> {lang}</Chip>
            <Btn small ghost><Icon kind="play" size={12}/> preview</Btn>
            <Btn small primary><Icon kind="download" size={12}/> export</Btn>
          </Row>
        </Row>

        <Row gap={20} style={{ alignItems: 'flex-start' }}>
          <MediaPlaceholder label="kitchen · 02" w={420} h={236} />
          <Col gap={8} style={{ flex: 1 }}>
            <H size={24}>script</H>
            <Mono dim>auto-translated when language changes</Mono>
            <Col gap={6} style={{ marginTop: 6 }}>
              {subs.map((line, i) => (
                <Row key={i} gap={8} align="flex-start">
                  <Mono size={11} style={{ width: 56, paddingTop: 4 }}>0:0{i*7}</Mono>
                  <Box pad={6} style={{ flex: 1, background: i === 1 ? wfTokens.paper2 : 'transparent' }}>
                    <span style={{ fontSize: 14 }}>{line}</span>
                  </Box>
                  <Icon kind="edit" size={12}/>
                </Row>
              ))}
            </Col>
          </Col>
        </Row>

        <div style={{ marginTop: 14 }}>
          <SectionLabel>timeline · 0:28</SectionLabel>
        </div>

        {/* single horizontal strip */}
        <div style={{ marginTop: 6 }}>
          <Row gap={2}>
            {sceneClips.map((s, i) => (
              <div key={s.n} style={{ flex: s.w * 10 }}>
                <MediaPlaceholder label={`${s.n} · ${s.label}`} w={'100%'} h={48} style={{ width: '100%' }} />
              </div>
            ))}
          </Row>
          <div style={{ height: 18, position: 'relative', marginTop: 4 }}>
            <div style={{ position: 'absolute', left: 0, right: 0, top: 8, borderTop: `1.5px dashed ${wfTokens.ink}` }} />
            {['0:00','0:07','0:14','0:21','0:28'].map((t, i) => (
              <Mono key={t} size={10} dim style={{ position: 'absolute', left: `${(i / 4) * 100}%`, transform: 'translateX(-50%)' }}>{t}</Mono>
            ))}
          </div>
          <Row gap={6} style={{ marginTop: 10 }}>
            <Tag>SUB</Tag><Waveform w={220} h={14} seed={2} /><Mono dim>voice · {lang}</Mono>
            <div style={{ flex: 1 }} />
            <Tag>OVERLAY</Tag><Chip>brand logo · 0:24</Chip><Chip>CTA · 0:26</Chip>
          </Row>
        </div>
      </Col>
    </Frame>
  );
};

// -------- Direction B — Studio (multi-track editor) --------
SCT.TimelineB = function TimelineB({ lang = 'EN' }) {
  const subs = subSamples[lang] || subSamples.EN;
  const tracks = [
    { label: 'video',     icon: 'square',    items: sceneClips.map(s => ({ ...s })) },
    { label: 'voice',     icon: 'mic',       wave: true },
    { label: 'subtitles', icon: 'sub',       chunks: subs },
    { label: 'overlays',  icon: 'wand',      pins: [{at: 0.85, label: 'logo'}, {at: 0.93, label: 'CTA'}] },
  ];
  return (
    <Frame url="video.studio/c/diwali-tea-ad/edit">
      <Col gap={0} style={{ height: '100%' }}>
        <Row style={{ padding: '8px 16px', borderBottom: `1.5px dashed ${wfTokens.ink}`, justifyContent: 'space-between' }}>
          <Row gap={10}><Mono>edit</Mono><Mono dim>· 0:14 / 0:28 · v3</Mono></Row>
          <Row gap={8}>
            <Chip><Icon kind="globe" size={12}/> {lang}</Chip>
            <Btn small ghost><Icon kind="play" size={12}/></Btn>
            <Btn small primary><Icon kind="download" size={12}/> export</Btn>
          </Row>
        </Row>

        {/* preview + inspector */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          <div style={{ flex: 1.2, padding: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRight: `1.5px dashed ${wfTokens.ink}` }}>
            <Col gap={6}>
              <MediaPlaceholder label="kitchen · 02" w={480} h={270} />
              <Row justify="center" gap={10}>
                <Icon kind="play" size={20}/>
                <Mono>0:14 / 0:28</Mono>
              </Row>
            </Col>
          </div>
          <Col gap={10} style={{ width: 260, padding: 14, overflow: 'hidden' }}>
            <SectionLabel>subtitle · selected</SectionLabel>
            <Box pad={8} dashed>
              <span style={{ fontSize: 14 }}>{subs[1]}</span>
            </Box>
            <Row gap={6}>
              <Mono dim>at 0:07</Mono><Mono dim>dur 0:03</Mono>
            </Row>
            <SectionLabel style={{ marginTop: 6 }}>position</SectionLabel>
            <Box pad={6} style={{ height: 70, position: 'relative' }}>
              <div style={{ position: 'absolute', left: '50%', bottom: 6, transform: 'translateX(-50%)', background: wfTokens.accent, padding: '2px 8px', fontSize: 11 }}>caption</div>
              <Mono size={10} dim style={{ position: 'absolute', top: 6, right: 6 }}>auto-avoid face</Mono>
            </Box>
            <SectionLabel>style</SectionLabel>
            <Row gap={6}><Chip on>plain</Chip><Chip>karaoke</Chip><Chip>kinetic</Chip></Row>
          </Col>
        </div>

        {/* tracks */}
        <Col gap={6} style={{ padding: '10px 14px 14px', borderTop: `1.5px dashed ${wfTokens.ink}` }}>
          <Row justify="space-between">
            <SectionLabel>tracks · 0:28</SectionLabel>
            <Mono dim>4 scenes · subtitles ({lang}) · overlays</Mono>
          </Row>
          {tracks.map((t, ti) => (
            <Row key={t.label} gap={8} align="center">
              <Row gap={6} style={{ width: 88 }}>
                <Icon kind={t.icon} size={12}/><Mono size={11}>{t.label}</Mono>
              </Row>
              <div style={{ flex: 1, height: 26, border: `1.5px solid ${wfTokens.ink}`, borderRadius: 4, display: 'flex', overflow: 'hidden' }} className="wobble">
                {t.items && t.items.map((it, i) => (
                  <div key={i} style={{ flex: it.w, borderRight: i < t.items.length - 1 ? `1px dashed ${wfTokens.ink}` : 'none', display: 'flex', alignItems: 'center', padding: '0 6px', fontFamily: wfTokens.fMono, fontSize: 10, background: i === 1 ? wfTokens.accent : 'transparent' }}>
                    {it.n} · {it.label}
                  </div>
                ))}
                {t.wave && <div style={{ flex: 1, display: 'flex', alignItems: 'center', padding: '0 8px' }}><Waveform w={500} h={20} seed={5} /></div>}
                {t.chunks && (
                  <div style={{ flex: 1, position: 'relative' }}>
                    {t.chunks.map((c, i) => (
                      <div key={i} style={{ position: 'absolute', top: 3, bottom: 3, left: `${(i / 4) * 100 + 1}%`, width: `${100 / 4 - 2}%`, border: `1px dashed ${wfTokens.ink}`, padding: '0 4px', fontSize: 10, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', background: i === 1 ? wfTokens.paper2 : 'transparent' }}>{c}</div>
                    ))}
                  </div>
                )}
                {t.pins && (
                  <div style={{ flex: 1, position: 'relative' }}>
                    {t.pins.map((p, i) => (
                      <div key={i} style={{ position: 'absolute', top: 3, bottom: 3, left: `${p.at * 100}%`, padding: '0 6px', background: wfTokens.accent, fontSize: 10, display: 'flex', alignItems: 'center' }}>{p.label}</div>
                    ))}
                  </div>
                )}
              </div>
            </Row>
          ))}
        </Col>
      </Col>
    </Frame>
  );
};

// -------- Direction C — Stage (minimal single-track) --------
SCT.TimelineC = function TimelineC({ lang = 'EN' }) {
  const subs = subSamples[lang] || subSamples.EN;
  return (
    <Frame url="video.studio/c/diwali-tea-ad/edit">
      <Col gap={0} style={{ height: '100%', padding: '14px 18px' }}>
        <Row justify="space-between" style={{ marginBottom: 10 }}>
          <Mono>edit · {lang}</Mono>
          <Row gap={8}><Btn small><Icon kind="download" size={12}/> export</Btn></Row>
        </Row>

        {/* hero preview with subtitle overlay drawn on top */}
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
          <div style={{ position: 'relative' }}>
            <MediaPlaceholder label="kitchen · 02" w={680} h={400} />
            <div style={{ position: 'absolute', left: 0, right: 0, bottom: 18, display: 'flex', justifyContent: 'center' }}>
              <div style={{ background: 'rgba(26,24,20,0.85)', color: wfTokens.paper, padding: '6px 14px', fontFamily: wfTokens.fPrint, fontSize: 16, borderRadius: 3 }}>{subs[1]}</div>
            </div>
            <Note style={{ position: 'absolute', right: -150, bottom: 30 }}>caption — drag to move</Note>
            <Sticky rot={3} style={{ position: 'absolute', left: -120, top: 30 }}>tap to edit text</Sticky>
          </div>
        </div>

        {/* mini-track */}
        <Col gap={6} style={{ marginTop: 12 }}>
          <Row gap={4}>
            {sceneClips.map((s, i) => (
              <div key={s.n} style={{ flex: s.w * 10 }}>
                <MediaPlaceholder label={s.n} w={'100%'} h={42} style={{ width: '100%', borderColor: i === 1 ? wfTokens.ink : wfTokens.ink2 }} />
              </div>
            ))}
          </Row>
          <Row gap={10} justify="center">
            <Icon kind="play" size={18}/>
            <Mono>0:14 / 0:28</Mono>
            <Mono dim>· subtitles {lang}</Mono>
            <Mono dim>· voice {lang}</Mono>
          </Row>
        </Col>
      </Col>
    </Frame>
  );
};

Object.assign(window, SCT);
