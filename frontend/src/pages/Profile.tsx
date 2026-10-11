import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { userAPI } from '../services/api';
import { User as UserIcon, Save } from 'lucide-react';

interface ProfileProps {
  onToast: (msg: string, type?: string) => void;
}

export const Profile: React.FC<ProfileProps> = ({ onToast }) => {
  const { user, updateUser } = useAuth();
  const [name, setName] = useState(user?.name || '');
  const [role, setRole] = useState(user?.target_role || 'Software Developer');
  const [exp, setExp] = useState(user?.experience_level || 'Intermediate');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      setName(user.name || '');
      setRole(user.target_role || 'Software Developer');
      setExp(user.experience_level || 'Intermediate');
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const updated = await userAPI.updateProfile({ name, target_role: role, experience_level: exp });
      updateUser(updated);
      onToast("Profile updated successfully!", "success");
    } catch (err: any) {
      onToast("Failed to update profile", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section>
      <div className="glass-card" style={{ maxWidth: '600px', margin: '0 auto' }}>
        <h2><UserIcon className="gradient-icon" size={24} style={{ display: 'inline', marginRight: '8px' }} /> Candidate Profile Settings</h2>

        <form onSubmit={handleSubmit} style={{ marginTop: '20px' }}>
          <div className="form-group">
            <label>Full Name</label>
            <input className="form-control" value={name} onChange={e => setName(e.target.value)} required />
          </div>

          <div className="form-group" style={{ marginTop: '16px' }}>
            <label>Email Address</label>
            <input className="form-control" value={user?.email || ''} disabled />
          </div>

          <div className="form-group" style={{ marginTop: '16px' }}>
            <label>Target Role</label>
            <select className="form-control" value={role} onChange={e => setRole(e.target.value)}>
              <option value="Software Developer">Software Developer</option>
              <option value="Backend Engineer">Backend Engineer</option>
              <option value="Frontend Engineer">Frontend Engineer</option>
              <option value="Full Stack Engineer">Full Stack Engineer</option>
              <option value="DevOps & Cloud Engineer">DevOps & Cloud Engineer</option>
              <option value="Data Engineer">Data Engineer</option>
            </select>
          </div>

          <div className="form-group" style={{ marginTop: '16px' }}>
            <label>Experience Level</label>
            <select className="form-control" value={exp} onChange={e => setExp(e.target.value)}>
              <option value="Junior (0-2 Yrs)">Junior (0-2 Yrs)</option>
              <option value="Intermediate (2-5 Yrs)">Intermediate (2-5 Yrs)</option>
              <option value="Senior (5+ Yrs)">Senior (5+ Yrs)</option>
            </select>
          </div>

          <button type="submit" className="btn btn-gradient btn-lg margin-top-lg" disabled={loading}>
            <Save size={18} /> {loading ? "Saving..." : "Save Profile Changes"}
          </button>
        </form>
      </div>
    </section>
  );
};
