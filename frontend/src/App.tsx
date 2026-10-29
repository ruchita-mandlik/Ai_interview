import React, { useState } from 'react';
import { AuthProvider } from './context/AuthContext';
import { Header } from './components/Header';
import { AuthModal } from './components/AuthModal';
import { Dashboard } from './pages/Dashboard';
import { MockInterview } from './pages/MockInterview';
import { VoiceInterview } from './pages/VoiceInterview';
import { CodeSandbox } from './pages/CodeSandbox';
import { Analytics } from './pages/Analytics';
import { StudyPlan } from './pages/StudyPlan';
import { InterviewMemory } from './pages/InterviewMemory';
import { Profile } from './pages/Profile';

export const AppContent: React.FC = () => {
  // Support hash routing like /app#analysis or /app#roadmap or /app#interview or /app#memory
  const getInitialTab = () => {
    const hash = window.location.hash.replace('#', '').toLowerCase();
    const validTabs = ['dashboard', 'practice', 'interview', 'adaptive', 'analysis', 'roadmap', 'plan', 'memory', 'voice', 'sandbox', 'analytics', 'profile'];
    if (hash && validTabs.includes(hash)) {
      return hash === 'plan' ? 'roadmap' : hash;
    }
    const params = new URLSearchParams(window.location.search);
    const tabParam = params.get('tab');
    if (tabParam && validTabs.includes(tabParam.toLowerCase())) {
      return tabParam.toLowerCase() === 'plan' ? 'roadmap' : tabParam.toLowerCase();
    }
    return 'dashboard';
  };

  const getInitialInterviewId = () => {
    const params = new URLSearchParams(window.location.search);
    return params.get('interviewId') || params.get('id') || null;
  };

  const [activeTab, setActiveTabState] = useState<string>(getInitialTab);
  const [selectedInterviewId, setSelectedInterviewId] = useState<string | null>(getInitialInterviewId);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: string } | null>(null);

  // Sync hash change dynamically
  React.useEffect(() => {
    const handleHashChange = () => {
      const rawHash = window.location.hash.replace('#', '').toLowerCase();
      if (!rawHash) return;
      if (rawHash === 'plan') {
        setActiveTabState('roadmap');
      } else {
        const valid = ['dashboard', 'practice', 'interview', 'adaptive', 'analysis', 'roadmap', 'memory', 'voice', 'sandbox', 'analytics', 'profile'];
        if (valid.includes(rawHash)) {
          setActiveTabState(rawHash);
        }
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const setActiveTab = (tab: string) => {
    const normalized = tab === 'plan' ? 'roadmap' : tab;
    setActiveTabState(normalized);
    window.location.hash = normalized;
  };

  const showToast = (msg: string, type = 'info') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  return (
    <div id="app-container">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        openAuthModal={() => setIsAuthOpen(true)}
      />

      <main className="content-area">
        {activeTab === 'dashboard' && (
          <Dashboard
            setActiveTab={setActiveTab}
            setSelectedInterviewId={setSelectedInterviewId}
            onToast={showToast}
          />
        )}
        {activeTab === 'practice' && (
          <MockInterview
            key="standard-practice"
            isAdaptive={false}
            onToast={showToast}
            openAuthModal={() => setIsAuthOpen(true)}
            setActiveTab={setActiveTab}
            setSelectedInterviewId={setSelectedInterviewId}
          />
        )}
        {(activeTab === 'interview' || activeTab === 'adaptive') && (
          <MockInterview
            key="adaptive-interview"
            isAdaptive={true}
            onToast={showToast}
            openAuthModal={() => setIsAuthOpen(true)}
            setActiveTab={setActiveTab}
            setSelectedInterviewId={setSelectedInterviewId}
          />
        )}
        {activeTab === 'analysis' && (
          <StudyPlan
            key={`analysis-${selectedInterviewId || 'latest'}`}
            initialSubTab="questions"
            selectedInterviewId={selectedInterviewId}
            setSelectedInterviewId={setSelectedInterviewId}
            onToast={showToast}
            setActiveTab={setActiveTab}
          />
        )}
        {(activeTab === 'roadmap' || activeTab === 'plan') && (
          <StudyPlan
            key={`roadmap-${selectedInterviewId || 'latest'}`}
            initialSubTab="roadmap"
            selectedInterviewId={selectedInterviewId}
            setSelectedInterviewId={setSelectedInterviewId}
            onToast={showToast}
            setActiveTab={setActiveTab}
          />
        )}
        {activeTab === 'memory' && (
          <InterviewMemory
            setActiveTab={setActiveTab}
            setSelectedInterviewId={setSelectedInterviewId}
            onToast={showToast}
          />
        )}
        {activeTab === 'voice' && (
          <VoiceInterview
            onToast={showToast}
            openAuthModal={() => setIsAuthOpen(true)}
            setActiveTab={setActiveTab}
            setSelectedInterviewId={setSelectedInterviewId}
          />
        )}
        {activeTab === 'sandbox' && <CodeSandbox onToast={showToast} openAuthModal={() => setIsAuthOpen(true)} />}
        {activeTab === 'analytics' && <Analytics />}
        {activeTab === 'profile' && <Profile onToast={showToast} />}
      </main>

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onToast={showToast}
      />

      {toast && (
        <div style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          background: 'rgba(17, 24, 39, 0.95)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          padding: '14px 20px',
          borderRadius: '8px',
          color: '#FFF',
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          zIndex: 1100
        }}>
          {toast.msg}
        </div>
      )}
    </div>
  );
};

export const App: React.FC = () => (
  <AuthProvider>
    <AppContent />
  </AuthProvider>
);

export default App;
