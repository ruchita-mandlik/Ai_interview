import React, { useEffect, useState } from 'react';
import { intelligenceAPI, interviewAPI } from '../services/api';
import {
  Brain,
  TrendingUp,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Search,
  Compass,
  Sparkles,
  ArrowRight,
  ArrowUpRight,
  ArrowDownRight,
  Target,
  Award,
  Calendar,
  Layers,
  History,
  Info,
  X
} from 'lucide-react';
import { Line, Bar, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface InterviewMemoryProps {
  setActiveTab: (tab: string) => void;
  setSelectedInterviewId?: (id: string | null) => void;
  onToast: (msg: string, type?: string) => void;
}

export const InterviewMemory: React.FC<InterviewMemoryProps> = ({
  setActiveTab,
  setSelectedInterviewId,
  onToast
}) => {
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [analytics, setAnalytics] = useState<any | null>(null);
  const [summary, setSummary] = useState<any | null>(null);

  // Filter state
  const [timeFilter, setTimeFilter] = useState<'all' | '30d' | '90d' | 'custom'>('all');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');

  // Session comparison selection
  const [sessionAId, setSessionAId] = useState<string | null>(null);
  const [sessionBId, setSessionBId] = useState<string | null>(null);

  // Evidence Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [modalTitle, setModalTitle] = useState('');
  const [modalContent, setModalContent] = useState<React.ReactNode>(null);

  useEffect(() => {
    fetchDashboardData();
  }, [timeFilter, dateFrom, dateTo, sessionAId, sessionBId]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const params: any = {};
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (sessionAId) params.session_a_id = sessionAId;
      if (sessionBId) params.session_b_id = sessionBId;

      const [analyticsRes, summaryRes] = await Promise.allSettled([
        intelligenceAPI.getAnalyticsDashboard(params),
        intelligenceAPI.getMemorySummary()
      ]);

      if (analyticsRes.status === 'fulfilled') {
        setAnalytics(analyticsRes.value);
        if (!sessionAId && analyticsRes.value.session_comparison) {
          setSessionAId(analyticsRes.value.session_comparison.session_a_id);
          setSessionBId(analyticsRes.value.session_comparison.session_b_id);
        }
      }
      if (summaryRes.status === 'fulfilled') {
        setSummary(summaryRes.value);
      }
    } catch (err: any) {
      onToast(`Failed to load memory analytics: ${err.message || 'Error'}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSyncTelemetry = async () => {
    try {
      setSyncing(true);
      onToast('Syncing interview memory intelligence...', 'info');
      await fetchDashboardData();
      onToast('Interview memory telemetry synchronized!', 'success');
    } catch (err: any) {
      onToast(`Sync failed: ${err.message || 'Error'}`, 'error');
    } finally {
      setSyncing(false);
    }
  };

  const handleTimeFilterChange = (filter: 'all' | '30d' | '90d') => {
    setTimeFilter(filter);
    const now = new Date();
    if (filter === '30d') {
      const d = new Date();
      d.setDate(now.getDate() - 30);
      setDateFrom(d.toISOString().split('T')[0]);
      setDateTo('');
    } else if (filter === '90d') {
      const d = new Date();
      d.setDate(now.getDate() - 90);
      setDateFrom(d.toISOString().split('T')[0]);
      setDateTo('');
    } else {
      setDateFrom('');
      setDateTo('');
    }
  };

  const inspectSession = async (sessionId: string) => {
    setModalTitle('Session Evidence Inspector');
    setModalContent(<div style={{ padding: '20px', textAlign: 'center', color: '#9CA3AF' }}>Loading session evaluations...</div>);
    setModalOpen(true);

    try {
      const res = await interviewAPI.getDetail(sessionId);
      const qs = res.questions || [];

      setModalContent(
        <div>
          <div style={{ marginBottom: '14px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '10px' }}>
            <h4 style={{ margin: '0 0 4px 0', fontSize: '16px', color: '#FFF' }}>{res.title || 'Technical Practice'}</h4>
            <div style={{ fontSize: '13px', color: '#9CA3AF' }}>
              Role: {res.target_role || 'Candidate'} • Topic: {res.topic || 'Technical'} ({res.difficulty || 'Medium'})
            </div>
          </div>
          <div style={{ maxHeight: '55vh', overflowY: 'auto' }}>
            {qs.length === 0 ? (
              <p style={{ color: '#9CA3AF', fontSize: '13px' }}>No question evaluations recorded.</p>
            ) : (
              qs.map((q: any, idx: number) => {
                const ev = q.evaluations && q.evaluations.length > 0 ? q.evaluations[0] : null;
                const score = ev ? Math.round(ev.overall_score > 10 ? ev.overall_score : ev.overall_score * 10) : '--';
                return (
                  <div key={q.id || idx} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '12px 14px', marginBottom: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <strong style={{ color: '#E0E7FF', fontSize: '13px' }}>Q{idx + 1}: {q.skill || q.category || 'Question'}</strong>
                      <span style={{ fontSize: '12px', fontWeight: 700, color: '#60A5FA' }}>Score: {score}%</span>
                    </div>
                    <p style={{ fontSize: '13px', color: '#D1D5DB', margin: 0 }}>{q.question_text}</p>
                  </div>
                );
              })
            )}
          </div>
        </div>
      );
    } catch (err: any) {
      setModalContent(<div style={{ color: '#EF4444', padding: '16px' }}>Failed to load evidence: {err.message}</div>);
    }
  };

  const inspectWeakness = (w: any) => {
    setModalTitle(`Weakness Evidence: ${w.concept}`);
    setModalContent(
      <div>
        <div style={{ marginBottom: '12px', color: '#9CA3AF', fontSize: '13px' }}>
          Category: <strong style={{ color: '#FFF' }}>{w.category}</strong> • Distinct Sessions: <strong style={{ color: '#F87171' }}>{w.session_occurrences}</strong>
        </div>
        <div style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px', padding: '14px', marginBottom: '14px' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#F87171', textTransform: 'uppercase', marginBottom: '4px' }}>Sample Answer Evidence</div>
          <div style={{ fontSize: '13px', color: '#E2E8F0', fontStyle: 'italic' }}>"{w.sample_evidence || 'Captured across evaluated responses.'}"</div>
        </div>
        <div>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase' }}>Observed Across Sessions:</span>
          <ul style={{ paddingLeft: '18px', marginTop: '6px', fontSize: '13px', color: '#D1D5DB' }}>
            {(w.supporting_sessions || []).map((s: any, idx: number) => (
              <li key={idx} style={{ marginBottom: '4px' }}>
                <strong>{s.title}</strong> ({s.date}) — Scored {Math.round(s.score || 0)}%
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
    setModalOpen(true);
  };

  if (loading && !analytics) {
    return (
      <div className="glass-card" style={{ textAlign: 'center', padding: '60px 20px', margin: '40px auto', maxWidth: '600px' }}>
        <div style={{ fontSize: '36px', marginBottom: '16px' }}>⏳</div>
        <h3 style={{ color: '#F9FAFB', marginBottom: '8px' }}>Analyzing Cross-Session Memory & Charts...</h3>
        <p style={{ color: '#9CA3AF', fontSize: '14px' }}>
          Synthesizing longitudinal progress, persistent mistakes, and like-for-like session comparisons from your actual interview records.
        </p>
      </div>
    );
  }

  const validSessionsCount = analytics?.valid_evaluated_sessions ?? 0;

  if (validSessionsCount === 0) {
    return (
      <div className="glass-card" style={{ textAlign: 'center', padding: '60px 24px', margin: '40px auto', maxWidth: '640px' }}>
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>💡</div>
        <h2 style={{ color: '#F9FAFB', marginBottom: '12px', fontWeight: 800 }}>No Interview Memory Recorded Yet</h2>
        <p style={{ color: '#9CA3AF', fontSize: '15px', lineHeight: '1.6', marginBottom: '28px' }}>
          {analytics?.exclusion_reason || 'Complete your first mock interview or answer adaptive questions. The Intelligence Engine will remember your performance, detect recurring mistakes, and prove real skill improvement.'}
        </p>
        <div style={{ display: 'flex', justifyContent: 'center', gap: '14px', flexWrap: 'wrap' }}>
          <button className="btn btn-primary btn-lg" onClick={() => setActiveTab('adaptive')}>
            <Sparkles size={18} /> Start Adaptive Interview
          </button>
          <button className="btn btn-secondary btn-lg" onClick={() => setActiveTab('dashboard')}>
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const avgVal = Number(analytics?.overall_average_score ?? 0);
  const avgScore = !isNaN(avgVal) ? Math.round(avgVal) : 0;
  const improvedSkills = (analytics?.skill_performance || []).filter((s: any) => s.status === 'improving' || s.status === 'mastered');
  const activeWeaknesses = (analytics?.weakness_frequency || []).filter((w: any) => w.status === 'active_weakness');

  // Chart 1: Score Trajectory
  const trajectory = analytics?.score_trajectory || [];
  const trajectoryData = {
    labels: trajectory.map((t: any) => t.date),
    datasets: [{
      label: 'Evaluation Score',
      data: trajectory.map((t: any) => t.score),
      borderColor: '#3B82F6',
      backgroundColor: 'rgba(59, 130, 246, 0.15)',
      borderWidth: 3,
      tension: 0.35,
      fill: true,
      pointBackgroundColor: '#60A5FA',
      pointRadius: 6,
      pointHoverRadius: 8
    }]
  };

  // Chart 2: Improvement Trend & Moving Average
  const improvement = analytics?.improvement_trend || [];
  const improvementData = {
    labels: improvement.map((i: any) => i.date),
    datasets: [
      {
        label: 'Session Score',
        data: improvement.map((i: any) => i.score),
        borderColor: '#93C5FD',
        borderDash: [5, 5],
        borderWidth: 2,
        pointRadius: 4,
        pointBackgroundColor: '#3B82F6'
      },
      {
        label: 'Cumulative Average Velocity',
        data: improvement.map((i: any) => i.cumulative_avg),
        borderColor: '#8B5CF6',
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        borderWidth: 3,
        tension: 0.3,
        fill: true,
        pointRadius: 5,
        pointBackgroundColor: '#A78BFA'
      }
    ]
  };

  // Chart 3: Skill-wise Performance (Baseline vs Latest)
  const skillsDisplay = (analytics?.skill_performance || []).slice(0, 8);
  const skillPerfData = {
    labels: skillsDisplay.map((s: any) => s.skill),
    datasets: [
      {
        label: 'Baseline Score',
        data: skillsDisplay.map((s: any) => s.baseline_score),
        backgroundColor: '#93C5FD',
        borderRadius: 6
      },
      {
        label: 'Latest Score',
        data: skillsDisplay.map((s: any) => s.latest_score),
        backgroundColor: '#10B981',
        borderRadius: 6
      }
    ]
  };

  // Chart 4: Weakness Frequency
  const weaknessDisplay = (analytics?.weakness_frequency || []).slice(0, 7);
  const weaknessFreqData = {
    labels: weaknessDisplay.map((w: any) => w.concept.length > 25 ? w.concept.substring(0, 23) + '...' : w.concept),
    datasets: [{
      label: 'Distinct Session Occurrences',
      data: weaknessDisplay.map((w: any) => w.session_occurrences),
      backgroundColor: weaknessDisplay.map((w: any) => w.status === 'active_weakness' ? '#EF4444' : w.status === 'improving' ? '#F59E0B' : '#10B981'),
      borderRadius: 6
    }]
  };

  // Chart 5: Session Comparison
  const comp = analytics?.session_comparison;
  const rubric = comp?.rubric_comparison || [];
  const sessionCompData = {
    labels: rubric.map((r: any) => r.dimension),
    datasets: [
      {
        label: comp?.session_a_title ? `${comp.session_a_title} (${comp.session_a_score}%)` : 'Session A',
        data: rubric.map((r: any) => r.session_a_score || 0),
        backgroundColor: '#3B82F6',
        borderRadius: 6
      },
      {
        label: comp?.session_b_title ? `${comp.session_b_title} (${comp.session_b_score}%)` : 'Session B',
        data: rubric.map((r: any) => r.session_b_score || 0),
        backgroundColor: '#6B7280',
        borderRadius: 6
      }
    ]
  };

  // Chart 6: Score Distribution
  const scoreDist = analytics?.score_distribution || [];
  const scoreDistData = {
    labels: scoreDist.map((d: any) => `${d.bin_label} (${d.count})`),
    datasets: [{
      data: scoreDist.map((d: any) => d.count),
      backgroundColor: ['#EF4444', '#F59E0B', '#3B82F6', '#10B981'],
      borderWidth: 2,
      borderColor: '#111827'
    }]
  };

  const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: { min: 0, max: 100, ticks: { color: '#9CA3AF', callback: (v: any) => v + '%' }, grid: { color: 'rgba(255,255,255,0.06)' } },
      x: { ticks: { color: '#9CA3AF', font: { size: 11 } }, grid: { display: false } }
    },
    plugins: {
      legend: { labels: { color: '#D1D5DB', boxWidth: 12, font: { size: 11 } } }
    }
  };

  return (
    <section style={{ maxWidth: '1200px', margin: '0 auto', paddingBottom: '60px' }}>
      {/* Top Welcome Banner */}
      <div
        className="glass-card"
        style={{
          background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.8) 0%, rgba(49, 46, 129, 0.8) 50%, rgba(67, 56, 202, 0.8) 100%)',
          marginBottom: '20px',
          padding: '30px',
          border: '1px solid rgba(139, 92, 246, 0.3)'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '20px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <span
                style={{
                  background: 'rgba(245, 158, 11, 0.2)',
                  color: '#FCD34D',
                  fontSize: '11px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  padding: '4px 10px',
                  borderRadius: '9999px',
                  border: '1px solid rgba(245, 158, 11, 0.4)'
                }}
              >
                Persistent Memory Active
              </span>
              <span style={{ color: '#C7D2FE', fontSize: '13px', fontWeight: 600 }}>
                Target Role: {analytics?.target_role || 'Software Engineering'}
              </span>
            </div>
            <h1 style={{ fontSize: '26px', fontWeight: 800, color: '#FFF', margin: '0 0 8px 0', fontFamily: 'Outfit' }}>
              Cross-Session Intelligence & Telemetry Dashboard
            </h1>
            <p style={{ color: '#E0E7FF', fontSize: '14px', lineHeight: '1.5', margin: 0 }}>
              Real evaluated performance across interviews. Interactive analytics tracking your score trajectory, recurring weaknesses, verified skill improvements, and targeted remediation.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
            <button
              onClick={handleSyncTelemetry}
              disabled={syncing}
              className="btn btn-secondary"
              style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}
            >
              <RefreshCw size={14} className={syncing ? 'spin' : ''} />
              {syncing ? 'Syncing...' : 'Sync Telemetry'}
            </button>
            <div style={{ display: 'flex', gap: '10px' }}>
              <div style={{ background: 'rgba(255, 255, 255, 0.08)', borderRadius: '10px', padding: '8px 14px', textAlign: 'center', minWidth: '85px' }}>
                <span style={{ fontSize: '20px', fontWeight: 800, color: '#FFF', display: 'block' }}>{validSessionsCount}</span>
                <span style={{ fontSize: '10px', color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 600 }}>Sessions</span>
              </div>
              <div style={{ background: 'rgba(255, 255, 255, 0.08)', borderRadius: '10px', padding: '8px 14px', textAlign: 'center', minWidth: '85px' }}>
                <span style={{ fontSize: '20px', fontWeight: 800, color: '#60A5FA', display: 'block' }}>{avgScore}%</span>
                <span style={{ fontSize: '10px', color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 600 }}>Avg Score</span>
              </div>
              <div style={{ background: 'rgba(255, 255, 255, 0.08)', borderRadius: '10px', padding: '8px 14px', textAlign: 'center', minWidth: '85px' }}>
                <span style={{ fontSize: '20px', fontWeight: 800, color: '#34D399', display: 'block' }}>{improvedSkills.length}</span>
                <span style={{ fontSize: '10px', color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 600 }}>Improved</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Date Filter & Exclusion Alert Bar */}
      <div
        className="glass-card"
        style={{
          padding: '14px 20px',
          marginBottom: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase' }}>Time Range:</span>
          <button
            className={`btn btn-sm ${timeFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => handleTimeFilterChange('all')}
          >
            All Time
          </button>
          <button
            className={`btn btn-sm ${timeFilter === '30d' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => handleTimeFilterChange('30d')}
          >
            Last 30 Days
          </button>
          <button
            className={`btn btn-sm ${timeFilter === '90d' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => handleTimeFilterChange('90d')}
          >
            Last 90 Days
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <label style={{ fontSize: '12px', color: '#9CA3AF' }}>From:</label>
          <input
            type="date"
            value={dateFrom}
            onChange={e => { setDateFrom(e.target.value); setTimeFilter('custom'); }}
            style={{ background: '#1F2937', color: '#FFF', border: '1px solid rgba(255,255,255,0.15)', padding: '4px 8px', borderRadius: '6px', fontSize: '12px' }}
          />
          <label style={{ fontSize: '12px', color: '#9CA3AF' }}>To:</label>
          <input
            type="date"
            value={dateTo}
            onChange={e => { setDateTo(e.target.value); setTimeFilter('custom'); }}
            style={{ background: '#1F2937', color: '#FFF', border: '1px solid rgba(255,255,255,0.15)', padding: '4px 8px', borderRadius: '6px', fontSize: '12px' }}
          />
        </div>

        {analytics?.excluded_incomplete_sessions > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#FCD34D', fontSize: '12px', background: 'rgba(245, 158, 11, 0.15)', padding: '4px 10px', borderRadius: '6px' }}>
            <Info size={14} />
            <span>{analytics.excluded_incomplete_sessions} session(s) excluded (in progress / unevaluated)</span>
          </div>
        )}
      </div>

      {/* Summary KPI Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div className="glass-card" style={{ padding: '16px 20px' }}>
          <span style={{ fontSize: '11px', color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700, display: 'block' }}>Evaluated Sessions</span>
          <span style={{ fontSize: '24px', fontWeight: 800, color: '#FFF' }}>{validSessionsCount}</span>
          <span style={{ fontSize: '12px', color: '#9CA3AF', display: 'block', marginTop: '2px' }}>
            {(analytics?.score_trajectory || []).reduce((acc: number, cur: any) => acc + (cur.total_questions || 0), 0)} questions evaluated
          </span>
        </div>

        <div className="glass-card" style={{ padding: '16px 20px' }}>
          <span style={{ fontSize: '11px', color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700, display: 'block' }}>Overall Average Score</span>
          <span style={{ fontSize: '24px', fontWeight: 800, color: '#60A5FA' }}>{avgScore}%</span>
          <span style={{ fontSize: '12px', color: '#9CA3AF', display: 'block', marginTop: '2px' }}>
            High: {analytics?.highest_score !== null ? `${Math.round(analytics.highest_score)}%` : '--'} | Low: {analytics?.lowest_score !== null ? `${Math.round(analytics.lowest_score)}%` : '--'}
          </span>
        </div>

        <div className="glass-card" style={{ padding: '16px 20px' }}>
          <span style={{ fontSize: '11px', color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700, display: 'block' }}>Verified Improved Skills</span>
          <span style={{ fontSize: '24px', fontWeight: 800, color: '#34D399' }}>{improvedSkills.length}</span>
          <span style={{ fontSize: '12px', color: '#9CA3AF', display: 'block', marginTop: '2px' }}>Supported by 2+ evaluations</span>
        </div>

        <div className="glass-card" style={{ padding: '16px 20px' }}>
          <span style={{ fontSize: '11px', color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700, display: 'block' }}>Recurring Weaknesses</span>
          <span style={{ fontSize: '24px', fontWeight: 800, color: '#F87171' }}>{activeWeaknesses.length}</span>
          <span style={{ fontSize: '12px', color: '#9CA3AF', display: 'block', marginTop: '2px' }}>Across 2+ distinct sessions</span>
        </div>
      </div>

      {/* Row 1 Charts: Score Trajectory & Improvement Trend */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '20px', marginBottom: '24px' }}>
        {/* Chart 1: Trajectory */}
        <div className="glass-card" style={{ padding: '22px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={18} color="#60A5FA" /> Chronological Score Trajectory
            </h3>
            <span style={{ fontSize: '11px', color: '#9CA3AF' }}>Click node to inspect</span>
          </div>
          <div style={{ height: '270px', position: 'relative' }}>
            <Line
              data={trajectoryData}
              options={{
                ...commonOptions,
                onClick: (_evt, els) => {
                  if (els && els.length > 0) {
                    const idx = els[0].index;
                    inspectSession(trajectory[idx].session_id);
                  }
                }
              }}
            />
          </div>
        </div>

        {/* Chart 2: Improvement Trend */}
        <div className="glass-card" style={{ padding: '22px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={18} color="#8B5CF6" /> Improvement Trend & Moving Average
            </h3>
            <span style={{ fontSize: '11px', color: '#9CA3AF' }}>Cumulative velocity</span>
          </div>
          <div style={{ height: '270px', position: 'relative' }}>
            <Line data={improvementData} options={commonOptions} />
          </div>
        </div>
      </div>

      {/* Row 2 Charts: Skill-wise Performance & Weakness Frequency */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '20px', marginBottom: '24px' }}>
        {/* Chart 3: Skill-wise Performance */}
        <div className="glass-card" style={{ padding: '22px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Target size={18} color="#34D399" /> Skill Performance (Baseline vs Latest)
            </h3>
            <span style={{ fontSize: '11px', color: '#9CA3AF' }}>Evidence-based</span>
          </div>
          <div style={{ height: '270px', position: 'relative' }}>
            <Bar data={skillPerfData} options={commonOptions} />
          </div>
        </div>

        {/* Chart 4: Weakness Frequency */}
        <div className="glass-card" style={{ padding: '22px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} color="#F87171" /> Weakness Frequency Across Sessions
            </h3>
            <span style={{ fontSize: '11px', color: '#9CA3AF' }}>Distinct Sessions Only</span>
          </div>
          <div style={{ height: '270px', position: 'relative' }}>
            <Bar
              data={weaknessFreqData}
              options={{
                indexAxis: 'y' as const,
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                  x: { ticks: { color: '#9CA3AF', stepSize: 1 }, grid: { color: 'rgba(255,255,255,0.06)' } },
                  y: { ticks: { color: '#9CA3AF', font: { size: 11 } }, grid: { display: false } }
                },
                plugins: { legend: { display: false } },
                onClick: (_evt, els) => {
                  if (els && els.length > 0) {
                    const idx = els[0].index;
                    inspectWeakness(weaknessDisplay[idx]);
                  }
                }
              }}
            />
          </div>
        </div>
      </div>

      {/* Row 3 Charts: Interactive Session Comparison & Score Distribution */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '20px', marginBottom: '24px' }}>
        {/* Chart 5: Session Comparison */}
        <div className="glass-card" style={{ padding: '22px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={18} color="#3B82F6" /> Session Comparison
            </h3>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <select
                value={sessionAId || ''}
                onChange={e => setSessionAId(e.target.value)}
                style={{ background: '#1F2937', color: '#FFF', border: '1px solid rgba(255,255,255,0.15)', padding: '4px 8px', borderRadius: '6px', fontSize: '12px' }}
              >
                {(analytics?.available_sessions || []).map((s: any) => (
                  <option key={s.id} value={s.id}>{s.title} ({s.score}%)</option>
                ))}
              </select>
              <span style={{ color: '#9CA3AF', fontSize: '11px', fontWeight: 700 }}>vs</span>
              <select
                value={sessionBId || ''}
                onChange={e => setSessionBId(e.target.value || null)}
                style={{ background: '#1F2937', color: '#FFF', border: '1px solid rgba(255,255,255,0.15)', padding: '4px 8px', borderRadius: '6px', fontSize: '12px' }}
              >
                <option value="">Baseline</option>
                {(analytics?.available_sessions || []).map((s: any) => (
                  <option key={s.id} value={s.id}>{s.title} ({s.score}%)</option>
                ))}
              </select>
            </div>
          </div>
          <div style={{ height: '240px', position: 'relative' }}>
            <Bar data={sessionCompData} options={commonOptions} />
          </div>

          {/* Badges for Resolved Weaknesses and Repeated Mistakes */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '14px', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
            <div>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#34D399', display: 'block', marginBottom: '4px' }}>✅ Resolved Weaknesses:</span>
              <div style={{ fontSize: '12px', color: '#9CA3AF' }}>
                {(comp?.newly_resolved_weaknesses || []).length > 0 ? (
                  comp.newly_resolved_weaknesses.map((item: any, idx: number) => {
                    const text = typeof item === 'object' && item !== null ? (item.concept_or_skill || item.concept || item.skill || JSON.stringify(item)) : String(item);
                    return <span key={idx} style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34D399', padding: '2px 6px', borderRadius: '4px', marginRight: '4px', display: 'inline-block', marginBottom: '2px' }}>{text}</span>;
                  })
                ) : (
                  <span style={{ fontStyle: 'italic' }}>None recorded</span>
                )}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#F87171', display: 'block', marginBottom: '4px' }}>🚨 Repeated Mistakes:</span>
              <div style={{ fontSize: '12px', color: '#9CA3AF' }}>
                {(comp?.repeated_mistakes || []).length > 0 ? (
                  comp.repeated_mistakes.map((item: any, idx: number) => {
                    const text = typeof item === 'object' && item !== null ? (item.mistake || item.concept || JSON.stringify(item)) : String(item);
                    return <span key={idx} style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#F87171', padding: '2px 6px', borderRadius: '4px', marginRight: '4px', display: 'inline-block', marginBottom: '2px' }}>{text}</span>;
                  })
                ) : (
                  <span style={{ fontStyle: 'italic' }}>Zero repeated mistakes</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Chart 6: Score Distribution */}
        <div className="glass-card" style={{ padding: '22px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Award size={18} color="#F59E0B" /> Score Distribution Bins
            </h3>
            <span style={{ fontSize: '11px', color: '#9CA3AF' }}>Valid Completed Sessions</span>
          </div>
          <div style={{ height: '270px', position: 'relative' }}>
            <Doughnut
              data={scoreDistData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { position: 'right', labels: { color: '#D1D5DB', boxWidth: 12, font: { size: 11 } } }
                }
              }}
            />
          </div>
        </div>
      </div>

      {/* Next Best Action Banner */}
      <div
        className="glass-card"
        style={{
          background: 'linear-gradient(135deg, rgba(30, 58, 138, 0.35) 0%, rgba(29, 78, 216, 0.25) 100%)',
          border: '1px solid rgba(59, 130, 246, 0.4)',
          marginBottom: '28px',
          padding: '24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '18px'
        }}
      >
        <div style={{ maxWidth: '750px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <Target size={18} color="#60A5FA" />
            <span style={{ fontSize: '12px', fontWeight: 700, color: '#93C5FD', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Next Best Action Recommendation
            </span>
          </div>
          <div style={{ fontSize: '15px', color: '#EFF6FF', fontWeight: 600, lineHeight: '1.5' }}>
            {summary?.next_best_action?.title ? (
              <span><strong>{summary.next_best_action.title}</strong> — {summary.next_best_action.reason}</span>
            ) : (
              'Complete focused practice on recurring technical weak areas to raise composite evaluation score.'
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={() => setActiveTab('adaptive')} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={16} /> Adaptive Drill
          </button>
          <button className="btn btn-secondary" onClick={() => setActiveTab('roadmap')} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Compass size={16} /> View Tasks
          </button>
        </div>
      </div>

      {/* Evaluated Sessions Archive Table */}
      <div className="glass-card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Evaluated Sessions Archive</h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#9CA3AF' }}>
              Direct telemetry of every session evaluated by the AI intelligence engine.
            </p>
          </div>
          <span style={{ fontSize: '12px', color: '#9CA3AF' }}>{trajectory.length} Valid Sessions</span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', color: '#9CA3AF' }}>
                <th style={{ padding: '12px 14px' }}>Date</th>
                <th style={{ padding: '12px 14px' }}>Role / Topic</th>
                <th style={{ padding: '12px 14px' }}>Type</th>
                <th style={{ padding: '12px 14px' }}>Score</th>
                <th style={{ padding: '12px 14px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {trajectory.slice().reverse().map((sess: any) => {
                const score = Math.round(sess.score);
                return (
                  <tr key={sess.session_id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                    <td style={{ padding: '14px', color: '#FFF' }}>{sess.date}</td>
                    <td style={{ padding: '14px', fontWeight: 600, color: '#D1D5DB' }}>
                      {sess.session_title} • {sess.topic}
                    </td>
                    <td style={{ padding: '14px', color: '#9CA3AF' }}>{sess.difficulty} Mock</td>
                    <td style={{ padding: '14px', fontWeight: 700, color: score >= 70 ? '#34D399' : score >= 50 ? '#60A5FA' : '#F87171' }}>
                      {score}%
                    </td>
                    <td style={{ padding: '14px', textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '8px' }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => inspectSession(sess.session_id)}
                          title="Inspect Evidence"
                        >
                          🔍 Inspect
                        </button>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            if (setSelectedInterviewId) setSelectedInterviewId(sess.session_id);
                            setActiveTab('analysis');
                          }}
                        >
                          <Search size={13} /> Analysis
                        </button>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            if (setSelectedInterviewId) setSelectedInterviewId(sess.session_id);
                            setActiveTab('roadmap');
                          }}
                        >
                          <Compass size={13} /> Roadmap
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal / Evidence Inspector */}
      {modalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1200,
            padding: '20px'
          }}
          onClick={() => setModalOpen(false)}
        >
          <div
            className="glass-card"
            style={{
              maxWidth: '650px',
              width: '100%',
              background: '#111827',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '14px',
              padding: '24px'
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
              <h3 style={{ margin: 0, fontSize: '18px', color: '#FFF' }}>{modalTitle}</h3>
              <button onClick={() => setModalOpen(false)} style={{ background: 'none', border: 'none', color: '#9CA3AF', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>
            {modalContent}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '18px', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '12px' }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setModalOpen(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
