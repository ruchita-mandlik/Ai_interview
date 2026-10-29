import React, { useState } from 'react';
import { Interview, Question, Evaluation, FinalReportResponse } from '../types';
import { interviewAPI, aiAPI, analysisAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import {
  Sliders,
  Play,
  Bot,
  PenTool,
  Forward,
  Award,
  CheckCircle2,
  Send,
  AlertCircle,
  Lightbulb,
  Sparkles,
  ArrowRight,
  X,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  FileText,
  Briefcase,
  Target,
  BookOpen,
  Check,
  AlertTriangle,
  Zap,
  Compass,
  Layers
} from 'lucide-react';

interface MockInterviewProps {
  onToast: (msg: string, type?: string) => void;
  openAuthModal: () => void;
  setActiveTab?: (tab: string) => void;
  setSelectedInterviewId?: (id: string | null) => void;
  isAdaptive?: boolean;
}

export const MockInterview: React.FC<MockInterviewProps> = ({ onToast, openAuthModal, setActiveTab, setSelectedInterviewId, isAdaptive = true }) => {
  const { isAuthenticated } = useAuth();

  // Config State
  const [role, setRole] = useState("Software Developer");
  const [experience, setExperience] = useState("Intermediate (2-5 Yrs)");
  const [interviewType, setInterviewType] = useState("Technical");
  const [difficulty, setDifficulty] = useState("Medium");
  const [selectedTopics, setSelectedTopics] = useState<string[]>(["Java", "OOP"]);
  const [totalQuestions, setTotalQuestions] = useState(5);

  // Advanced Personalization State
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [jobDescription, setJobDescription] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [customSkills, setCustomSkills] = useState("");
  const [additionalInstructions, setAdditionalInstructions] = useState("");

  // Active Session State
  const [interview, setInterview] = useState<Interview | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [questionIndex, setQuestionIndex] = useState(1);
  const [userAnswer, setUserAnswer] = useState("");
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [adaptiveDecision, setAdaptiveDecision] = useState<any | null>(null);
  const [trackedGaps, setTrackedGaps] = useState<string[]>([]);
  const [finalReport, setFinalReport] = useState<FinalReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [skipLoading, setSkipLoading] = useState(false);
  const [nextBtnLabel, setNextBtnLabel] = useState("Proceed to Next Question");

  // In-Session Clarification & Hint State
  const [showClarifyModal, setShowClarifyModal] = useState(false);
  const [clarifyQuery, setClarifyQuery] = useState("");
  const [clarifyLoading, setClarifyLoading] = useState(false);
  const [clarificationData, setClarificationData] = useState<{
    clarification: string;
    hint?: string;
    focus_areas?: string[];
  } | null>(null);

  // Expanded report question index
  const [expandedQuestionIdx, setExpandedQuestionIdx] = useState<number | null>(null);

  const topicsList = ["Java", "OOP", "DBMS", "Operating Systems", "System Design", "Data Structures", "Algorithms", "Microservices", "Cloud / AWS"];

  const toggleTopic = (t: string) => {
    if (selectedTopics.includes(t)) {
      if (selectedTopics.length > 1) {
        setSelectedTopics(selectedTopics.filter(item => item !== t));
      }
    } else {
      setSelectedTopics([...selectedTopics, t]);
    }
  };

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    if (!isAuthenticated) {
      openAuthModal();
      return;
    }

    setLoading(true);
    try {
      const skillsArray = customSkills
        .split(',')
        .map(s => s.trim())
        .filter(Boolean);

      const res = await interviewAPI.create({
        role,
        experience_level: experience,
        difficulty,
        interview_type: interviewType,
        topics: selectedTopics,
        skills: skillsArray.length > 0 ? skillsArray : undefined,
        job_description: jobDescription.trim() || undefined,
        resume_text: resumeText.trim() || undefined,
        additional_instructions: additionalInstructions.trim() || undefined,
        total_questions: totalQuestions,
        is_adaptive: isAdaptive !== false
      });

      setInterview(res.interview);
      setCurrentQuestion(res.first_question);
      setQuestionIndex(1);
      setUserAnswer("");
      setEvaluation(null);
      setFinalReport(null);
      setClarificationData(null);
      setShowClarifyModal(false);
      onToast(
        isAdaptive !== false 
          ? "AI Adaptive Interview session started! Dynamic question engine active." 
          : "Standard Mock Interview session started! Question set prepared.",
        "success"
      );
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Failed to start interview", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleRequestClarification = async () => {
    if (!interview || !currentQuestion) return;
    setClarifyLoading(true);
    try {
      const res = await interviewAPI.askClarification(
        interview.id,
        currentQuestion.id,
        clarifyQuery.trim() || "Please provide scope clarification, key focus areas, and a guiding hint for this question."
      );
      setClarificationData({
        clarification: res.clarification,
        hint: res.hint,
        focus_areas: (res as any).focus_areas || []
      });
      onToast("Interviewer hint & clarification received!", "success");
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Failed to fetch clarification", "error");
    } finally {
      setClarifyLoading(false);
    }
  };

  const handleSubmitAnswer = async () => {
    if (loading) return;
    if (!userAnswer.trim()) {
      onToast("Please provide your answer before submitting.", "amber");
      return;
    }
    if (!interview || !currentQuestion) return;

    setLoading(true);
    try {
      const res = await interviewAPI.submitAnswer(interview.id, currentQuestion.id, userAnswer);
      setEvaluation(res.evaluation);
      setClarificationData(null);
      setShowClarifyModal(false);

      if (isAdaptive !== false) {
        if (res.adaptive_decision) {
          setAdaptiveDecision(res.adaptive_decision);
        } else if (res.adaptive_action) {
          setAdaptiveDecision({
            action: res.adaptive_action,
            updated_difficulty: res.current_difficulty || currentQuestion.difficulty,
            decision_rationale: res.decision_rationale || currentQuestion.adaptation_reason || "",
            assessment_objective: res.assessment_objective || "",
            identified_knowledge_gaps: res.knowledge_gaps || []
          });
        }

        if (res.knowledge_gaps && res.knowledge_gaps.length > 0) {
          setTrackedGaps(res.knowledge_gaps);
        }
      } else {
        setAdaptiveDecision(null);
      }

      if (res.follow_up_question) {
        setCurrentQuestion(res.follow_up_question);
        setNextBtnLabel("Answer Contextual Follow-Up Probe");
      } else if (res.next_question) {
        setCurrentQuestion(res.next_question);
        setQuestionIndex(prev => prev + 1);
        setNextBtnLabel("Proceed to Next Question");
      } else if (res.interview_completed) {
        setNextBtnLabel("View Final Performance Report");
      }
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Evaluation failed", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleProceedNext = async () => {
    if (loading) return;
    if (nextBtnLabel.includes("Final Performance Report")) {
      if (!interview) return;
      setLoading(true);
      try {
        const rep = await aiAPI.getReport(interview.id);
        setFinalReport(rep);
        // Automatically trigger deep analysis generation from completed interview data
        if (interview.id) {
          if (setSelectedInterviewId) setSelectedInterviewId(interview.id);
          analysisAPI.generate(interview.id).catch(err => {
            console.warn("Background deep analysis generation:", err);
          });
        }
      } catch (err: any) {
        onToast("Failed to fetch final report", "error");
      } finally {
        setLoading(false);
      }
    } else {
      setUserAnswer("");
      setEvaluation(null);
      setAdaptiveDecision(null);
      setClarificationData(null);
      setShowClarifyModal(false);
    }
  };

  const handleSkip = async () => {
    if (!interview || loading || skipLoading) return;
    setSkipLoading(true);
    try {
      const activeQId = currentQuestion?.id;
      const res = await interviewAPI.skipQuestion(interview.id, activeQId);
      setClarificationData(null);
      setShowClarifyModal(false);
      setAdaptiveDecision(null);

      const isCompleted = Boolean(res?.interview_completed || res?.status === "completed" || (!res?.next_question && !res?.id));
      if (isCompleted) {
        onToast("Interview completed. Loading diagnostic performance report...", "info");
        const rep = await aiAPI.getReport(interview.id);
        setFinalReport(rep);
        // Automatically trigger deep analysis generation from completed interview data
        if (interview.id) {
          if (setSelectedInterviewId) setSelectedInterviewId(interview.id);
          analysisAPI.generate(interview.id).catch(err => {
            console.warn("Background deep analysis generation on skip complete:", err);
          });
        }
      } else {
        const nextQ = res?.next_question || res;
        setCurrentQuestion(nextQ);
        setQuestionIndex(prev => prev + 1);
        setUserAnswer("");
        setEvaluation(null);
        onToast("Question skipped. Moving to next topic.", "info");
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || "Failed to skip question";
      onToast(`Skip question failed: ${detail}`, "error");
    } finally {
      setSkipLoading(false);
    }
  };

  const exitSession = () => {
    if (window.confirm("Exit interview session? Your progress will be saved in history.")) {
      setInterview(null);
      setCurrentQuestion(null);
      setFinalReport(null);
      setEvaluation(null);
      setAdaptiveDecision(null);
      setTrackedGaps([]);
      setClarificationData(null);
      setShowClarifyModal(false);
    }
  };

  const wordCount = userAnswer.trim() ? userAnswer.trim().split(/\s+/).length : 0;

  // View: Final Report
  if (finalReport) {
    return (
      <section>
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
            <div>
              <span className="badge badge-primary" style={{ marginBottom: '8px', display: 'inline-block' }}>
                {finalReport.readiness_level || "Comprehensive Evaluation"}
              </span>
              <h2><Award className="gradient-icon" size={24} style={{ display: 'inline', marginRight: '8px' }} /> Performance Diagnostic Report</h2>
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              {setActiveTab && (
                <>
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      if (setSelectedInterviewId && interview) setSelectedInterviewId(interview.id);
                      setActiveTab('analysis');
                    }}
                    style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
                    id="btn-view-deep-analysis"
                  >
                    <Sparkles size={16} /> Deep AI Analysis
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      if (setSelectedInterviewId && interview) setSelectedInterviewId(interview.id);
                      setActiveTab('roadmap');
                    }}
                    style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
                    id="btn-view-preparation-roadmap"
                  >
                    <Compass size={16} /> Preparation Roadmap
                  </button>
                </>
              )}
              <button className="btn btn-secondary" onClick={() => { setInterview(null); setFinalReport(null); }}>
                <Play size={16} /> Start New Session
              </button>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px', marginBottom: '24px' }}>
            <div style={{ background: 'var(--gradient-primary)', padding: '24px', borderRadius: '16px', textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <span style={{ fontSize: '14px', opacity: 0.9 }}>Overall Mock Rating</span>
              <div style={{ fontSize: '52px', fontWeight: 800, fontFamily: 'Outfit', color: '#FFF' }}>
                {finalReport.overall_score.toFixed(1)}
              </div>
              <span style={{ fontSize: '13px', opacity: 0.8 }}>
                {finalReport.score_out_of_10 ? `${finalReport.score_out_of_10.toFixed(1)} / 10` : 'out of 100'}
              </span>
              {finalReport.readiness_level && (
                <div style={{ marginTop: '12px', background: 'rgba(255,255,255,0.2)', padding: '4px 12px', borderRadius: '20px', fontSize: '13px', fontWeight: 600 }}>
                  Level: {finalReport.readiness_level}
                </div>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
                <span style={{ fontSize: '12px', color: '#9CA3AF' }}>Technical Knowledge</span>
                <strong style={{ display: 'block', fontSize: '22px', marginTop: '4px', color: '#818CF8' }}>{finalReport.technical_knowledge_score.toFixed(0)}%</strong>
              </div>
              <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
                <span style={{ fontSize: '12px', color: '#9CA3AF' }}>Communication</span>
                <strong style={{ display: 'block', fontSize: '22px', marginTop: '4px', color: '#34D399' }}>{finalReport.communication_score.toFixed(0)}%</strong>
              </div>
              <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
                <span style={{ fontSize: '12px', color: '#9CA3AF' }}>Problem Solving</span>
                <strong style={{ display: 'block', fontSize: '22px', marginTop: '4px', color: '#FBBF24' }}>{finalReport.problem_solving_score.toFixed(0)}%</strong>
              </div>
              <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
                <span style={{ fontSize: '12px', color: '#9CA3AF' }}>Answer Quality</span>
                <strong style={{ display: 'block', fontSize: '22px', marginTop: '4px', color: '#F472B6' }}>{finalReport.answer_quality_score.toFixed(0)}%</strong>
              </div>
            </div>
          </div>

          {/* Executive AI Summary & Readiness Estimate */}
          <div style={{ background: 'rgba(11, 15, 23, 0.8)', padding: '20px', borderRadius: '12px', marginBottom: '24px', border: '1px solid rgba(255,255,255,0.08)' }}>
            <h4 style={{ marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Bot size={18} color="#8B5CF6" /> Executive AI Summary
            </h4>
            <p style={{ fontSize: '14px', color: '#E2E8F0', lineHeight: '1.6', marginBottom: finalReport.readiness_estimate ? '12px' : '0' }}>
              {finalReport.personalized_summary}
            </p>
            {finalReport.readiness_estimate && (
              <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '10px 14px', borderRadius: '8px', fontSize: '13px', color: '#C4B5FD', borderLeft: '3px solid #8B5CF6' }}>
                <strong>Role Readiness Assessment:</strong> {finalReport.readiness_estimate}
              </div>
            )}
          </div>

          {/* Topics and Skill Gaps */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px', marginBottom: '28px' }}>
            <div style={{ padding: '16px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <h4 style={{ color: '#10B981', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle2 size={16} /> Strong Topics
              </h4>
              <ul style={{ paddingLeft: '18px', margin: 0 }}>
                {finalReport.strong_topics.map((t, idx) => (
                  <li key={idx} style={{ fontSize: '13px', color: '#E2E8F0', marginBottom: '4px' }}>{t}</li>
                ))}
              </ul>
            </div>

            <div style={{ padding: '16px', borderRadius: '12px', background: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
              <h4 style={{ color: '#F59E0B', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <AlertCircle size={16} /> Areas to Improve / Gaps
              </h4>
              <ul style={{ paddingLeft: '18px', margin: 0 }}>
                {(finalReport.skill_gaps && finalReport.skill_gaps.length > 0 ? finalReport.skill_gaps : finalReport.weak_topics).map((t, idx) => (
                  <li key={idx} style={{ fontSize: '13px', color: '#E2E8F0', marginBottom: '4px' }}>{t}</li>
                ))}
              </ul>
            </div>

            {finalReport.recommendations && finalReport.recommendations.length > 0 && (
              <div style={{ padding: '16px', borderRadius: '12px', background: 'rgba(99, 102, 241, 0.05)', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
                <h4 style={{ color: '#818CF8', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Lightbulb size={16} /> Key Recommendations
                </h4>
                <ul style={{ paddingLeft: '18px', margin: 0 }}>
                  {finalReport.recommendations.map((r, idx) => (
                    <li key={idx} style={{ fontSize: '13px', color: '#E2E8F0', marginBottom: '4px' }}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Question-by-Question Diagnostic Review */}
          {finalReport.question_results && finalReport.question_results.length > 0 && (
            <div style={{ marginTop: '24px' }}>
              <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '18px' }}>
                <BookOpen size={20} color="#8B5CF6" /> Detailed Question-by-Question Review
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {finalReport.question_results.map((qr, idx) => {
                  const isExpanded = expandedQuestionIdx === idx;
                  return (
                    <div
                      key={idx}
                      style={{
                        background: 'rgba(17, 24, 39, 0.7)',
                        border: '1px solid rgba(255,255,255,0.08)',
                        borderRadius: '12px',
                        overflow: 'hidden'
                      }}
                    >
                      <div
                        onClick={() => setExpandedQuestionIdx(isExpanded ? null : idx)}
                        style={{
                          padding: '16px 20px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          cursor: 'pointer',
                          background: isExpanded ? 'rgba(31, 41, 55, 0.5)' : 'transparent'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
                          <span style={{
                            background: qr.is_skipped ? 'rgba(156, 163, 175, 0.2)' : qr.score >= 80 ? 'rgba(16, 185, 129, 0.2)' : qr.score >= 60 ? 'rgba(245, 158, 11, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                            color: qr.is_skipped ? '#9CA3AF' : qr.score >= 80 ? '#10B981' : qr.score >= 60 ? '#F59E0B' : '#EF4444',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            fontWeight: 700,
                            fontSize: '13px'
                          }}>
                            {qr.is_skipped ? 'Skipped (Not Scored)' : (qr.score_out_of_10 ? `${qr.score_out_of_10.toFixed(1)}/10` : `${(qr.score || 0).toFixed(0)}%`)}
                          </span>
                          <div>
                            <span style={{ fontSize: '12px', color: '#9CA3AF', marginRight: '8px' }}>Q{qr.question_number} • {qr.topic}</span>
                            <div style={{ fontWeight: 600, fontSize: '14px', color: '#F8FAFC', marginTop: '2px' }}>{qr.question}</div>
                          </div>
                        </div>
                        <div style={{ color: '#9CA3AF', marginLeft: '12px' }}>
                          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                        </div>
                      </div>

                      {isExpanded && (
                        <div style={{ padding: '20px', borderTop: '1px solid rgba(255,255,255,0.06)', background: 'rgba(11, 15, 23, 0.95)' }}>
                          {qr.is_skipped ? (
                            <div style={{ background: 'rgba(156, 163, 175, 0.1)', borderLeft: '3px solid #9CA3AF', padding: '10px 14px', borderRadius: '6px', marginBottom: '14px' }}>
                              <span style={{ fontSize: '13px', color: '#9CA3AF', fontWeight: 600 }}>Candidate skipped this question. Excluded from score calculation.</span>
                            </div>
                          ) : (
                            <div style={{ marginBottom: '14px' }}>
                              <span style={{ fontSize: '12px', fontWeight: 600, color: '#9CA3AF', textTransform: 'uppercase' }}>Candidate Response:</span>
                              <p style={{ background: 'rgba(31, 41, 55, 0.4)', padding: '12px', borderRadius: '8px', fontSize: '13px', color: '#E2E8F0', marginTop: '4px', fontStyle: 'italic', lineHeight: '1.5' }}>
                                "{qr.user_answer || "No response provided"}"
                              </p>
                            </div>
                          )}

                          {qr.strengths && qr.strengths.length > 0 && (
                            <div style={{ marginBottom: '12px' }}>
                              <span style={{ fontSize: '12px', fontWeight: 600, color: '#10B981' }}>Key Strengths:</span>
                              <ul style={{ margin: '4px 0 0 18px', padding: 0 }}>
                                {qr.strengths.map((s, sIdx) => (
                                  <li key={sIdx} style={{ fontSize: '13px', color: '#E2E8F0' }}>{s}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {qr.missing_concepts && qr.missing_concepts.length > 0 && (
                            <div style={{ marginBottom: '12px' }}>
                              <span style={{ fontSize: '12px', fontWeight: 600, color: '#F59E0B' }}>Missing Concepts:</span>
                              <ul style={{ margin: '4px 0 0 18px', padding: 0 }}>
                                {qr.missing_concepts.map((m, mIdx) => (
                                  <li key={mIdx} style={{ fontSize: '13px', color: '#E2E8F0' }}>{m}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {qr.incorrect_claims && qr.incorrect_claims.length > 0 && (
                            <div style={{ marginBottom: '12px', background: 'rgba(239, 68, 68, 0.08)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                              <span style={{ fontSize: '12px', fontWeight: 600, color: '#EF4444' }}>Inaccurate Claims / Misconceptions:</span>
                              <ul style={{ margin: '4px 0 0 18px', padding: 0 }}>
                                {qr.incorrect_claims.map((ic, icIdx) => (
                                  <li key={icIdx} style={{ fontSize: '13px', color: '#FCA5A5' }}>{ic}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {qr.model_answer && (
                            <div style={{ marginTop: '12px', background: 'rgba(99, 102, 241, 0.08)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
                              <span style={{ fontSize: '12px', fontWeight: 600, color: '#818CF8' }}>Benchmark Model Answer:</span>
                              <p style={{ fontSize: '13px', color: '#E2E8F0', marginTop: '4px', lineHeight: '1.5' }}>{qr.model_answer}</p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Post-Interview Bottom Call-to-Action */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            padding: '20px 24px',
            borderRadius: '12px',
            marginTop: '28px',
            flexWrap: 'wrap',
            gap: '16px'
          }}>
            <div>
              <h4 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>Next Step: In-Depth AI Diagnostics & Roadmap</h4>
              <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#9CA3AF' }}>
                Inspect evidence-based skill gaps, rubric misconceptions, and access your personalized preparation roadmap.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              {setActiveTab && (
                <>
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      if (setSelectedInterviewId && interview) setSelectedInterviewId(interview.id);
                      setActiveTab('analysis');
                    }}
                  >
                    <Sparkles size={16} style={{ display: 'inline', marginRight: '6px' }} />
                    View Deep AI Analysis
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      if (setSelectedInterviewId && interview) setSelectedInterviewId(interview.id);
                      setActiveTab('roadmap');
                    }}
                  >
                    <Compass size={16} style={{ display: 'inline', marginRight: '6px' }} />
                    View Preparation Roadmap
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </section>
    );
  }

  // View: Active Session Room
  if (interview && currentQuestion) {
    const diffLower = (currentQuestion.difficulty || "medium").toLowerCase();
    const diffColor = diffLower === 'hard' ? '#FCA5A5' : diffLower === 'easy' ? '#6EE7B7' : '#FDE68A';
    const diffBg = diffLower === 'hard' ? 'rgba(239, 68, 68, 0.15)' : diffLower === 'easy' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)';
    const diffBorder = diffLower === 'hard' ? 'rgba(239, 68, 68, 0.3)' : diffLower === 'easy' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)';

    return (
      <section>
        <div className="room-top-bar glass-card">
          <div className="room-meta">
            {isAdaptive !== false ? (
              <span className="meta-pill" style={{ background: 'rgba(139, 92, 246, 0.2)', color: '#A78BFA', border: '1px solid rgba(139, 92, 246, 0.4)' }}>
                🧠 Adaptive AI Studio
              </span>
            ) : (
              <span className="meta-pill" style={{ background: 'rgba(59, 130, 246, 0.2)', color: '#60A5FA', border: '1px solid rgba(59, 130, 246, 0.4)' }}>
                🚀 Standard Mock Practice
              </span>
            )}
            <span className="meta-pill pill-role">{interview.role}</span>
            <span className="meta-pill pill-progress">Question {questionIndex} of {interview.total_questions}</span>
            <span className="meta-pill" style={{ background: diffBg, color: diffColor, border: `1px solid ${diffBorder}` }}>
              {currentQuestion.difficulty}
            </span>
            <span className="meta-pill pill-topic">{currentQuestion.topic}</span>
            {isAdaptive !== false && trackedGaps.length > 0 && (
              <span className="meta-pill" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#FBBF24', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                <AlertCircle size={12} style={{ display: 'inline', marginRight: '4px' }} />
                {trackedGaps.length} Knowledge Gap{trackedGaps.length > 1 ? 's' : ''} Tracked
              </span>
            )}
          </div>
          <button className="btn btn-outline-danger btn-sm" onClick={exitSession}>
            <X size={14} /> Exit
          </button>
        </div>

        {/* Question Card */}
        <div className="glass-card question-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flex: 1 }}>
              <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: 'var(--gradient-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Bot size={24} color="#FFF" />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '6px' }}>
                  <span style={{ fontSize: '12px', background: 'rgba(139, 92, 246, 0.2)', color: '#8B5CF6', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
                    {currentQuestion.question_type || "Technical"}
                  </span>
                  {isAdaptive !== false && currentQuestion.adaptive_action && (
                    <span style={{
                      fontSize: '11px',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontWeight: 700,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      background:
                        currentQuestion.adaptive_action === 'INCREASE_DIFFICULTY' ? 'rgba(139, 92, 246, 0.25)' :
                        currentQuestion.adaptive_action === 'FOLLOW_UP' ? 'rgba(59, 130, 246, 0.25)' :
                        currentQuestion.adaptive_action === 'SIMPLIFY' ? 'rgba(16, 185, 129, 0.25)' :
                        currentQuestion.adaptive_action === 'CLARIFY' ? 'rgba(245, 158, 11, 0.25)' : 'rgba(100, 116, 139, 0.25)',
                      color:
                        currentQuestion.adaptive_action === 'INCREASE_DIFFICULTY' ? '#C4B5FD' :
                        currentQuestion.adaptive_action === 'FOLLOW_UP' ? '#93C5FD' :
                        currentQuestion.adaptive_action === 'SIMPLIFY' ? '#6EE7B7' :
                        currentQuestion.adaptive_action === 'CLARIFY' ? '#FDE68A' : '#CBD5E1',
                      border: '1px solid currentColor'
                    }}>
                      {currentQuestion.adaptive_action === 'INCREASE_DIFFICULTY' && <Zap size={11} />}
                      {currentQuestion.adaptive_action === 'FOLLOW_UP' && <Target size={11} />}
                      {currentQuestion.adaptive_action === 'SIMPLIFY' && <Compass size={11} />}
                      {currentQuestion.adaptive_action === 'CLARIFY' && <HelpCircle size={11} />}
                      {currentQuestion.adaptive_action === 'NEXT_TOPIC' && <Layers size={11} />}
                      {currentQuestion.adaptive_action.replace('_', ' ')}
                    </span>
                  )}
                </div>
                <h3 style={{ fontSize: '18px', fontWeight: 700, margin: '4px 0', color: '#F8FAFC', lineHeight: '1.4' }}>{currentQuestion.question}</h3>
                {currentQuestion.adaptation_reason && (
                  <div style={{ marginTop: '8px', fontSize: '12px', color: '#94A3B8', display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                    <Sparkles size={13} color="#A78BFA" style={{ flexShrink: 0, marginTop: '2px' }} />
                    <span><strong style={{ color: '#C4B5FD' }}>Adaptive Rationale:</strong> {currentQuestion.adaptation_reason}</span>
                  </div>
                )}
                {currentQuestion.assessment_objective && (
                  <div style={{ marginTop: '4px', fontSize: '12px', color: '#94A3B8', display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                    <Target size={13} color="#60A5FA" style={{ flexShrink: 0, marginTop: '2px' }} />
                    <span><strong style={{ color: '#93C5FD' }}>Assessment Objective:</strong> {currentQuestion.assessment_objective}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Hint / Clarification Button */}
            {!evaluation && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setShowClarifyModal(true);
                  if (!clarificationData) {
                    handleRequestClarification();
                  }
                }}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                <HelpCircle size={15} color="#8B5CF6" />
                <span>Interviewer Hint</span>
              </button>
            )}
          </div>
        </div>

        {/* Clarification Drawer / Box */}
        {showClarifyModal && (
          <div className="glass-card" style={{ border: '1px solid rgba(139, 92, 246, 0.4)', background: 'rgba(15, 23, 42, 0.95)', marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#C4B5FD', margin: 0, fontSize: '15px' }}>
                <HelpCircle size={18} color="#8B5CF6" /> Interviewer Scope Guidance & Hints
              </h4>
              <button className="btn btn-sm btn-secondary" onClick={() => setShowClarifyModal(false)}>
                <X size={14} />
              </button>
            </div>

            {clarifyLoading ? (
              <div style={{ padding: '16px', textAlign: 'center', color: '#9CA3AF' }}>
                <span className="loading-spinner"></span> Formulating interviewer clarification...
              </div>
            ) : clarificationData ? (
              <div>
                <p style={{ fontSize: '14px', color: '#E2E8F0', marginBottom: '12px', lineHeight: '1.5' }}>
                  {clarificationData.clarification}
                </p>

                {clarificationData.hint && (
                  <div style={{ background: 'rgba(245, 158, 11, 0.1)', borderLeft: '3px solid #F59E0B', padding: '10px 14px', borderRadius: '6px', marginBottom: '12px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#F59E0B', display: 'block' }}>💡 Technical Guiding Thought:</span>
                    <span style={{ fontSize: '13px', color: '#FDE68A' }}>{clarificationData.hint}</span>
                  </div>
                )}

                {clarificationData.focus_areas && clarificationData.focus_areas.length > 0 && (
                  <div>
                    <span style={{ fontSize: '12px', color: '#9CA3AF', display: 'block', marginBottom: '6px' }}>Recommended Concepts to Address:</span>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      {clarificationData.focus_areas.map((fa, i) => (
                        <span key={i} style={{ background: 'rgba(139, 92, 246, 0.15)', color: '#C4B5FD', padding: '3px 10px', borderRadius: '12px', fontSize: '12px' }}>
                          ✓ {fa}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : null}

            <div style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
              <input
                type="text"
                className="form-control"
                placeholder="Ask specific question to interviewer (e.g. 'Can I assume single-threaded execution?')..."
                value={clarifyQuery}
                onChange={e => setClarifyQuery(e.target.value)}
                style={{ fontSize: '13px' }}
                onKeyDown={e => { if (e.key === 'Enter') handleRequestClarification(); }}
              />
              <button className="btn btn-primary btn-sm" onClick={handleRequestClarification} disabled={clarifyLoading}>
                Ask
              </button>
            </div>
          </div>
        )}

        {/* Answer Card */}
        <div className="glass-card answer-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: 600 }}>
              <PenTool size={14} style={{ display: 'inline', marginRight: '4px' }} /> Your Answer Response:
            </label>
            <span style={{ fontSize: '12px', color: '#6B7280' }}>{wordCount} words</span>
          </div>

          <textarea
            className="answer-textarea"
            placeholder="Type your structured response here... (Break into: Core Definition, How it Works, Key Trade-offs & Production Edge Cases)"
            value={userAnswer}
            onChange={e => setUserAnswer(e.target.value)}
            disabled={loading || !!evaluation}
          />

          {!evaluation && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '16px' }}>
              <button 
                type="button"
                className="btn btn-secondary" 
                onClick={handleSkip} 
                disabled={loading || skipLoading}
              >
                {skipLoading ? (
                  <>
                    <span className="loading-spinner" style={{ width: '14px', height: '14px', marginRight: '6px' }}></span>
                    Skipping Question...
                  </>
                ) : (
                  <>
                    <Forward size={16} /> Skip / Pass Question
                  </>
                )}
              </button>
              <button 
                type="button"
                className="btn btn-gradient btn-lg" 
                onClick={handleSubmitAnswer} 
                disabled={loading || skipLoading}
              >
                <Send size={16} /> {loading ? "Evaluating Answer..." : "Submit Answer"}
              </button>
            </div>
          )}
        </div>

        {/* Evaluation Card */}
        {evaluation && (
          <div className="glass-card" style={{ border: '1px solid rgba(139, 92, 246, 0.4)', marginTop: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{ background: 'var(--gradient-primary)', padding: '8px 16px', borderRadius: '12px', color: '#FFF' }}>
                  <span style={{ fontSize: '28px', fontWeight: 800 }}>
                    {evaluation.score_out_of_10 ? evaluation.score_out_of_10.toFixed(1) : (evaluation.score / 10).toFixed(1)}
                  </span> / 10
                </div>
                <div>
                  <h4 style={{ fontSize: '18px', margin: 0 }}>AI Diagnostic Evaluation</h4>
                  <span style={{ fontSize: '12px', color: '#9CA3AF' }}>Weighted Rubric Score: {evaluation.score.toFixed(1)}%</span>
                </div>
              </div>

              {evaluation.evaluation_type && (
                <span className="badge badge-primary">
                  {evaluation.evaluation_type.toUpperCase()}
                </span>
              )}
            </div>

            {/* Adaptive Decision Card */}
            {isAdaptive !== false && adaptiveDecision && (
              <div style={{
                background: 'rgba(139, 92, 246, 0.08)',
                border: '1px solid rgba(139, 92, 246, 0.3)',
                borderRadius: '10px',
                padding: '16px',
                marginBottom: '20px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Sparkles size={16} color="#A78BFA" />
                    <strong style={{ color: '#DDD6FE', fontSize: '14px' }}>Adaptive Intelligence Engine Decision</strong>
                  </div>
                  <span style={{
                    fontSize: '11px',
                    padding: '3px 10px',
                    borderRadius: '6px',
                    fontWeight: 700,
                    background:
                      adaptiveDecision.action === 'INCREASE_DIFFICULTY' ? 'rgba(139, 92, 246, 0.25)' :
                      adaptiveDecision.action === 'FOLLOW_UP' ? 'rgba(59, 130, 246, 0.25)' :
                      adaptiveDecision.action === 'SIMPLIFY' ? 'rgba(16, 185, 129, 0.25)' :
                      adaptiveDecision.action === 'CLARIFY' ? 'rgba(245, 158, 11, 0.25)' : 'rgba(100, 116, 139, 0.25)',
                    color:
                      adaptiveDecision.action === 'INCREASE_DIFFICULTY' ? '#C4B5FD' :
                      adaptiveDecision.action === 'FOLLOW_UP' ? '#93C5FD' :
                      adaptiveDecision.action === 'SIMPLIFY' ? '#6EE7B7' :
                      adaptiveDecision.action === 'CLARIFY' ? '#FDE68A' : '#CBD5E1',
                    border: '1px solid currentColor'
                  }}>
                    {adaptiveDecision.action.replace('_', ' ')} • Difficulty: {adaptiveDecision.updated_difficulty || currentQuestion.difficulty}
                  </span>
                </div>
                <p style={{ fontSize: '13px', color: '#E2E8F0', margin: '4px 0 8px 0', lineHeight: '1.5' }}>
                  {adaptiveDecision.decision_rationale}
                </p>
                {adaptiveDecision.assessment_objective && (
                  <div style={{ fontSize: '12px', color: '#94A3B8', marginTop: '6px' }}>
                    <strong style={{ color: '#C4B5FD' }}>Next Assessment Objective:</strong> {adaptiveDecision.assessment_objective}
                  </div>
                )}
                {adaptiveDecision.identified_knowledge_gaps && adaptiveDecision.identified_knowledge_gaps.length > 0 && (
                  <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '11px', color: '#FBBF24', fontWeight: 600 }}>Tracked Knowledge Gaps:</span>
                    {adaptiveDecision.identified_knowledge_gaps.map((gap: string, gIdx: number) => (
                      <span key={gIdx} style={{ fontSize: '11px', background: 'rgba(245, 158, 11, 0.15)', color: '#FDE68A', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                        • {gap}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Rubric Breakdown Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '20px' }}>
              <div style={{ padding: '14px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                <h5 style={{ color: '#10B981', marginBottom: '6px' }}>
                  <CheckCircle2 size={14} style={{ display: 'inline', marginRight: '4px' }} /> Strengths
                </h5>
                <ul style={{ paddingLeft: '18px', margin: 0 }}>
                  {evaluation.strengths.map((s, i) => <li key={i} style={{ fontSize: '13px', color: '#E2E8F0', marginBottom: '4px' }}>{s}</li>)}
                </ul>
              </div>

              <div style={{ padding: '14px', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                <h5 style={{ color: '#F59E0B', marginBottom: '6px' }}>
                  <AlertCircle size={14} style={{ display: 'inline', marginRight: '4px' }} /> Missing Concepts & Gaps
                </h5>
                <ul style={{ paddingLeft: '18px', margin: 0 }}>
                  {(evaluation.missing_concepts && evaluation.missing_concepts.length > 0 ? evaluation.missing_concepts : [...evaluation.weaknesses, ...evaluation.missing_points]).map((w, i) => (
                    <li key={i} style={{ fontSize: '13px', color: '#E2E8F0', marginBottom: '4px' }}>{w}</li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Inaccurate Claims / Misconceptions */}
            {evaluation.incorrect_claims && evaluation.incorrect_claims.length > 0 && (
              <div style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '14px', borderRadius: '8px', marginBottom: '16px' }}>
                <h5 style={{ color: '#EF4444', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <AlertTriangle size={15} /> Inaccuracies & Misconceptions to Correct
                </h5>
                <ul style={{ margin: '4px 0 0 18px', padding: 0 }}>
                  {evaluation.incorrect_claims.map((ic, i) => (
                    <li key={i} style={{ fontSize: '13px', color: '#FCA5A5' }}>{ic}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Model Answer Benchmark */}
            <div style={{ background: 'rgba(11, 15, 23, 0.8)', padding: '16px', borderRadius: '8px', marginBottom: '16px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <h5 style={{ fontSize: '13px', fontWeight: 700, marginBottom: '6px', color: '#F59E0B', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Lightbulb size={14} color="#F59E0B" /> Model Answer Benchmark
              </h5>
              <p style={{ fontSize: '13px', color: '#E2E8F0', lineHeight: '1.6', margin: 0 }}>
                {evaluation.improved_sample_answer || evaluation.ideal_answer}
              </p>
            </div>

            {/* Actionable Feedback */}
            <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '14px', borderRadius: '8px', marginBottom: '20px', display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: '13px', border: '1px solid rgba(139, 92, 246, 0.2)' }}>
              <Sparkles size={18} color="#8B5CF6" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', color: '#C4B5FD', marginBottom: '2px' }}>Actionable Coaching Tip:</strong>
                <span style={{ color: '#E2E8F0', lineHeight: '1.5' }}>
                  {evaluation.actionable_feedback || evaluation.improvement_tip}
                </span>
              </div>
            </div>

            <button className="btn btn-gradient btn-lg w-100" onClick={handleProceedNext} disabled={loading}>
              {nextBtnLabel} <ArrowRight size={18} />
            </button>
          </div>
        )}
      </section>
    );
  }

  // View: Setup Form
  return (
    <section>
      <div className="glass-card" style={{ maxWidth: '780px', margin: '0 auto' }}>
        <div style={{ marginBottom: '24px' }}>
          <h2>
            {isAdaptive !== false ? (
              <>
                <Sparkles className="gradient-icon" size={24} style={{ display: 'inline', marginRight: '8px' }} />
                Adaptive AI Interview Studio
              </>
            ) : (
              <>
                <Play className="gradient-icon" size={24} style={{ display: 'inline', marginRight: '8px' }} />
                Start Practice — Standard Mock Interview
              </>
            )}
          </h2>
          <p style={{ fontSize: '14px', color: '#9CA3AF' }}>
            {isAdaptive !== false 
              ? "Dynamic AI-driven session with real-time question branching, difficulty scaling, and reasoning challenges." 
              : "Structured, predictable mock interview with pre-generated questions and comprehensive end-of-session diagnostic scoring."}
          </p>
        </div>

        {setActiveTab && (
          <div style={{
            background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.15))',
            border: '1px solid rgba(139, 92, 246, 0.3)',
            padding: '16px 20px',
            borderRadius: '12px',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'var(--gradient-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontSize: '20px' }}>🎙️</span>
              </div>
              <div>
                <div style={{ fontWeight: '700', fontSize: '0.95rem' }}>Want a live spoken conversation?</div>
                <div style={{ fontSize: '0.8rem', color: '#9CA3AF' }}>Practice with our AI Voice Simulator with natural speech and live transcription.</div>
              </div>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              style={{ padding: '8px 16px', fontSize: '0.85rem' }}
              onClick={() => setActiveTab('voice')}
            >
              Launch Voice Mode 🎙️
            </button>
          </div>
        )}

        <form onSubmit={handleStart}>
          <div className="form-grid">
            <div className="form-group">
              <label>Target Role</label>
              <select className="form-control" value={role} onChange={e => setRole(e.target.value)}>
                <option value="Software Developer">Software Developer</option>
                <option value="Backend Engineer">Backend Engineer</option>
                <option value="Frontend Engineer">Frontend Engineer</option>
                <option value="Full Stack Engineer">Full Stack Engineer</option>
                <option value="DevOps & Cloud Engineer">DevOps & Cloud Engineer</option>
                <option value="Data Engineer">Data Engineer</option>
                <option value="System Architect">System Architect</option>
              </select>
            </div>

            <div className="form-group">
              <label>Experience Level</label>
              <select className="form-control" value={experience} onChange={e => setExperience(e.target.value)}>
                <option value="Junior (0-2 Yrs)">Junior (0-2 Yrs)</option>
                <option value="Intermediate (2-5 Yrs)">Intermediate (2-5 Yrs)</option>
                <option value="Senior (5+ Yrs)">Senior (5+ Yrs)</option>
                <option value="Lead / Staff (8+ Yrs)">Lead / Staff (8+ Yrs)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Interview Type</label>
              <select className="form-control" value={interviewType} onChange={e => setInterviewType(e.target.value)}>
                <option value="Technical">Technical Core & Architecture</option>
                <option value="HR">HR & Behavioral (STAR Method)</option>
                <option value="Coding">Coding & Algorithm Concepts</option>
                <option value="System Design">System Design & Scalability</option>
              </select>
            </div>

            <div className="form-group">
              <label>Difficulty</label>
              <select className="form-control" value={difficulty} onChange={e => setDifficulty(e.target.value)}>
                <option value="Easy">Easy</option>
                <option value="Medium">Medium</option>
                <option value="Hard">Hard</option>
                <option value="Adaptive">Adaptive (Scales dynamically)</option>
              </select>
            </div>
          </div>

          <div className="form-group" style={{ marginTop: '20px' }}>
            <label>Topics of Focus</label>
            <div className="topic-chips">
              {topicsList.map(t => (
                <button
                  key={t}
                  type="button"
                  className={`chip ${selectedTopics.includes(t) ? 'active' : ''}`}
                  onClick={() => toggleTopic(t)}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="form-group" style={{ marginTop: '20px' }}>
            <label>Total Questions: {totalQuestions}</label>
            <input
              type="range"
              min={3}
              max={15}
              value={totalQuestions}
              onChange={e => setTotalQuestions(parseInt(e.target.value))}
              style={{ width: '100%', accentColor: '#8B5CF6' }}
            />
          </div>

          {/* Advanced Personalization Accordion */}
          <div style={{ marginTop: '24px', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '16px' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowAdvanced(!showAdvanced)}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', justifyContent: 'space-between', padding: '10px 14px' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sparkles size={16} color="#8B5CF6" />
                <strong>Advanced Personalization (Job Description, Resume & Custom Skills)</strong>
              </span>
              {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>

            {showAdvanced && (
              <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '16px', background: 'rgba(15, 23, 42, 0.4)', padding: '16px', borderRadius: '12px' }}>
                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Briefcase size={14} color="#818CF8" /> Target Job Description (Optional)
                  </label>
                  <textarea
                    className="form-control"
                    rows={3}
                    placeholder="Paste the key responsibilities, tech stack, or requirements from the target Job Description..."
                    value={jobDescription}
                    onChange={e => setJobDescription(e.target.value)}
                    style={{ fontSize: '13px' }}
                  />
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <FileText size={14} color="#34D399" /> Candidate Resume / Profile Background (Optional)
                  </label>
                  <textarea
                    className="form-control"
                    rows={3}
                    placeholder="Paste your resume summary, notable projects, or experience highlights..."
                    value={resumeText}
                    onChange={e => setResumeText(e.target.value)}
                    style={{ fontSize: '13px' }}
                  />
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Target size={14} color="#FBBF24" /> Specific Target Skills / Technologies (Optional)
                  </label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. Kafka, Redis, Docker, Kubernetes, AWS, Spring Boot"
                    value={customSkills}
                    onChange={e => setCustomSkills(e.target.value)}
                    style={{ fontSize: '13px' }}
                  />
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <BookOpen size={14} color="#F472B6" /> Interviewer Guidelines / Special Instructions (Optional)
                  </label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. Focus on high throughput, distributed locking, and edge-cases"
                    value={additionalInstructions}
                    onChange={e => setAdditionalInstructions(e.target.value)}
                    style={{ fontSize: '13px' }}
                  />
                </div>
              </div>
            )}
          </div>

          <button type="submit" className="btn btn-gradient btn-lg w-100" style={{ marginTop: '28px' }} disabled={loading}>
            <Play size={18} /> {loading ? "Initializing Interview..." : (isAdaptive !== false ? "Launch Adaptive AI Session" : "Launch Standard Mock Interview")}
          </button>
        </form>
      </div>
    </section>
  );
};
