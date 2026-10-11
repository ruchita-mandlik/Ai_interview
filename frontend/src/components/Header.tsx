import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  Brain,
  PieChart,
  Mic,
  PenTool,
  Code,
  LineChart,
  CalendarCheck,
  User as UserIcon,
  LogIn,
  LogOut
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
          <span className="brand-name">AI Prep<span className="brand-highlight">Pro</span></span>
          <span className="brand-tagline">AI Technical Interview Coach</span>
        </div>
      </div>

      <nav className="main-nav">
        <button
          className={`nav-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          <PieChart size={18} /> <span>Dashboard</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'interview' ? 'active' : ''}`}
          onClick={() => setActiveTab('interview')}
        >
          <PenTool size={18} /> <span>Written Mock</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'voice' ? 'active' : ''}`}
          onClick={() => setActiveTab('voice')}
        >
          <Mic size={18} /> <span>Voice Simulator</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'sandbox' ? 'active' : ''}`}
          onClick={() => setActiveTab('sandbox')}
        >
          <Code size={18} /> <span>Code Sandbox</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'analytics' ? 'active' : ''}`}
          onClick={() => setActiveTab('analytics')}
        >
          <LineChart size={18} /> <span>Analytics</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'plan' ? 'active' : ''}`}
          onClick={() => setActiveTab('plan')}
        >
          <CalendarCheck size={18} /> <span>7-Day Plan</span>
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
