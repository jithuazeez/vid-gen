// Screen 1: Chat — agent-driven with suggestion chips. Real conversational flow.

function ChatScreen() {
  const { state, dispatch } = useApp();
  const { messages, questionIndex, brief, draft, isTyping } = state;
  const scrollRef = React.useRef(null);
  const inputRef = React.useRef(null);

  const currentQ = CONVERSATION[questionIndex];
  const allDone = questionIndex >= CONVERSATION.length;

  // bootstrap: post first AI question once
  React.useEffect(() => {
    if (messages.length === 0) {
      askQuestion(0);
    }
    // eslint-disable-next-line
  }, []);

  // autoscroll on new message
  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  function askQuestion(idx) {
    const q = CONVERSATION[idx];
    if (!q) {
      dispatch({ type: 'PUSH_MESSAGE', message: {
        role: 'ai',
        text: `Perfect — I have everything I need. We'll plan a ${brief.duration || ''} ${brief.style || ''} ${brief.type || 'video'} about ${brief.topic || 'your topic'}, in ${brief.language || 'English'}. Ready when you are.`,
        ready: true,
      }});
      return;
    }
    dispatch({ type: 'SET_TYPING', value: true });
    setTimeout(() => {
      dispatch({ type: 'SET_TYPING', value: false });
      dispatch({ type: 'PUSH_MESSAGE', message: { role: 'ai', text: q.question, chips: q.chips, key: q.key } });
    }, 550);
  }

  function submit(rawValue) {
    const value = String(rawValue || '').trim();
    if (!value) return;
    if (allDone) return;

    const q = CONVERSATION[questionIndex];
    // normalize chip labels with parens (e.g., "9:16 (vertical)" → "9:16")
    const briefValue = value.includes('(') ? value.split('(')[0].trim() : value;

    dispatch({ type: 'PUSH_MESSAGE', message: { role: 'user', text: value } });
    dispatch({ type: 'SET_BRIEF', key: q.key, value: briefValue });
    dispatch({ type: 'SET_DRAFT', value: '' });
    dispatch({ type: 'NEXT_QUESTION' });

    setTimeout(() => askQuestion(questionIndex + 1), 350);
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit(draft);
    }
  };

  const onStartPlanning = () => {
    dispatch({ type: 'GOTO', screen: 'storyboard' });
  };

  // count filled slots
  const filled = SUMMARY_SLOTS.filter(s => brief[s.key]).length;

  return (
    <ProjectShell
      onBack={() => dispatch({ type: 'GOTO', screen: 'welcome' })}
      left={<>
        <BrandMark />
        <Separator vertical style={{ height: 20 }} />
        <span style={{ fontSize: 14, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{state.projectTitle}</span>
        <Badge variant="secondary" style={{ marginLeft: 2, flexShrink: 0 }}>draft</Badge>
      </>}
      right={<>
        <Button variant="ghost" size="icon-sm" title="Settings"><ICON.Settings size={15} /></Button>
        <ThemeToggle />
      </>}
    >
      <div data-screen-label="01-chat" style={{
        display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 340px',
        height: 'calc(100vh - 56px)', minHeight: 0,
      }}>
        {/* Chat column */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, borderRight: '1px solid var(--border)' }}>
          <div ref={scrollRef} style={{
            flex: 1, overflowY: 'auto', padding: '32px 40px 24px',
          }}>
            <div style={{ maxWidth: 680, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 18 }}>
              {messages.map((m, i) => (
                <MessageBubble
                  key={i}
                  msg={m}
                  onChip={submit}
                  disabledChips={i !== messages.length - 1 || m.role !== 'ai'}
                />
              ))}
              {isTyping && <TypingBubble />}
              {allDone && messages[messages.length - 1]?.ready && (
                <div className="anim-fade" style={{ display: 'flex', justifyContent: 'flex-start', marginTop: 4 }}>
                  <Button onClick={onStartPlanning}>
                    Start planning <ICON.ArrowRight size={14} />
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Composer */}
          <div style={{ borderTop: '1px solid var(--border)', padding: '14px 40px 18px', background: 'var(--background)' }}>
            <div style={{ maxWidth: 680, margin: '0 auto' }}>
              <div style={{
                display: 'flex', alignItems: 'flex-end', gap: 8,
                border: '1px solid var(--input)', borderRadius: 12,
                padding: 8, background: 'var(--background)',
                transition: 'border-color 120ms ease, box-shadow 120ms ease',
              }}
              onFocusCapture={(e) => { e.currentTarget.style.borderColor = 'var(--ring)'; e.currentTarget.style.boxShadow = '0 0 0 3px hsl(0 0% 50% / 0.10)'; }}
              onBlurCapture={(e) => { e.currentTarget.style.borderColor = 'var(--input)'; e.currentTarget.style.boxShadow = 'none'; }}
              >
                <textarea
                  ref={inputRef}
                  value={draft}
                  onChange={(e) => dispatch({ type: 'SET_DRAFT', value: e.target.value })}
                  onKeyDown={onKeyDown}
                  placeholder={allDone ? "All set — click Start planning above." : "Type your reply, or tap a suggestion above…"}
                  disabled={allDone}
                  rows={1}
                  style={{
                    flex: 1, resize: 'none',
                    border: 'none', outline: 'none', background: 'transparent',
                    fontSize: 15, lineHeight: 1.5, padding: '6px 8px',
                    fontFamily: 'var(--font-sans)', color: 'var(--foreground)',
                    minHeight: 28, maxHeight: 160,
                  }}
                />
                <Button variant="ghost" size="icon-sm" title="Voice"><ICON.Mic size={15} /></Button>
                <Button size="icon-sm" onClick={() => submit(draft)} disabled={!draft.trim() || allDone} title="Send (↵)">
                  <ICON.ArrowUp size={14} />
                </Button>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, color: 'var(--muted-foreground)', gap: 12 }}>
                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Chips are shortcuts — typing always wins.</span>
                <span style={{ whiteSpace: 'nowrap', flexShrink: 0 }}><Mono size={11} dim>↵</Mono> send · <Mono size={11} dim>⇧↵</Mono> newline</span>
              </div>
            </div>
          </div>
        </div>

        {/* Brief summary */}
        <BriefSummary brief={brief} filled={filled} total={SUMMARY_SLOTS.length} allDone={allDone} onStart={onStartPlanning} />
      </div>
    </ProjectShell>
  );
}

function MessageBubble({ msg, onChip, disabledChips }) {
  if (msg.role === 'user') {
    return (
      <div className="anim-fade" style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <div style={{
          maxWidth: 520,
          background: 'var(--primary)', color: 'var(--primary-foreground)',
          padding: '10px 14px', borderRadius: '16px 16px 4px 16px',
          fontSize: 15, lineHeight: 1.5,
        }}>{msg.text}</div>
      </div>
    );
  }
  // AI
  return (
    <div className="anim-fade" style={{ display: 'flex', gap: 12 }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%',
        background: 'var(--primary)', color: 'var(--primary-foreground)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <ICON.Sparkles size={14} strokeWidth={2} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0, maxWidth: 560 }}>
        <div style={{
          fontSize: 15, lineHeight: 1.55, color: 'var(--foreground)',
        }}>{msg.text}</div>
        {msg.chips && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {msg.chips.map(c => (
              <Chip key={c} onClick={() => onChip(c)} disabled={disabledChips}>{c}</Chip>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="anim-fade" style={{ display: 'flex', gap: 12 }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%',
        background: 'var(--primary)', color: 'var(--primary-foreground)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <ICON.Sparkles size={14} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, height: 24 }}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--muted-foreground)',
            animation: `bounceDot 1.2s ${i * 0.15}s infinite ease-in-out both`,
          }} />
        ))}
      </div>
    </div>
  );
}

function BriefSummary({ brief, filled, total, allDone, onStart }) {
  return (
    <aside style={{
      background: 'var(--background)',
      display: 'flex', flexDirection: 'column', minHeight: 0,
    }}>
      <div style={{ padding: '20px 20px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--foreground)', whiteSpace: 'nowrap' }}>Your brief</span>
          <Mono dim size={11} style={{ whiteSpace: 'nowrap' }}>{filled} / {total}</Mono>
        </div>
        <div style={{ height: 4, background: 'var(--muted)', borderRadius: 999, overflow: 'hidden' }}>
          <div style={{
            height: '100%', width: `${(filled / total) * 100}%`,
            background: 'var(--foreground)', borderRadius: 999,
            transition: 'width 350ms cubic-bezier(.22,1,.36,1)',
          }} />
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 16px 16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {SUMMARY_SLOTS.map(slot => {
            const value = brief[slot.key];
            const done = !!value;
            return (
              <div key={slot.key} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 8px', borderRadius: 6,
                gap: 12,
                background: done ? 'transparent' : 'transparent',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                  <div style={{
                    width: 16, height: 16, borderRadius: '50%',
                    border: `1.5px solid ${done ? 'var(--foreground)' : 'var(--border)'}`,
                    background: done ? 'var(--foreground)' : 'transparent',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                    transition: 'all 160ms ease',
                  }}>
                    {done && <ICON.Check size={10} strokeWidth={3} style={{ color: 'var(--background)' }} />}
                  </div>
                  <span style={{ fontSize: 13, color: done ? 'var(--foreground)' : 'var(--muted-foreground)' }}>{slot.label}</span>
                </div>
                <span style={{
                  fontSize: 13, color: done ? 'var(--foreground)' : 'var(--muted-foreground)',
                  fontWeight: done ? 500 : 400,
                  textAlign: 'right',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  maxWidth: 200,
                }}>{value || '—'}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ padding: '12px 16px 20px', borderTop: '1px solid var(--border)' }}>
        <Button onClick={onStart} disabled={!allDone} style={{ width: '100%' }}>
          Start planning <ICON.ArrowRight size={14} />
        </Button>
        {!allDone && (
          <div style={{ marginTop: 8, textAlign: 'center', fontSize: 11, color: 'var(--muted-foreground)' }}>
            Enabled when all 10 slots are filled
          </div>
        )}
      </div>
    </aside>
  );
}

window.ChatScreen = ChatScreen;
