import React, { useState, useEffect, useRef } from 'react';
import { Interview, Question, Evaluation, FinalReportResponse, AdaptiveDecision } from '../types';
import { interviewAPI, aiAPI, voiceAPI, analysisAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Play,
  Pause,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Lightbulb,
  Sparkles,
  ArrowRight,
  Send,
  Sliders,
  Forward,
  Award,
  Clock,
  Brain,
  HelpCircle,
  Zap,
  Target,
  Compass,
  Layers,
  X
} from 'lucide-react';

interface VoiceInterviewProps {
  onToast: (msg: string, type?: string) => void;
  openAuthModal: () => void;
  setActiveTab: (tab: string) => void;
  setSelectedInterviewId?: (id: string | null) => void;
}

export const VoiceInterview: React.FC<VoiceInterviewProps> = ({
  onToast,
  openAuthModal,
  setActiveTab,
  setSelectedInterviewId
}) => {
  const { isAuthenticated, user } = useAuth();

  // Configuration State
  const [role, setRole] = useState("Software Developer");
  const [experience, setExperience] = useState("Intermediate (2-5 Yrs)");
  const [interviewType, setInterviewType] = useState("Technical");
  const [difficulty, setDifficulty] = useState("Medium");
  const [selectedTopics, setSelectedTopics] = useState<string[]>(["Java", "OOP"]);
  const [totalQuestions, setTotalQuestions] = useState(4);
  const [selectedVoice, setSelectedVoice] = useState("Google US English");
  const [speechRate, setSpeechRate] = useState(1.0);

  // Active Session State
  const [interview, setInterview] = useState<Interview | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [questionIndex, setQuestionIndex] = useState(1);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [adaptiveDecision, setAdaptiveDecision] = useState<AdaptiveDecision | null>(null);
  const [trackedGaps, setTrackedGaps] = useState<string[]>([]);
  const [finalReport, setFinalReport] = useState<FinalReportResponse | null>(null);
  const [expandedQuestionIdx, setExpandedQuestionIdx] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [skipLoading, setSkipLoading] = useState(false);
  const [nextBtnLabel, setNextBtnLabel] = useState("Proceed to Next Question");

  // Timer State
  const [timeLeft, setTimeLeft] = useState(1200); // 20 minutes default
  const [isPaused, setIsPaused] = useState(false);

  // Speech Recognition (STT) State
  const [isListening, setIsListening] = useState(false);
  const [liveInterim, setLiveInterim] = useState("");
  const [finalTranscript, setFinalTranscript] = useState("");
  const [userEditedAnswer, setUserEditedAnswer] = useState("");
  const [micPermission, setMicPermission] = useState<'prompt' | 'granted' | 'denied' | 'unsupported'>('prompt');
  const [isManualMode, setIsManualMode] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);

  // Text-To-Speech (TTS) State
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);

  // Refs
  const recognitionRef = useRef<any>(null);
  const recordingTimerRef = useRef<any>(null);
  const sessionTimerRef = useRef<any>(null);

  const topicsList = [
    "Java",
    "OOP",
    "Data Structures",
    "Algorithms",
    "System Design",
    "DBMS & SQL",
    "Operating Systems",
    "Microservices",
    "Cloud Architecture"
  ];

  // 1. Initialize Speech Recognition & Synthesis capabilities check
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setMicPermission('unsupported');
    }

    // Check microphone permission status if supported
    if (navigator.permissions && navigator.permissions.query) {
      navigator.permissions.query({ name: 'microphone' as any }).then(res => {
        if (res.state === 'granted') setMicPermission('granted');
        else if (res.state === 'denied') setMicPermission('denied');
        res.onchange = () => {
          if (res.state === 'granted') setMicPermission('granted');
          else if (res.state === 'denied') setMicPermission('denied');
        };
      }).catch(() => {});
    }

    return () => {
      stopListening();
      stopSpeaking();
      clearInterval(sessionTimerRef.current);
      clearInterval(recordingTimerRef.current);
    };
  }, []);

  // 2. Session Countdown Timer
  useEffect(() => {
    if (interview && !finalReport && !isPaused) {
      sessionTimerRef.current = setInterval(() => {
        setTimeLeft(prev => {
          if (prev <= 1) {
            clearInterval(sessionTimerRef.current);
            handleAutoFinish();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      clearInterval(sessionTimerRef.current);
    }
    return () => clearInterval(sessionTimerRef.current);
  }, [interview, finalReport, isPaused]);

  // 3. Spoken Question Trigger on Question Change
  useEffect(() => {
    if (currentQuestion && !isMuted) {
      const textToSpeak = currentQuestion.spoken_intro
        ? `${currentQuestion.spoken_intro} ${currentQuestion.question}`
        : currentQuestion.question;
      speakText(textToSpeak);
    }
  }, [currentQuestion]);

  // Helper: Format Seconds to mm:ss
  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const toggleTopic = (t: string) => {
    if (selectedTopics.includes(t)) {
      if (selectedTopics.length > 1) {
        setSelectedTopics(selectedTopics.filter(item => item !== t));
      }
    } else {
      setSelectedTopics([...selectedTopics, t]);
    }
  };

  // 4. Text-To-Speech implementation
  const speakText = (text: string) => {
    if (isMuted || !('speechSynthesis' in window)) return;

    window.speechSynthesis.cancel(); // Stop any active speech

    const cleanText = text.replace(/[*_#`]/g, '');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = speechRate;
    utterance.pitch = 1.0;

    // Pick selected voice if available
    const voices = window.speechSynthesis.getVoices();
    const match = voices.find(v => v.name.includes(selectedVoice) || v.lang === 'en-US');
    if (match) utterance.voice = match;

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  };

  const stopSpeaking = () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  };

  // 5. Speech Recognition implementation
  const startListening = () => {
    stopSpeaking(); // Interrupt AI speech so candidate is not spoken over

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      onToast("Speech Recognition is not supported in this browser. Switched to manual input.", "amber");
      setIsManualMode(true);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
        setMicPermission('granted');
        setRecordingSeconds(0);
        recordingTimerRef.current = setInterval(() => {
          setRecordingSeconds(prev => prev + 1);
        }, 1000);
      };

      recognition.onresult = (event: any) => {
        let interim = "";
        let accumulatedFinal = finalTranscript;

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            accumulatedFinal += (accumulatedFinal ? " " : "") + event.results[i][0].transcript.trim();
          } else {
            interim += event.results[i][0].transcript;
          }
        }

        setLiveInterim(interim);
        setFinalTranscript(accumulatedFinal);
        setUserEditedAnswer(accumulatedFinal + (interim ? " " + interim : ""));
      };

      recognition.onerror = (event: any) => {
        console.warn("Speech recognition error:", event.error);
        if (event.error === 'not-allowed') {
          setMicPermission('denied');
          onToast("Microphone access was denied. Please allow microphone permissions or type your answer.", "error");
          setIsManualMode(true);
        }
        setIsListening(false);
        clearInterval(recordingTimerRef.current);
      };

      recognition.onend = () => {
        setIsListening(false);
        clearInterval(recordingTimerRef.current);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err: any) {
      console.error("Failed to start speech recognition:", err);
      setIsListening(false);
      clearInterval(recordingTimerRef.current);
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
    }
    setIsListening(false);
    clearInterval(recordingTimerRef.current);
  };

  const handleRetryRecording = () => {
    stopListening();
    setLiveInterim("");
    setFinalTranscript("");
    setUserEditedAnswer("");
    setRecordingSeconds(0);
    onToast("Transcript cleared. Click microphone to speak again.", "info");
  };

  // 6. Start Voice Interview Session
  const handleStartInterview = async (e: React.FormEvent) => {
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
        total_questions: totalQuestions,
        mode: "voice",
        voice_name: selectedVoice
      });

      setInterview(res.interview);
      setCurrentQuestion(res.first_question);
      setQuestionIndex(1);
      setUserEditedAnswer("");
      setFinalTranscript("");
      setEvaluation(null);
      setFinalReport(null);
      setTimeLeft(totalQuestions * 300); // 5 mins per question

      onToast("Voice Interview started! Listen to the AI interviewer.", "success");
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Failed to start voice interview session", "error");
    } finally {
      setLoading(false);
    }
  };

  // 7. Submit Candidate Answer (Speech transcript or edited text)
  const handleSubmitAnswer = async () => {
    stopListening();
    stopSpeaking();

    const answerToSubmit = userEditedAnswer.trim();
    if (!answerToSubmit) {
      onToast("Please speak or write your answer before submitting.", "amber");
      return;
    }
    if (!interview || !currentQuestion) return;

    setLoading(true);
    try {
      const res = await interviewAPI.submitAnswer(
        interview.id,
        currentQuestion.id,
        answerToSubmit,
        {
          transcript_raw: finalTranscript || answerToSubmit,
          is_voice_submission: !isManualMode && !!finalTranscript,
          audio_duration_seconds: recordingSeconds > 0 ? recordingSeconds : undefined
        }
      );

      setEvaluation(res.evaluation);
      if (res.adaptive_decision) {
        setAdaptiveDecision(res.adaptive_decision);
      }
      if (res.knowledge_gaps && Array.isArray(res.knowledge_gaps)) {
        setTrackedGaps(res.knowledge_gaps);
      }
      if (res.current_difficulty) {
        setDifficulty(res.current_difficulty);
      }

      if (res.follow_up_question) {
        setCurrentQuestion(res.follow_up_question);
        setNextBtnLabel("Answer Contextual Follow-Up Probe");
        onToast("AI Interviewer asked a contextual follow-up probe!", "info");
      } else if (res.next_question) {
        setCurrentQuestion(res.next_question);
        setQuestionIndex(prev => prev + 1);
        setNextBtnLabel("Proceed to Next Question");
      } else if (res.interview_completed) {
        setNextBtnLabel("View Final Interview Performance Report");
        onToast("All questions completed! Review your final score.", "success");
      }
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Answer evaluation failed", "error");
    } finally {
      setLoading(false);
    }
  };

  // 8. Proceed to Next Question or Final Report
  const handleProceedNext = async () => {
    stopSpeaking();
    stopListening();

    if (nextBtnLabel.includes("Final Interview Performance Report")) {
      if (!interview) return;
      setLoading(true);
      try {
        const rep = await aiAPI.getReport(interview.id);
        setFinalReport(rep);
        if (interview.id) {
          if (setSelectedInterviewId) setSelectedInterviewId(interview.id);
          analysisAPI.generate(interview.id).catch(err => {
            console.warn("Background deep analysis generation (voice):", err);
          });
        }
      } catch (err: any) {
        onToast("Failed to compile final evaluation report", "error");
      } finally {
        setLoading(false);
      }
    } else {
      setUserEditedAnswer("");
      setFinalTranscript("");
      setLiveInterim("");
      setEvaluation(null);
      setAdaptiveDecision(null);
    }
  };

  // 9. Skip Question
  const handleSkip = async () => {
    if (!interview || loading || skipLoading) return;
    if (!window.confirm("Skip current question and advance to the next topic?")) return;

    stopSpeaking();
    stopListening();
    setSkipLoading(true);
    try {
      const activeQId = currentQuestion?.id;
      const res = await interviewAPI.skipQuestion(interview.id, activeQId);
      const isCompleted = Boolean(res?.interview_completed || res?.status === "completed" || (!res?.next_question && !res?.id));
      if (isCompleted) {
        onToast("Interview completed. Compiling final performance report...", "info");
        const rep = await aiAPI.getReport(interview.id);
        setFinalReport(rep);
        if (interview.id) {
          if (setSelectedInterviewId) setSelectedInterviewId(interview.id);
          analysisAPI.generate(interview.id).catch(err => {
            console.warn("Background deep analysis generation on voice skip:", err);
          });
        }
      } else {
        const nextQ = res?.next_question || res;
        setCurrentQuestion(nextQ);
        setQuestionIndex(prev => prev + 1);
        setUserEditedAnswer("");
        setFinalTranscript("");
        setLiveInterim("");
        setEvaluation(null);
        setAdaptiveDecision(null);
        onToast("Skipped to next question.", "info");
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || "Failed to skip question";
      onToast(`Skip question failed: ${detail}`, "error");
    } finally {
      setSkipLoading(false);
    }
  };

  const handleAutoFinish = async () => {
    if (!interview) return;
    onToast("Session duration reached. Compiling final performance synthesis...", "info");
    setLoading(true);
    try {
      const rep = await aiAPI.getReport(interview.id);
      setFinalReport(rep);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleExitSession = () => {
    if (window.confirm("Exit the voice interview? Any completed answers are safely preserved.")) {
      stopSpeaking();
      stopListening();
      setInterview(null);
      setCurrentQuestion(null);
      setFinalReport(null);
      setEvaluation(null);
      setAdaptiveDecision(null);
      setTrackedGaps([]);
    }
  };

  // ==========================================
  // RENDER: Final Performance Synthesis Report
  // ==========================================
  if (finalReport && interview) {
    return (
      <div className="interview-page animate-fade-in" style={{ maxWidth: '960px', margin: '0 auto' }}>
        <div className="glass-card" style={{ padding: '36px', textAlign: 'center' }}>
          <div style={{
            width: '80px',
            height: '80px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(99, 102, 241, 0.3))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px auto',
            border: '2px solid rgba(16, 185, 129, 0.4)'
          }}>
            <Award size={40} color="#10B981" />
          </div>

          <span className="badge badge-success" style={{ marginBottom: '12px', display: 'inline-block' }}>
            {finalReport.readiness_level ? `Readiness: ${finalReport.readiness_level}` : "Voice Interview Completed"}
          </span>
          <h1 style={{ fontSize: '2.2rem', marginBottom: '8px' }}>
            Performance Synthesis Report
          </h1>
          <p className="text-secondary" style={{ maxWidth: '640px', margin: '0 auto 20px auto' }}>
            {finalReport.personalized_summary}
          </p>

          {finalReport.readiness_estimate && (
            <div style={{ background: 'rgba(139, 92, 246, 0.1)', borderLeft: '3px solid #8B5CF6', padding: '12px 16px', borderRadius: '8px', textAlign: 'left', maxWidth: '720px', margin: '0 auto 28px auto', color: '#C4B5FD', fontSize: '0.9rem' }}>
              <strong>Role Readiness Assessment:</strong> {finalReport.readiness_estimate}
            </div>
          )}

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '16px',
            marginBottom: '32px'
          }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontSize: '0.85rem', color: '#9CA3AF', marginBottom: '6px' }}>Overall Readiness</div>
              <div style={{ fontSize: '2.2rem', fontWeight: '800', color: '#10B981' }}>{finalReport.overall_score}%</div>
              {finalReport.score_out_of_10 && (
                <div style={{ fontSize: '0.8rem', color: '#6EE7B7' }}>{finalReport.score_out_of_10.toFixed(1)} / 10</div>
              )}
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontSize: '0.85rem', color: '#9CA3AF', marginBottom: '6px' }}>Technical Knowledge</div>
              <div style={{ fontSize: '2.2rem', fontWeight: '800', color: '#6366F1' }}>{finalReport.technical_knowledge_score}%</div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontSize: '0.85rem', color: '#9CA3AF', marginBottom: '6px' }}>Verbal Clarity</div>
              <div style={{ fontSize: '2.2rem', fontWeight: '800', color: '#EC4899' }}>{finalReport.communication_score}%</div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontSize: '0.85rem', color: '#9CA3AF', marginBottom: '6px' }}>Problem Solving</div>
              <div style={{ fontSize: '2.2rem', fontWeight: '800', color: '#F59E0B' }}>{finalReport.problem_solving_score}%</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', textAlign: 'left', marginBottom: '32px' }}>
            <div style={{ background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '20px', borderRadius: '12px' }}>
              <h4 style={{ color: '#34D399', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <CheckCircle2 size={18} /> Demonstrated Strengths
              </h4>
              <ul style={{ paddingLeft: '20px', color: '#D1D5DB', fontSize: '0.95rem' }}>
                {finalReport.strong_topics.map((t, idx) => (
                  <li key={idx} style={{ marginBottom: '6px' }}>{t}</li>
                ))}
              </ul>
            </div>

            <div style={{ background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '20px', borderRadius: '12px' }}>
              <h4 style={{ color: '#F87171', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <AlertCircle size={18} /> High-Priority Growth Areas & Gaps
              </h4>
              <ul style={{ paddingLeft: '20px', color: '#D1D5DB', fontSize: '0.95rem' }}>
                {(finalReport.skill_gaps && finalReport.skill_gaps.length > 0 ? finalReport.skill_gaps : finalReport.weak_topics).map((t, idx) => (
                  <li key={idx} style={{ marginBottom: '6px' }}>{t}</li>
                ))}
              </ul>
            </div>
          </div>

          {finalReport.recommendations && finalReport.recommendations.length > 0 && (
            <div style={{ textAlign: 'left', background: 'rgba(255,255,255,0.02)', padding: '20px', borderRadius: '12px', marginBottom: '32px' }}>
              <h4 style={{ color: '#A78BFA', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <Sparkles size={18} /> AI Interviewer Strategic Recommendations
              </h4>
              <ul style={{ paddingLeft: '20px', color: '#D1D5DB', fontSize: '0.95rem' }}>
                {finalReport.recommendations.map((r, idx) => (
                  <li key={idx} style={{ marginBottom: '8px' }}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Question Results Breakdown */}
          {finalReport.question_results && finalReport.question_results.length > 0 && (
            <div style={{ textAlign: 'left', marginBottom: '32px' }}>
              <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.2rem' }}>
                <Award size={20} color="#8B5CF6" /> Spoken Question-by-Question Review
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
                            {qr.is_skipped ? 'Skipped' : (qr.score_out_of_10 ? `${qr.score_out_of_10.toFixed(1)}/10` : `${(qr.score || 0).toFixed(0)}%`)}
                          </span>
                          <div>
                            <span style={{ fontSize: '12px', color: '#9CA3AF', marginRight: '8px' }}>Q{qr.question_number} • {qr.topic}</span>
                            <div style={{ fontWeight: 600, fontSize: '14px', color: '#F8FAFC', marginTop: '2px' }}>{qr.question}</div>
                          </div>
                        </div>
                        <div style={{ color: '#9CA3AF', marginLeft: '12px', fontSize: '12px' }}>
                          {isExpanded ? '▲ Hide Details' : '▼ View Breakdown'}
                        </div>
                      </div>

                      {isExpanded && (
                        <div style={{ padding: '20px', borderTop: '1px solid rgba(255,255,255,0.06)', background: 'rgba(11, 15, 23, 0.95)' }}>
                          <div style={{ marginBottom: '14px' }}>
                            <span style={{ fontSize: '12px', fontWeight: 600, color: '#9CA3AF', textTransform: 'uppercase' }}>Transcribed Response:</span>
                            <p style={{ background: 'rgba(31, 41, 55, 0.4)', padding: '12px', borderRadius: '8px', fontSize: '13px', color: '#E2E8F0', marginTop: '4px', fontStyle: 'italic', lineHeight: '1.5' }}>
                              "{qr.user_answer || "No response provided"}"
                            </p>
                          </div>

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

          <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', flexWrap: 'wrap', marginTop: '24px' }}>
            <button
              className="btn btn-primary"
              onClick={() => {
                const iId = interview?.id;
                setInterview(null);
                setFinalReport(null);
                if (setSelectedInterviewId && iId) setSelectedInterviewId(iId);
                setActiveTab('analysis');
              }}
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              id="voice-btn-view-analysis"
            >
              <Sparkles size={16} /> View Deep AI Analysis
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => {
                const iId = interview?.id;
                setInterview(null);
                setFinalReport(null);
                if (setSelectedInterviewId && iId) setSelectedInterviewId(iId);
                setActiveTab('roadmap');
              }}
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              id="voice-btn-view-roadmap"
            >
              <Compass size={16} /> View Preparation Roadmap
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => {
                setInterview(null);
                setFinalReport(null);
                setActiveTab('analytics');
              }}
            >
              View Analytics Dashboard
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => {
                setInterview(null);
                setFinalReport(null);
              }}
            >
              Start New Voice Session
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ==========================================
  // RENDER: Configuration & Setup View
  // ==========================================
  if (!interview) {
    return (
      <div className="interview-page animate-fade-in" style={{ maxWidth: '900px', margin: '0 auto' }}>
        <div style={{ marginBottom: '28px', textAlign: 'center' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.25)', padding: '6px 14px', borderRadius: '20px', color: '#A5B4FC', fontSize: '0.85rem', fontWeight: '600', marginBottom: '12px' }}>
            <Mic size={14} /> AI Voice Interview Simulator
          </div>
          <h1 style={{ fontSize: '2.4rem', fontWeight: '800', marginBottom: '8px' }}>
            Interactive AI Voice Interview
          </h1>
          <p className="text-secondary" style={{ maxWidth: '600px', margin: '0 auto' }}>
            Simulate a realistic spoken interview with real-time speech recognition, natural text-to-speech feedback, and adaptive follow-up probes.
          </p>
        </div>

        <div className="glass-card">
          <form onSubmit={handleStartInterview}>
            <div className="form-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
              <div>
                <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  Target Job Role
                </label>
                <select className="form-select" value={role} onChange={e => setRole(e.target.value)}>
                  <option value="Software Developer">Software Developer</option>
                  <option value="Java Backend Engineer">Java Backend Engineer</option>
                  <option value="Full Stack Engineer">Full Stack Engineer</option>
                  <option value="Frontend Engineer">Frontend Engineer</option>
                  <option value="DevOps & Cloud Engineer">DevOps & Cloud Engineer</option>
                  <option value="Systems Architect">Systems Architect</option>
                </select>
              </div>

              <div>
                <label className="form-label">Experience Level</label>
                <select className="form-select" value={experience} onChange={e => setExperience(e.target.value)}>
                  <option value="Entry Level (0-2 Yrs)">Entry Level (0-2 Yrs)</option>
                  <option value="Intermediate (2-5 Yrs)">Intermediate (2-5 Yrs)</option>
                  <option value="Senior (5+ Yrs)">Senior (5+ Yrs)</option>
                  <option value="Lead / Staff Engineer">Lead / Staff Engineer</option>
                </select>
              </div>

              <div>
                <label className="form-label">Interview Type</label>
                <select className="form-select" value={interviewType} onChange={e => setInterviewType(e.target.value)}>
                  <option value="Technical">Technical Deep-Dive</option>
                  <option value="System Design">System Design & Architecture</option>
                  <option value="HR / Behavioral">HR & Behavioral (STAR Method)</option>
                </select>
              </div>

              <div>
                <label className="form-label">Difficulty Level</label>
                <select className="form-select" value={difficulty} onChange={e => setDifficulty(e.target.value)}>
                  <option value="Easy">Easy (Conceptual Fundamentals)</option>
                  <option value="Medium">Medium (Practical Architecture)</option>
                  <option value="Hard">Hard (Edge Cases & Concurrency)</option>
                </select>
              </div>

              <div>
                <label className="form-label">Question Count & Duration</label>
                <select className="form-select" value={totalQuestions} onChange={e => setTotalQuestions(Number(e.target.value))}>
                  <option value={3}>3 Questions (~15 Minutes)</option>
                  <option value={4}>4 Questions (~20 Minutes)</option>
                  <option value={5}>5 Questions (~25 Minutes)</option>
                  <option value={8}>8 Questions (~40 Minutes)</option>
                </select>
              </div>

              <div>
                <label className="form-label">Interviewer Voice Profile</label>
                <select className="form-select" value={selectedVoice} onChange={e => setSelectedVoice(e.target.value)}>
                  <option value="Google US English">Google US English (Professional Female)</option>
                  <option value="Microsoft David">Microsoft David (Authoritative Male)</option>
                  <option value="Microsoft Zira">Microsoft Zira (Clear Female)</option>
                </select>
              </div>
            </div>

            <div style={{ marginBottom: '24px' }}>
              <label className="form-label" style={{ marginBottom: '10px' }}>
                Technical Topics & Skills
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {topicsList.map(t => {
                  const isSelected = selectedTopics.includes(t);
                  return (
                    <button
                      key={t}
                      type="button"
                      onClick={() => toggleTopic(t)}
                      style={{
                        background: isSelected ? 'rgba(99, 102, 241, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                        border: isSelected ? '1px solid #6366F1' : '1px solid rgba(255, 255, 255, 0.1)',
                        color: isSelected ? '#A5B4FC' : '#9CA3AF',
                        padding: '8px 16px',
                        borderRadius: '20px',
                        fontSize: '0.85rem',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease'
                      }}
                    >
                      {isSelected ? '✓ ' : '+ '}{t}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Hardware Pre-flight Check */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              padding: '16px 20px',
              borderRadius: '12px',
              marginBottom: '28px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  background: micPermission === 'denied' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: micPermission === 'denied' ? '#EF4444' : '#10B981'
                }}>
                  <Mic size={18} />
                </div>
                <div>
                  <div style={{ fontSize: '0.9rem', fontWeight: '600' }}>
                    Microphone Status: {micPermission === 'granted' ? 'Ready & Verified' : micPermission === 'denied' ? 'Access Denied' : 'Browser Ready'}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#9CA3AF' }}>
                    {micPermission === 'unsupported' ? 'Web Speech API not detected. Keyboard manual input will be active.' : 'Continuous voice recognition enabled with live transcription.'}
                  </div>
                </div>
              </div>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ padding: '6px 14px', fontSize: '0.85rem' }}
                onClick={() => {
                  navigator.mediaDevices.getUserMedia({ audio: true })
                    .then(stream => {
                      setMicPermission('granted');
                      onToast("Microphone verified successfully!", "success");
                      stream.getTracks().forEach(t => t.stop());
                    })
                    .catch(() => {
                      setMicPermission('denied');
                      onToast("Microphone permission was denied in your browser settings.", "error");
                    });
                }}
              >
                Test Microphone
              </button>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '14px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setActiveTab('interview')}
              >
                Switch to Written Mode
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
                style={{ padding: '12px 28px', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                <Play size={18} /> {loading ? "Initializing AI Interviewer..." : "Launch Voice Interview Session"}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  // ==========================================
  // RENDER: Active Interactive Voice Session
  // ==========================================
  return (
    <div className="interview-page animate-fade-in" style={{ maxWidth: '1000px', margin: '0 auto' }}>
      {/* Top Session Progress Bar */}
      <div className="glass-card" style={{ padding: '16px 24px', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <span className="badge badge-primary" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Mic size={14} /> LIVE VOICE SESSION
          </span>
          <span style={{ fontWeight: '700', fontSize: '0.95rem' }}>
            Question {questionIndex} of {interview.total_questions || totalQuestions}
          </span>
          <span className="badge" style={{
            background: (currentQuestion?.difficulty || difficulty) === 'Hard' ? 'rgba(239, 68, 68, 0.2)' :
                        (currentQuestion?.difficulty || difficulty) === 'Medium' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(16, 185, 129, 0.2)',
            color: (currentQuestion?.difficulty || difficulty) === 'Hard' ? '#F87171' :
                   (currentQuestion?.difficulty || difficulty) === 'Medium' ? '#FBBF24' : '#34D399',
            fontWeight: '600'
          }}>
            {currentQuestion?.difficulty || difficulty}
          </span>
          {trackedGaps.length > 0 && (
            <span className="badge" style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#F87171', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
              {trackedGaps.length} Gaps Tracked
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* Audio Mute Toggle */}
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: '6px 12px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '6px' }}
            onClick={() => {
              if (!isMuted) stopSpeaking();
              setIsMuted(!isMuted);
            }}
            title={isMuted ? "Unmute AI Interviewer Voice" : "Mute AI Interviewer Voice"}
          >
            {isMuted ? <VolumeX size={16} color="#EF4444" /> : <Volume2 size={16} color="#10B981" />}
            <span>{isMuted ? "Muted" : "Audio On"}</span>
          </button>

          {/* Session Timer */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: timeLeft < 120 ? 'rgba(239, 68, 68, 0.15)' : 'rgba(255, 255, 255, 0.05)',
            border: timeLeft < 120 ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(255, 255, 255, 0.1)',
            padding: '6px 14px',
            borderRadius: '20px',
            fontWeight: '700',
            fontSize: '0.9rem',
            color: timeLeft < 120 ? '#EF4444' : '#F9FAFB'
          }}>
            <Clock size={16} /> {formatTime(timeLeft)}
          </div>

          {/* Pause / Resume */}
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: '6px 10px' }}
            onClick={() => setIsPaused(!isPaused)}
            title={isPaused ? "Resume Session" : "Pause Session"}
          >
            {isPaused ? <Play size={16} /> : <Pause size={16} />}
          </button>

          {/* Exit Session */}
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: '6px 10px', color: '#EF4444' }}
            onClick={handleExitSession}
            title="Exit Session"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Main Split Grid: Interviewer Left, Candidate Response Right */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.15fr', gap: '24px', alignItems: 'start' }}>
        {/* LEFT: AI Interviewer Persona Panel */}
        <div className="glass-card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '20px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '16px' }}>
            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: isSpeaking
                ? 'linear-gradient(135deg, #EC4899, #8B5CF6)'
                : 'linear-gradient(135deg, #6366F1, #3B82F6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: isSpeaking
                ? '0 0 24px rgba(236, 72, 153, 0.6)'
                : '0 0 16px rgba(99, 102, 241, 0.3)',
              transition: 'all 0.3s ease',
              animation: isSpeaking ? 'pulse 1.5s infinite' : 'none'
            }}>
              <Brain size={28} color="#FFF" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h3 style={{ fontSize: '1.1rem', margin: 0 }}>AI Technical Interviewer</h3>
                {isSpeaking && (
                  <span className="badge" style={{ background: 'rgba(236, 72, 153, 0.2)', color: '#F472B6', fontSize: '0.75rem' }}>
                    Speaking...
                  </span>
                )}
              </div>
              <span className="text-secondary" style={{ fontSize: '0.85rem' }}>
                {role} • {interviewType}
              </span>
            </div>
          </div>

          {/* Adaptive Engine Indicator */}
          {currentQuestion?.adaptive_action && currentQuestion.adaptive_action !== 'NEXT_TOPIC' && (
            <div style={{
              background: currentQuestion.adaptive_action === 'INCREASE_DIFFICULTY' ? 'rgba(16, 185, 129, 0.12)' :
                          currentQuestion.adaptive_action === 'SIMPLIFY' ? 'rgba(99, 102, 241, 0.12)' :
                          currentQuestion.adaptive_action === 'CLARIFY' ? 'rgba(245, 158, 11, 0.12)' : 'rgba(236, 72, 153, 0.12)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              padding: '10px 14px',
              borderRadius: '8px',
              marginBottom: '16px',
              color: '#F9FAFB',
              fontSize: '0.85rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '700' }}>
                <Zap size={14} color="#FBBF24" />
                <span>Adaptive Strategy: {currentQuestion.adaptive_action.replace(/_/g, ' ')}</span>
              </div>
              {currentQuestion.assessment_objective && (
                <div style={{ fontSize: '0.8rem', color: '#CBD5E1', marginTop: '4px' }}>
                  <strong>Objective:</strong> {currentQuestion.assessment_objective}
                </div>
              )}
              {currentQuestion.adaptation_reason && (
                <div style={{ fontSize: '0.8rem', color: '#94A3B8', marginTop: '2px', fontStyle: 'italic' }}>
                  {currentQuestion.adaptation_reason}
                </div>
              )}
            </div>
          )}

          {/* Follow-up Probe Alert if applicable */}
          {currentQuestion?.is_follow_up && !currentQuestion?.adaptive_action && (
            <div style={{
              background: 'rgba(245, 158, 11, 0.1)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              padding: '10px 14px',
              borderRadius: '8px',
              marginBottom: '16px',
              color: '#FBBF24',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <Sparkles size={16} />
              <span><strong>Contextual Follow-up Probe:</strong> Exploring your previous statement.</span>
            </div>
          )}

          {/* Conversational Prelude Quote */}
          {currentQuestion?.spoken_intro && (
            <div style={{
              fontStyle: 'italic',
              color: '#93C5FD',
              fontSize: '0.95rem',
              marginBottom: '12px',
              lineHeight: '1.5'
            }}>
              "{currentQuestion.spoken_intro}"
            </div>
          )}

          {/* Core Question Text */}
          <div style={{
            fontSize: '1.15rem',
            fontWeight: '600',
            lineHeight: '1.6',
            color: '#F9FAFB',
            marginBottom: '20px'
          }}>
            {currentQuestion?.question}
          </div>

          {currentQuestion?.additional_instruction && (
            <div style={{
              background: 'rgba(255, 255, 255, 0.03)',
              padding: '12px 16px',
              borderRadius: '8px',
              fontSize: '0.85rem',
              color: '#9CA3AF',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px'
            }}>
              <Lightbulb size={16} style={{ flexShrink: 0, marginTop: '2px', color: '#F59E0B' }} />
              <span>{currentQuestion.additional_instruction}</span>
            </div>
          )}

          {/* Audio Replay & Controls Bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            paddingTop: '16px'
          }}>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ padding: '8px 14px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '6px' }}
              onClick={() => {
                const text = currentQuestion?.spoken_intro
                  ? `${currentQuestion.spoken_intro} ${currentQuestion?.question}`
                  : (currentQuestion?.question || "");
                speakText(text);
              }}
              disabled={isSpeaking}
            >
              <RotateCcw size={14} /> Replay Question Aloud
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#9CA3AF' }}>
              <span>Speed:</span>
              <button
                type="button"
                style={{
                  background: speechRate === 1.0 ? 'rgba(99, 102, 241, 0.3)' : 'transparent',
                  border: 'none',
                  color: speechRate === 1.0 ? '#A5B4FC' : '#9CA3AF',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
                onClick={() => setSpeechRate(1.0)}
              >
                1.0x
              </button>
              <button
                type="button"
                style={{
                  background: speechRate === 1.15 ? 'rgba(99, 102, 241, 0.3)' : 'transparent',
                  border: 'none',
                  color: speechRate === 1.15 ? '#A5B4FC' : '#9CA3AF',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
                onClick={() => setSpeechRate(1.15)}
              >
                1.15x
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT: Candidate Spoken Response & Transcript Panel */}
        <div className="glass-card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.1rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Mic size={18} color="#6366F1" /> Your Spoken Answer
            </h3>
            <button
              type="button"
              style={{
                background: 'transparent',
                border: 'none',
                color: isManualMode ? '#10B981' : '#9CA3AF',
                fontSize: '0.8rem',
                cursor: 'pointer',
                textDecoration: 'underline'
              }}
              onClick={() => {
                if (isListening) stopListening();
                setIsManualMode(!isManualMode);
              }}
            >
              {isManualMode ? "Switch to Voice Microphone" : "Switch to Keyboard Typing"}
            </button>
          </div>

          {/* Voice Microphone Center Stage Controls */}
          {!isManualMode && (
            <div style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              padding: '24px',
              textAlign: 'center',
              marginBottom: '20px'
            }}>
              <div style={{ position: 'relative', display: 'inline-block', marginBottom: '16px' }}>
                <button
                  type="button"
                  onClick={isListening ? stopListening : startListening}
                  disabled={loading}
                  style={{
                    width: '84px',
                    height: '84px',
                    borderRadius: '50%',
                    background: isListening
                      ? 'linear-gradient(135deg, #EF4444, #F43F5E)'
                      : 'linear-gradient(135deg, #6366F1, #8B5CF6)',
                    border: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#FFF',
                    cursor: 'pointer',
                    boxShadow: isListening
                      ? '0 0 32px rgba(239, 68, 68, 0.6)'
                      : '0 0 20px rgba(99, 102, 241, 0.4)',
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
                  }}
                  title={isListening ? "Click to Finish Recording" : "Click to Start Speaking"}
                >
                  {isListening ? <MicOff size={36} /> : <Mic size={36} />}
                </button>
              </div>

              <div>
                <div style={{ fontSize: '1rem', fontWeight: '700', marginBottom: '4px' }}>
                  {isListening ? "Listening to your answer..." : userEditedAnswer ? "Answer Transcribed" : "Click Microphone to Answer"}
                </div>
                <div style={{ fontSize: '0.85rem', color: '#9CA3AF' }}>
                  {isListening
                    ? `Recording: ${formatTime(recordingSeconds)} • Speak clearly into your microphone`
                    : "Your spoken response will be transcribed live in real-time."}
                </div>
              </div>

              {/* Action Buttons while reviewing transcript */}
              {userEditedAnswer && !isListening && (
                <div style={{ display: 'flex', justifyContent: 'center', gap: '12px', marginTop: '16px' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: '6px 14px', fontSize: '0.85rem' }}
                    onClick={handleRetryRecording}
                  >
                    Clear & Retry Voice
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: '6px 14px', fontSize: '0.85rem' }}
                    onClick={startListening}
                  >
                    Continue Speaking
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Editable Live Transcript Area */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: '600', color: '#CBD5E1' }}>
                Transcript & Answer Text:
              </label>
              <span style={{ fontSize: '0.8rem', color: '#9CA3AF' }}>
                {userEditedAnswer.trim().split(/\s+/).filter(Boolean).length} words
              </span>
            </div>

            <textarea
              className="form-textarea"
              value={userEditedAnswer}
              onChange={e => setUserEditedAnswer(e.target.value)}
              placeholder={isListening ? "Listening... your words will appear here as you speak..." : "Your spoken response will appear here. You can edit, format, or add code before submitting."}
              rows={6}
              style={{
                width: '100%',
                background: 'rgba(13, 17, 23, 0.85)',
                color: '#F9FAFB',
                borderRadius: '10px',
                padding: '14px',
                border: isListening ? '1px solid #6366F1' : '1px solid rgba(255, 255, 255, 0.1)',
                fontSize: '0.95rem',
                lineHeight: '1.6',
                resize: 'vertical'
              }}
            />

            {liveInterim && (
              <div style={{
                marginTop: '6px',
                padding: '6px 10px',
                background: 'rgba(99, 102, 241, 0.1)',
                borderRadius: '6px',
                color: '#C7D2FE',
                fontSize: '0.85rem',
                fontStyle: 'italic'
              }}>
                Live: {liveInterim}...
              </div>
            )}
          </div>

          {/* Submit / Skip Action Bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}
              onClick={handleSkip}
              disabled={loading || skipLoading}
            >
              {skipLoading ? (
                <>
                  <span className="loading-spinner" style={{ width: '12px', height: '12px', marginRight: '4px' }}></span>
                  Skipping...
                </>
              ) : (
                <>
                  <Forward size={14} /> Skip Question
                </>
              )}
            </button>

            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSubmitAnswer}
              disabled={loading || skipLoading || isListening || !userEditedAnswer.trim()}
              style={{
                padding: '12px 24px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '0.95rem'
              }}
            >
              {loading ? (
                <>AI Evaluating Rubric...</>
              ) : (
                <><Send size={16} /> Submit Spoken Answer</>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Real-time Evaluation Rubric Modal / Card if evaluated */}
      {evaluation && (
        <div className="glass-card animate-fade-in" style={{ marginTop: '28px', borderLeft: '4px solid #10B981', padding: '28px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
            <div>
              <span className="badge badge-success" style={{ marginBottom: '8px', display: 'inline-block' }}>
                AI Rubric Assessment
              </span>
              <h3 style={{ fontSize: '1.4rem', margin: 0 }}>
                Answer Score: {evaluation.score}%
              </h3>
            </div>

            <button
              className="btn btn-primary"
              onClick={handleProceedNext}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 20px' }}
            >
              <span>{nextBtnLabel}</span> <ArrowRight size={16} />
            </button>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '12px',
            marginBottom: '20px'
          }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>Technical Correctness</div>
              <div style={{ fontSize: '1.2rem', fontWeight: '700', color: '#10B981' }}>{evaluation.correctness}%</div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>Conceptual Depth</div>
              <div style={{ fontSize: '1.2rem', fontWeight: '700', color: '#6366F1' }}>{evaluation.technical_depth}%</div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>Verbal Clarity</div>
              <div style={{ fontSize: '1.2rem', fontWeight: '700', color: '#EC4899' }}>{evaluation.clarity}%</div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>Completeness</div>
              <div style={{ fontSize: '1.2rem', fontWeight: '700', color: '#F59E0B' }}>{evaluation.completeness}%</div>
            </div>
          </div>

          {/* Adaptive Intelligence Engine Decision */}
          {adaptiveDecision && (
            <div style={{
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(16, 185, 129, 0.05))',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              borderRadius: '10px',
              padding: '16px 20px',
              marginBottom: '20px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Brain size={18} color="#818CF8" />
                  <span style={{ fontWeight: '700', color: '#C7D2FE', fontSize: '0.95rem' }}>
                    Adaptive Engine Strategy: {adaptiveDecision.action.replace(/_/g, ' ')}
                  </span>
                </div>
                <span className="badge" style={{
                  background: 'rgba(99, 102, 241, 0.2)',
                  color: '#A5B4FC',
                  fontWeight: '700'
                }}>
                  Difficulty: {adaptiveDecision.updated_difficulty}
                </span>
              </div>
              <p style={{ margin: '0 0 8px 0', fontSize: '0.88rem', color: '#E2E8F0', lineHeight: '1.5' }}>
                <strong>Interviewer Rationale:</strong> {adaptiveDecision.decision_rationale}
              </p>
              {adaptiveDecision.assessment_objective && (
                <div style={{ fontSize: '0.82rem', color: '#94A3B8' }}>
                  <strong>Next Objective:</strong> {adaptiveDecision.assessment_objective}
                </div>
              )}
              {adaptiveDecision.identified_knowledge_gaps && adaptiveDecision.identified_knowledge_gaps.length > 0 && (
                <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  <span style={{ fontSize: '0.78rem', color: '#F87171', fontWeight: '600' }}>Targeted Gaps:</span>
                  {adaptiveDecision.identified_knowledge_gaps.map((gap, idx) => (
                    <span key={idx} className="badge" style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#FCA5A5', fontSize: '0.75rem' }}>
                      {gap}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {evaluation.communication_notes && (
            <div style={{
              background: 'rgba(99, 102, 241, 0.08)',
              border: '1px solid rgba(99, 102, 241, 0.2)',
              padding: '12px 16px',
              borderRadius: '8px',
              marginBottom: '20px',
              fontSize: '0.9rem',
              color: '#C7D2FE'
            }}>
              <strong>Interviewer Communication Note:</strong> {evaluation.communication_notes}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
            <div style={{ background: 'rgba(16, 185, 129, 0.05)', padding: '14px', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <div style={{ color: '#34D399', fontWeight: '600', marginBottom: '6px', fontSize: '0.85rem' }}>
                Key Strengths:
              </div>
              <ul style={{ paddingLeft: '16px', fontSize: '0.85rem', color: '#D1D5DB' }}>
                {evaluation.strengths.map((s, idx) => <li key={idx}>{s}</li>)}
              </ul>
            </div>

            <div style={{ background: 'rgba(239, 68, 68, 0.05)', padding: '14px', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
              <div style={{ color: '#F87171', fontWeight: '600', marginBottom: '6px', fontSize: '0.85rem' }}>
                Areas for Improvement:
              </div>
              <ul style={{ paddingLeft: '16px', fontSize: '0.85rem', color: '#D1D5DB' }}>
                {evaluation.weaknesses.map((w, idx) => <li key={idx}>{w}</li>)}
              </ul>
            </div>
          </div>

          {evaluation.ideal_answer && (
            <details style={{ marginTop: '12px', background: 'rgba(255,255,255,0.02)', padding: '12px 16px', borderRadius: '8px' }}>
              <summary style={{ cursor: 'pointer', color: '#93C5FD', fontWeight: '600', fontSize: '0.85rem' }}>
                View Recommended Model Answer
              </summary>
              <p style={{ marginTop: '10px', fontSize: '0.9rem', color: '#E2E8F0', lineHeight: '1.6' }}>
                {evaluation.ideal_answer}
              </p>
            </details>
          )}
        </div>
      )}
    </div>
  );
};
