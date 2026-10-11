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
import { Profile } from './pages/Profile';

export const AppContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: string } | null>(null);

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
        {activeTab === 'dashboard' && <Dashboard setActiveTab={setActiveTab} onToast={showToast} />}
        {activeTab === 'interview' && <MockInterview onToast={showToast} openAuthModal={() => setIsAuthOpen(true)} setActiveTab={setActiveTab} />}
        {activeTab === 'voice' && <VoiceInterview onToast={showToast} openAuthModal={() => setIsAuthOpen(true)} setActiveTab={setActiveTab} />}
        {activeTab === 'sandbox' && <CodeSandbox onToast={showToast} openAuthModal={() => setIsAuthOpen(true)} />}
        {activeTab === 'analytics' && <Analytics />}
        {activeTab === 'plan' && <StudyPlan />}
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
