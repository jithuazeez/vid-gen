// Screen 1: Chat + Preview (hero) — 3 directions
// Width 1200, height 750 for desktop artboards.

const SCP = {};

const cpData = {
  title: 'Untitled · diwali tea ad',
  lang: 'EN',
  scenes: ['s1','s2','s3','s4'],
};

// -------- Direction A — DOCUMENT --------
// vertical scroll, chat as transcript, preview embedded inline
SCP.ChatPreviewA = function ChatPreviewA({ lang = 'EN' }) {
  return (
    <Frame url="video.studio/c/diwali-tea-ad">
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* top bar */}
        <Row style={{ padding: '10px 24px', borderBottom: `1.5px dashed ${wfTokens.ink}`, justifyContent: 'space-between' }}>
          <Row gap={10}>
            <Icon kind="spark" size={18} />
            <span style={{ fontFamily: wfTokens.fHand, fontSize: 22 }}>video.studio</span>
            <Mono dim>/ {cpData.title}</Mono>
          </Row>
          <Row gap={8}>
            <Chip><Icon kind="globe" size={12} /> {lang}</Chip>
            <Btn small>save</Btn>
            <Btn primary small>generate →</Btn>
          </Row>
        </Row>

        {/* document column */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', justifyContent: 'center' }}>
          <Col gap={18} style={{ width: 620, padding: '28px 0' }}>
            <div>
              <H size={32}>Let's plan your video.</H>
              <Mono>3 questions answered · 6 to go</Mono>
            </div>

            <Bubble from="ai">What's the video for, and roughly how long?</Bubble>
            <Bubble from="user">A 30-second Diwali ad for our masala chai brand. Warm, family moments.</Bubble>

            <Bubble from="ai">
              Great. I'm picturing 4 scenes — a lamp lighting, a kitchen, a family on a balcony, and the product close-up. Sound right?
            </Bubble>

            {/* embedded scene strip inside the conversation */}
            <Box pad={14} style={{ background: wfTokens.paper }}>
              <Row justify="space-between" style={{ marginBottom: 10 }}>
                <SectionLabel>proposed scenes · v1</SectionLabel>
                <Row gap={6}><Icon kind="refresh" size={12} /><Mono>regenerate</Mono></Row>
              </Row>
              <Row gap={10}>
                {['lamp','kitchen','balcony','product'].map((s, i) => (
                  <Col key={s} gap={4} style={{ width: 130 }}>
                    <MediaPlaceholder label={`0${i+1} · ${s}`} w={130} h={75} />
                    <Mono size={10}>0:0{i*7} – 0:{(i+1)*7}</Mono>
                  </Col>
                ))}
              </Row>
            </Box>

            <Bubble from="user">Yes — make the family scene a grandfather and granddaughter.</Bubble>
            <Bubble from="ai">Done. Should the narration be a warm woman's voice in {lang === 'EN' ? 'English' : lang === 'HI' ? 'Hindi' : 'your chosen language'}?</Bubble>

            {/* composer */}
            <Box pad={10} style={{ marginTop: 4 }}>
              <Row justify="space-between">
                <span style={{ color: wfTokens.ink3, fontFamily: wfTokens.fPrint }}>Reply… ('continue' to keep going)</span>
                <Row gap={6}>
                  <Icon kind="mic" />
                  <Icon kind="send" />
                </Row>
              </Row>
            </Box>
            <Row gap={6} style={{ flexWrap: 'wrap' }}>
              <Chip>warm woman</Chip><Chip>cinematic</Chip><Chip>1:1 square</Chip>
              <Chip>subtitles: on</Chip><Chip>CTA at end</Chip>
            </Row>
          </Col>
        </div>
      </div>
    </Frame>
  );
};

// -------- Direction B — STUDIO --------
// Split 50/50, video-editor feel, with timeline ribbon at bottom
SCP.ChatPreviewB = function ChatPreviewB({ lang = 'EN' }) {
  return (
    <Frame url="video.studio/c/diwali-tea-ad">
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* top bar */}
        <Row style={{ padding: '8px 16px', borderBottom: `1.5px dashed ${wfTokens.ink}`, justifyContent: 'space-between' }}>
          <Row gap={10}>
            <Icon kind="folder" size={14} />
            <Mono>diwali-tea-ad</Mono>
            <Mono dim>· draft v3 · 0:28</Mono>
          </Row>
          <Row gap={8}>
            <Chip><Icon kind="globe" size={12} /> {lang}</Chip>
            <Btn small ghost><Icon kind="play" size={12} /> preview</Btn>
            <Btn small primary><Icon kind="download" size={12} /> export</Btn>
          </Row>
        </Row>

        {/* split body */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          {/* left: chat */}
          <Col gap={10} style={{ flex: 1, padding: 16, borderRight: `1.5px dashed ${wfTokens.ink}`, overflow: 'hidden' }}>
            <Row justify="space-between">
              <SectionLabel>conversation</SectionLabel>
              <Mono dim>3 / 9 fields</Mono>
            </Row>
            <Bubble from="ai">What's the video for?</Bubble>
            <Bubble from="user">30s Diwali ad for masala chai brand. Warm, family moments.</Bubble>
            <Bubble from="ai">Got it — visual style?</Bubble>
            <Bubble from="user">Cinematic, golden-hour, soft grain.</Bubble>
            <Bubble from="ai">Narration tone in {lang === 'EN' ? 'English' : 'your language'}?</Bubble>

            <div style={{ flex: 1 }} />

            {/* composer */}
            <Box pad={10}>
              <Row justify="space-between">
                <span style={{ color: wfTokens.ink3 }}>your reply…</span>
                <Row gap={6}><Icon kind="mic" /><Icon kind="send" /></Row>
              </Row>
            </Box>
            <Row gap={6} style={{ flexWrap: 'wrap' }}>
              <Chip>warm woman</Chip><Chip>narrator-male</Chip><Chip>no narration</Chip>
            </Row>
          </Col>

          {/* right: preview */}
          <Col gap={12} style={{ flex: 1, padding: 16, overflow: 'hidden' }}>
            <Row justify="space-between">
              <SectionLabel>preview · scene 02</SectionLabel>
              <Mono dim>1:1 · 0:07 / 0:28</Mono>
            </Row>
            <MediaPlaceholder label="01 · lamp lighting" w={520} h={300} style={{ alignSelf: 'center' }} />
            <Row gap={10} justify="center">
              <Icon kind="play" size={20} />
              <Mono>‹ ‹</Mono>
              <Mono>0:07 / 0:28</Mono>
              <Mono>› ›</Mono>
            </Row>
          </Col>
        </div>

        {/* bottom timeline ribbon */}
        <Col gap={4} style={{ padding: '8px 16px', borderTop: `1.5px dashed ${wfTokens.ink}` }}>
          <Row justify="space-between">
            <SectionLabel>timeline</SectionLabel>
            <Mono dim>4 scenes · subtitles · voice ({lang})</Mono>
          </Row>
          <Row gap={4}>
            {['lamp','kitchen','balcony','product'].map((s, i) => (
              <Box key={s} pad={6} style={{ flex: i === 1 ? 2 : 1, background: i === 0 ? wfTokens.accent : 'transparent' }}>
                <Mono size={10}>0{i+1} · {s}</Mono>
              </Box>
            ))}
          </Row>
        </Col>
      </div>
    </Frame>
  );
};

// -------- Direction C — STAGE --------
// Preview is hero, chat is slim right rail
SCP.ChatPreviewC = function ChatPreviewC({ lang = 'EN' }) {
  return (
    <Frame url="video.studio/c/diwali-tea-ad">
      <div style={{ display: 'flex', height: '100%' }}>
        {/* main stage */}
        <Col gap={0} style={{ flex: 1, padding: '14px 18px', minWidth: 0 }}>
          <Row justify="space-between" style={{ marginBottom: 10 }}>
            <Row gap={10}>
              <Icon kind="spark" size={16} />
              <Mono>diwali-tea-ad</Mono>
            </Row>
            <Row gap={8}>
              <Chip><Icon kind="globe" size={12} /> {lang}</Chip>
              <Btn small><Icon kind="download" size={12} /> export</Btn>
            </Row>
          </Row>

          {/* hero preview */}
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0 }}>
            <MediaPlaceholder label="scene 02 · kitchen" w={520} h={520} />
          </div>

          {/* scrubber */}
          <Row gap={10} justify="center" style={{ padding: '10px 0 6px' }}>
            <Icon kind="play" size={22} />
            <div style={{ flex: 1, maxWidth: 480, height: 22, border: `1.5px solid ${wfTokens.ink}`, borderRadius: 4, position: 'relative' }} className="wobble">
              <div style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: '28%', background: wfTokens.accent }} />
              <div style={{ position: 'absolute', top: -4, bottom: -4, left: '28%', width: 2, background: wfTokens.ink }} />
            </div>
            <Mono>0:07 / 0:28</Mono>
          </Row>

          {/* scene strip */}
          <Row gap={6}>
            {['lamp','kitchen','balcony','product'].map((s, i) => (
              <div key={s} style={{ flex: 1 }}>
                <MediaPlaceholder label={`0${i+1}`} w={'100%'} h={48} style={{ width: '100%', borderColor: i === 1 ? wfTokens.ink : wfTokens.ink2 }} />
              </div>
            ))}
          </Row>
        </Col>

        {/* right rail: chat */}
        <Col gap={10} style={{ width: 320, borderLeft: `1.5px dashed ${wfTokens.ink}`, padding: 14, overflow: 'hidden' }}>
          <Row justify="space-between">
            <SectionLabel>director</SectionLabel>
            <Mono dim>3/9</Mono>
          </Row>
          <Bubble from="ai">What's the video for?</Bubble>
          <Bubble from="user">30s Diwali ad, masala chai, warm family.</Bubble>
          <Bubble from="ai">Style?</Bubble>
          <Bubble from="user">Cinematic, golden-hour.</Bubble>
          <Bubble from="ai">Narration tone in {lang}?</Bubble>

          <div style={{ flex: 1 }} />

          <Box pad={8}>
            <Row justify="space-between">
              <span style={{ color: wfTokens.ink3, fontSize: 13 }}>reply…</span>
              <Icon kind="send" size={14} />
            </Row>
          </Box>
          <Row gap={4} style={{ flexWrap: 'wrap' }}>
            <Chip>warm woman</Chip><Chip>male</Chip><Chip>none</Chip>
          </Row>
        </Col>
      </div>
    </Frame>
  );
};

Object.assign(window, SCP);
