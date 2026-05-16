// App state machine + conversation script + scene/language data.

const CONVERSATION = [
  {
    key: 'type',
    summaryLabel: 'Type',
    question: "Hey — let's plan your video. What kind are we making?",
    chips: ['Explainer', 'Cinematic', 'Social reel', 'Ad', 'Product demo', 'Pitch'],
  },
  {
    key: 'topic',
    summaryLabel: 'Topic',
    question: 'Got it. What\'s it about? A sentence is enough.',
    chips: ['Coffee brand launch', 'Fitness app', 'B2B onboarding', 'Travel destination', 'Restaurant menu'],
    multiline: true,
  },
  {
    key: 'style',
    summaryLabel: 'Style',
    question: 'What visual style are you going for?',
    chips: ['Realistic', 'Animated', 'Documentary', 'Stop-motion', 'Stylised'],
  },
  {
    key: 'sceneRefs',
    summaryLabel: 'Scene refs',
    question: "Do you have any scene or location references? Even a mood-board helps us match the look.",
    chips: ['Upload reference images', 'Use a link / Pinterest board', 'Match my brand kit', 'Skip — no references'],
    kind: 'reference',
    referenceKind: 'scene',
  },
  {
    key: 'duration',
    summaryLabel: 'Duration',
    question: 'About how long should it be?',
    chips: ['15s', '30s', '45s', '60s'],
  },
  {
    key: 'aspect',
    summaryLabel: 'Aspect',
    question: 'Which aspect ratio? This affects framing.',
    chips: ['9:16 (vertical)', '16:9 (wide)', '1:1 (square)', '4:5 (feed)'],
  },
  {
    key: 'language',
    summaryLabel: 'Language',
    question: 'Which language for narration and subtitles?',
    chips: ['English', 'Hindi', 'Marathi', 'Tamil', 'Punjabi'],
  },
  {
    key: 'tone',
    summaryLabel: 'Tone',
    question: 'What tone should the narration carry?',
    chips: ['Warm', 'Energetic', 'Calm', 'Bold', 'Inspiring', 'Playful'],
  },
  {
    key: 'people',
    summaryLabel: 'People?',
    question: 'Should there be people on camera, or voice-over only?',
    chips: ['Voice-over only', 'A presenter', 'A small group', 'Background extras only'],
  },
  {
    key: 'charRefs',
    summaryLabel: 'Character refs',
    question: 'Have any character references? Upload photos so we can keep faces consistent across scenes.',
    chips: ['Upload 1 photo', 'Upload 2–3 photos', 'Describe in writing', 'Skip — generate fresh'],
    kind: 'reference',
    referenceKind: 'character',
    dependsOn: { key: 'people', notEquals: 'Voice-over only' },
  },
  {
    key: 'music',
    summaryLabel: 'Music',
    question: 'And background music?',
    chips: ['Soft acoustic', 'Cinematic strings', 'Upbeat electronic', 'Ambient', 'No music'],
  },
  {
    key: 'subtitles',
    summaryLabel: 'Subtitles',
    question: 'Last one — how should we handle subtitles?',
    chips: ['Auto-generate', 'Burned in', 'Sidecar .srt', 'None'],
  },
];

const SUMMARY_SLOTS = CONVERSATION.map(c => ({ key: c.key, label: c.summaryLabel }));

// Mock scenes for storyboard (5 scenes, ~6s each)
const SCENES = [
  {
    id: 's1',
    title: 'Opening pour',
    start: 0, duration: 6,
    visualPrompt: 'Hand pouring espresso into a tiny glass cup, warm overhead light, shallow depth of field, slow-motion drop.',
    script: 'Crafted from beans grown at 1,800 metres — every cup tells a story.',
    speaker: false,
    subtitle: 'auto',
    chars: [],
  },
  {
    id: 's2',
    title: 'Beans roasting',
    start: 6, duration: 6,
    visualPrompt: 'Beans roasting in a brass drum, warm tungsten light, slow rotation, steam catching the light.',
    script: 'Sourced from a single family farm in the Western Ghats.',
    speaker: false,
    subtitle: 'auto',
    chars: [],
  },
  {
    id: 's3',
    title: 'Fresh cup',
    start: 12, duration: 6,
    visualPrompt: 'Steam rising from a fresh cup of coffee, morning light through a café window, soft jazz feel.',
    script: 'Served fresh, every single morning.',
    speaker: false,
    subtitle: 'auto',
    chars: [],
  },
  {
    id: 's4',
    title: 'Barista handoff',
    start: 18, duration: 6,
    visualPrompt: 'A barista hands a cup across the counter, smiling, eye contact with the camera, soft bokeh background.',
    script: 'Made by hands that genuinely care.',
    speaker: true,
    subtitle: 'bottom',
    chars: ['Barista — warm smile, mid-20s, apron, neat hair'],
  },
  {
    id: 's5',
    title: 'Brand reveal',
    start: 24, duration: 6,
    visualPrompt: 'Logo lock-up over dark coffee texture, slow zoom out, brand mark reveals on a soft glow.',
    script: 'Northbean. Coffee, the long way.',
    speaker: false,
    subtitle: 'auto',
    chars: [],
  },
];

const SUBTITLES_BY_LANG = {
  English: [
    { start: 0,  end: 2,  text: 'Crafted from beans' },
    { start: 2,  end: 5,  text: 'grown at 1,800 metres' },
    { start: 5,  end: 6,  text: 'every cup tells a story.' },
    { start: 6,  end: 9,  text: 'Sourced from a single family farm' },
    { start: 9,  end: 12, text: 'in the Western Ghats.' },
    { start: 12, end: 15, text: 'Served fresh, every morning.' },
    { start: 18, end: 21, text: 'Made by hands that care.' },
    { start: 24, end: 27, text: 'Northbean.' },
    { start: 27, end: 30, text: 'Coffee, the long way.' },
  ],
  Hindi: [
    { start: 0,  end: 2,  text: '1,800 मीटर पर उगाई गई' },
    { start: 2,  end: 5,  text: 'फलियों से बना' },
    { start: 5,  end: 6,  text: 'हर कप एक कहानी है।' },
    { start: 6,  end: 9,  text: 'एक परिवार के खेत से' },
    { start: 9,  end: 12, text: 'पश्चिमी घाट में।' },
    { start: 12, end: 15, text: 'रोज़ ताज़ा परोसा जाता है।' },
    { start: 18, end: 21, text: 'देखभाल से बनाया गया।' },
    { start: 24, end: 27, text: 'नॉर्थबीन।' },
    { start: 27, end: 30, text: 'कॉफ़ी, लंबे रास्ते से।' },
  ],
  Marathi: [
    { start: 0,  end: 2,  text: '१,८०० मीटर वर पिकवलेल्या' },
    { start: 2,  end: 5,  text: 'दाण्यांपासून बनवलेली' },
    { start: 5,  end: 6,  text: 'प्रत्येक कप एक कथा सांगतो.' },
    { start: 6,  end: 9,  text: 'एका कुटुंबाच्या शेतातून' },
    { start: 9,  end: 12, text: 'पश्चिम घाटातील.' },
    { start: 12, end: 15, text: 'दररोज ताजे.' },
    { start: 18, end: 21, text: 'काळजीने बनवलेले.' },
    { start: 24, end: 27, text: 'नॉर्थबीन.' },
    { start: 27, end: 30, text: 'कॉफी, लांबचा प्रवास.' },
  ],
  Tamil: [
    { start: 0,  end: 2,  text: '1,800 மீட்டர் உயரத்தில்' },
    { start: 2,  end: 5,  text: 'வளர்ந்த விதைகளில் இருந்து' },
    { start: 5,  end: 6,  text: 'ஒவ்வொரு கோப்பையும் ஒரு கதை.' },
    { start: 6,  end: 9,  text: 'ஒரே குடும்ப பண்ணையில் இருந்து' },
    { start: 9,  end: 12, text: 'மேற்கு தொடர்ச்சி மலையில்.' },
    { start: 12, end: 15, text: 'தினமும் புதியதாக.' },
    { start: 18, end: 21, text: 'அக்கறையால் செய்யப்பட்டது.' },
    { start: 24, end: 27, text: 'நார்த்பீன்.' },
    { start: 27, end: 30, text: 'காபி, நீளமான பாதை.' },
  ],
  Punjabi: [
    { start: 0,  end: 2,  text: '1,800 ਮੀਟਰ ਉੱਤੇ ਉਗਾਏ' },
    { start: 2,  end: 5,  text: 'ਬੀਨਜ਼ ਤੋਂ ਬਣਾਈ' },
    { start: 5,  end: 6,  text: 'ਹਰ ਕੱਪ ਇੱਕ ਕਹਾਣੀ।' },
    { start: 6,  end: 9,  text: 'ਇੱਕ ਪਰਿਵਾਰਕ ਖੇਤ ਤੋਂ' },
    { start: 9,  end: 12, text: 'ਪੱਛਮੀ ਘਾਟ ਵਿੱਚ।' },
    { start: 12, end: 15, text: 'ਹਰ ਸਵੇਰ ਤਾਜ਼ਾ।' },
    { start: 18, end: 21, text: 'ਪਿਆਰ ਨਾਲ ਬਣਾਈ ਗਈ।' },
    { start: 24, end: 27, text: 'ਨੌਰਥਬੀਨ।' },
    { start: 27, end: 30, text: 'ਕੌਫ਼ੀ, ਲੰਮੇ ਰਸਤੇ।' },
  ],
};

const LANGUAGES = [
  { code: 'English',  native: 'English' },
  { code: 'Hindi',    native: 'हिन्दी' },
  { code: 'Marathi',  native: 'मराठी' },
  { code: 'Tamil',    native: 'தமிழ்' },
  { code: 'Punjabi',  native: 'ਪੰਜਾਬੀ' },
];

const STAGES = [
  { key: 'storyboard', label: 'Storyboard' },
  { key: 'scenes',     label: 'Scenes' },
  { key: 'voice',      label: 'Voice' },
  { key: 'subtitles',  label: 'Subtitles' },
  { key: 'overlays',   label: 'Overlays' },
  { key: 'composite',  label: 'Composite' },
];

// ─────────────────────────────────────────────────────────────────────
// Reducer
// ─────────────────────────────────────────────────────────────────────
const initialState = {
  screen: 'welcome',                   // welcome | chat | storyboard | progress | review
  projectTitle: 'Untitled video',
  // chat
  questionIndex: 0,                    // pointer into CONVERSATION
  brief: {},                           // { type, topic, style, ... }
  messages: [],                        // [{ role:'ai'|'user', text, chips? }]
  draft: '',                           // chat composer text
  isTyping: false,
  // storyboard
  scenes: SCENES.map(s => ({ ...s })),
  selectedSceneId: null,
  // progress
  jobId: null,
  stageIndex: 0,
  sceneStates: [],                     // per-scene render state
  // review
  playing: false,
  currentTime: 0,
  rightTab: 'subtitles',
  language: 'English',
  // export
  exportOpen: false,
  exportState: 'configure',            // configure | rendering | done
  exportProgress: 0,
  exportOptions: { quality: '1080p', subtitles: 'burned' },
};

function appReducer(state, action) {
  switch (action.type) {
    case 'SET':              return { ...state, ...action.patch };
    case 'GOTO':             return { ...state, screen: action.screen };
    case 'PUSH_MESSAGE':     return { ...state, messages: [...state.messages, action.message] };
    case 'REPLACE_LAST_MESSAGE': {
      const m = state.messages.slice(0, -1).concat(action.message);
      return { ...state, messages: m };
    }
    case 'SET_BRIEF':        return { ...state, brief: { ...state.brief, [action.key]: action.value } };
    case 'NEXT_QUESTION':    return { ...state, questionIndex: state.questionIndex + 1 };
    case 'SET_DRAFT':        return { ...state, draft: action.value };
    case 'SET_TYPING':       return { ...state, isTyping: action.value };
    case 'SELECT_SCENE':     return { ...state, selectedSceneId: action.id };
    case 'UPDATE_SCENE': {
      const scenes = state.scenes.map(s => s.id === action.id ? { ...s, ...action.patch } : s);
      return { ...state, scenes };
    }
    case 'SET_STAGE':        return { ...state, stageIndex: action.index };
    case 'SET_SCENE_STATES': return { ...state, sceneStates: action.states };
    case 'SET_TIME':         return { ...state, currentTime: action.t };
    case 'TOGGLE_PLAY':      return { ...state, playing: !state.playing };
    case 'SET_RIGHT_TAB':    return { ...state, rightTab: action.tab };
    case 'SET_LANG':         return { ...state, language: action.lang };
    case 'OPEN_EXPORT':      return { ...state, exportOpen: true, exportState: 'configure', exportProgress: 0 };
    case 'CLOSE_EXPORT':     return { ...state, exportOpen: false };
    case 'SET_EXPORT_STATE': return { ...state, exportState: action.value };
    case 'SET_EXPORT_PROG':  return { ...state, exportProgress: action.value };
    case 'SET_EXPORT_OPT':   return { ...state, exportOptions: { ...state.exportOptions, ...action.patch } };
    case 'RESET':            return { ...initialState };
    default:                 return state;
  }
}

const AppCtx = React.createContext(null);

function useApp() { return React.useContext(AppCtx); }

function AppProvider({ children }) {
  const [state, dispatch] = React.useReducer(appReducer, initialState);
  return <AppCtx.Provider value={{ state, dispatch }}>{children}</AppCtx.Provider>;
}

Object.assign(window, {
  CONVERSATION, SUMMARY_SLOTS, SCENES, SUBTITLES_BY_LANG, LANGUAGES, STAGES,
  AppCtx, AppProvider, useApp,
});
