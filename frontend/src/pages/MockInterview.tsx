import React, { useState } from 'react';
import { Interview, Question, Evaluation, FinalReportResponse } from '../types';
import { interviewAPI, aiAPI } from '../services/api';
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
  X
} from 'lucide-react';

interface MockInterviewProps {
  onToast: (msg: string, type?: string) => void;
  openAuthModal: () => void;
  setActiveTab?: (tab: string) => void;
}

export const MockInterview: React.FC<MockInterviewProps> = ({ onToast, openAuthModal, setActiveTab }) => {
  const { isAuthenticated } = useAuth();

  // Config State
  const [role, setRole] = useState("Software Developer");
  const [experience, setExperience] = useState("Intermediate (2-5 Yrs)");
  const [interviewType, setInterviewType] = useState("Technical");
  const [difficulty, setDifficulty] = useState("Medium");
  const [selectedTopics, setSelectedTopics] = useState<string[]>(["Java", "OOP"]);
  const [totalQuestions, setTotalQuestions] = useState(5);

  // Active Session State
  const [interview, setInterview] = useState<Interview | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [questionIndex, setQuestionIndex] = useState(1);
  const [userAnswer, setUserAnswer] = useState("");
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [finalReport, setFinalReport] = useState<FinalReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [nextBtnLabel, setNextBtnLabel] = useState("Proceed to Next Question");

  const topicsList = ["Java", "OOP", "DBMS", "Operating Systems", "System Design", "Data Structures", "Algorithms"];

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
    if (!isAuthenticated) {
      openAuthModal();
      return;
    }

    setLoading(true);
    try {
      const res = await interviewAPI.create({
        role,
        experience_level: experience,
        difficulty,
        interview_type: interviewType,
        topics: selectedTopics,
        total_questions: totalQuestions
      });

      setInterview(res.interview);
      setCurrentQuestion(res.first_question);
      setQuestionIndex(1);
      setUserAnswer("");
      setEvaluation(null);
      setFinalReport(null);
      onToast("AI Mock Interview session started!", "success");
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Failed to start interview", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitAnswer = async () => {
    if (!userAnswer.trim()) {
      onToast("Please provide your answer before submitting.", "amber");
      return;
    }
    if (!interview || !currentQuestion) return;

    setLoading(true);
    try {
      const res = await interviewAPI.submitAnswer(interview.id, currentQuestion.id, userAnswer);
      setEvaluation(res.evaluation);

      if (res.follow_up_question) {
        setCurrentQuestion(res.follow_up_question);
        setNextBtnLabel("Answer Follow-Up Question");
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
    if (nextBtnLabel.includes("Final Performance Report")) {
      if (!interview) return;
      setLoading(true);
      try {
        const rep = await aiAPI.getReport(interview.id);
        setFinalReport(rep);
      } catch (err: any) {
        onToast("Failed to fetch final report", "error");
      } finally {
        setLoading(false);
      }
    } else {
      setUserAnswer("");
      setEvaluation(null);
    }
  };

  const handleSkip = async () => {
    if (!interview) return;
    setLoading(true);
    try {
      const nextQ = await interviewAPI.skipQuestion(interview.id);
      if (nextQ) {
        setCurrentQuestion(nextQ);
        setQuestionIndex(prev => prev + 1);
        setUserAnswer("");
        setEvaluation(null);
      } else {
        const rep = await aiAPI.getReport(interview.id);
        setFinalReport(rep);
      }
    } catch (err: any) {
      onToast("Skip question failed", "error");
    } finally {
      setLoading(false);
    }
  };

  const exitSession = () => {
    if (window.confirm("Exit interview session?")) {
      setInterview(null);
      setCurrentQuestion(null);
      setFinalReport(null);
    }
  };

  const wordCount = userAnswer.trim() ? userAnswer.trim().split(/\s+/).length : 0;

  // View: Final Report
  if (finalReport) {
    return (
      <section>
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <h2><Award className="gradient-icon" size={24} style={{ display: 'inline', marginRight: '8px' }} /> Performance Diagnostic Report</h2>
            <button className="btn btn-primary" onClick={() => { setInterview(null); setFinalReport(null); }}>
              <Play size={16} /> Start New Session
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px', marginBottom: '24px' }}>
            <div style={{ background: 'var(--gradient-primary)', padding: '24px', borderRadius: '16px', textAlign: 'center' }}>
              <span style={{ fontSize: '14px', opacity: 0.9 }}>Overall Mock Rating</span>
              <div style={{ fontSize: '48px', fontWeight: 800, fontFamily: 'Outfit', color: '#FFF' }}>
                {finalReport.overall_score}
              </div>
              <span style={{ fontSize: '13px', opacity: 0.8 }}>out of 100</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '16px', borderRadius: '12px' }}>
                <span style={{ fontSize: '12px', color: '#9CA3AF' }}>Technical Knowledge</span>
                <strong style={{ display: 'block', fontSize: '20px' }}>{finalReport.technical_knowledge_score}%</strong>
              </div>
              <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '16px', borderRadius: '12px' }}>
                <span style={{ fontSize: '12px', color: '#9CA3AF' }}>Communication</span>
                <strong style={{ display: 'block', fontSize: '20px' }}>{finalReport.communication_score}%</strong>
              </div>
              <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '16px', borderRadius: '12px' }}>
                <span style={{ fontSize: '12px', color: '#9CA3AF' }}>Problem Solving</span>
                <strong style={{ display: 'block', fontSize: '20px' }}>{finalReport.problem_solving_score}%</strong>
              </div>
              <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '16px', borderRadius: '12px' }}>
                <span style={{ fontSize: '12px', color: '#9CA3AF' }}>Answer Quality</span>
                <strong style={{ display: 'block', fontSize: '20px' }}>{finalReport.answer_quality_score}%</strong>
              </div>
            </div>
          </div>

          <div style={{ background: 'rgba(11, 15, 23, 0.8)', padding: '20px', borderRadius: '12px', marginBottom: '24px' }}>
            <h4 style={{ marginBottom: '8px' }}>Executive AI Summary</h4>
            <p style={{ fontSize: '14px', color: '#9CA3AF' }}>{finalReport.personalized_summary}</p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div style={{ padding: '16px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <h4 style={{ color: '#10B981', marginBottom: '8px' }}>Strong Topics</h4>
              <ul>{finalReport.strong_topics.map((t, idx) => <li key={idx}>{t}</li>)}</ul>
            </div>
            <div style={{ padding: '16px', borderRadius: '12px', background: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
              <h4 style={{ color: '#F59E0B', marginBottom: '8px' }}>Areas to Improve</h4>
              <ul>{finalReport.weak_topics.map((t, idx) => <li key={idx}>{t}</li>)}</ul>
            </div>
          </div>
        </div>
      </section>
    );
  }

  // View: Active Session Room
  if (interview && currentQuestion) {
    return (
      <section>
        <div className="room-top-bar glass-card">
          <div className="room-meta">
            <span className="meta-pill pill-role">{interview.role}</span>
            <span className="meta-pill pill-progress">Question {questionIndex} of {interview.total_questions}</span>
            <span className="meta-pill pill-diff">{currentQuestion.difficulty}</span>
            <span className="meta-pill pill-topic">{currentQuestion.topic}</span>
          </div>
          <button className="btn btn-outline-danger btn-sm" onClick={exitSession}>
            <X size={14} /> Exit
          </button>
        </div>

        <div className="glass-card question-card">
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: 'var(--gradient-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Bot size={24} color="#FFF" />
            </div>
            <div>
              <span style={{ fontSize: '12px', background: 'rgba(139, 92, 246, 0.2)', color: '#8B5CF6', padding: '2px 8px', borderRadius: '4px' }}>
                {currentQuestion.question_type}
              </span>
              <h3 style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px' }}>{currentQuestion.question}</h3>
            </div>
          </div>
        </div>

        <div className="glass-card answer-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: 600 }}><PenTool size={14} style={{ display: 'inline', marginRight: '4px' }} /> Your Answer Response:</label>
            <span style={{ fontSize: '12px', color: '#6B7280' }}>{wordCount} words</span>
          </div>

          <textarea
            className="answer-textarea"
            placeholder="Type your response here..."
            value={userAnswer}
            onChange={e => setUserAnswer(e.target.value)}
            disabled={loading || !!evaluation}
          />

          {!evaluation && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '16px' }}>
              <button className="btn btn-secondary" onClick={handleSkip} disabled={loading}>
                <Forward size={16} /> Skip
              </button>
              <button className="btn btn-gradient btn-lg" onClick={handleSubmitAnswer} disabled={loading}>
                <Send size={16} /> {loading ? "Evaluating..." : "Submit Answer"}
              </button>
            </div>
          )}
        </div>

        {evaluation && (
          <div className="glass-card" style={{ border: '1px solid rgba(139, 92, 246, 0.4)', marginTop: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '20px' }}>
              <div style={{ background: 'var(--gradient-primary)', padding: '8px 16px', borderRadius: '12px', color: '#FFF' }}>
                <span style={{ fontSize: '28px', fontWeight: 800 }}>{evaluation.score.toFixed(1)}</span> / 10
              </div>
              <div>
                <h4 style={{ fontSize: '18px' }}>AI Diagnostic Evaluation</h4>
                <span style={{ fontSize: '12px', color: '#6B7280' }}>Instant Analysis</span>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
              <div style={{ padding: '14px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                <h5 style={{ color: '#10B981', marginBottom: '6px' }}><CheckCircle2 size={14} style={{ display: 'inline', marginRight: '4px' }} /> Strengths</h5>
                <ul>{evaluation.strengths.map((s, i) => <li key={i} style={{ fontSize: '13px' }}>{s}</li>)}</ul>
              </div>

              <div style={{ padding: '14px', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                <h5 style={{ color: '#F59E0B', marginBottom: '6px' }}><AlertCircle size={14} style={{ display: 'inline', marginRight: '4px' }} /> Missing / Weak Points</h5>
                <ul>{[...evaluation.weaknesses, ...evaluation.missing_points].map((w, i) => <li key={i} style={{ fontSize: '13px' }}>{w}</li>)}</ul>
              </div>
            </div>

            <div style={{ background: 'rgba(11, 15, 23, 0.8)', padding: '16px', borderRadius: '8px', marginBottom: '16px' }}>
              <h5 style={{ fontSize: '13px', fontWeight: 700, marginBottom: '4px' }}><Lightbulb size={14} color="#F59E0B" style={{ display: 'inline', marginRight: '4px' }} /> Model Answer Benchmark</h5>
              <p style={{ fontSize: '13px', color: '#9CA3AF' }}>{evaluation.ideal_answer}</p>
            </div>

            <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '12px', borderRadius: '8px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
              <Sparkles size={16} color="#8B5CF6" />
              <span>{evaluation.improvement_tip}</span>
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
      <div className="glass-card" style={{ maxWidth: '720px', margin: '0 auto' }}>
        <div style={{ marginBottom: '24px' }}>
          <h2><Sliders className="gradient-icon" size={24} style={{ display: 'inline', marginRight: '8px' }} /> Configure AI Mock Session</h2>
          <p style={{ fontSize: '14px', color: '#9CA3AF' }}>Customize parameters for tailored dynamic question generation.</p>
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
            justifyContent: 'space-between'
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
              </select>
            </div>

            <div className="form-group">
              <label>Experience Level</label>
              <select className="form-control" value={experience} onChange={e => setExperience(e.target.value)}>
                <option value="Junior (0-2 Yrs)">Junior (0-2 Yrs)</option>
                <option value="Intermediate (2-5 Yrs)">Intermediate (2-5 Yrs)</option>
                <option value="Senior (5+ Yrs)">Senior (5+ Yrs)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Interview Type</label>
              <select className="form-control" value={interviewType} onChange={e => setInterviewType(e.target.value)}>
                <option value="Technical">Technical Core & Fundamentals</option>
                <option value="HR">HR & Behavioral (STAR Method)</option>
                <option value="Coding">Coding & Algorithm Concepts</option>
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

          <button type="submit" className="btn btn-gradient btn-lg w-100" style={{ marginTop: '28px' }} disabled={loading}>
            <Play size={18} /> {loading ? "Initializing Interview..." : "Begin Mock Session"}
          </button>
        </form>
      </div>
    </section>
  );
};
