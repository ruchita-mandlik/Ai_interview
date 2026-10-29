import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  Brain,
  PieChart,
  Play,
  Mic,
  PenTool,
  Code,
  LineChart,
  CalendarCheck,
  Search,
  Compass,
  Sparkles,
  User as UserIcon,
  LogIn,
  LogOut,
  Lightbulb
} from 'lucide-react';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  openAuthModal: () => void;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, setActiveTab, openAuthModal }) => {
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <header className="app-header">
      <div className="logo-container" onClick={() => setActiveTab('dashboard')}>
        <div className="logo-icon">
          <Brain size={24} />
        </div>
        <div className="logo-text">
          <span className="brand-name">Interview<span className="brand-highlight">AI</span></span>
          <span className="brand-tagline">AI Interview Studio & Analytics</span>
        </div>
      </div>

      <nav className="main-nav">
        <button
          className={`nav-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
          id="nav-dashboard"
        >
          <PieChart size={18} /> <span>Dashboard</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'practice' ? 'active' : ''}`}
          onClick={() => setActiveTab('practice')}
          id="nav-start-practice"
        >
          <Play size={18} /> <span>Start Practice</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'interview' || activeTab === 'adaptive' ? 'active' : ''}`}
          onClick={() => setActiveTab('adaptive')}
          id="nav-adaptive-interview"
        >
          <Sparkles size={18} /> <span>Adaptive Interview</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'analysis' ? 'active' : ''}`}
          onClick={() => setActiveTab('analysis')}
          id="nav-deep-analysis"
        >
          <Search size={18} /> <span>Deep AI Analysis</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'roadmap' || activeTab === 'plan' ? 'active' : ''}`}
          onClick={() => setActiveTab('roadmap')}
          id="nav-preparation-roadmap"
        >
          <Compass size={18} /> <span>Preparation Roadmap</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'memory' ? 'active' : ''}`}
          onClick={() => setActiveTab('memory')}
          id="nav-interview-memory"
        >
          <Lightbulb size={18} /> <span>Interview Memory</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'voice' ? 'active' : ''}`}
          onClick={() => setActiveTab('voice')}
          id="nav-voice"
        >
          <Mic size={18} /> <span>Voice Simulator</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'sandbox' ? 'active' : ''}`}
          onClick={() => setActiveTab('sandbox')}
          id="nav-sandbox"
        >
          <Code size={18} /> <span>Code Sandbox</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'analytics' ? 'active' : ''}`}
          onClick={() => setActiveTab('analytics')}
          id="nav-analytics"
        >
          <LineChart size={18} /> <span>Analytics</span>
        </button>
      </nav>

      <div className="header-actions">
        {isAuthenticated && user ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div className="user-pill" onClick={() => setActiveTab('profile')}>
              <div className="user-avatar">
                <UserIcon size={16} />
              </div>
              <div className="user-info">
                <span className="user-name">{user.name}</span>
                <span className="user-role">{user.target_role}</span>
              </div>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={logout} title="Sign Out">
              <LogOut size={16} />
            </button>
          </div>
        ) : (
          <button className="btn btn-gradient-sm" onClick={openAuthModal}>
            <LogIn size={16} /> Login / Register
          </button>
        )}
      </div>
    </header>
  );
};
