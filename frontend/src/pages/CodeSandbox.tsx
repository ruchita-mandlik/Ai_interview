import React, { useState } from 'react';
import { CodingEvaluationResponse } from '../types';
import { aiAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { Code, Sparkles, Bug, Lightbulb, Clock, Cpu } from 'lucide-react';

interface CodeSandboxProps {
  onToast: (msg: string, type?: string) => void;
  openAuthModal: () => void;
}

const PRESETS: Record<string, { problem: string; lang: string; code: string }> = {
  custom: {
    problem: "",
    lang: "Python",
    code: "# Type or paste custom code here..."
  },
  lru: {
    problem: "Implement Least Recently Used (LRU) cache with O(1) time complexity.",
    lang: "Python",
    code: `class LRUCache:\n    def __init__(self, capacity: int):\n        self.cap = capacity\n        self.cache = {}\n\n    def get(self, key: int) -> int:\n        if key in self.cache:\n            val = self.cache[key]\n            del self.cache[key]\n            self.cache[key] = val\n            return val\n        return -1\n\n    def put(self, key: int, value: int) -> None:\n        if key in self.cache:\n            del self.cache[key]\n        elif len(self.cache) >= self.cap:\n            oldest = next(iter(self.cache))\n            del self.cache[oldest]\n        self.cache[key] = value`
  },
  twosum: {
    problem: "Given an array of integers, return indices of two numbers that add up to target.",
    lang: "JavaScript",
    code: `function twoSum(nums, target) {\n    const map = new Map();\n    for (let i = 0; i < nums.length; i++) {\n        const diff = target - nums[i];\n        if (map.has(diff)) return [map.get(diff), i];\n        map.set(nums[i], i);\n    }\n    return [];\n}`
  }
};

export const CodeSandbox: React.FC<CodeSandboxProps> = ({ onToast, openAuthModal }) => {
  const { isAuthenticated } = useAuth();
  const [preset, setPreset] = useState("custom");
  const [problem, setProblem] = useState("");
  const [lang, setLang] = useState("Python");
  const [code, setCode] = useState("# Write code implementation...");
  const [result, setResult] = useState<CodingEvaluationResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const handlePresetChange = (val: string) => {
    setPreset(val);
    const item = PRESETS[val] || PRESETS.custom;
    setProblem(item.problem);
    setLang(item.lang);
    setCode(item.code);
  };

  const handleEvaluate = async () => {
    if (!isAuthenticated) {
      openAuthModal();
      return;
    }
    if (!code.trim()) {
      onToast("Code editor cannot be empty.", "amber");
      return;
    }

    setLoading(true);
    try {
      const res = await aiAPI.evaluateCode({
        problem_statement: problem || "General Algorithmic Solution",
        language: lang,
        code
      });
      setResult(res);
      onToast("Code evaluated successfully!", "success");
    } catch (err: any) {
      onToast(err.response?.data?.detail || "Code evaluation failed", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section>
      <div className="sandbox-container">
        <div className="glass-card">
          <h3><Code className="gradient-icon" size={20} style={{ display: 'inline', marginRight: '6px' }} /> Code Sandbox</h3>
          <p style={{ fontSize: '13px', color: '#9CA3AF', marginBottom: '16px' }}>Static analysis, complexity, & edge-case review.</p>

          <div className="form-group">
            <label>Sample Presets</label>
            <select className="form-control" value={preset} onChange={e => handlePresetChange(e.target.value)}>
              <option value="custom">Custom Snippet</option>
              <option value="lru">LRU Cache (Medium)</option>
              <option value="twosum">Two Sum (Easy)</option>
            </select>
          </div>

          <div className="form-group" style={{ marginTop: '14px' }}>
            <label>Language</label>
            <select className="form-control" value={lang} onChange={e => setLang(e.target.value)}>
              <option value="Python">Python 3</option>
              <option value="JavaScript">JavaScript</option>
              <option value="Java">Java</option>
              <option value="C++">C++</option>
            </select>
          </div>

          <div className="form-group" style={{ marginTop: '14px' }}>
            <label>Problem Objective</label>
            <textarea
              className="form-control"
              style={{ minHeight: '80px', fontSize: '13px' }}
              value={problem}
              onChange={e => setProblem(e.target.value)}
              placeholder="Describe constraints or goal..."
            />
          </div>

          <button className="btn btn-gradient btn-lg w-100" style={{ marginTop: '20px' }} onClick={handleEvaluate} disabled={loading}>
            <Sparkles size={18} /> {loading ? "Analyzing..." : "Evaluate Code with AI"}
          </button>
        </div>

        <div>
          <div className="glass-card" style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px', fontSize: '13px', fontWeight: 700 }}>
              <span>Code Editor</span>
              <span style={{ color: '#8B5CF6' }}>{lang}</span>
            </div>
            <textarea
              className="code-textarea"
              value={code}
              onChange={e => setCode(e.target.value)}
              spellCheck={false}
            />
          </div>

          {result && (
            <div className="glass-card" style={{ border: '1px solid rgba(16, 185, 129, 0.4)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h4>Diagnostic Analysis</h4>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <span style={{ background: 'rgba(31, 41, 55, 0.8)', padding: '4px 10px', borderRadius: '9999px', fontSize: '12px' }}>
                    <Clock size={12} style={{ display: 'inline', marginRight: '4px' }} /> Time: <strong>{result.time_complexity}</strong>
                  </span>
                  <span style={{ background: 'rgba(31, 41, 55, 0.8)', padding: '4px 10px', borderRadius: '9999px', fontSize: '12px' }}>
                    <Cpu size={12} style={{ display: 'inline', marginRight: '4px' }} /> Space: <strong>{result.space_complexity}</strong>
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '16px', marginBottom: '16px' }}>
                <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '12px', borderRadius: '8px', flex: 1 }}>
                  <span style={{ fontSize: '12px', color: '#6B7280' }}>Correctness</span>
                  <strong style={{ display: 'block', fontSize: '18px', color: '#10B981' }}>{result.correctness_score}/10</strong>
                </div>
                <div style={{ background: 'rgba(31, 41, 55, 0.6)', padding: '12px', borderRadius: '8px', flex: 1 }}>
                  <span style={{ fontSize: '12px', color: '#6B7280' }}>Code Quality</span>
                  <strong style={{ display: 'block', fontSize: '18px', color: '#8B5CF6' }}>{result.code_quality_score}/10</strong>
                </div>
              </div>

              <div style={{ marginBottom: '14px' }}>
                <h5 style={{ fontSize: '13px', color: '#F59E0B' }}><Bug size={14} style={{ display: 'inline', marginRight: '4px' }} /> Potential Bugs & Edge Cases</h5>
                <ul style={{ fontSize: '13px', color: '#9CA3AF', paddingLeft: '18px' }}>
                  {result.bugs_found.concat(result.missing_edge_cases).map((b, i) => <li key={i}>{b}</li>)}
                </ul>
              </div>

              <div style={{ marginBottom: '14px' }}>
                <h5 style={{ fontSize: '13px', color: '#8B5CF6' }}><Lightbulb size={14} style={{ display: 'inline', marginRight: '4px' }} /> Optimizations</h5>
                <ul style={{ fontSize: '13px', color: '#9CA3AF', paddingLeft: '18px' }}>
                  {result.optimization_suggestions.map((o, i) => <li key={i}>{o}</li>)}
                </ul>
              </div>

              <div>
                <h5 style={{ fontSize: '13px', color: '#10B981', marginBottom: '6px' }}>Refactored Code Benchmark</h5>
                <pre className="code-block">{result.ideal_code_snippet}</pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
