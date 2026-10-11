import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { X, LogIn, UserPlus, Zap } from 'lucide-react';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onToast: (msg: string, type?: string) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onToast }) => {
  const { login, register, demoLogin } = useAuth();
  const [tab, setTab] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (tab === 'login') {
        await login(email, password);
        onToast("Logged in successfully!", "success");
      } else {
        await register(name, email, password);
        onToast("Account registered successfully!", "success");
      }
      onClose();
    } catch (err: any) {
      onToast(err.response?.data?.detail || err.message || "Auth error", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setLoading(true);
    try {
      await demoLogin();
      onToast("Logged in as Demo Candidate!", "success");
      onClose();
    } catch (err: any) {
      onToast("Demo login failed", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-box glass-card">
        <button className="modal-close" onClick={onClose}>
          <X size={20} />
        </button>

        <div className="auth-tabs">
          <button
            className={`auth-tab-btn ${tab === 'login' ? 'active' : ''}`}
            onClick={() => setTab('login')}
          >
            Login
          </button>
          <button
            className={`auth-tab-btn ${tab === 'register' ? 'active' : ''}`}
            onClick={() => setTab('register')}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {tab === 'register' && (
            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label>Full Name</label>
              <input
                type="text"
                className="form-control"
                placeholder="Alex Morgan"
                value={name}
                onChange={e => setName(e.target.value)}
                required
              />
            </div>
          )}

          <div className="form-group">
            <label>Email Address</label>
            <input
              type="email"
              className="form-control"
              placeholder="candidate@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group" style={{ marginTop: '16px' }}>
            <label>Password</label>
            <input
              type="password"
              className="form-control"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>

          <button type="submit" className="btn btn-gradient btn-lg w-100" style={{ marginTop: '24px' }} disabled={loading}>
            {tab === 'login' ? <LogIn size={18} /> : <UserPlus size={18} />}
            {loading ? "Processing..." : tab === 'login' ? "Sign In" : "Create Account"}
          </button>
        </form>

        <div className="auth-divider"><span>OR</span></div>

        <button className="btn btn-secondary w-100" onClick={handleDemo} disabled={loading}>
          <Zap size={18} style={{ color: '#F59E0B' }} /> Quick Start as Demo Candidate
        </button>
      </div>
    </div>
  );
};
