// Screen 2: Scene plan / Storyboard — 3 directions

const SCS = {};

const scenes = [
  { n: '01', label: 'lamp lighting',     desc: 'close-up on diya being lit, golden bokeh background', dur: '0:00 – 0:07' },
  { n: '02', label: 'kitchen',           desc: "grandmother stirring chai, steam rising, wide-warm",  dur: '0:07 – 0:14' },
  { n: '03', label: 'balcony',           desc: 'grandfather & granddaughter sharing chai, fairy lights', dur: '0:14 – 0:22' },
  { n: '04', label: 'product close-up',  desc: 'tin lands on tea-tray, logo reveal, soft glow',       dur: '0:22 – 0:28' },
];

// -------- Direction A — Document --------
SCS.StoryboardA = function StoryboardA({ lang = 'EN' }) {
  return (
    <Frame url="video.studio/c/diwali-tea-ad/storyboard">
      <Col gap={14} style={{ padding: '20px 32px', height: '100%', overflow: 'hidden' }}>
        <Row justify="space-between">
          <Col gap={2}>
            <H size={28}>Scene plan</H>
            <Mono dim>4 scenes · 0:28 total · {lang}</Mono>
          </Col>
          <Row gap={8}>
            <Btn small ghost><Icon kind="plus" size={12}/> add scene</Btn>
            <Btn small><Icon kind="refresh" size={12}/> regenerate plan</Btn>
            <Btn small primary>approve →</Btn>
          </Row>
        </Row>

        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', justifyContent: 'center' }}>
          <Col gap={12} style={{ width: 740 }}>
            {scenes.map((s, i) => (
              <Row key={s.n} gap={16} align="flex-start">
                <Mono size={14} style={{ width: 28, paddingTop: 4 }}>{s.n}</Mono>
                <MediaPlaceholder label={s.label} w={220} h={124} />
                <Col gap={4} style={{ flex: 1 }}>
                  <Row gap={8}>
                    <span style={{ fontFamily: wfTokens.fHand, fontSize: 22 }}>{s.label}</span>
                    <Mono dim>{s.dur}</Mono>
                  </Row>
                  <span style={{ fontSize: 13, color: wfTokens.ink2, lineHeight: 1.35 }}>{s.desc}</span>
                  <Row gap={6} style={{ marginTop: 4 }}>
                    <Chip>VO: warm female</Chip>
                    <Chip>music: low brass</Chip>
                    <Icon kind="edit" size={12} />
                    <Icon kind="refresh" size={12} />
                  </Row>
                </Col>
              </Row>
            ))}
          </Col>
        </div>
      </Col>
    </Frame>
  );
};

// -------- Direction B — Studio (grid + detail) --------
SCS.StoryboardB = function StoryboardB({ lang = 'EN' }) {
  return (
    <Frame url="video.studio/c/diwali-tea-ad/storyboard">
      <Col gap={0} style={{ height: '100%' }}>
        <Row style={{ padding: '8px 16px', borderBottom: `1.5px dashed ${wfTokens.ink}`, justifyContent: 'space-between' }}>
          <Row gap={10}>
            <Mono>storyboard</Mono>
            <Mono dim>· 4 scenes · {lang}</Mono>
          </Row>
          <Row gap={8}>
            <Btn small ghost><Icon kind="refresh" size={12}/> reroll</Btn>
            <Btn small primary>approve & generate →</Btn>
          </Row>
        </Row>
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          {/* grid */}
          <div style={{ flex: 1.4, padding: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, alignContent: 'start', overflow: 'hidden' }}>
            {scenes.map((s, i) => (
              <Box key={s.n} pad={10} style={{ background: i === 1 ? wfTokens.paper2 : 'transparent' }}>
                <Col gap={6}>
                  <Row justify="space-between">
                    <Mono>{s.n} · {s.label}</Mono>
                    <Mono dim>{s.dur}</Mono>
                  </Row>
                  <MediaPlaceholder label={s.label} w={'100%'} h={120} style={{ width: '100%' }} />
                  <Row gap={6}>
                    <Chip>edit</Chip><Chip>regen</Chip>
                  </Row>
                </Col>
              </Box>
            ))}
          </div>
          {/* detail panel */}
          <Col gap={10} style={{ flex: 1, borderLeft: `1.5px dashed ${wfTokens.ink}`, padding: 16, overflow: 'hidden' }}>
            <SectionLabel>scene 02 — kitchen</SectionLabel>
            <MediaPlaceholder label="kitchen" w={'100%'} h={180} style={{ width: '100%' }} />
            <Col gap={6}>
              <span style={{ fontFamily: wfTokens.fHand, fontSize: 18 }}>shot description</span>
              <Box pad={10} dashed>
                <span style={{ fontSize: 13, lineHeight: 1.4, color: wfTokens.ink2 }}>
                  Grandmother stirring chai in a copper pot. Soft steam rising. Warm tungsten window light, medium-wide.
                </span>
              </Box>
            </Col>
            <Col gap={6}>
              <span style={{ fontFamily: wfTokens.fHand, fontSize: 18 }}>narration ({lang})</span>
              <Box pad={10} dashed>
                <span style={{ fontSize: 13, color: wfTokens.ink2 }}>"Some traditions don't need to be taught — only tasted."</span>
              </Box>
            </Col>
            <Row gap={6}>
              <Btn small><Icon kind="refresh" size={12}/> reroll image</Btn>
              <Btn small ghost><Icon kind="edit" size={12}/> edit prompt</Btn>
            </Row>
          </Col>
        </div>
      </Col>
    </Frame>
  );
};

// -------- Direction C — Stage (big hero + strip) --------
SCS.StoryboardC = function StoryboardC({ lang = 'EN' }) {
  return (
    <Frame url="video.studio/c/diwali-tea-ad/storyboard">
      <Col gap={0} style={{ height: '100%', padding: '14px 18px' }}>
        <Row justify="space-between" style={{ marginBottom: 8 }}>
          <Row gap={8}><Mono>storyboard / scene 02</Mono><Mono dim>· kitchen</Mono></Row>
          <Row gap={8}>
            <Btn small ghost><Icon kind="edit" size={12}/> edit shot</Btn>
            <Btn small><Icon kind="refresh" size={12}/> reroll</Btn>
            <Btn small primary>approve all →</Btn>
          </Row>
        </Row>

        <div style={{ flex: 1, display: 'flex', gap: 16, minHeight: 0 }}>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <MediaPlaceholder label="kitchen" w={620} h={460} />
          </div>
          <Col gap={10} style={{ width: 220 }}>
            <SectionLabel>shot notes</SectionLabel>
            <Box pad={8} dashed>
              <span style={{ fontSize: 12, color: wfTokens.ink2, lineHeight: 1.4 }}>
                Grandmother stirring chai. Soft steam. Warm tungsten light. Medium wide.
              </span>
            </Box>
            <SectionLabel>narration · {lang}</SectionLabel>
            <Box pad={8} dashed>
              <span style={{ fontSize: 12, color: wfTokens.ink2 }}>"Some traditions don't need to be taught — only tasted."</span>
            </Box>
            <SectionLabel>continuity</SectionLabel>
            <Row gap={4}>
              <Chip>same grandmother</Chip>
            </Row>
            <Row gap={4}>
              <Chip>same kitchen</Chip>
            </Row>
          </Col>
        </div>

        {/* strip */}
        <Row gap={8} style={{ marginTop: 12 }}>
          {scenes.map((s, i) => (
            <Col key={s.n} gap={4} style={{ flex: 1 }}>
              <MediaPlaceholder label={s.n} w={'100%'} h={68} style={{ width: '100%', borderColor: i === 1 ? wfTokens.ink : wfTokens.ink2 }} />
              <Mono size={10} dim>{s.label}</Mono>
            </Col>
          ))}
        </Row>
      </Col>
    </Frame>
  );
};

Object.assign(window, SCS);
