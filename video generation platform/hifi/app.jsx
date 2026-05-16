// Root — routes between screens.

function Root() {
  const { state } = useApp();
  const screen = state.screen;

  let view = null;
  if (screen === 'welcome')         view = <WelcomeScreen />;
  else if (screen === 'chat')       view = <ChatScreen />;
  else if (screen === 'storyboard') view = <StoryboardScreen />;
  else if (screen === 'progress')   view = <ProgressScreen />;
  else if (screen === 'review')     view = <ReviewScreen />;

  return <div key={screen} className="anim-fade">{view}</div>;
}

function App() {
  return (
    <AppProvider>
      <Root />
    </AppProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
