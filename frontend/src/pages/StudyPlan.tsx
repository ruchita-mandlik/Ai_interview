import React, { useEffect, useState } from 'react';
import {
  Calendar,
  Clock,
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  Award,
  BookOpen,
  ChevronDown,
  ChevronUp,
  FileQuestion,
  HelpCircle,
  Lightbulb,
  Target,
  Sparkles,
  ArrowRight,
  TrendingUp,
  Sliders,
  Code2
} from 'lucide-react';
import {
  DeepAnalysisRoadmapResponse,
  RoadmapTask,
  EvidenceSkillGap,
  QuestionEvidenceAnalysis,
  DiagnosticReassessmentQuestion,
  Interview
} from '../types';
import { analysisAPI, interviewAPI } from '../services/api';

interface StudyPlanProps {
  initialSubTab?: 'roadmap' | 'gaps' | 'questions' | 'strengths' | 'reassess';
  selectedInterviewId?: string | null;
  setSelectedInterviewId?: (id: string | null) => void;
  onToast?: (msg: string, type?: string) => void;
  setActiveTab?: (tab: string) => void;
}

export const StudyPlan: React.FC<StudyPlanProps> = ({
  initialSubTab,
  selectedInterviewId,
  setSelectedInterviewId,
  onToast,
  setActiveTab
}) => {
  const [roadmap, setRoadmap] = useState<DeepAnalysisRoadmapResponse | null>(null);
  const [completedInterviews, setCompletedInterviews] = useState<Interview[]>([]);
  const [currentInterviewId, setCurrentInterviewId] = useState<string | null>(selectedInterviewId || null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [generatingNew, setGeneratingNew] = useState(false);
  const [recalibrating, setRecalibrating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Active view tab
  const [activeSubTab, setActiveSubTab] = useState<'roadmap' | 'gaps' | 'questions' | 'strengths' | 'reassess'>(initialSubTab || 'roadmap');

  // Filter states
  const [selectedPhase, setSelectedPhase] = useState<number | 'all'>('all');
  const [taskFilter, setTaskFilter] = useState<'all' | 'pending' | 'completed'>('all');

  // Expansion states
  const [expandedTaskIds, setExpandedTaskIds] = useState<Set<string>>(new Set());
  const [expandedQuestionIds, setExpandedQuestionIds] = useState<Set<string>>(new Set());
  const [revealedReassessIds, setRevealedReassessIds] = useState<Set<string>>(new Set());

  // Preference form states
  const [targetDate, setTargetDate] = useState<string>('');
  const [dailyHours, setDailyHours] = useState<number>(2.0);

  useEffect(() => {
    loadInterviewsAndRoadmap();
  }, [selectedInterviewId]);

  const loadInterviewsAndRoadmap = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      // 1. Fetch user's interviews for selector
      let interviews: Interview[] = [];
      try {
        interviews = await interviewAPI.list();
        setCompletedInterviews(interviews);
      } catch (e) {
        console.warn("Failed to fetch interview list:", e);
      }

      // 2. Determine target interview ID
      let targetId = selectedInterviewId;
      if (!targetId && interviews.length > 0) {
        // Prioritize completed interviews with questions
        const completed = interviews.find(i => i.status === 'completed' && (i.completed_questions || 0) > 0);
        targetId = completed ? completed.id : interviews[0].id;
      }

      if (targetId) {
        setCurrentInterviewId(targetId);
        try {
          const data = await analysisAPI.getByInterviewId(targetId);
          setRoadmap(data);
          if (data.target_interview_date) setTargetDate(data.target_interview_date);
          if (data.daily_study_hours) setDailyHours(data.daily_study_hours);
          return;
        } catch {
          // No roadmap for this interview yet; try getLatest fallback
        }
      }

      // Fallback: try latest roadmap
      try {
        const latestData = await analysisAPI.getLatest();
        if (latestData) {
          setRoadmap(latestData);
          setCurrentInterviewId(latestData.interview_id);
          if (latestData.target_interview_date) setTargetDate(latestData.target_interview_date);
          if (latestData.daily_study_hours) setDailyHours(latestData.daily_study_hours);
        }
      } catch (err: any) {
        if (!targetId) {
          setErrorMsg(err.response?.data?.detail || 'No recent interview analysis found. Complete an interview to generate your personalized roadmap.');
        }
      }
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to load interview roadmap data.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectInterview = async (interviewId: string) => {
    setCurrentInterviewId(interviewId);
    if (setSelectedInterviewId) setSelectedInterviewId(interviewId);
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await analysisAPI.getByInterviewId(interviewId);
      setRoadmap(data);
      if (data.target_interview_date) setTargetDate(data.target_interview_date);
      if (data.daily_study_hours) setDailyHours(data.daily_study_hours);
    } catch {
      setRoadmap(null);
      setErrorMsg(`No deep analysis generated yet for this interview session. Click "Generate Deep AI Analysis" below to run evidence synthesis.`);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateForInterview = async (interviewId: string) => {
    if (!interviewId) return;
    setGeneratingNew(true);
    setErrorMsg(null);
    try {
      const data = await analysisAPI.generate(interviewId, {
        force_refresh: true,
        target_interview_date: targetDate || undefined,
        daily_study_hours: dailyHours
      });
      setRoadmap(data);
      setCurrentInterviewId(interviewId);
      if (setSelectedInterviewId) setSelectedInterviewId(interviewId);
      if (data.target_interview_date) setTargetDate(data.target_interview_date);
      if (data.daily_study_hours) setDailyHours(data.daily_study_hours);
      onToast?.('Deep AI Analysis & Personalized Roadmap generated from completed interview data!', 'success');
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'Failed to generate analysis.';
      setErrorMsg(detail);
      onToast?.(detail, 'error');
    } finally {
      setGeneratingNew(false);
    }
  };

  const handleRegenerate = async () => {
    const targetId = roadmap?.interview_id || currentInterviewId;
    if (!targetId) return;
    setRegenerating(true);
    try {
      const data = await analysisAPI.generate(targetId, {
        force_refresh: true,
        target_interview_date: targetDate || undefined,
        daily_study_hours: dailyHours
      });
      setRoadmap(data);
      onToast?.('Deep interview analysis & roadmap regenerated successfully!', 'success');
    } catch (err: any) {
      onToast?.(err.response?.data?.detail || 'Failed to regenerate analysis.', 'error');
    } finally {
      setRegenerating(false);
    }
  };

  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roadmap) return;
    setRecalibrating(true);
    try {
      const data = await analysisAPI.updatePreferences(roadmap.id, {
        target_interview_date: targetDate || undefined,
        daily_study_hours: Number(dailyHours)
      });
      setRoadmap(data);
      onToast?.('Study preferences updated & roadmap timeline recalibrated!', 'success');
    } catch (err: any) {
      onToast?.(err.response?.data?.detail || 'Failed to update preferences.', 'error');
    } finally {
      setRecalibrating(false);
    }
  };

  const handleToggleTask = async (task: RoadmapTask) => {
    if (!roadmap) return;
    const nextStatus = task.status === 'completed' ? 'pending' : 'completed';

    // Optimistic local update
    const updatedTasks = roadmap.roadmap_tasks.map(t =>
      t.task_id === task.task_id
        ? { ...t, status: nextStatus, completed_at: nextStatus === 'completed' ? new Date().toISOString() : null }
        : t
    );
    setRoadmap({ ...roadmap, roadmap_tasks: updatedTasks });

    try {
      const freshData = await analysisAPI.updateTaskStatus(roadmap.id, task.task_id, nextStatus);
      setRoadmap(freshData);
      onToast?.(
        nextStatus === 'completed'
          ? `Completed "${task.topic}"! Readiness score updated.`
          : `Marked "${task.topic}" as pending.`,
        'success'
      );
    } catch (err: any) {
      // Revert on error
      if (currentInterviewId) handleSelectInterview(currentInterviewId);
      onToast?.('Failed to update task status.', 'error');
    }
  };

  const toggleTaskExpand = (taskId: string) => {
    const next = new Set(expandedTaskIds);
    if (next.has(taskId)) next.delete(taskId);
    else next.add(taskId);
    setExpandedTaskIds(next);
  };

  const toggleQuestionExpand = (qId: string) => {
    const next = new Set(expandedQuestionIds);
    if (next.has(qId)) next.delete(qId);
    else next.add(qId);
    setExpandedQuestionIds(next);
  };

  const toggleReassessSolution = (id: string) => {
    const next = new Set(revealedReassessIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setRevealedReassessIds(next);
  };

  if (loading || generatingNew) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 20px' }}>
        <RotateCw size={36} className="spinning-icon" style={{ color: '#8B5CF6', marginBottom: '16px' }} />
        <h3 style={{ fontSize: '20px', fontWeight: 600 }}>
          {generatingNew ? 'Synthesizing Deep AI Interview Analysis & Personalized Roadmap...' : 'Loading Interview Intelligence Telemetry...'}
        </h3>
        <p style={{ color: '#9CA3AF', marginTop: '6px' }}>Evaluating technical correctness, conceptual depth, misconceptions, and evidence.</p>
      </div>
    );
  }

  if (!roadmap) {
    const selectedInterviewObj = completedInterviews.find(i => i.id === currentInterviewId);

    return (
      <div className="deep-roadmap-container" style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '840px', margin: '20px auto' }}>
        {/* Session Picker Bar */}
        {completedInterviews.length > 0 && (
          <div className="glass-card" style={{ padding: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase' }}>Select Interview Session:</span>
              <select
                value={currentInterviewId || ''}
                onChange={e => handleSelectInterview(e.target.value)}
                style={{
                  background: 'rgba(17, 24, 39, 0.9)',
                  color: '#FFF',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  fontSize: '13px',
                  fontWeight: 600
                }}
              >
                {completedInterviews.map(i => (
                  <option key={i.id} value={i.id}>
                    {i.title || i.role || 'Mock Session'} ({i.topic || (i.topics && i.topics[0]) || 'General'}) • {i.status === 'completed' ? `Score: ${Math.round(i.overall_score || 0)}%` : 'In Progress'} • {i.created_at || i.started_at ? new Date(i.created_at || i.started_at).toLocaleDateString() : 'Recent'}
                  </option>
                ))}
              </select>
            </div>
            {currentInterviewId && (
              <button
                className="btn btn-primary"
                onClick={() => handleGenerateForInterview(currentInterviewId)}
                disabled={generatingNew}
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                <Sparkles size={16} /> Generate Deep Analysis
              </button>
            )}
          </div>
        )}

        <div className="glass-card" style={{ textAlign: 'center', padding: '50px 24px' }}>
          <Target size={48} style={{ color: '#8B5CF6', marginBottom: '16px' }} />
          <h2 style={{ fontSize: '22px', fontWeight: 700, marginBottom: '10px' }}>
            {selectedInterviewObj ? `Ready to Analyze: ${selectedInterviewObj.title || selectedInterviewObj.role || 'Interview Session'}` : 'No Post-Interview Analysis Yet'}
          </h2>
          <p style={{ color: '#9CA3AF', fontSize: '15px', lineHeight: 1.6, marginBottom: '24px', maxWidth: '600px', margin: '0 auto 24px auto' }}>
            {selectedInterviewObj
              ? `You have a completed interview session (${selectedInterviewObj.topic || (selectedInterviewObj.topics && selectedInterviewObj.topics[0]) || 'Technical'}, ${selectedInterviewObj.difficulty || 'Medium'}). Click below to deeply evaluate your answers, connect weaknesses to actual evidence, and generate your customized 7-day preparation roadmap.`
              : (errorMsg || 'Complete an adaptive mock or voice interview first. Our AI will deeply evaluate your answers, connect weaknesses to actual evidence, and generate your customized preparation roadmap.')}
          </p>

          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
            {selectedInterviewObj && (
              <button
                className="btn btn-primary"
                onClick={() => handleGenerateForInterview(selectedInterviewObj.id)}
                disabled={generatingNew}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 24px', fontSize: '15px' }}
              >
                <Sparkles size={18} /> Generate Deep AI Analysis & Roadmap
              </button>
            )}
            {setActiveTab && (
              <button className="btn btn-secondary" onClick={() => setActiveTab('interview')} style={{ padding: '12px 20px' }}>
                Start New Adaptive Interview <ArrowRight size={16} style={{ display: 'inline', marginLeft: '6px' }} />
              </button>
            )}
            {setActiveTab && (
              <button className="btn btn-secondary" onClick={() => setActiveTab('voice')} style={{ padding: '12px 20px' }}>
                Try Voice Simulator
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Calculate task completion metrics
  const totalTasks = roadmap.roadmap_tasks.length;
  const completedTasks = roadmap.roadmap_tasks.filter(t => t.status === 'completed').length;
  const completionPercent = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;
  const totalHours = roadmap.roadmap_tasks.reduce((acc, t) => acc + (t.estimated_duration_hours || 1.5), 0);
  const remainingHours = roadmap.roadmap_tasks
    .filter(t => t.status !== 'completed')
    .reduce((acc, t) => acc + (t.estimated_duration_hours || 1.5), 0);
  const criticalRemaining = roadmap.roadmap_tasks
    .filter(t => (t.priority || '').toUpperCase() === 'CRITICAL' && t.status !== 'completed').length;

  // Filter tasks
  const filteredTasks = roadmap.roadmap_tasks.filter(t => {
    if (selectedPhase !== 'all' && t.phase_number !== selectedPhase) return false;
    if (taskFilter === 'pending' && t.status === 'completed') return false;
    if (taskFilter === 'completed' && t.status !== 'completed') return false;
    return true;
  });

  const getScoreColor = (score: number) => {
    if (score >= 85) return '#10B981'; // Emerald
    if (score >= 65) return '#F59E0B'; // Amber
    return '#EF4444'; // Rose
  };

  const getPriorityBadgeClass = (priority: string) => {
    const p = priority.toUpperCase();
    if (p === 'CRITICAL') return 'badge-critical';
    if (p === 'HIGH') return 'badge-high';
    return 'badge-medium';
  };

  return (
    <div className="deep-roadmap-container" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Session Selector Bar */}
      {completedInterviews.length > 0 && (
        <div className="glass-card" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Active Interview Session:
            </span>
            <select
              value={currentInterviewId || roadmap.interview_id}
              onChange={e => handleSelectInterview(e.target.value)}
              style={{
                background: 'rgba(17, 24, 39, 0.95)',
                color: '#FFF',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '8px',
                padding: '8px 12px',
                fontSize: '13px',
                fontWeight: 600
              }}
              id="select-interview-session"
            >
              {completedInterviews.map(i => (
                <option key={i.id} value={i.id}>
                  {i.title || i.role || 'Mock Session'} ({i.topic || (i.topics && i.topics[0]) || 'General'}) • {i.status === 'completed' ? `Score: ${Math.round(i.overall_score || 0)}%` : 'In Progress'} • {i.created_at || i.started_at ? new Date(i.created_at || i.started_at).toLocaleDateString() : 'Recent'}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleRegenerate}
              disabled={regenerating}
              id="btn-refresh-analysis"
            >
              <RotateCw size={14} className={regenerating ? 'spinning-icon' : ''} />
              {regenerating ? 'Regenerating...' : 'Refresh AI Analysis'}
            </button>
          </div>
        </div>
      )}

      {/* Top Header Card */}
      <div className="glass-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <Sparkles size={24} style={{ color: '#8B5CF6' }} />
              <h1 style={{ fontSize: '24px', fontWeight: 800, margin: 0, letterSpacing: '-0.02em' }}>
                AI Post-Interview Intelligence & Personalized Roadmap
              </h1>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
              <span className="badge badge-purple">{roadmap.target_role}</span>
              <span className="badge badge-blue">{roadmap.target_difficulty} Difficulty</span>
              <span style={{ fontSize: '13px', color: '#9CA3AF' }}>
                Evaluated {new Date(roadmap.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              className="btn btn-secondary"
              onClick={handleRegenerate}
              disabled={regenerating}
              title="Regenerate full deep analysis and fresh roadmap"
            >
              <RotateCw size={16} className={regenerating ? 'spinning-icon' : ''} />
              {regenerating ? 'Regenerating...' : 'Regenerate Analysis'}
            </button>
          </div>
        </div>

        {/* Readiness Score & Executive Overview */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '16px',
          background: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: '12px',
          padding: '18px'
        }}>
          {/* Readiness Gauge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '18px' }}>
            <div style={{
              position: 'relative',
              width: '84px',
              height: '84px',
              borderRadius: '50%',
              background: `conic-gradient(${getScoreColor(roadmap.readiness_score)} ${roadmap.readiness_score * 3.6}deg, rgba(255, 255, 255, 0.08) 0deg)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: `0 0 16px ${getScoreColor(roadmap.readiness_score)}33`
            }}>
              <div style={{
                width: '68px',
                height: '68px',
                borderRadius: '50%',
                background: '#0B0F19',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <span style={{ fontSize: '19px', fontWeight: 800, color: '#FFF' }}>
                  {Math.round(roadmap.readiness_score)}%
                </span>
              </div>
            </div>

            <div>
              <span style={{ fontSize: '12px', textTransform: 'uppercase', color: '#9CA3AF', letterSpacing: '0.05em', fontWeight: 600 }}>
                Interview Readiness
              </span>
              <h4 style={{ fontSize: '17px', fontWeight: 700, color: getScoreColor(roadmap.readiness_score), margin: '2px 0 4px 0' }}>
                {roadmap.readiness_level}
              </h4>
              <span style={{ fontSize: '12px', color: '#6B7280' }}>
                Dynamic progression calibrated by task mastery
              </span>
            </div>
          </div>

          {/* Quick Metrics */}
          <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', borderLeft: '1px solid rgba(255,255,255,0.06)', paddingLeft: '16px', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ textAlign: 'center' }}>
              <span style={{ fontSize: '22px', fontWeight: 800, color: '#8B5CF6' }}>
                {completedTasks}/{totalTasks}
              </span>
              <div style={{ fontSize: '12px', color: '#9CA3AF', marginTop: '2px' }}>Tasks Done ({completionPercent}%)</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <span style={{ fontSize: '22px', fontWeight: 800, color: '#3B82F6' }}>
                {Math.round(remainingHours * 10) / 10}h
              </span>
              <div style={{ fontSize: '12px', color: '#9CA3AF', marginTop: '2px' }}>Remaining Effort</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <span style={{ fontSize: '22px', fontWeight: 800, color: '#EF4444' }}>
                {criticalRemaining}
              </span>
              <div style={{ fontSize: '12px', color: '#9CA3AF', marginTop: '2px' }}>Critical Left</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <span style={{ fontSize: '22px', fontWeight: 800, color: '#10B981' }}>
                {roadmap.strengths.length}
              </span>
              <div style={{ fontSize: '12px', color: '#9CA3AF', marginTop: '2px' }}>Strong Areas</div>
            </div>
          </div>
        </div>

        {/* Executive Summary paragraph */}
        <div style={{ fontSize: '14px', lineHeight: 1.6, color: '#D1D5DB', background: 'rgba(139, 92, 246, 0.05)', border: '1px solid rgba(139, 92, 246, 0.15)', borderRadius: '8px', padding: '14px 16px' }}>
          <strong style={{ color: '#C084FC', display: 'block', marginBottom: '4px' }}>Executive Post-Interview Diagnosis:</strong>
          {roadmap.executive_summary}
        </div>

        {/* Schedule & Pacing Configuration Bar */}
        <form onSubmit={handleSavePreferences} style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '14px',
          alignItems: 'center',
          background: 'rgba(0, 0, 0, 0.25)',
          padding: '12px 16px',
          borderRadius: '8px',
          border: '1px solid rgba(255, 255, 255, 0.05)'
        }}>
          <Sliders size={16} style={{ color: '#9CA3AF' }} />
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#E5E7EB' }}>Roadmap Timeline Calibration:</span>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <label style={{ fontSize: '12px', color: '#9CA3AF' }}>Target Interview Date:</label>
            <input
              type="date"
              value={targetDate}
              onChange={e => setTargetDate(e.target.value)}
              className="input-sm"
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '6px',
                color: '#FFF',
                padding: '4px 8px',
                fontSize: '12px'
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <label style={{ fontSize: '12px', color: '#9CA3AF' }}>Daily Study Hours:</label>
            <input
              type="number"
              min="0.5"
              max="12"
              step="0.5"
              value={dailyHours}
              onChange={e => setDailyHours(parseFloat(e.target.value) || 2.0)}
              style={{
                width: '64px',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '6px',
                color: '#FFF',
                padding: '4px 8px',
                fontSize: '12px'
              }}
            />
            <span style={{ fontSize: '12px', color: '#6B7280' }}>hrs/day</span>
          </div>

          <button
            type="submit"
            className="btn btn-secondary btn-sm"
            disabled={recalibrating}
            style={{ marginLeft: 'auto' }}
          >
            {recalibrating ? 'Recalibrating...' : 'Recalibrate Timeline'}
          </button>
        </form>
      </div>

      {/* Navigation Sub-Tabs */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        paddingBottom: '12px'
      }}>
        {/* Deep AI Analysis Tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#818CF8', textTransform: 'uppercase', letterSpacing: '0.06em', marginRight: '4px' }}>
            🔍 Deep AI Analysis:
          </span>
          <button
            className={`tab-btn ${activeSubTab === 'questions' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('questions')}
            id="tab-btn-questions"
          >
            <FileQuestion size={16} /> Question Diagnostics & Rubrics ({roadmap.question_analyses.length})
          </button>
          <button
            className={`tab-btn ${activeSubTab === 'gaps' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('gaps')}
            id="tab-btn-gaps"
          >
            <AlertTriangle size={16} /> Evidence Skill Gaps ({roadmap.skill_gaps.length})
          </button>
          <button
            className={`tab-btn ${activeSubTab === 'strengths' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('strengths')}
            id="tab-btn-strengths"
          >
            <Award size={16} /> Validated Strengths ({roadmap.strengths.length})
          </button>
        </div>

        {/* Personalized Preparation Roadmap Tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#34D399', textTransform: 'uppercase', letterSpacing: '0.06em', marginRight: '4px' }}>
            📅 Preparation Roadmap:
          </span>
          <button
            className={`tab-btn ${activeSubTab === 'roadmap' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('roadmap')}
            id="tab-btn-roadmap"
          >
            <BookOpen size={16} /> Sequenced Tasks & Timeline ({roadmap.roadmap_tasks.length})
          </button>
          <button
            className={`tab-btn ${activeSubTab === 'reassess' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('reassess')}
            id="tab-btn-reassess"
          >
            <Lightbulb size={16} /> Diagnostic Reassessment Suite ({roadmap.reassessment_questions.length})
          </button>
        </div>
      </div>

      {/* TAB 1: Sequenced Preparation Roadmap */}
      {activeSubTab === 'roadmap' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Phase Cards Carousel / Progress */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '12px'
          }}>
            {roadmap.roadmap_phases.map(phase => {
              const isSelected = selectedPhase === phase.phase_number;
              return (
                <div
                  key={phase.phase_number}
                  className={`glass-card phase-card ${isSelected ? 'phase-card-selected' : ''}`}
                  onClick={() => setSelectedPhase(isSelected ? 'all' : phase.phase_number)}
                  style={{
                    padding: '16px',
                    cursor: 'pointer',
                    border: isSelected ? '1px solid #8B5CF6' : '1px solid rgba(255, 255, 255, 0.08)',
                    background: isSelected ? 'rgba(139, 92, 246, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontSize: '11px', fontWeight: 800, color: '#C084FC', textTransform: 'uppercase' }}>
                      Phase {phase.phase_number}
                    </span>
                    <span style={{ fontSize: '11px', color: '#9CA3AF' }}>
                      <Clock size={11} style={{ display: 'inline', marginRight: '3px' }} />
                      {phase.duration_weeks} wks
                    </span>
                  </div>
                  <h4 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '8px' }}>{phase.title}</h4>
                  <div style={{ fontSize: '12px', color: '#9CA3AF', marginBottom: '10px' }}>
                    <strong style={{ color: '#D1D5DB' }}>Milestone:</strong> {phase.milestone}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {phase.focus_areas.map((fa, idx) => (
                      <span key={idx} style={{ fontSize: '10px', background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: '4px', color: '#9CA3AF' }}>
                        {fa}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Task Filter Controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span style={{ fontSize: '13px', color: '#9CA3AF' }}>Filter Tasks:</span>
              <button
                className={`filter-btn ${selectedPhase === 'all' ? 'active' : ''}`}
                onClick={() => setSelectedPhase('all')}
              >
                All Phases
              </button>
              {[1, 2, 3, 4].map(p => (
                <button
                  key={p}
                  className={`filter-btn ${selectedPhase === p ? 'active' : ''}`}
                  onClick={() => setSelectedPhase(p)}
                >
                  Phase {p}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              {(['all', 'pending', 'completed'] as const).map(f => (
                <button
                  key={f}
                  className={`filter-btn ${taskFilter === f ? 'active' : ''}`}
                  onClick={() => setTaskFilter(f)}
                  style={{ textTransform: 'capitalize' }}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {/* Interactive Task Cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {filteredTasks.length === 0 ? (
              <div className="glass-card" style={{ padding: '32px', textAlign: 'center', color: '#9CA3AF' }}>
                No preparation tasks match the selected phase and status filter.
              </div>
            ) : (
              filteredTasks.map(task => {
                const isCompleted = task.status === 'completed';
                const isExpanded = expandedTaskIds.has(task.task_id);

                return (
                  <div
                    key={task.task_id}
                    className="glass-card"
                    style={{
                      padding: '18px',
                      borderLeft: isCompleted
                        ? '4px solid #10B981'
                        : task.priority === 'CRITICAL'
                        ? '4px solid #EF4444'
                        : task.priority === 'HIGH'
                        ? '4px solid #F59E0B'
                        : '4px solid #8B5CF6',
                      opacity: isCompleted ? 0.85 : 1.0,
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
                      <input
                        type="checkbox"
                        checked={isCompleted}
                        onChange={() => handleToggleTask(task)}
                        style={{ width: '20px', height: '20px', cursor: 'pointer', marginTop: '2px' }}
                      />

                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '6px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span className={`priority-badge ${getPriorityBadgeClass(task.priority)}`}>
                              {task.priority}
                            </span>
                            <span style={{ fontSize: '11px', color: '#9CA3AF', fontWeight: 600 }}>
                              PHASE {task.phase_number} • DAY {task.day_or_sequence}
                            </span>
                            <span style={{ fontSize: '11px', color: '#6B7280' }}>
                              <Clock size={11} style={{ display: 'inline', marginRight: '3px' }} />
                              {task.estimated_duration_hours} hrs
                            </span>
                          </div>

                          {isCompleted && (
                            <span style={{ fontSize: '11px', color: '#10B981', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <CheckCircle2 size={12} /> Completed
                            </span>
                          )}
                        </div>

                        <h3 style={{
                          fontSize: '17px',
                          fontWeight: 700,
                          margin: '0 0 8px 0',
                          textDecoration: isCompleted ? 'line-through' : 'none',
                          color: isCompleted ? '#9CA3AF' : '#FFF'
                        }}>
                          {task.topic}
                        </h3>

                        {/* Subtopics */}
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
                          {task.subtopics.map((st, i) => (
                            <span key={i} style={{ fontSize: '11px', background: 'rgba(255, 255, 255, 0.05)', padding: '2px 8px', borderRadius: '4px', color: '#9CA3AF' }}>
                              {st}
                            </span>
                          ))}
                        </div>

                        {/* Expandable Details */}
                        {isExpanded && (
                          <div style={{
                            marginTop: '14px',
                            paddingTop: '14px',
                            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '12px'
                          }}>
                            {/* Learning Objectives */}
                            <div>
                              <strong style={{ fontSize: '12px', color: '#C084FC', display: 'block', marginBottom: '4px' }}>
                                Learning Objectives:
                              </strong>
                              <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '13px', color: '#D1D5DB' }}>
                                {task.learning_objectives.map((obj, i) => (
                                  <li key={i} style={{ marginBottom: '3px' }}>{obj}</li>
                                ))}
                              </ul>
                            </div>

                            {/* Practical Exercise */}
                            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '12px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                              <strong style={{ fontSize: '12px', color: '#F59E0B', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                                <Code2 size={14} /> Practical Hands-on Exercise:
                              </strong>
                              <p style={{ margin: 0, fontSize: '13px', color: '#E5E7EB', lineHeight: 1.5 }}>
                                {task.practical_exercise}
                              </p>
                            </div>

                            {/* Expected Outcomes & Criteria */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                              <div>
                                <strong style={{ fontSize: '11px', textTransform: 'uppercase', color: '#9CA3AF', display: 'block', marginBottom: '2px' }}>
                                  Expected Outcomes
                                </strong>
                                <span style={{ fontSize: '13px', color: '#D1D5DB' }}>{task.expected_outcomes}</span>
                              </div>
                              <div>
                                <strong style={{ fontSize: '11px', textTransform: 'uppercase', color: '#9CA3AF', display: 'block', marginBottom: '2px' }}>
                                  Measurable Completion Criteria
                                </strong>
                                <span style={{ fontSize: '13px', color: '#D1D5DB' }}>{task.completion_criteria}</span>
                              </div>
                            </div>
                          </div>
                        )}

                        <button
                          className="btn-text"
                          onClick={() => toggleTaskExpand(task.task_id)}
                          style={{ marginTop: '8px', fontSize: '12px', color: '#8B5CF6', display: 'flex', alignItems: 'center', gap: '4px', padding: 0, background: 'none', border: 'none', cursor: 'pointer' }}
                        >
                          {isExpanded ? <>Less details <ChevronUp size={14} /></> : <>More details, exercises & criteria <ChevronDown size={14} /></>}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Evidence-Based Skill Gaps */}
      {activeSubTab === 'gaps' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ fontSize: '14px', color: '#9CA3AF', lineHeight: 1.5 }}>
            Every identified weakness below is directly tied to the exact question and verbatim excerpt from your interview answers.
            No assumptions or generic flaws are invented.
          </div>

          {roadmap.skill_gaps.map((gap, idx) => (
            <div
              key={gap.gap_id || idx}
              className="glass-card"
              style={{
                padding: '20px',
                borderLeft: gap.finding_type === 'CONFIRMED_WEAKNESS' ? '4px solid #EF4444' : '4px solid #F59E0B'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px', marginBottom: '10px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span className={`priority-badge ${getPriorityBadgeClass(gap.priority)}`}>{gap.priority}</span>
                    <span style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: gap.finding_type === 'CONFIRMED_WEAKNESS' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                      color: gap.finding_type === 'CONFIRMED_WEAKNESS' ? '#F87171' : '#FBBF24'
                    }}>
                      {gap.finding_type.replace('_', ' ')}
                    </span>
                    <span style={{ fontSize: '11px', color: '#9CA3AF' }}>Confidence: {gap.confidence_level}</span>
                  </div>
                  <h3 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>{gap.competency}</h3>
                  <span style={{ fontSize: '12px', color: '#6B7280' }}>Category: {gap.category}</span>
                </div>
              </div>

              {/* Exact Evidence Box */}
              {gap.evidence_question_text && (
                <div style={{
                  background: 'rgba(0, 0, 0, 0.35)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '8px',
                  padding: '12px 14px',
                  margin: '12px 0'
                }}>
                  <div style={{ fontSize: '12px', color: '#C084FC', fontWeight: 600, marginBottom: '4px' }}>
                    Interview Evidence (Question #{gap.evidence_question_number}):
                  </div>
                  <div style={{ fontSize: '13px', color: '#E5E7EB', fontStyle: 'italic', marginBottom: '6px' }}>
                    "{gap.evidence_question_text}"
                  </div>
                  {gap.candidate_answer_excerpt && (
                    <div style={{ fontSize: '12px', color: '#9CA3AF', background: 'rgba(255, 255, 255, 0.03)', padding: '6px 10px', borderRadius: '4px' }}>
                      <strong style={{ color: '#D1D5DB' }}>Candidate Stated:</strong> "{gap.candidate_answer_excerpt}"
                    </div>
                  )}
                </div>
              )}

              {/* Analysis of Defect */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px', margin: '14px 0' }}>
                <div>
                  <strong style={{ fontSize: '12px', color: '#EF4444', display: 'block', marginBottom: '2px' }}>
                    What Was Missing / Incorrect:
                  </strong>
                  <p style={{ margin: 0, fontSize: '13px', color: '#D1D5DB', lineHeight: 1.5 }}>
                    {gap.what_was_missing_or_incorrect}
                  </p>
                </div>
                <div>
                  <strong style={{ fontSize: '12px', color: '#F59E0B', display: 'block', marginBottom: '2px' }}>
                    Why It Matters in Production / Hiring:
                  </strong>
                  <p style={{ margin: 0, fontSize: '13px', color: '#D1D5DB', lineHeight: 1.5 }}>
                    {gap.why_it_matters}
                  </p>
                </div>
              </div>

              <div>
                <strong style={{ fontSize: '12px', color: '#10B981', display: 'block', marginBottom: '2px' }}>
                  Correct Engineering Understanding:
                </strong>
                <p style={{ margin: 0, fontSize: '13px', color: '#D1D5DB', lineHeight: 1.5 }}>
                  {gap.correct_understanding}
                </p>
              </div>

              {/* Remediation Path (4 steps) */}
              <div style={{
                marginTop: '16px',
                background: 'rgba(139, 92, 246, 0.06)',
                border: '1px solid rgba(139, 92, 246, 0.15)',
                borderRadius: '8px',
                padding: '14px'
              }}>
                <strong style={{ fontSize: '13px', color: '#C084FC', display: 'block', marginBottom: '8px' }}>
                  Targeted Remediation Path:
                </strong>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                  <div>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', color: '#9CA3AF', fontWeight: 600, display: 'block' }}>1. What Went Wrong</span>
                    <span style={{ fontSize: '12px', color: '#E5E7EB' }}>{gap.remediation_path.what_went_wrong}</span>
                  </div>
                  <div>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', color: '#9CA3AF', fontWeight: 600, display: 'block' }}>2. What to Learn</span>
                    <span style={{ fontSize: '12px', color: '#E5E7EB' }}>{gap.remediation_path.what_to_learn}</span>
                  </div>
                  <div>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', color: '#9CA3AF', fontWeight: 600, display: 'block' }}>3. What to Practice</span>
                    <span style={{ fontSize: '12px', color: '#E5E7EB' }}>{gap.remediation_path.what_to_practice}</span>
                  </div>
                  <div>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', color: '#9CA3AF', fontWeight: 600, display: 'block' }}>4. How to Verify</span>
                    <span style={{ fontSize: '12px', color: '#E5E7EB' }}>{gap.remediation_path.how_to_verify}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB 3: Question-by-Question Deep Review */}
      {activeSubTab === 'questions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {roadmap.question_analyses.map(qa => {
            const isExpanded = expandedQuestionIds.has(qa.question_id);
            return (
              <div key={qa.question_id} className="glass-card" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px', marginBottom: '10px' }}>
                  <div>
                    <span style={{ fontSize: '12px', fontWeight: 800, color: '#8B5CF6' }}>
                      QUESTION {qa.question_number}
                    </span>
                    <h3 style={{ fontSize: '16px', fontWeight: 700, margin: '4px 0 0 0' }}>{qa.question_text}</h3>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: getScoreColor(qa.technical_correctness * 10) }}>
                      Score: {qa.technical_correctness}/10
                    </span>
                  </div>
                </div>

                {/* Candidate Excerpt */}
                <div style={{
                  background: 'rgba(0, 0, 0, 0.3)',
                  borderLeft: '3px solid #8B5CF6',
                  padding: '10px 14px',
                  borderRadius: '0 6px 6px 0',
                  margin: '12px 0',
                  fontSize: '13px',
                  color: '#D1D5DB'
                }}>
                  <strong style={{ color: '#C084FC', display: 'block', fontSize: '11px', textTransform: 'uppercase', marginBottom: '2px' }}>
                    Your Answer Excerpt:
                  </strong>
                  "{qa.candidate_answer_excerpt}"
                </div>

                {/* Rubric Breakdown Grid */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: '10px',
                  background: 'rgba(255, 255, 255, 0.02)',
                  padding: '12px',
                  borderRadius: '6px',
                  margin: '12px 0'
                }}>
                  <div>
                    <span style={{ fontSize: '11px', color: '#9CA3AF' }}>Correctness</span>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: '#FFF' }}>{qa.technical_correctness}/10</div>
                  </div>
                  <div>
                    <span style={{ fontSize: '11px', color: '#9CA3AF' }}>Understanding</span>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: '#FFF' }}>{qa.conceptual_understanding}/10</div>
                  </div>
                  <div>
                    <span style={{ fontSize: '11px', color: '#9CA3AF' }}>Depth & Clarity</span>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: '#FFF' }}>{qa.depth_and_clarity}/10</div>
                  </div>
                  <div>
                    <span style={{ fontSize: '11px', color: '#9CA3AF' }}>Reasoning</span>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: '#FFF' }}>{qa.reasoning_approach}/10</div>
                  </div>
                  <div>
                    <span style={{ fontSize: '11px', color: '#9CA3AF' }}>Completeness</span>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: '#FFF' }}>{qa.completeness}/10</div>
                  </div>
                </div>

                {/* Strengths & Misconceptions tags */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
                  {qa.key_strengths.length > 0 && (
                    <div style={{ background: 'rgba(16, 185, 129, 0.05)', padding: '10px', borderRadius: '6px', border: '1px solid rgba(16, 185, 129, 0.1)' }}>
                      <strong style={{ fontSize: '12px', color: '#10B981', display: 'block', marginBottom: '4px' }}>
                        Demonstrated Strengths:
                      </strong>
                      <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: '#D1D5DB' }}>
                        {qa.key_strengths.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                  )}

                  {qa.misconceptions.length > 0 && (
                    <div style={{ background: 'rgba(239, 68, 68, 0.05)', padding: '10px', borderRadius: '6px', border: '1px solid rgba(239, 68, 68, 0.1)' }}>
                      <strong style={{ fontSize: '12px', color: '#EF4444', display: 'block', marginBottom: '4px' }}>
                        Misconceptions Identified:
                      </strong>
                      <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: '#D1D5DB' }}>
                        {qa.misconceptions.map((m, i) => <li key={i}>{m}</li>)}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Expandable Missing & Poorly Explained Aspects */}
                {isExpanded && (
                  <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(255, 255, 255, 0.06)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {qa.missing_concepts.length > 0 && (
                      <div>
                        <strong style={{ fontSize: '12px', color: '#F59E0B' }}>Missing Concepts:</strong>
                        <ul style={{ margin: '4px 0 0 0', paddingLeft: '18px', fontSize: '12px', color: '#D1D5DB' }}>
                          {qa.missing_concepts.map((mc, i) => <li key={i}>{mc}</li>)}
                        </ul>
                      </div>
                    )}

                    {qa.poorly_explained_aspects.length > 0 && (
                      <div>
                        <strong style={{ fontSize: '12px', color: '#C084FC' }}>Correct Conclusions but Weakly Explained:</strong>
                        <ul style={{ margin: '4px 0 0 0', paddingLeft: '18px', fontSize: '12px', color: '#D1D5DB' }}>
                          {qa.poorly_explained_aspects.map((pe, i) => <li key={i}>{pe}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                <button
                  onClick={() => toggleQuestionExpand(qa.question_id)}
                  style={{ marginTop: '10px', fontSize: '12px', color: '#8B5CF6', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                >
                  {isExpanded ? 'Hide deep evaluation notes ▲' : 'Show missing concepts & explanation analysis ▼'}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* TAB 4: Strengths & Untested Competencies */}
      {activeSubTab === 'strengths' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
          {/* Demonstrated Strengths */}
          <div className="glass-card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <Award size={20} style={{ color: '#10B981' }} />
              <h3 style={{ fontSize: '17px', fontWeight: 700, margin: 0 }}>Demonstrated Masteries</h3>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {roadmap.strengths.map((str, i) => (
                <div key={i} style={{ background: 'rgba(255, 255, 255, 0.02)', border: '1px solid rgba(16, 185, 129, 0.15)', borderRadius: '8px', padding: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontSize: '14px', fontWeight: 700, color: '#FFF' }}>{str.competency}</span>
                    <span style={{ fontSize: '11px', color: '#10B981' }}>{str.category}</span>
                  </div>
                  <p style={{ margin: '0 0 6px 0', fontSize: '13px', color: '#D1D5DB' }}>
                    {str.demonstrated_mastery}
                  </p>
                  {str.candidate_excerpt && (
                    <div style={{ fontSize: '11px', color: '#9CA3AF', fontStyle: 'italic' }}>
                      Evidence quote: "{str.candidate_excerpt}"
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Untested Competencies */}
          <div className="glass-card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <HelpCircle size={20} style={{ color: '#60A5FA' }} />
              <h3 style={{ fontSize: '17px', fontWeight: 700, margin: 0 }}>Untested Target Role Competencies</h3>
            </div>
            <p style={{ fontSize: '13px', color: '#9CA3AF', margin: '0 0 14px 0' }}>
              These competencies are essential for a {roadmap.target_role} but were not tested in this session.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {roadmap.untested_competencies.map((unt, i) => (
                <div key={i} style={{ background: 'rgba(255, 255, 255, 0.02)', border: '1px solid rgba(96, 165, 250, 0.15)', borderRadius: '8px', padding: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontSize: '14px', fontWeight: 700, color: '#FFF' }}>{unt.competency}</span>
                    <span style={{ fontSize: '11px', color: '#60A5FA' }}>{unt.category}</span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#D1D5DB', marginBottom: '6px' }}>
                    <strong style={{ color: '#9CA3AF' }}>Why it matters:</strong> {unt.importance_for_role}
                  </div>
                  <div style={{ fontSize: '12px', color: '#C084FC' }}>
                    <strong style={{ color: '#9CA3AF' }}>Recommended next step:</strong> {unt.recommended_next_step}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: Diagnostic Reassessment Suite */}
      {activeSubTab === 'reassess' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ fontSize: '14px', color: '#9CA3AF', lineHeight: 1.5 }}>
            These targeted diagnostic questions are tailored to test whether you have successfully resolved the specific skill gaps identified in your interview.
          </div>

          {roadmap.reassessment_questions.map((rq, idx) => {
            const isRevealed = revealedReassessIds.has(rq.id);
            return (
              <div key={rq.id || idx} className="glass-card" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: '#C084FC' }}>
                    DIAGNOSTIC RETEST #{idx + 1} • {rq.competency}
                  </span>
                  <span className="badge badge-purple">{rq.difficulty}</span>
                </div>

                <h3 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 12px 0' }}>{rq.question_text}</h3>

                {/* Key Points to hit */}
                <div style={{ marginBottom: '14px' }}>
                  <strong style={{ fontSize: '12px', color: '#9CA3AF', display: 'block', marginBottom: '4px' }}>
                    Key Concepts to Cover in Your Answer:
                  </strong>
                  <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '13px', color: '#D1D5DB' }}>
                    {rq.expected_key_points.map((kp, i) => (
                      <li key={i} style={{ marginBottom: '2px' }}>{kp}</li>
                    ))}
                  </ul>
                </div>

                {/* Reveal Benchmark Solution Toggle */}
                {isRevealed && (
                  <div style={{
                    background: 'rgba(16, 185, 129, 0.05)',
                    border: '1px solid rgba(16, 185, 129, 0.2)',
                    borderRadius: '8px',
                    padding: '14px',
                    marginTop: '10px'
                  }}>
                    <strong style={{ fontSize: '12px', color: '#10B981', display: 'block', marginBottom: '6px' }}>
                      Benchmark Model Solution:
                    </strong>
                    <p style={{ margin: 0, fontSize: '13px', color: '#E5E7EB', lineHeight: 1.6 }}>
                      {rq.benchmark_solution}
                    </p>
                  </div>
                )}

                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => toggleReassessSolution(rq.id)}
                  style={{ marginTop: '12px' }}
                >
                  {isRevealed ? 'Hide Benchmark Solution' : 'Reveal Benchmark Solution'}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
export default StudyPlan;
