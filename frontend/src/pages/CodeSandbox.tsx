import React, { useState, useEffect, useRef } from 'react';
import {
  Code,
  Sparkles,
  Play,
  Send,
  RefreshCw,
  Copy,
  Check,
  Lightbulb,
  Clock,
  Cpu,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Terminal,
  Settings,
  PlusCircle,
  FolderOpen,
  ArrowRight,
  BookOpen
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { codingAPI } from '../services/api';
import {
  CodingInterview,
  CodingQuestion,
  TestCaseResult,
  CustomRunResult,
  CodingSubmissionResult
} from '../types';

interface CodeSandboxProps {
  onToast: (msg: string, type?: string) => void;
  openAuthModal: () => void;
}

const DEFAULT_STARTER_CODES: Record<string, string> = {
  python: `def solution(nums, target):
    # Write your solution here
    seen = {}
    for i, num in enumerate(nums):
        diff = target - num
        if diff in seen:
            return [seen[diff], i]
        seen[num] = i
    return []
`,
  javascript: `function solution(nums, target) {
    // Write your solution here
    const map = new Map();
    for (let i = 0; i < nums.length; i++) {
        const diff = target - nums[i];
        if (map.has(diff)) return [map.get(diff), i];
        map.set(nums[i], i);
    }
    return [];
}
`,
  java: `import java.util.*;

public class Solution {
    public int[] solution(int[] nums, int target) {
        // Write your solution here
        Map<Integer, Integer> map = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int comp = target - nums[i];
            if (map.containsKey(comp)) {
                return new int[]{map.get(comp), i};
            }
            map.put(nums[i], i);
        }
        return new int[]{};
    }
}
`,
  cpp: `#include <iostream>
#include <vector>
#include <unordered_map>
using namespace std;

// Write your solution here
int main() {
    // Standard I/O or solution execution
    return 0;
}
`
};

export const CodeSandbox: React.FC<CodeSandboxProps> = ({ onToast, openAuthModal }) => {
  const { isAuthenticated } = useAuth();

  // State: Interview & Question
  const [interviewsList, setInterviewsList] = useState<CodingInterview[]>([]);
  const [currentInterview, setCurrentInterview] = useState<CodingInterview | null>(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState<number>(0);
  const [loadingSession, setLoadingSession] = useState<boolean>(true);
  const [showConfigModal, setShowConfigModal] = useState<boolean>(false);

  // New Interview Form
  const [newRole, setNewRole] = useState<string>("Software Engineer");
  const [newTopic, setNewTopic] = useState<string>("Data Structures & Algorithms");
  const [newDifficulty, setNewDifficulty] = useState<string>("Medium");
  const [newLanguage, setNewLanguage] = useState<string>("python");
  const [creatingInterview, setCreatingInterview] = useState<boolean>(false);

  // Editor State
  const [language, setLanguage] = useState<string>("python");
  const [code, setCode] = useState<string>(DEFAULT_STARTER_CODES.python);
  const [fontSize, setFontSize] = useState<number>(14);
  const [copied, setCopied] = useState<boolean>(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Hints Accordion
  const [revealedHints, setRevealedHints] = useState<Record<number, boolean>>({});

  // Execution & Console Drawer
  const [activeTab, setActiveTab] = useState<'tests' | 'custom' | 'console' | 'review'>('tests');
  const [isRunningTests, setIsRunningTests] = useState<boolean>(false);
  const [isRunningCustom, setIsRunningCustom] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isGeneratingNext, setIsGeneratingNext] = useState<boolean>(false);

  const [testResults, setTestResults] = useState<TestCaseResult[]>([]);
  const [selectedTestCaseIndex, setSelectedTestCaseIndex] = useState<number>(0);
  const [customInput, setCustomInput] = useState<string>("[2, 7, 11, 15]\n9");
  const [customResult, setCustomResult] = useState<CustomRunResult | null>(null);
  const [consoleLog, setConsoleLog] = useState<string>("");
  const [submissionResult, setSubmissionResult] = useState<CodingSubmissionResult | null>(null);

  const currentQuestion: CodingQuestion | null =
    currentInterview && currentInterview.questions && currentInterview.questions.length > 0
      ? currentInterview.questions[currentQuestionIndex] || currentInterview.questions[0]
      : null;

  // Initial Load: Fetch User Coding Interviews
  useEffect(() => {
    if (!isAuthenticated) {
      setLoadingSession(false);
      return;
    }
    loadCodingInterviews();
  }, [isAuthenticated]);

  const loadCodingInterviews = async () => {
    setLoadingSession(true);
    try {
      const list = await codingAPI.list();
      setInterviewsList(list);

      // Check URL query param for interview ID
      const params = new URLSearchParams(window.location.search);
      const urlId = params.get("codingId") || params.get("id");

      let selected: CodingInterview | null = null;
      if (urlId) {
        selected = list.find(i => i.id === urlId) || null;
      }
      if (!selected && list.length > 0) {
        selected = list[0];
      }

      if (selected) {
        loadSessionDetails(selected);
      } else {
        // Automatically create a starter interview if user has none
        handleCreateInterview(false);
      }
    } catch (err: any) {
      console.warn("Failed to load coding interview list:", err);
      // Fallback
      handleCreateInterview(false);
    } finally {
      setLoadingSession(false);
    }
  };

  const loadSessionDetails = (interview: CodingInterview) => {
    setCurrentInterview(interview);
    setCurrentQuestionIndex(0);
    const lang = (interview.language || "python").toLowerCase();
    setLanguage(lang);

    const q = interview.questions && interview.questions.length > 0 ? interview.questions[0] : null;
    if (q) {
      // Check if there was an existing submission for this question
      const existingSub = interview.submissions?.find(s => s.question_id === q.id);
      if (existingSub) {
        setCode(existingSub.submitted_code);
        setSubmissionResult(existingSub);
        if (existingSub.test_case_results && existingSub.test_case_results.length > 0) {
          setTestResults(existingSub.test_case_results);
        }
      } else {
        setCode(q.starter_code || DEFAULT_STARTER_CODES[lang] || DEFAULT_STARTER_CODES.python);
        setSubmissionResult(null);
      }

      if (q.sample_test_cases && q.sample_test_cases.length > 0) {
        setCustomInput(q.sample_test_cases[0].input);
      }
    }
    setRevealedHints({});
  };

  const handleCreateInterview = async (showModalOnComplete = true) => {
    if (!isAuthenticated) {
      openAuthModal();
      return;
    }

    setCreatingInterview(true);
    try {
      const res = await codingAPI.create({
        target_role: newRole,
        experience_level: "Intermediate",
        topic: newTopic,
        difficulty: newDifficulty,
        language: newLanguage
      });
      onToast(`Created: ${res.title}`, "success");
      setCurrentInterview(res);
      setInterviewsList(prev => [res, ...prev]);
      setCurrentQuestionIndex(0);
      setLanguage(res.language || newLanguage);

      const q = res.questions[0];
      if (q) {
        setCode(q.starter_code || DEFAULT_STARTER_CODES[newLanguage] || DEFAULT_STARTER_CODES.python);
        if (q.sample_test_cases && q.sample_test_cases.length > 0) {
          setCustomInput(q.sample_test_cases[0].input);
        }
      }
      setTestResults([]);
      setSubmissionResult(null);
      setRevealedHints({});
      setShowConfigModal(false);
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Failed to create coding interview", "error");
    } finally {
      setCreatingInterview(false);
    }
  };

  // Generate Next Problem in Session
  const handleNextProblem = async () => {
    if (!currentInterview) return;
    setIsGeneratingNext(true);
    try {
      const newQ = await codingAPI.nextProblem(currentInterview.id);
      onToast(`Generated Challenge #${newQ.question_number}: ${newQ.title}`, "success");
      const updatedInterview = await codingAPI.get(currentInterview.id);
      setCurrentInterview(updatedInterview);
      const newIdx = updatedInterview.questions.findIndex(q => q.id === newQ.id);
      setCurrentQuestionIndex(newIdx >= 0 ? newIdx : updatedInterview.questions.length - 1);
      setCode(newQ.starter_code || DEFAULT_STARTER_CODES[language] || DEFAULT_STARTER_CODES.python);
      setTestResults([]);
      setSubmissionResult(null);
      setRevealedHints({});
      setActiveTab('tests');
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Failed to generate next problem", "error");
    } finally {
      setIsGeneratingNext(false);
    }
  };

  // Language Change
  const handleLanguageChange = (newLang: string) => {
    setLanguage(newLang);
    // If the code is just default starter or empty, switch to new template
    const isStarter = Object.values(DEFAULT_STARTER_CODES).some(
      s => s.trim() === code.trim()
    ) || (currentQuestion && code.trim() === currentQuestion.starter_code.trim());

    if (isStarter || !code.trim()) {
      setCode(DEFAULT_STARTER_CODES[newLang] || "# Write solution here\n");
    }
    onToast(`Language set to ${newLang.toUpperCase()}`, "info");
  };

  // Reset Code
  const handleResetCode = () => {
    if (currentQuestion?.starter_code) {
      setCode(currentQuestion.starter_code);
    } else {
      setCode(DEFAULT_STARTER_CODES[language] || "");
    }
    onToast("Code reset to starter template.", "info");
  };

  // Copy Code
  const handleCopyCode = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onToast("Code copied to clipboard!", "success");
  };

  // Handle Tab and Enter indentation in textarea
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Run tests shortcut: Ctrl+Enter or Cmd+Enter
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleRunSampleTests();
      return;
    }

    if (e.key === 'Tab') {
      e.preventDefault();
      const target = e.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const newCode = code.substring(0, start) + "    " + code.substring(end);
      setCode(newCode);
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.selectionStart = textareaRef.current.selectionEnd = start + 4;
        }
      }, 0);
    } else if (e.key === 'Enter') {
      // Auto-indentation
      const target = e.currentTarget;
      const start = target.selectionStart;
      const currentLine = code.substring(0, start).split('\n').pop() || '';
      const match = currentLine.match(/^(\s+)/);
      if (match) {
        e.preventDefault();
        const indent = match[1];
        const newCode = code.substring(0, start) + '\n' + indent + code.substring(start);
        setCode(newCode);
        setTimeout(() => {
          if (textareaRef.current) {
            textareaRef.current.selectionStart = textareaRef.current.selectionEnd = start + 1 + indent.length;
          }
        }, 0);
      }
    }
  };

  // Run Sample Tests
  const handleRunSampleTests = async () => {
    if (!isAuthenticated) {
      openAuthModal();
      return;
    }
    if (!currentQuestion) {
      onToast("No active question to test.", "amber");
      return;
    }

    setIsRunningTests(true);
    setActiveTab('tests');
    try {
      const res = await codingAPI.runTests({
        question_id: currentQuestion.id,
        language,
        code
      });

      setTestResults(res.results);
      setSelectedTestCaseIndex(0);

      const stdoutLogs = res.results.map((r, i) => `[Case #${i + 1}] Passed: ${r.passed ? 'YES' : 'NO'} | Time: ${r.execution_time_ms}ms\nOutput: ${r.actual_output}\n${r.error ? `Error: ${r.error}\n` : ''}`).join('\n');
      setConsoleLog(stdoutLogs);

      if (res.all_passed) {
        onToast(`All ${res.total_test_cases} sample test cases passed!`, "success");
      } else {
        onToast(`${res.passed_test_cases}/${res.total_test_cases} test cases passed.`, "amber");
      }
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Code execution failed", "error");
      setConsoleLog(`Execution error: ${err.message || String(err)}`);
    } finally {
      setIsRunningTests(false);
    }
  };

  // Run Custom Input
  const handleRunCustomInput = async () => {
    if (!isAuthenticated) {
      openAuthModal();
      return;
    }

    setIsRunningCustom(true);
    setActiveTab('custom');
    try {
      const res = await codingAPI.runCustom({
        code,
        language,
        custom_input: customInput
      });

      setCustomResult(res);
      setConsoleLog(`[Custom Execution] Time: ${res.execution_time_ms}ms\nOutput: ${res.actual_output}\n${res.error ? `Error: ${res.error}` : ''}`);
      onToast("Custom input executed successfully!", "info");
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Execution failed", "error");
    } finally {
      setIsRunningCustom(false);
    }
  };

  // Submit Final Solution (Runs All Tests + Gemini AI Evaluation)
  const handleFinalSubmit = async () => {
    if (!isAuthenticated) {
      openAuthModal();
      return;
    }
    if (!currentQuestion) {
      onToast("No active question to submit.", "amber");
      return;
    }

    setIsSubmitting(true);
    setActiveTab('review');
    try {
      const res = await codingAPI.submit({
        question_id: currentQuestion.id,
        language,
        code
      });

      setSubmissionResult(res);
      setTestResults(res.test_case_results || []);
      if (currentInterview) {
        currentInterview.total_score = res.coding_score;
        currentInterview.status = "completed";
      }

      onToast(`Submission evaluated! Score: ${res.coding_score}/100`, "success");
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Failed to submit code solution", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Generate line numbers for gutter
  const lineCount = (code || "").split('\n').length;
  const lineNumbers = Array.from({ length: Math.max(1, lineCount) }, (_, i) => i + 1);

  // Difficulty badge class
  const getDifficultyColor = (diff: string) => {
    const d = (diff || "Medium").toLowerCase();
    if (d === 'easy') return { bg: 'rgba(16, 185, 129, 0.2)', text: '#10B981', border: 'rgba(16, 185, 129, 0.4)' };
    if (d === 'hard') return { bg: 'rgba(239, 68, 68, 0.2)', text: '#EF4444', border: 'rgba(239, 68, 68, 0.4)' };
    return { bg: 'rgba(245, 158, 11, 0.2)', text: '#F59E0B', border: 'rgba(245, 158, 11, 0.4)' };
  };

  const diffStyle = currentQuestion ? getDifficultyColor(currentQuestion.difficulty) : getDifficultyColor("Medium");

  return (
    <div className="coding-studio-page" style={{ padding: '0 24px 32px 24px', maxWidth: '1680px', margin: '0 auto' }}>
      {/* Top Header Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 20px',
        background: 'rgba(17, 24, 39, 0.85)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '14px',
        marginBottom: '20px',
        backdropFilter: 'blur(16px)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFF'
          }}>
            <Code size={22} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: '#FFF' }}>
                {currentQuestion?.title || "AI Coding Assessment"}
              </h2>
              <span style={{
                fontSize: '11px',
                fontWeight: 800,
                padding: '3px 10px',
                borderRadius: '9999px',
                background: diffStyle.bg,
                color: diffStyle.text,
                border: `1px solid ${diffStyle.border}`
              }}>
                {currentQuestion?.difficulty || "Medium"}
              </span>
              {currentInterview?.status === 'completed' && (
                <span style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  padding: '3px 10px',
                  borderRadius: '9999px',
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#10B981',
                  border: '1px solid rgba(16, 185, 129, 0.3)'
                }}>
                  Completed • Score: {currentInterview.total_score || 0}/100
                </span>
              )}
            </div>
            <p style={{ fontSize: '12px', color: '#9CA3AF', margin: '2px 0 0 0' }}>
              Role: <strong style={{ color: '#E5E7EB' }}>{currentInterview?.target_role || "Software Engineer"}</strong> • Topic: <strong style={{ color: '#8B5CF6' }}>{currentQuestion?.skill || currentInterview?.topic || "DSA"}</strong> • Submissions Persisted in AI Readiness
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Interview Switcher Dropdown */}
          {interviewsList.length > 1 && (
            <select
              className="form-control"
              style={{ width: 'auto', fontSize: '12px', padding: '6px 12px', background: 'rgba(31, 41, 55, 0.8)' }}
              value={currentInterview?.id || ""}
              onChange={e => {
                const found = interviewsList.find(i => i.id === e.target.value);
                if (found) loadSessionDetails(found);
              }}
            >
              {interviewsList.map(intv => (
                <option key={intv.id} value={intv.id}>
                  {intv.title} ({intv.difficulty})
                </option>
              ))}
            </select>
          )}

          <button
            className="btn btn-secondary"
            style={{ fontSize: '12px', padding: '8px 14px', display: 'flex', alignItems: 'center', gap: '6px' }}
            onClick={() => setShowConfigModal(true)}
            id="btn-new-coding-session"
          >
            <PlusCircle size={15} /> New Challenge
          </button>
        </div>
      </div>

      {/* Main Split-Screen Workspace */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(380px, 1fr) minmax(500px, 1.25fr)',
        gap: '20px',
        alignItems: 'start'
      }}>
        {/* ========================================================= */}
        {/* LEFT PANEL: PROBLEM SPECIFICATION & HINTS               */}
        {/* ========================================================= */}
        <div className="glass-card" style={{ maxHeight: 'calc(100vh - 180px)', overflowY: 'auto', padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '12px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: '#8B5CF6', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Problem Description
            </span>
            <span style={{ fontSize: '12px', color: '#9CA3AF' }}>
              Question {currentQuestionIndex + 1} of {currentInterview?.questions.length || 1}
            </span>
          </div>

          {loadingSession ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#9CA3AF' }}>
              <RefreshCw size={24} className="spinning-icon" style={{ margin: '0 auto 12px auto' }} />
              <p>Generating dynamic DSA challenge via Gemini API...</p>
            </div>
          ) : currentQuestion ? (
            <div>
              {/* Problem Description */}
              <div style={{
                fontSize: '14px',
                color: '#E5E7EB',
                lineHeight: '1.7',
                whiteSpace: 'pre-line',
                marginBottom: '20px'
              }}>
                {currentQuestion.description}
              </div>

              {/* Input & Output Specifications */}
              {currentQuestion.input_format && (
                <div style={{ marginBottom: '16px' }}>
                  <h4 style={{ fontSize: '12px', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', marginBottom: '6px' }}>
                    Input Format
                  </h4>
                  <div style={{ background: 'rgba(31, 41, 55, 0.5)', padding: '10px 14px', borderRadius: '8px', fontSize: '13px', color: '#D1D5DB' }}>
                    {currentQuestion.input_format}
                  </div>
                </div>
              )}

              {currentQuestion.output_format && (
                <div style={{ marginBottom: '16px' }}>
                  <h4 style={{ fontSize: '12px', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', marginBottom: '6px' }}>
                    Output Format
                  </h4>
                  <div style={{ background: 'rgba(31, 41, 55, 0.5)', padding: '10px 14px', borderRadius: '8px', fontSize: '13px', color: '#D1D5DB' }}>
                    {currentQuestion.output_format}
                  </div>
                </div>
              )}

              {/* Constraints Box */}
              {currentQuestion.constraints && (
                <div style={{ marginBottom: '20px' }}>
                  <h4 style={{ fontSize: '12px', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', marginBottom: '6px' }}>
                    Constraints & Complexity Target
                  </h4>
                  <div style={{
                    fontFamily: 'var(--font-code)',
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: '#38BDF8',
                    lineHeight: '1.5'
                  }}>
                    {currentQuestion.constraints}
                  </div>
                </div>
              )}

              {/* Sample Test Cases */}
              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ fontSize: '12px', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', marginBottom: '10px' }}>
                  Sample Test Cases
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {currentQuestion.sample_test_cases?.map((tc, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: 'rgba(31, 41, 55, 0.4)',
                        border: '1px solid rgba(255, 255, 255, 0.06)',
                        borderRadius: '8px',
                        padding: '12px'
                      }}
                    >
                      <div style={{ fontSize: '12px', fontWeight: 700, color: '#8B5CF6', marginBottom: '6px' }}>
                        Example {idx + 1}
                      </div>
                      <div style={{ fontSize: '12px', marginBottom: '4px' }}>
                        <span style={{ color: '#9CA3AF' }}>Input: </span>
                        <code style={{ background: 'rgba(0,0,0,0.3)', padding: '2px 6px', borderRadius: '4px', color: '#38BDF8' }}>
                          {tc.input}
                        </code>
                      </div>
                      <div style={{ fontSize: '12px', marginBottom: tc.explanation ? '4px' : '0' }}>
                        <span style={{ color: '#9CA3AF' }}>Output: </span>
                        <code style={{ background: 'rgba(0,0,0,0.3)', padding: '2px 6px', borderRadius: '4px', color: '#10B981' }}>
                          {tc.expected_output}
                        </code>
                      </div>
                      {tc.explanation && (
                        <div style={{ fontSize: '12px', color: '#9CA3AF', marginTop: '4px' }}>
                          <span>Explanation: {tc.explanation}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Progressive Hints Accordion (Optional, Doesn't Reveal Solution) */}
              {currentQuestion.hints && currentQuestion.hints.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <h4 style={{ fontSize: '12px', fontWeight: 700, color: '#F59E0B', textTransform: 'uppercase', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Lightbulb size={14} /> Progressive Conceptual Hints
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {currentQuestion.hints.map((hintText, hIdx) => {
                      const isRevealed = revealedHints[hIdx];
                      return (
                        <div
                          key={hIdx}
                          style={{
                            background: 'rgba(245, 158, 11, 0.05)',
                            border: '1px solid rgba(245, 158, 11, 0.2)',
                            borderRadius: '8px',
                            overflow: 'hidden'
                          }}
                        >
                          <button
                            style={{
                              width: '100%',
                              padding: '10px 14px',
                              background: 'transparent',
                              border: 'none',
                              color: '#FCD34D',
                              fontSize: '12px',
                              fontWeight: 700,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              cursor: 'pointer'
                            }}
                            onClick={() => setRevealedHints(prev => ({ ...prev, [hIdx]: !prev[hIdx] }))}
                          >
                            <span>💡 Hint {hIdx + 1} {isRevealed ? "" : "(Click to Reveal Insight)"}</span>
                            {isRevealed ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </button>
                          {isRevealed && (
                            <div style={{ padding: '10px 14px', borderTop: '1px solid rgba(245, 158, 11, 0.15)', fontSize: '13px', color: '#F3F4F6', lineHeight: '1.5' }}>
                              {hintText}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Next Sequential Question Button */}
              <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '16px', display: 'flex', justifyContent: 'space-between' }}>
                <button
                  className="btn btn-secondary"
                  style={{ fontSize: '12px', padding: '8px 14px' }}
                  onClick={handleNextProblem}
                  disabled={isGeneratingNext}
                >
                  {isGeneratingNext ? (
                    <><RefreshCw size={14} className="spinning-icon" /> Generating Challenge...</>
                  ) : (
                    <><Sparkles size={14} /> Generate Next Problem</>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#9CA3AF' }}>
              <p>No coding assessment loaded.</p>
              <button className="btn btn-primary" onClick={() => setShowConfigModal(true)} style={{ marginTop: '12px' }}>
                Start Coding Interview
              </button>
            </div>
          )}
        </div>

        {/* ========================================================= */}
        {/* RIGHT PANEL: SPLIT-SCREEN IDE & EXECUTION CONSOLE        */}
        {/* ========================================================= */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Editor Header Toolbar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 18px',
            background: 'rgba(17, 24, 39, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '12px 12px 0 0',
            borderBottom: 'none'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '12px', color: '#9CA3AF', fontWeight: 600 }}>Language:</span>
              <select
                className="form-control"
                style={{ width: 'auto', fontSize: '13px', padding: '6px 12px', fontWeight: 700 }}
                value={language}
                onChange={e => handleLanguageChange(e.target.value)}
                id="select-editor-language"
              >
                <option value="python">Python 3 (CPython 3.12)</option>
                <option value="javascript">JavaScript (Node.js 24)</option>
                <option value="java">Java (JDK 17 javac)</option>
                <option value="cpp">C++ (g++ C++17)</option>
              </select>

              <span style={{ fontSize: '11px', color: '#6B7280', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Clock size={12} /> Limit: 3.0s / 256MB
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                style={{
                  background: 'transparent',
                  border: '1px solid rgba(255,255,255,0.1)',
                  color: '#9CA3AF',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  fontSize: '11px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
                onClick={handleCopyCode}
                title="Copy Code to Clipboard"
              >
                {copied ? <Check size={13} color="#10B981" /> : <Copy size={13} />}
                {copied ? "Copied" : "Copy"}
              </button>

              <button
                style={{
                  background: 'transparent',
                  border: '1px solid rgba(255,255,255,0.1)',
                  color: '#9CA3AF',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  fontSize: '11px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
                onClick={handleResetCode}
                title="Reset to Starter Template"
              >
                <RefreshCw size={13} /> Reset
              </button>
            </div>
          </div>

          {/* Interactive Code Editor with Line Numbers Gutter */}
          <div style={{
            position: 'relative',
            background: '#0F172A',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderTop: 'none',
            borderRadius: '0 0 12px 12px',
            overflow: 'hidden',
            display: 'flex'
          }}>
            {/* Line Numbers Column */}
            <div style={{
              width: '46px',
              padding: '16px 0',
              background: '#0B0F19',
              borderRight: '1px solid rgba(255, 255, 255, 0.05)',
              userSelect: 'none',
              textAlign: 'right',
              paddingRight: '10px',
              fontFamily: 'var(--font-code)',
              fontSize: `${fontSize}px`,
              lineHeight: '1.6',
              color: '#475569'
            }}>
              {lineNumbers.map(n => (
                <div key={n}>{n}</div>
              ))}
            </div>

            {/* Code Textarea */}
            <textarea
              ref={textareaRef}
              value={code}
              onChange={e => setCode(e.target.value)}
              onKeyDown={handleKeyDown}
              spellCheck={false}
              style={{
                flex: 1,
                minHeight: '380px',
                padding: '16px 18px',
                background: 'transparent',
                border: 'none',
                outline: 'none',
                resize: 'vertical',
                color: '#F8FAFC',
                fontFamily: 'var(--font-code)',
                fontSize: `${fontSize}px`,
                lineHeight: '1.6',
                whiteSpace: 'pre',
                overflowX: 'auto',
                tabSize: 4
              }}
              placeholder="// Write your algorithm solution here..."
              id="code-editor-textarea"
            />
          </div>

          {/* Execution Drawer Tabs & Output Console */}
          <div className="glass-card" style={{ padding: '16px 20px', marginTop: '4px' }}>
            {/* Drawer Tab Headers */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid rgba(255,255,255,0.08)',
              paddingBottom: '10px',
              marginBottom: '14px'
            }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  className={`tab-btn ${activeTab === 'tests' ? 'active' : ''}`}
                  onClick={() => setActiveTab('tests')}
                  style={{ padding: '6px 14px', fontSize: '12px' }}
                >
                  <CheckCircle2 size={14} /> Test Cases ({testResults.length})
                </button>
                <button
                  className={`tab-btn ${activeTab === 'custom' ? 'active' : ''}`}
                  onClick={() => setActiveTab('custom')}
                  style={{ padding: '6px 14px', fontSize: '12px' }}
                >
                  <Terminal size={14} /> Custom Input
                </button>
                <button
                  className={`tab-btn ${activeTab === 'console' ? 'active' : ''}`}
                  onClick={() => setActiveTab('console')}
                  style={{ padding: '6px 14px', fontSize: '12px' }}
                >
                  <Terminal size={14} /> Raw Console
                </button>
                {submissionResult && (
                  <button
                    className={`tab-btn ${activeTab === 'review' ? 'active' : ''}`}
                    onClick={() => setActiveTab('review')}
                    style={{
                      padding: '6px 14px',
                      fontSize: '12px',
                      background: 'rgba(16, 185, 129, 0.15)',
                      color: '#10B981',
                      borderColor: 'rgba(16, 185, 129, 0.4)'
                    }}
                  >
                    <Sparkles size={14} /> AI Diagnostic ({submissionResult.coding_score}/100)
                  </button>
                )}
              </div>

              {/* Action Buttons: Run Code / Submit */}
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  className="btn btn-secondary"
                  style={{ fontSize: '13px', padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
                  onClick={handleRunSampleTests}
                  disabled={isRunningTests || isSubmitting}
                  id="btn-run-code"
                >
                  {isRunningTests ? (
                    <><RefreshCw size={14} className="spinning-icon" /> Running...</>
                  ) : (
                    <><Play size={14} color="#10B981" /> Run Code (Ctrl+Enter)</>
                  )}
                </button>

                <button
                  className="btn btn-gradient"
                  style={{ fontSize: '13px', padding: '8px 20px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 800 }}
                  onClick={handleFinalSubmit}
                  disabled={isSubmitting || isRunningTests}
                  id="btn-submit-solution"
                >
                  {isSubmitting ? (
                    <><RefreshCw size={14} className="spinning-icon" /> Evaluating...</>
                  ) : (
                    <><Send size={14} /> Submit Final Solution</>
                  )}
                </button>
              </div>
            </div>

            {/* TAB CONTENT 1: TEST CASES RESULTS */}
            {activeTab === 'tests' && (
              <div>
                {testResults.length === 0 ? (
                  <div style={{ padding: '24px 0', textAlign: 'center', color: '#9CA3AF', fontSize: '13px' }}>
                    Click <strong>"Run Code"</strong> to execute your code in an isolated sandbox against sample test cases.
                  </div>
                ) : (
                  <div>
                    {/* Test Case Pills */}
                    <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
                      {testResults.map((tc, idx) => (
                        <button
                          key={idx}
                          onClick={() => setSelectedTestCaseIndex(idx)}
                          style={{
                            padding: '6px 14px',
                            borderRadius: '8px',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            background: selectedTestCaseIndex === idx ? 'rgba(255,255,255,0.1)' : 'rgba(31, 41, 55, 0.4)',
                            border: selectedTestCaseIndex === idx ? '1px solid #8B5CF6' : '1px solid rgba(255,255,255,0.06)',
                            color: tc.passed ? '#10B981' : '#EF4444'
                          }}
                        >
                          {tc.passed ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                          Case {idx + 1} ({tc.execution_time_ms}ms)
                        </button>
                      ))}
                    </div>

                    {/* Selected Test Case Details */}
                    {testResults[selectedTestCaseIndex] && (
                      <div style={{
                        background: 'rgba(15, 23, 42, 0.6)',
                        padding: '14px',
                        borderRadius: '8px',
                        border: '1px solid rgba(255, 255, 255, 0.05)',
                        fontFamily: 'var(--font-code)',
                        fontSize: '12px'
                      }}>
                        <div style={{ marginBottom: '8px' }}>
                          <span style={{ color: '#9CA3AF' }}>Input: </span>
                          <div style={{ background: '#0B0F19', padding: '6px 10px', borderRadius: '4px', marginTop: '4px', color: '#38BDF8' }}>
                            {testResults[selectedTestCaseIndex].input}
                          </div>
                        </div>
                        <div style={{ marginBottom: '8px' }}>
                          <span style={{ color: '#9CA3AF' }}>Expected Output: </span>
                          <div style={{ background: '#0B0F19', padding: '6px 10px', borderRadius: '4px', marginTop: '4px', color: '#10B981' }}>
                            {testResults[selectedTestCaseIndex].expected_output}
                          </div>
                        </div>
                        <div style={{ marginBottom: '8px' }}>
                          <span style={{ color: '#9CA3AF' }}>Actual Output: </span>
                          <div style={{
                            background: '#0B0F19',
                            padding: '6px 10px',
                            borderRadius: '4px',
                            marginTop: '4px',
                            color: testResults[selectedTestCaseIndex].passed ? '#10B981' : '#EF4444'
                          }}>
                            {testResults[selectedTestCaseIndex].actual_output || "(Empty output)"}
                          </div>
                        </div>
                        {testResults[selectedTestCaseIndex].error && (
                          <div>
                            <span style={{ color: '#EF4444', fontWeight: 700 }}>Diagnostics / Traceback: </span>
                            <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '8px 10px', borderRadius: '4px', marginTop: '4px', color: '#FCA5A5', whiteSpace: 'pre-wrap' }}>
                              {testResults[selectedTestCaseIndex].error}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* TAB CONTENT 2: CUSTOM INPUT */}
            {activeTab === 'custom' && (
              <div>
                <div style={{ marginBottom: '12px' }}>
                  <label style={{ fontSize: '12px', color: '#9CA3AF', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
                    Provide Custom Input (Piped to standard execution input / arguments):
                  </label>
                  <textarea
                    className="form-control"
                    style={{ minHeight: '80px', fontFamily: 'var(--font-code)', fontSize: '13px' }}
                    value={customInput}
                    onChange={e => setCustomInput(e.target.value)}
                    placeholder="Enter input string or JSON..."
                  />
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '14px' }}>
                  <button
                    className="btn btn-secondary"
                    style={{ fontSize: '12px', padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '6px' }}
                    onClick={handleRunCustomInput}
                    disabled={isRunningCustom}
                  >
                    <Play size={13} color="#38BDF8" /> {isRunningCustom ? "Executing..." : "Run with Custom Input"}
                  </button>
                </div>

                {customResult && (
                  <div style={{
                    background: 'rgba(15, 23, 42, 0.8)',
                    padding: '12px',
                    borderRadius: '8px',
                    fontFamily: 'var(--font-code)',
                    fontSize: '12px'
                  }}>
                    <div style={{ color: '#9CA3AF', marginBottom: '4px' }}>
                      Execution Result ({customResult.execution_time_ms}ms):
                    </div>
                    <div style={{ background: '#0B0F19', padding: '8px 12px', borderRadius: '4px', color: '#38BDF8', whiteSpace: 'pre-wrap' }}>
                      {customResult.actual_output || "(No return output)"}
                    </div>
                    {customResult.error && (
                      <div style={{ marginTop: '8px', color: '#EF4444', whiteSpace: 'pre-wrap' }}>
                        Error: {customResult.error}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* TAB CONTENT 3: RAW CONSOLE LOG */}
            {activeTab === 'console' && (
              <div style={{
                background: '#0B0F19',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                padding: '14px',
                borderRadius: '8px',
                fontFamily: 'var(--font-code)',
                fontSize: '12px',
                color: '#CBD5E1',
                minHeight: '120px',
                whiteSpace: 'pre-wrap'
              }}>
                {consoleLog || "Console is idle. Click 'Run Code' or 'Submit Final Solution' to view execution output."}
              </div>
            )}

            {/* TAB CONTENT 4: AI REVIEW & DIAGNOSTIC */}
            {activeTab === 'review' && submissionResult && (
              <div style={{
                background: 'rgba(17, 24, 39, 0.7)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                padding: '18px',
                borderRadius: '10px'
              }}>
                {/* Metric Summary Cards */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: '12px',
                  marginBottom: '16px'
                }}>
                  <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '11px', color: '#9CA3AF' }}>Overall Score</div>
                    <div style={{ fontSize: '22px', fontWeight: 800, color: '#10B981' }}>{submissionResult.coding_score}/100</div>
                  </div>
                  <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '11px', color: '#9CA3AF' }}>Correctness</div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#38BDF8' }}>{submissionResult.correctness_score}%</div>
                  </div>
                  <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '11px', color: '#9CA3AF' }}>Time Complexity</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, color: '#F59E0B' }}>{submissionResult.time_complexity}</div>
                  </div>
                  <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '11px', color: '#9CA3AF' }}>Space Complexity</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, color: '#8B5CF6' }}>{submissionResult.space_complexity}</div>
                  </div>
                </div>

                {/* AI Review Text */}
                <div style={{ marginBottom: '14px', fontSize: '13px', color: '#E5E7EB', lineHeight: '1.6' }}>
                  <p><strong>Evaluation Summary:</strong> {submissionResult.code_review}</p>
                </div>

                {/* Strengths & Mistakes Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                  {submissionResult.strengths?.length > 0 && (
                    <div style={{ background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '12px', borderRadius: '8px' }}>
                      <h5 style={{ fontSize: '12px', color: '#10B981', fontWeight: 700, marginBottom: '6px' }}>Key Strengths</h5>
                      <ul style={{ fontSize: '12px', color: '#D1D5DB', paddingLeft: '16px', margin: 0 }}>
                        {submissionResult.strengths.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                  )}

                  {submissionResult.detected_mistakes?.length > 0 && (
                    <div style={{ background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '12px', borderRadius: '8px' }}>
                      <h5 style={{ fontSize: '12px', color: '#EF4444', fontWeight: 700, marginBottom: '6px' }}>Mistakes & Edge Cases</h5>
                      <ul style={{ fontSize: '12px', color: '#D1D5DB', paddingLeft: '16px', margin: 0 }}>
                        {submissionResult.detected_mistakes.map((m, i) => <li key={i}>{m}</li>)}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Optimization Suggestions */}
                {submissionResult.optimization_suggestions?.length > 0 && (
                  <div style={{ marginBottom: '14px', background: 'rgba(139, 92, 246, 0.05)', border: '1px solid rgba(139, 92, 246, 0.2)', padding: '12px', borderRadius: '8px' }}>
                    <h5 style={{ fontSize: '12px', color: '#8B5CF6', fontWeight: 700, marginBottom: '6px' }}>Recommended Optimizations</h5>
                    <ul style={{ fontSize: '12px', color: '#D1D5DB', paddingLeft: '16px', margin: 0 }}>
                      {submissionResult.optimization_suggestions.map((o, i) => <li key={i}>{o}</li>)}
                    </ul>
                  </div>
                )}

                {/* Model Reference Solution */}
                {submissionResult.model_solution && (
                  <div>
                    <h5 style={{ fontSize: '12px', color: '#9CA3AF', fontWeight: 700, marginBottom: '6px' }}>Optimal Reference Solution</h5>
                    <pre style={{
                      background: '#0B0F19',
                      padding: '12px',
                      borderRadius: '8px',
                      fontFamily: 'var(--font-code)',
                      fontSize: '12px',
                      color: '#38BDF8',
                      overflowX: 'auto'
                    }}>
                      {submissionResult.model_solution}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ========================================================= */}
      {/* MODAL: NEW CODING CHALLENGE CONFIGURATION                */}
      {/* ========================================================= */}
      {showConfigModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div className="glass-card" style={{ width: '100%', maxWidth: '480px', padding: '28px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: '#FFF' }}>
                New Coding Interview Assessment
              </h3>
              <button
                onClick={() => setShowConfigModal(false)}
                style={{ background: 'transparent', border: 'none', color: '#9CA3AF', cursor: 'pointer', fontSize: '18px' }}
              >
                ✕
              </button>
            </div>

            <div className="form-group" style={{ marginBottom: '14px' }}>
              <label>Target Role</label>
              <input
                type="text"
                className="form-control"
                value={newRole}
                onChange={e => setNewRole(e.target.value)}
                placeholder="e.g. Software Engineer, Backend Developer"
              />
            </div>

            <div className="form-group" style={{ marginBottom: '14px' }}>
              <label>Topic / Algorithmic Focus</label>
              <select className="form-control" value={newTopic} onChange={e => setNewTopic(e.target.value)}>
                <option value="Data Structures & Algorithms">Data Structures & Algorithms (General)</option>
                <option value="Arrays & Hash Table">Arrays & Hash Table</option>
                <option value="Strings & Two Pointers">Strings & Two Pointers</option>
                <option value="Dynamic Programming">Dynamic Programming</option>
                <option value="Binary Search & Sorting">Binary Search & Sorting</option>
                <option value="Trees & Graphs">Trees & Graphs</option>
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: '14px' }}>
              <label>Difficulty</label>
              <select className="form-control" value={newDifficulty} onChange={e => setNewDifficulty(e.target.value)}>
                <option value="Easy">Easy (Fundamental DSA)</option>
                <option value="Medium">Medium (Standard Industry)</option>
                <option value="Hard">Hard (Advanced Competitive)</option>
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: '20px' }}>
              <label>Primary Language</label>
              <select className="form-control" value={newLanguage} onChange={e => setNewLanguage(e.target.value)}>
                <option value="python">Python 3</option>
                <option value="javascript">JavaScript (Node.js)</option>
                <option value="java">Java (JDK 17)</option>
                <option value="cpp">C++ (g++)</option>
              </select>
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                className="btn btn-secondary w-50"
                onClick={() => setShowConfigModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-gradient w-50"
                onClick={() => handleCreateInterview(true)}
                disabled={creatingInterview}
              >
                {creatingInterview ? <RefreshCw size={15} className="spinning-icon" /> : <Sparkles size={15} />} Generate Assessment
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
