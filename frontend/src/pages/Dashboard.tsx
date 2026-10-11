import React, { useEffect, useState } from 'react';
import { OverviewAnalyticsResponse } from '../types';
import { analyticsAPI } from '../services/api';
import { Play, Code, ClipboardCheck, Star, Trophy, MessageSquare, LineChart as ChartIcon, CheckCircle2, AlertCircle, Calendar } from 'lucide-react';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

interface DashboardProps {
  setActiveTab: (tab: string) => void;
  onToast: (msg: string, type?: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ setActiveTab, onToast }) => {
  const [data, setData] = useState<OverviewAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      const res = await analyticsAPI.getOverview();
      setData(res);
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
            <button className="btn btn-primary btn-lg" onClick={() => setActiveTab('interview')}>
              <Play size={18} /> Start New Mock Interview
            </button>
            <button className="btn btn-secondary btn-lg" onClick={() => setActiveTab('sandbox')}>
              <Code size={18} /> Test Code Sandbox
            </button>
          </div>
        </div>

        <div className="hero-widget glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase' }}>Readiness Index</span>
            <span style={{ fontSize: '11px', padding: '4px 10px', borderRadius: '9999px', background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
              Live AI Gauge
            </span>
          </div>

          <div style={{ textAlign: 'center', margin: '20px 0' }}>
            <span style={{ fontSize: '38px', fontWeight: 800, fontFamily: 'Outfit', color: '#10B981' }}>
              {data ? `${data.readiness_score}%` : '84%'}
            </span>
            <span style={{ display: 'block', fontSize: '12px', color: '#6B7280' }}>Target Role Match</span>
          </div>

          <p style={{ fontSize: '13px', color: '#9CA3AF', lineHeight: '1.4' }}>
            {data?.readiness_explanation || "Your performance shows high proficiency. Practice weak topics to reach top 5% standing."}
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

          <button className="btn btn-gradient w-100" onClick={() => setActiveTab('plan')}>
            <Calendar size={18} /> Launch 7-Day Study Plan
          </button>
        </div>
      </div>
    </section>
  );
};
