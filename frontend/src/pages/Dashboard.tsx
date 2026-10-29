import React, { useEffect, useState } from 'react';
import { OverviewAnalyticsResponse, Interview } from '../types';
import { analyticsAPI, interviewAPI, readinessAPI } from '../services/api';
import {
  Play,
  Code,
  ClipboardCheck,
  Star,
  Trophy,
  MessageSquare,
  LineChart as ChartIcon,
  CheckCircle2,
  AlertCircle,
  Calendar,
  Sparkles,
  Search,
  Compass,
  Brain,
  ArrowRight,
  RefreshCw
} from 'lucide-react';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

interface DashboardProps {
  setActiveTab: (tab: string) => void;
  setSelectedInterviewId?: (id: string | null) => void;
  onToast: (msg: string, type?: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ setActiveTab, setSelectedInterviewId, onToast }) => {
  const [data, setData] = useState<OverviewAnalyticsResponse | null>(null);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const handleRecalculate = async () => {
    try {
      setRecalculating(true);
      onToast('Recalculating readiness intelligence with latest session data...', 'info');
      await readinessAPI.recalculate();
      await fetchDashboard();
      onToast('Readiness scores updated successfully!', 'success');
    } catch (err: any) {
      onToast(`Recalculation failed: ${err.message || 'Error'}`, 'error');
    } finally {
      setRecalculating(false);
    }
  };


  const fetchDashboard = async () => {
    try {
      setLoading(true);
      const [analyticsRes, interviewsRes] = await Promise.allSettled([
        analyticsAPI.getOverview(),
        interviewAPI.list()
      ]);
      if (analyticsRes.status === 'fulfilled') {
        setData(analyticsRes.value);
      }
      if (interviewsRes.status === 'fulfilled') {
        setInterviews(interviewsRes.value);
      }
    } catch (err: any) {
      // Toast handled by API or context
    } finally {
      setLoading(false);
    }
  };

  const chartData = {
    labels: data?.performance_trend.map(t => t.date) || [],
    datasets: [{
      label: 'Overall Score',
      data: data?.performance_trend.map(t => t.score) || [],
      borderColor: '#8B5CF6',
      backgroundColor: 'rgba(139, 92, 246, 0.15)',
      borderWidth: 3,
      fill: true,
      tension: 0.4,
      pointRadius: 5,
      pointBackgroundColor: '#EC4899'
    }]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      y: { min: 40, max: 100, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#9CA3AF' } },
      x: { grid: { display: false }, ticks: { color: '#9CA3AF' } }
    }
  };

  return (
    <section>
      <div className="hero-banner">
        <div className="hero-text">
          <h1 className="hero-title">
            Ace Your Next Tech Interview with <span className="gradient-text">AI Precision</span>
          </h1>
          <p className="hero-subtitle">
            Adaptive technical & behavioral mock sessions, instant AI scoring, live code diagnostic reviews, and data-driven 7-day study paths.
          </p>
          <div className="hero-buttons">
            <button className="btn btn-primary btn-lg" onClick={() => setActiveTab('practice')} id="hero-btn-practice">
              <Play size={18} /> Start Practice (Standard Mock)
            </button>
            <button className="btn btn-primary btn-lg" onClick={() => setActiveTab('adaptive')} id="hero-btn-adaptive" style={{ background: 'linear-gradient(135deg, #8B5CF6 0%, #EC4899 100%)' }}>
              <Sparkles size={18} /> Adaptive AI Interview
            </button>
            <button className="btn btn-secondary btn-lg" onClick={() => setActiveTab('sandbox')} id="hero-btn-sandbox">
              <Code size={18} /> Test Code Sandbox
            </button>
          </div>
        </div>

        <div className="hero-widget glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase' }}>Readiness Index</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                onClick={handleRecalculate}
                disabled={recalculating}
                className="btn btn-secondary"
                style={{ fontSize: '11px', padding: '3px 8px', display: 'flex', alignItems: 'center', gap: '4px' }}
                title="Recalculate live AI readiness from evaluations"
              >
                <RefreshCw size={12} className={recalculating ? 'spin' : ''} />
                {recalculating ? 'Syncing...' : 'Recalculate'}
              </button>
              <span style={{ fontSize: '11px', padding: '4px 10px', borderRadius: '9999px', background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                Live AI Gauge
              </span>
            </div>
          </div>

          <div style={{ textAlign: 'center', margin: '20px 0' }}>
            <span style={{ fontSize: '38px', fontWeight: 800, fontFamily: 'Outfit', color: data && data.readiness_score > 0 ? '#10B981' : '#6B7280' }}>
              {data ? `${Math.round(data.readiness_score)}%` : '0%'}
            </span>
            <span style={{ display: 'block', fontSize: '12px', color: '#6B7280' }}>Target Role Match</span>
          </div>

          <p style={{ fontSize: '13px', color: '#9CA3AF', lineHeight: '1.4' }}>
            {data?.readiness_explanation || "Complete mock interviews to calibrate your AI readiness telemetry."}
          </p>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card glass-card">
          <div className="stat-icon icon-purple"><ClipboardCheck size={24} /></div>
          <div>
            <span className="stat-title">Interviews Completed</span>
            <span className="stat-number">{data?.interviews_completed ?? 0}</span>
          </div>
        </div>

        <div className="stat-card glass-card">
          <div className="stat-icon icon-blue"><Star size={24} /></div>
          <div>
            <span className="stat-title">Average Evaluation</span>
            <span className="stat-number">{data?.average_score ?? 0}/100</span>
          </div>
        </div>

        <div className="stat-card glass-card">
          <div className="stat-icon icon-emerald"><Trophy size={24} /></div>
          <div>
            <span className="stat-title">Best Mock Score</span>
            <span className="stat-number">{data?.best_score ?? 0}/100</span>
          </div>
        </div>

        <div className="stat-card glass-card">
          <div className="stat-icon icon-amber"><MessageSquare size={24} /></div>
          <div>
            <span className="stat-title">Questions Answered</span>
            <span className="stat-number">{data?.questions_answered ?? 0}</span>
          </div>
        </div>
      </div>

      {/* 3 Core Highlight Features Banner */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '20px',
        margin: '28px 0'
      }}>
        {/* Feature 1: Adaptive Interview */}
        <div className="glass-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', borderTop: '3px solid #8B5CF6' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <div style={{ background: 'rgba(139, 92, 246, 0.15)', padding: '10px', borderRadius: '10px', color: '#8B5CF6' }}>
                <Brain size={22} />
              </div>
              <h3 style={{ margin: 0, fontSize: '17px', fontWeight: 700 }}>Adaptive Interview</h3>
            </div>
            <p style={{ fontSize: '13px', color: '#9CA3AF', lineHeight: '1.5', margin: '0 0 16px 0' }}>
              Dynamic difficulty escalation or simplification, contextual follow-up probes, multi-dimensional rubric scoring, and live clarification hints.
            </p>
          </div>
          <button
            className="btn btn-primary w-100"
            onClick={() => setActiveTab('adaptive')}
            id="dash-btn-adaptive"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
          >
            <Sparkles size={16} /> Launch Adaptive Session
          </button>
        </div>

        {/* Feature 2: Deep AI Analysis */}
        <div className="glass-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', borderTop: '3px solid #3B82F6' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <div style={{ background: 'rgba(59, 130, 246, 0.15)', padding: '10px', borderRadius: '10px', color: '#3B82F6' }}>
                <Search size={22} />
              </div>
              <h3 style={{ margin: 0, fontSize: '17px', fontWeight: 700 }}>Deep AI Interview Analysis</h3>
            </div>
            <p style={{ fontSize: '13px', color: '#9CA3AF', lineHeight: '1.5', margin: '0 0 16px 0' }}>
              Unpack question-by-question evidence, conceptual misconceptions, missing concepts, rubric diagnostics, and confirmed skill gaps.
            </p>
          </div>
          <button
            className="btn btn-secondary w-100"
            onClick={() => setActiveTab('analysis')}
            id="dash-btn-analysis"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', borderColor: 'rgba(59, 130, 246, 0.4)', color: '#93C5FD' }}
          >
            <Search size={16} /> View Deep Analysis
          </button>
        </div>

        {/* Feature 3: Preparation Roadmap */}
        <div className="glass-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', borderTop: '3px solid #10B981' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <div style={{ background: 'rgba(16, 185, 129, 0.15)', padding: '10px', borderRadius: '10px', color: '#10B981' }}>
                <Compass size={22} />
              </div>
              <h3 style={{ margin: 0, fontSize: '17px', fontWeight: 700 }}>Personalized Roadmap</h3>
            </div>
            <p style={{ fontSize: '13px', color: '#9CA3AF', lineHeight: '1.5', margin: '0 0 16px 0' }}>
              Sequenced milestone phases, interactive daily task checklists, target interview scheduling, and targeted reassessment questions.
            </p>
          </div>
          <button
            className="btn btn-secondary w-100"
            onClick={() => setActiveTab('roadmap')}
            id="dash-btn-roadmap"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', borderColor: 'rgba(16, 185, 129, 0.4)', color: '#6EE7B7' }}
          >
            <Compass size={16} /> Open Preparation Roadmap
          </button>
        </div>
      </div>

      <div className="dashboard-split">
        <div className="glass-card chart-card">
          <div className="card-header">
            <h3><ChartIcon className="gradient-icon" size={20} style={{ display: 'inline', marginRight: '8px' }} /> Performance History Trend</h3>
          </div>
          <div className="chart-wrapper">
            {loading ? <p>Loading chart telemetry...</p> : <Line data={chartData} options={chartOptions} />}
          </div>
        </div>

        <div className="glass-card topic-card">
          <div className="card-header">
            <h3>Skill Focus Areas</h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '24px' }}>
            <div style={{ padding: '14px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <span style={{ fontSize: '12px', color: '#9CA3AF', display: 'block' }}>
                <CheckCircle2 size={14} color="#10B981" style={{ display: 'inline', marginRight: '4px' }} /> Strongest Subject
              </span>
              <strong style={{ fontSize: '15px' }}>{data?.strongest_topic || "Java & OOP"}</strong>
            </div>

            <div style={{ padding: '14px', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
              <span style={{ fontSize: '12px', color: '#9CA3AF', display: 'block' }}>
                <AlertCircle size={14} color="#F59E0B" style={{ display: 'inline', marginRight: '4px' }} /> Priority Focus
              </span>
              <strong style={{ fontSize: '15px' }}>{data?.weakest_topic || "Operating Systems"}</strong>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-primary w-100" onClick={() => setActiveTab('analysis')}>
              <Search size={16} /> Deep Analysis
            </button>
            <button className="btn btn-secondary w-100" onClick={() => setActiveTab('roadmap')}>
              <Compass size={16} /> Roadmap
            </button>
          </div>
        </div>
      </div>

      {/* Recent Interview Activity Section with direct action buttons */}
      <div className="glass-card" style={{ marginTop: '28px', padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Recent Interview Sessions</h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#9CA3AF' }}>
              Select any completed session to inspect its deep evidence analysis or preparation roadmap.
            </p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab('interview')}>
            <Play size={14} /> New Practice
          </button>
        </div>

        {interviews.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '36px 16px', color: '#9CA3AF' }}>
            <p>No interview sessions found yet. Start an adaptive interview session above!</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', color: '#9CA3AF' }}>
                  <th style={{ padding: '12px 14px' }}>Session / Role</th>
                  <th style={{ padding: '12px 14px' }}>Topic & Difficulty</th>
                  <th style={{ padding: '12px 14px' }}>Date</th>
                  <th style={{ padding: '12px 14px' }}>Status</th>
                  <th style={{ padding: '12px 14px' }}>Score</th>
                  <th style={{ padding: '12px 14px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {interviews.slice(0, 5).map(item => (
                  <tr key={item.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                    <td style={{ padding: '14px', fontWeight: 600, color: '#FFF' }}>
                      {item.title || item.role || 'Mock Session'}
                    </td>
                    <td style={{ padding: '14px', color: '#9CA3AF' }}>
                      {item.topic || (item.topics && item.topics[0]) || 'General'} • {item.difficulty || 'Medium'}
                    </td>
                    <td style={{ padding: '14px', color: '#9CA3AF' }}>
                      {item.created_at || item.started_at ? new Date(item.created_at || item.started_at).toLocaleDateString() : 'Recent'}
                    </td>
                    <td style={{ padding: '14px' }}>
                      <span className={`badge ${item.status === 'completed' ? 'badge-success' : 'badge-amber'}`}>
                        {item.status === 'completed' ? 'Completed' : 'In Progress'}
                      </span>
                    </td>
                    <td style={{ padding: '14px', fontWeight: 700, color: item.status === 'completed' ? '#10B981' : '#9CA3AF' }}>
                      {item.status === 'completed' ? `${Math.round(item.overall_score || 0)}%` : 'In Progress'}
                    </td>
                    <td style={{ padding: '14px', textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '8px' }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            if (setSelectedInterviewId) setSelectedInterviewId(item.id);
                            setActiveTab('analysis');
                          }}
                          title="View Deep AI Analysis"
                        >
                          <Search size={14} /> Analysis
                        </button>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            if (setSelectedInterviewId) setSelectedInterviewId(item.id);
                            setActiveTab('roadmap');
                          }}
                          title="View Preparation Roadmap"
                        >
                          <Compass size={14} /> Roadmap
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
};
