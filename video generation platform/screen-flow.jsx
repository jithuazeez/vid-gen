// Screens for the screenflow.md spec — single committed direction.
// 6 artboards: Welcome · Chat · Storyboard · Progress · Review · Export

const SF = {};

// Shared data
const sfBrief = [
  { k: 'Type',     v: 'social reel',          done: true  },
  { k: 'Style',    v: 'realistic',            done: true  },
  { k: 'Topic',    v: 'coffee brand',         done: true  },
  { k: 'Duration', v: '30s',                  done: false },
  { k: 'Language', v: '—',                    done: false },
  { k: 'Tone',     v: '—',                    done: false },
  { k: 'People?',  v: '—',                    done: false },
  { k: 'Music?',   v: '—',                    done: false },
  { k: 'Subs?',    v: '—',                    done: false },
  { k: 'Aspect',   v: '—',                    done: false },
];

const sfScenes = [
  { n: 1, t: '0:00', d: '0:06', vis: 'Hand pouring espresso into a tiny glass cup, warm overhead light, shallow DOF', script: '"Crafted from beans grown at 1,800 metres."',     speaker: false, sub: 'auto' },
  { n: 2, t: '0:06', d: '0:06', vis: 'Beans roasting in a brass drum, warm tungsten light, slow rotation',         script: '"Sourced from a single family farm."',           speaker: false, sub: 'auto' },
  { n: 3, t: '0:12', d: '0:06', vis: 'Steam rising from a fresh cup, morning light through café window',          script: '"Served fresh, every morning."',                 speaker: false, sub: 'auto' },
  { n: 4, t: '0:18', d: '0:06', vis: 'Barista handing a cup across the counter, smiling, eye contact with camera',script: '"Made by hands that care."',                     speaker: true,  sub: 'bottom' },
  { n: 5, t: '0:24', d: '0:06', vis: 'Logo lock-up over dark coffee texture, slow zoom, brand mark reveal',        script: '"Northbean. Coffee, the long way."',             speaker: false, sub: 'auto' },
];

// ───── Welcome ─────────────────────────────────────────────────
SF.Welcome = function Welcome() {
  return (
    <Frame url="video.studio">
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 24 }}>
        <Row gap={10}>
          <Icon kind="spark" size={26} />
          <span style={{ fontFamily: wfTokens.fHand, fontSize: 56, lineHeight: 1 }}>video.studio</span>
        </Row>
        <Col gap={4} style={{ alignItems: 'center', textAlign: 'center' }}>
          <span style={{ fontFamily: wfTokens.fHand, fontSize: 30, lineHeight: 1.1, maxWidth: 520 }}>
            Tell us about your video — we'll figure out the rest.
          </span>
          <Mono dim>conversational · multilingual · scene-aware</Mono>
        </Col>
        <Btn primary><Icon kind="plus" size={14}/> Start a new video</Btn>
        <Row gap={6} style={{ marginTop: 6 }}>
          <Mono dim size={10}>or</Mono>
          <Mono dim size={10}>open recent · diwali tea ad · monsoon promo</Mono>
        </Row>
      </div>
    </Frame>
  );
};

// ───── 1. Chat — 60/40 split ───────────────────────────────────
SF.Chat = function Chat({ lang = 'EN', ready = false }) {
  const brief = sfBrief.map((b, i) => {
    if (!ready) return b;
    // when ready, fill them all
    const fills = { Duration: '30s', Language: lang, Tone: 'warm, confident', 'People?': 'yes · barista', 'Music?': 'soft acoustic', 'Subs?': 'auto', Aspect: '9:16' };
    return { ...b, v: fills[b.k] || b.v, done: true };
  });
  const filled = brief.filter(b => b.done).length;

  return (
    <Frame url={`video.studio/projects/np-coffee/chat`}>
      <Col gap={0} style={{ height: '100%' }}>
        {/* header */}
        <Row style={{ padding: '10px 18px', borderBottom: `1.5px dashed ${wfTokens.ink}`, justifyContent: 'space-between' }}>
          <Row gap={10}>
            <Mono>◀ back</Mono>
            <Mono dim>·</Mono>
            <span style={{ fontFamily: wfTokens.fHand, fontSize: 22 }}>Untitled coffee project</span>
          </Row>
          <Row gap={10}><Mono dim>{lang}</Mono><Icon kind="gear" size={14}/></Row>
        </Row>

        {/* body */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          {/* chat column (60%) */}
          <Col gap={12} style={{ flex: 6, padding: '18px 24px', borderRight: `1.5px dashed ${wfTokens.ink}`, overflow: 'hidden' }}>
            <Bubble from="ai">What kind of video do you want to create?</Bubble>
            <ChipRow chips={['Explainer','Cinematic','Social reel','Ad','Product demo','Pitch']} selected="Social reel" />
            <Bubble from="user">A social reel about my coffee brand.</Bubble>

            <Bubble from="ai">Got it — a social reel. What visual style?</Bubble>
            <ChipRow chips={['Realistic','Animated','Documentary','Stop-motion','Stylised']} selected="Realistic" />
            <Bubble from="user">Realistic, warm and a bit cinematic.</Bubble>

            <Bubble from="ai">
              {ready
                ? `Perfect. I have everything I need — a 30-second realistic social reel for a coffee brand, in ${lang}, 9:16, with auto subtitles. Ready to plan the scenes?`
                : `Nice. About how long should it be?`}
            </Bubble>
            {!ready && <ChipRow chips={['15 sec','30 sec','45 sec','60 sec','custom…']} />}

            <div style={{ flex: 1 }} />

            {/* composer */}
            <Col gap={8}>
              <Box pad={10}>
                <Row justify="space-between">
                  <span style={{ color: wfTokens.ink3, fontFamily: wfTokens.fPrint, fontSize: 14 }}>
                    Type your message… (or tap a suggestion above)
                  </span>
                  <Row gap={8}><Mono dim size={10}>↵ send</Mono><Icon kind="send" size={14}/></Row>
                </Row>
              </Box>
              <Mono dim size={10}>chips are shortcuts — typing always wins</Mono>
            </Col>
          </Col>

          {/* brief summary (40%) */}
          <Col gap={12} style={{ flex: 4, padding: '18px 22px', overflow: 'hidden' }}>
            <Row justify="space-between" align="flex-start">
              <Col gap={2}>
                <span style={{ fontFamily: wfTokens.fHand, fontSize: 26, lineHeight: 1 }}>Your video</span>
                <Mono dim>{filled} of 10 collected</Mono>
              </Col>
              {ready && <Sticky rot={2}>ready!</Sticky>}
            </Row>

            <Box pad={14}>
              <Col gap={8}>
                {brief.map(b => (
                  <Row key={b.k} justify="space-between" align="center">
                    <Row gap={8} style={{ width: 110 }}>
                      <Icon kind={b.done ? 'check' : 'circle'} size={12} color={b.done ? wfTokens.ink : wfTokens.ink3}/>
                      <Mono size={11} style={{ color: b.done ? wfTokens.ink : wfTokens.ink3 }}>{b.k}</Mono>
                    </Row>
                    <span style={{ flex: 1, textAlign: 'right', fontFamily: wfTokens.fPrint, fontSize: 14, color: b.done ? wfTokens.ink : wfTokens.ink3 }}>{b.v}</span>
                  </Row>
                ))}
              </Col>
            </Box>

            <div style={{ flex: 1 }} />

            <Col gap={6}>
              <Btn primary={ready} ghost={!ready} style={{ width: '100%', justifyContent: 'center', opacity: ready ? 1 : 0.55 }}>
                Start planning {ready ? '→' : ''}
              </Btn>
              {!ready && <Mono dim size={10} style={{ textAlign: 'center' }}>enabled when all 10 slots are filled</Mono>}
            </Col>
          </Col>
        </div>
      </Col>
    </Frame>
  );
};

function ChipRow({ chips, selected }) {
  return (
    <Row gap={6} style={{ flexWrap: 'wrap', paddingLeft: 4 }}>
      {chips.map(c => (
        <Chip key={c} on={c === selected}>{c}</Chip>
      ))}
      <span style={{ fontFamily: wfTokens.fHand, fontSize: 14, color: wfTokens.ink3, alignSelf: 'center', marginLeft: 4 }}>or type your own</span>
    </Row>
  );
}

// ───── 2. Storyboard ───────────────────────────────────────────
SF.Storyboard = function Storyboard({ lang = 'EN', openDetail = false }) {
  return (
    <Frame url="video.studio/projects/np-coffee/storyboard">
      <Col gap={0} style={{ height: '100%' }}>
        <Row style={{ padding: '10px 18px', borderBottom: `1.5px dashed ${wfTokens.ink}`, justifyContent: 'space-between' }}>
          <Row gap={10}>
            <Mono>◀ back to chat</Mono>
            <Mono dim>·</Mono>
            <span style={{ fontFamily: wfTokens.fHand, fontSize: 22 }}>Northbean coffee · 30s · 9:16 · {lang}</span>
          </Row>
          <Row gap={8}>
            <Btn small ghost><Icon kind="refresh" size={12}/> regenerate all</Btn>
            <Btn small primary>generate →</Btn>
          </Row>
        </Row>

        <div style={{ flex: 1, display: 'flex', minHeight: 0, position: 'relative' }}>
          {/* grid */}
          <Col gap={14} style={{ flex: 1, padding: '18px 24px', overflow: 'hidden' }}>
            <Row justify="space-between">
              <Col gap={2}>
                <span style={{ fontFamily: wfTokens.fHand, fontSize: 22 }}>Scenes</span>
                <Mono dim>5 · 0:30 total · click a card to edit</Mono>
              </Col>
              <Row gap={6}>
                <Btn small ghost><Icon kind="plus" size={12}/> add scene</Btn>
              </Row>
            </Row>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
              {sfScenes.map((s, i) => (
                <Box key={s.n} pad={10} style={{ background: (openDetail && i === 0) ? wfTokens.paper2 : 'transparent' }}>
                  <Col gap={8}>
                    <Row justify="space-between">
                      <Mono>scene {s.n}</Mono>
                      <Mono dim>{s.t} · {s.d}</Mono>
                    </Row>
                    <MediaPlaceholder label={`scene ${s.n}`} w={'100%'} h={150} style={{ width: '100%' }} />
                    <Col gap={4}>
                      <span style={{ fontSize: 12, lineHeight: 1.35, color: wfTokens.ink2 }}>{truncate(s.vis, 78)}</span>
                      <span style={{ fontSize: 13, fontStyle: 'italic', lineHeight: 1.35 }}>{truncate(s.script, 60)}</span>
                    </Col>
                    <Row justify="space-between">
                      <Row gap={8}>
                        <Row gap={4}>
                          <Icon kind={s.speaker ? 'check' : 'circle'} size={11} color={s.speaker ? wfTokens.ink : wfTokens.ink3}/>
                          <Mono size={10} dim={!s.speaker}>speaking</Mono>
                        </Row>
                        <Mono size={10} dim>subs: {s.sub}</Mono>
                      </Row>
                      <Mono size={11}>⋯</Mono>
                    </Row>
                  </Col>
                </Box>
              ))}
              {/* add new placeholder */}
              <Box pad={10} dashed style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 220 }}>
                <Col gap={6} style={{ alignItems: 'center' }}>
                  <Icon kind="plus" size={20} color={wfTokens.ink3}/>
                  <Mono dim size={11}>add scene</Mono>
                </Col>
              </Box>
            </div>
          </Col>

          {/* slide-in detail panel */}
          {openDetail && (
            <Col gap={12} style={{
              width: 460, flex: '0 0 460px',
              borderLeft: `1.5px solid ${wfTokens.ink}`,
              background: wfTokens.paper,
              padding: '18px 22px',
              overflow: 'hidden',
              boxShadow: '-6px 0 0 rgba(0,0,0,0.04)',
            }}>
              <Row justify="space-between">
                <Col gap={2}>
                  <Mono>scene 1 · 0:06</Mono>
                  <span style={{ fontFamily: wfTokens.fHand, fontSize: 22 }}>opening pour</span>
                </Col>
                <Mono>✕</Mono>
              </Row>
              <Divider />

              <Col gap={4}>
                <SectionLabel>narration script</SectionLabel>
                <Box pad={10} dashed>
                  <span style={{ fontSize: 14, lineHeight: 1.45 }}>"Crafted from beans grown at 1,800 metres, every cup tells a story."</span>
                </Box>
              </Col>

              <Col gap={4}>
                <SectionLabel>visual direction</SectionLabel>
                <Box pad={10} dashed>
                  <span style={{ fontSize: 13, lineHeight: 1.45, color: wfTokens.ink2 }}>
                    Hand pouring espresso into a tiny glass cup, warm overhead light, shallow depth of field, slow-motion drop.
                  </span>
                </Box>
              </Col>

              <Col gap={4}>
                <SectionLabel>characters in scene</SectionLabel>
                <Row gap={6}>
                  <Mono dim size={11}>none — voice-over only</Mono>
                  <Chip>+ add character</Chip>
                </Row>
              </Col>

              <Col gap={4}>
                <SectionLabel>speaking on camera</SectionLabel>
                <Col gap={4}>
                  <Row gap={8}><Icon kind="check" size={12}/><span style={{ fontSize: 13 }}><strong>Off</strong> · lip-sync skipped</span></Row>
                  <Row gap={8}><Icon kind="circle" size={12} color={wfTokens.ink3}/><span style={{ fontSize: 13, color: wfTokens.ink2 }}>On · MuseTalk syncs mouth to narration</span></Row>
                </Col>
              </Col>

              <Col gap={4}>
                <SectionLabel>subtitle position</SectionLabel>
                <Row gap={6}>
                  <Chip on>auto</Chip><Chip>top</Chip><Chip>bottom</Chip><Chip>custom</Chip>
                </Row>
              </Col>

              <div style={{ flex: 1 }} />
              <Row gap={8} justify="space-between">
                <Btn small ghost><Icon kind="refresh" size={12}/> regenerate scene</Btn>
                <Row gap={6}>
                  <Btn small ghost>discard</Btn>
                  <Btn small primary>save</Btn>
                </Row>
              </Row>
            </Col>
          )}
        </div>
      </Col>
    </Frame>
  );
};

// ───── 3. Progress ─────────────────────────────────────────────
SF.Progress = function Progress({ lang = 'EN' }) {
  const stages = [
    { k: 'storyboard', s: 'done' },
    { k: 'scenes',     s: 'active' },
    { k: 'voice',      s: 'pending' },
    { k: 'subtitles',  s: 'pending' },
    { k: 'overlays',   s: 'pending' },
    { k: 'composite',  s: 'pending' },
  ];
  const scenes = [
    { n: 1, state: 'composited', label: 'composited' },
    { n: 2, state: 'lipsync',    label: 'lip-sync' },
    { n: 3, state: 'sceneGen',   label: 'scene gen · 45%' },
    { n: 4, state: 'waiting',    label: 'waiting' },
    { n: 5, state: 'waiting',    label: 'waiting' },
  ];

  return (
    <Frame url="video.studio/projects/np-coffee/progress/r-7421">
      <Col gap={0} style={{ height: '100%' }}>
        <Row style={{ padding: '10px 18px', borderBottom: `1.5px dashed ${wfTokens.ink}`, justifyContent: 'space-between' }}>
          <Row gap={10}>
            <Mono>◀ back to storyboard</Mono>
            <Mono dim>·</Mono>
            <span style={{ fontFamily: wfTokens.fHand, fontSize: 22 }}>Northbean coffee · 30s · 9:16 · {lang}</span>
          </Row>
          <Btn small ghost>cancel</Btn>
        </Row>

        <Col gap={18} style={{ padding: '22px 32px', flex: 1, overflow: 'hidden' }}>
          <Row justify="space-between" align="flex-start">
            <Col gap={2}>
              <H size={30}>Generating your video</H>
              <Mono dim>estimated time remaining · ~1 min 20 s · job r-7421</Mono>
            </Col>
            <Sticky rot={-2}>don't close the tab</Sticky>
          </Row>

          {/* stepper */}
          <Box pad={18}>
            <Row gap={0} align="center" justify="space-between" style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', left: 24, right: 24, top: '50%', borderTop: `1.5px dashed ${wfTokens.ink}`, opacity: 0.5 }} />
              {stages.map((st, i) => {
                const done = st.s === 'done';
                const active = st.s === 'active';
                return (
                  <Col key={st.k} gap={6} style={{ alignItems: 'center', zIndex: 1, background: wfTokens.paper, padding: '0 6px' }}>
                    <div className="wobble" style={{
                      width: 30, height: 30, borderRadius: '50%',
                      border: `1.5px solid ${wfTokens.ink}`,
                      background: done ? wfTokens.ink : active ? wfTokens.accent : wfTokens.paper,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: done ? wfTokens.paper : wfTokens.ink,
                    }}>
                      {done ? <Icon kind="check" size={14} color={wfTokens.paper}/> : active ? <Icon kind="spark" size={14}/> : <Mono size={11} dim>{i+1}</Mono>}
                    </div>
                    <Mono size={11} style={{ color: active ? wfTokens.ink : wfTokens.ink2 }}>{st.k}</Mono>
                  </Col>
                );
              })}
            </Row>
          </Box>

          <Col gap={8}>
            <SectionLabel>per-scene progress</SectionLabel>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
              {scenes.map(s => (
                <Box key={s.n} pad={10}>
                  <Col gap={8}>
                    <Mono size={11}>scene {s.n}</Mono>
                    <div style={{ position: 'relative' }}>
                      <MediaPlaceholder label={s.state === 'composited' ? '▶ play' : 'rendering'} w={'100%'} h={120} style={{ width: '100%' }} />
                      {s.state === 'sceneGen' && (
                        <div style={{ position: 'absolute', left: 8, right: 8, bottom: 8, height: 6, border: `1px solid ${wfTokens.ink}`, background: wfTokens.paper }}>
                          <div style={{ height: '100%', width: '45%', background: wfTokens.accent }} />
                        </div>
                      )}
                    </div>
                    <Row gap={6}>
                      {s.state === 'composited' && <><Icon kind="check" size={12}/><Mono size={10}>{s.label}</Mono></>}
                      {s.state === 'lipsync'    && <><Icon kind="spark" size={12}/><Mono size={10}>{s.label}</Mono></>}
                      {s.state === 'sceneGen'   && <><Icon kind="refresh" size={12}/><Mono size={10}>{s.label}</Mono></>}
                      {s.state === 'waiting'    && <><Icon kind="circle" size={11} color={wfTokens.ink3}/><Mono size={10} dim>{s.label}</Mono></>}
                    </Row>
                  </Col>
                </Box>
              ))}
            </div>
          </Col>

          <Box pad={10} dashed>
            <Row gap={10}>
              <Mono dim size={11}>GPU queue · cold start ~30s</Mono>
              <Mono dim size={11}>·</Mono>
              <Mono dim size={11}>tab can be backgrounded · we'll save progress</Mono>
            </Row>
          </Box>
        </Col>
      </Col>
    </Frame>
  );
};

// ───── 4. Review & Edit ────────────────────────────────────────
SF.Review = function Review({ lang = 'EN', tab = 'subtitles' }) {
  const cues = sfSubtitles[lang] || sfSubtitles.EN;

  return (
    <Frame url="video.studio/projects/np-coffee/review">
      <Col gap={0} style={{ height: '100%' }}>
        <Row style={{ padding: '10px 18px', borderBottom: `1.5px dashed ${wfTokens.ink}`, justifyContent: 'space-between' }}>
          <Row gap={10}>
            <Mono>◀ back</Mono>
            <Mono dim>·</Mono>
            <span style={{ fontFamily: wfTokens.fHand, fontSize: 22 }}>Northbean coffee · 30s · 9:16</span>
          </Row>
          <Row gap={10}>
            <Box pad={4} style={{ padding: '4px 10px' }}>
              <Row gap={6}><Icon kind="globe" size={12}/><Mono size={11}>language · {lang} ▾</Mono></Row>
            </Box>
            <Btn small primary><Icon kind="download" size={12}/> export</Btn>
          </Row>
        </Row>

        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          {/* player */}
          <Col gap={10} style={{ flex: 1.3, padding: 18, borderRight: `1.5px dashed ${wfTokens.ink}`, minWidth: 0 }}>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
              <div style={{ position: 'relative' }}>
                <MediaPlaceholder label="9:16 player" w={290} h={510} />
                {/* subtitle overlay sample */}
                <div style={{ position: 'absolute', left: 0, right: 0, bottom: 26, display: 'flex', justifyContent: 'center' }}>
                  <div style={{ background: 'rgba(26,24,20,0.85)', color: wfTokens.paper, padding: '5px 10px', fontFamily: wfTokens.fPrint, fontSize: 13 }}>{cues[1].text}</div>
                </div>
                {/* CTA overlay */}
                <div className="wobble" style={{ position: 'absolute', right: 12, top: 24, background: wfTokens.accent, color: wfTokens.ink, padding: '4px 10px', fontSize: 11, fontFamily: wfTokens.fHand }}>Buy now →</div>
              </div>
            </div>
            <Row gap={10} align="center">
              <Icon kind="play" size={18}/>
              <div className="wobble" style={{ flex: 1, height: 18, border: `1.5px solid ${wfTokens.ink}`, position: 'relative' }}>
                <div style={{ position: 'absolute', inset: 0, width: '28%', background: wfTokens.accent }} />
                <div style={{ position: 'absolute', top: -3, bottom: -3, left: '28%', width: 2, background: wfTokens.ink }} />
              </div>
              <Mono size={11}>0:08 / 0:30</Mono>
            </Row>

            {/* timeline */}
            <Col gap={4} style={{ marginTop: 2 }}>
              <SectionLabel>timeline</SectionLabel>
              <Col gap={3}>
                <Track label="scenes" icon="square">
                  {sfScenes.map((s, i) => (
                    <div key={s.n} style={{ flex: 1, borderRight: i < sfScenes.length - 1 ? `1px dashed ${wfTokens.ink}` : 'none', padding: '0 6px', display: 'flex', alignItems: 'center', fontFamily: wfTokens.fMono, fontSize: 10, background: i === 1 ? wfTokens.paper2 : 'transparent' }}>
                      S{s.n}
                    </div>
                  ))}
                </Track>
                <Track label="voice" icon="mic">
                  <div style={{ flex: 1, display: 'flex', alignItems: 'center', padding: '0 6px' }}>
                    <Waveform w={520} h={16} seed={6} />
                  </div>
                </Track>
                <Track label="subs" icon="sub">
                  {cues.map((c, i) => (
                    <div key={i} style={{ flex: 1, borderRight: i < cues.length - 1 ? `1px dashed ${wfTokens.ink}` : 'none', padding: '2px 6px', fontSize: 10, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', background: i === 1 ? wfTokens.paper2 : 'transparent' }}>{c.text}</div>
                  ))}
                </Track>
                <Track label="overlay" icon="wand">
                  <div style={{ flex: 1, position: 'relative' }}>
                    <div style={{ position: 'absolute', left: '22%', top: 2, bottom: 2, width: '18%', background: wfTokens.accent, fontSize: 10, padding: '2px 6px' }}>Buy now →</div>
                    <div style={{ position: 'absolute', left: '70%', top: 2, bottom: 2, width: '24%', background: wfTokens.accent, fontSize: 10, padding: '2px 6px' }}>Try free</div>
                  </div>
                </Track>
                <Track label="music" icon="play">
                  <div style={{ flex: 1, display: 'flex', alignItems: 'center', padding: '0 6px' }}>
                    <div style={{ flex: 1, height: 3, background: wfTokens.ink, opacity: 0.4 }} />
                    <Mono size={10} dim style={{ marginLeft: 8 }}>−18 dB</Mono>
                  </div>
                </Track>
              </Col>
              <Mono dim size={10}>▲ playhead at 0:08</Mono>
            </Col>
          </Col>

          {/* right panel */}
          <Col gap={10} style={{ width: 320, padding: 16, overflow: 'hidden' }}>
            <Row gap={6}>
              {['subtitles','overlays','audio','scenes'].map(t => (
                <Chip key={t} on={t === tab}>{t}</Chip>
              ))}
            </Row>

            {tab === 'subtitles' && (
              <Col gap={6}>
                <Row justify="space-between">
                  <SectionLabel>cues · {lang}</SectionLabel>
                  <Mono dim size={10}>regenerate all</Mono>
                </Row>
                {cues.map((c, i) => (
                  <Box key={i} pad={8} style={{ background: i === 1 ? wfTokens.paper2 : 'transparent' }}>
                    <Row justify="space-between" align="flex-start">
                      <Col gap={2}>
                        <Mono size={10} dim>{c.start} – {c.end}</Mono>
                        <span style={{ fontSize: 13, lineHeight: 1.3 }}>{c.text}</span>
                      </Col>
                      <Mono>⋯</Mono>
                    </Row>
                  </Box>
                ))}
                <Btn small ghost style={{ alignSelf: 'flex-start' }}><Icon kind="plus" size={12}/> add cue</Btn>
              </Col>
            )}
            {tab === 'overlays' && (
              <Col gap={6}>
                <Row justify="space-between"><SectionLabel>overlays</SectionLabel><Mono dim size={10}>+ add</Mono></Row>
                <Box pad={8}><Row justify="space-between"><Col gap={2}><Mono size={10} dim>0:08 – 0:13 · fade</Mono><span style={{ fontSize: 13 }}>Buy now →</span></Col><Mono>⋯</Mono></Row></Box>
                <Box pad={8}><Row justify="space-between"><Col gap={2}><Mono size={10} dim>0:21 – 0:28 · slide up</Mono><span style={{ fontSize: 13 }}>Try free</span></Col><Mono>⋯</Mono></Row></Box>
              </Col>
            )}
            {tab === 'audio' && (
              <Col gap={10}>
                <SectionLabel>background music</SectionLabel>
                <Col gap={4}>
                  <Mono size={11}>volume</Mono>
                  <div className="wobble" style={{ height: 18, border: `1.5px solid ${wfTokens.ink}`, position: 'relative' }}>
                    <div style={{ position: 'absolute', inset: 0, width: '60%', background: wfTokens.accent }} />
                  </div>
                  <Mono dim size={10}>−18 dB</Mono>
                </Col>
                <Row gap={6}><Chip on>enabled</Chip><Chip>off</Chip></Row>
                <Btn small ghost><Icon kind="refresh" size={12}/> regenerate music</Btn>
              </Col>
            )}
            {tab === 'scenes' && (
              <Col gap={6}>
                <SectionLabel>quick regenerate</SectionLabel>
                {sfScenes.map(s => (
                  <Box key={s.n} pad={8}>
                    <Row justify="space-between">
                      <Mono size={11}>scene {s.n}</Mono>
                      <Btn small ghost><Icon kind="refresh" size={12}/></Btn>
                    </Row>
                  </Box>
                ))}
              </Col>
            )}
          </Col>
        </div>
      </Col>
    </Frame>
  );
};

function Track({ label, icon, children }) {
  return (
    <Row gap={8} align="center">
      <Row gap={6} style={{ width: 72 }}>
        <Icon kind={icon} size={11}/>
        <Mono size={10}>{label}</Mono>
      </Row>
      <div className="wobble" style={{ flex: 1, height: 22, border: `1.5px solid ${wfTokens.ink}`, borderRadius: 3, display: 'flex', overflow: 'hidden' }}>
        {children}
      </div>
    </Row>
  );
}

// Sample subtitle cues by language
const sfSubtitles = {
  EN: [
    { start: '0:00', end: '0:02', text: 'Crafted from beans' },
    { start: '0:02', end: '0:05', text: 'grown at 1,800 metres' },
    { start: '0:05', end: '0:08', text: 'every cup tells a story' },
    { start: '0:08', end: '0:12', text: 'Sourced from one family farm' },
    { start: '0:12', end: '0:16', text: 'Served fresh, every morning' },
  ],
  HI: [
    { start: '0:00', end: '0:02', text: '1,800 मीटर पर उगाई गई' },
    { start: '0:02', end: '0:05', text: 'फलियों से बना' },
    { start: '0:05', end: '0:08', text: 'हर कप एक कहानी है' },
    { start: '0:08', end: '0:12', text: 'एक परिवार के खेत से' },
    { start: '0:12', end: '0:16', text: 'रोज़ ताज़ा परोसा' },
  ],
  MR: [
    { start: '0:00', end: '0:02', text: '१,८०० मीटर वर पिकवलेल्या' },
    { start: '0:02', end: '0:05', text: 'दाण्यांपासून बनवलेली' },
    { start: '0:05', end: '0:08', text: 'प्रत्येक कप एक कथा सांगतो' },
    { start: '0:08', end: '0:12', text: 'एका कुटुंबाच्या शेतातून' },
    { start: '0:12', end: '0:16', text: 'दररोज ताजे' },
  ],
  TA: [
    { start: '0:00', end: '0:02', text: '1,800 மீட்டர் உயரத்தில்' },
    { start: '0:02', end: '0:05', text: 'வளர்ந்த விதைகளில் இருந்து' },
    { start: '0:05', end: '0:08', text: 'ஒவ்வொரு கோப்பையும் ஒரு கதை' },
    { start: '0:08', end: '0:12', text: 'ஒரே குடும்ப பண்ணையில் இருந்து' },
    { start: '0:12', end: '0:16', text: 'தினமும் புதியதாக' },
  ],
  PA: [
    { start: '0:00', end: '0:02', text: '1,800 ਮੀਟਰ ਉੱਤੇ ਉਗਾਏ' },
    { start: '0:02', end: '0:05', text: 'ਬੀਨਜ਼ ਤੋਂ ਬਣਾਈ' },
    { start: '0:05', end: '0:08', text: 'ਹਰ ਕੱਪ ਇੱਕ ਕਹਾਣੀ' },
    { start: '0:08', end: '0:12', text: 'ਇੱਕ ਪਰਿਵਾਰਕ ਖੇਤ ਤੋਂ' },
    { start: '0:12', end: '0:16', text: 'ਹਰ ਸਵੇਰ ਤਾਜ਼ਾ' },
  ],
};

// ───── 5. Export Modal ─────────────────────────────────────────
SF.Export = function ExportScreen({ lang = 'EN', state = 'configure' }) {
  return (
    <Frame url="video.studio/projects/np-coffee/review">
      {/* dim background = the review screen */}
      <div style={{ position: 'absolute', inset: 0, background: wfTokens.paper2, opacity: 0.5 }} />
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
        <Box pad={0} style={{ width: 460, background: wfTokens.paper, boxShadow: '4px 6px 0 rgba(0,0,0,0.06)' }}>
          {state === 'configure' && (
            <Col gap={14} style={{ padding: '20px 24px' }}>
              <Row justify="space-between"><H size={26}>Export</H><Mono>✕</Mono></Row>
              <Divider />

              <Field label="language" value="English (read-only from review)" />
              <Field label="format"   ctrl={<Row gap={6}><Chip on>MP4</Chip><Mono dim size={10}>more soon</Mono></Row>} />
              <Field label="quality"  ctrl={<Row gap={6}><Chip>720p</Chip><Chip on>1080p</Chip></Row>} />
              <Field label="aspect"   value="9:16 · locked from brief" />
              <Field label="subtitles" ctrl={<Row gap={6}><Chip on>burned in</Chip><Chip>sidecar .srt</Chip><Chip>both</Chip></Row>} />
              <Row justify="space-between" style={{ marginTop: 4 }}>
                <Mono dim size={11}>estimated size</Mono>
                <Mono size={11}>~ 14 MB</Mono>
              </Row>

              <Divider />
              <Row gap={8} justify="flex-end">
                <Btn small ghost>cancel</Btn>
                <Btn small primary>start export</Btn>
              </Row>
            </Col>
          )}
          {state === 'progress' && (
            <Col gap={14} style={{ padding: '24px 28px' }}>
              <Row justify="space-between"><H size={26}>Exporting…</H><Mono>✕</Mono></Row>
              <Col gap={6}>
                <div className="wobble" style={{ height: 18, border: `1.5px solid ${wfTokens.ink}`, position: 'relative' }}>
                  <div style={{ position: 'absolute', inset: 0, width: '42%', background: wfTokens.accent }} />
                </div>
                <Mono dim size={11}>42% · muxing audio and burning subtitles…</Mono>
              </Col>
              <Mono dim size={10}>you can close this modal — we'll keep going in the background</Mono>
            </Col>
          )}
          {state === 'done' && (
            <Col gap={14} style={{ padding: '24px 28px' }}>
              <Row justify="space-between" align="center">
                <Row gap={8}><Icon kind="check" size={18}/><H size={26}>Export ready</H></Row>
                <Mono>✕</Mono>
              </Row>
              <Box pad={12} dashed>
                <Row justify="space-between">
                  <Col gap={2}>
                    <span style={{ fontSize: 14 }}>northbean_{lang.toLowerCase()}_1080p.mp4</span>
                    <Mono dim size={10}>14.2 MB · 9:16 · burned subs · {lang}</Mono>
                  </Col>
                  <Icon kind="download" size={16}/>
                </Row>
              </Box>
              <Row gap={8}>
                <Btn small primary style={{ flex: 1, justifyContent: 'center' }}><Icon kind="download" size={12}/> download</Btn>
                <Btn small ghost style={{ flex: 1, justifyContent: 'center' }}>copy link</Btn>
              </Row>
              <Mono dim size={10}>signed link expires in 1 h</Mono>
            </Col>
          )}
        </Box>
      </div>
    </Frame>
  );
};

function Field({ label, value, ctrl }) {
  return (
    <Row justify="space-between" align="center">
      <Mono size={11} dim style={{ width: 100 }}>{label}</Mono>
      <div style={{ flex: 1, textAlign: 'right' }}>
        {ctrl || <span style={{ fontSize: 13 }}>{value}</span>}
      </div>
    </Row>
  );
}

function truncate(s, n) { return s.length > n ? s.slice(0, n - 1) + '…' : s; }

Object.assign(window, SF);
window.ExportScreen = SF.Export;
