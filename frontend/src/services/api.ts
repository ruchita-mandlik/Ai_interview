import axios from 'axios';
import {
  TokenResponse,
  User,
  Interview,
  Question,
  AnswerResponse,
  OverviewAnalyticsResponse,
  CodingEvaluationResponse,
  FinalReportResponse,
  PreparationPlanResponse,
  DeepAnalysisRoadmapResponse,
  CodingInterview,
  CodingQuestion,
  CodeRunResult,
  CustomRunResult,
  CodingSubmissionResult,
  CodingInterviewCreateRequest
} from '../types';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json'
  }
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authAPI = {
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const res = await api.post('/auth/login', { email, password });
    return res.data;
  },
  register: async (payload: { name: string; email: string; password: string; target_role?: string; experience_level?: string }): Promise<TokenResponse> => {
    const res = await api.post('/auth/register', payload);
    return res.data;
  },
  getMe: async (): Promise<User> => {
    const res = await api.get('/auth/me');
    return res.data;
  }
};

export const userAPI = {
  getProfile: async (): Promise<User> => {
    const res = await api.get('/users/profile');
    return res.data;
  },
  updateProfile: async (payload: Partial<User>): Promise<User> => {
    const res = await api.put('/users/profile', payload);
    return res.data;
  }
};

export const interviewAPI = {
  create: async (payload: {
    role: string;
    experience_level: string;
    difficulty: string;
    interview_type: string;
    topics: string[];
    skills?: string[];
    total_questions: number;
    job_description?: string;
    resume_text?: string;
    additional_instructions?: string;
    mode?: string;
    voice_name?: string;
    is_adaptive?: boolean;
  }): Promise<{ interview: Interview; first_question: Question; interviewer_intro?: string }> => {
    const res = await api.post('/interviews', payload);
    return res.data;
  },
  list: async (): Promise<Interview[]> => {
    const res = await api.get('/interviews');
    return res.data;
  },
  getDetail: async (interviewId: string) => {
    const res = await api.get(`/interviews/${interviewId}`);
    return res.data;
  },
  get: async (interviewId: string) => {
    const res = await api.get(`/interviews/${interviewId}`);
    return res.data;
  },
  askClarification: async (
    interviewId: string,
    questionId: string,
    query: string
  ): Promise<{ clarification: string; hint?: string; topic?: string }> => {
    const res = await api.post(`/interviews/${interviewId}/clarify`, { question_id: questionId, query });
    return res.data;
  },
  submitAnswer: async (
    interviewId: string,
    questionId: string,
    answer: string,
    voiceMeta?: { transcript_raw?: string; is_voice_submission?: boolean; audio_duration_seconds?: number }
  ): Promise<AnswerResponse> => {
    const payload = {
      answer,
      ...(voiceMeta || {})
    };
    const res = await api.post(`/interviews/${interviewId}/answer?question_id=${questionId}`, payload);
    return res.data;
  },
  skipQuestion: async (interviewId: string, questionId?: string): Promise<any> => {
    const url = questionId ? `/interviews/${interviewId}/next?question_id=${encodeURIComponent(questionId)}` : `/interviews/${interviewId}/next`;
    const res = await api.post(url);
    return res.data;
  },
  complete: async (interviewId: string) => {
    const res = await api.post(`/interviews/${interviewId}/complete`);
    return res.data;
  }
};

export const voiceAPI = {
  getConfig: async () => {
    const res = await api.get('/voice/config');
    return res.data;
  },
  transcribeAudio: async (audioBlob: Blob) => {
    const formData = new FormData();
    formData.append('file', audioBlob, 'candidate_voice.webm');
    const res = await api.post('/voice/transcribe', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  }
};

export const analyticsAPI = {
  getOverview: async (): Promise<OverviewAnalyticsResponse> => {
    const res = await api.get('/analytics/overview');
    return res.data;
  }
};

export const aiAPI = {
  evaluateCode: async (payload: {
    problem_statement: string;
    language: string;
    code: string;
    difficulty?: string;
    topic?: string;
  }): Promise<CodingEvaluationResponse> => {
    const res = await api.post('/ai/evaluate-code', payload);
    return res.data;
  },
  getReport: async (interviewId: string): Promise<FinalReportResponse> => {
    const res = await api.get(`/ai/report/${interviewId}`);
    return res.data;
  }
};

export const recommendationAPI = {
  getPlan: async (): Promise<PreparationPlanResponse> => {
    const res = await api.get('/recommendations/plan');
    return res.data;
  }
};

export const analysisAPI = {
  generate: async (
    interviewId: string,
    params?: { force_refresh?: boolean; target_interview_date?: string; daily_study_hours?: number }
  ): Promise<DeepAnalysisRoadmapResponse> => {
    const query = new URLSearchParams();
    if (params?.force_refresh) query.append('force_refresh', 'true');
    if (params?.target_interview_date) query.append('target_interview_date', params.target_interview_date);
    if (params?.daily_study_hours) query.append('daily_study_hours', params.daily_study_hours.toString());
    const qs = query.toString() ? `?${query.toString()}` : '';
    const res = await api.post(`/analysis/${interviewId}/generate${qs}`);
    return res.data;
  },
  getLatest: async (): Promise<DeepAnalysisRoadmapResponse> => {
    const res = await api.get('/analysis/latest');
    return res.data;
  },
  listAll: async (): Promise<DeepAnalysisRoadmapResponse[]> => {
    const res = await api.get('/analysis/list/all');
    return res.data;
  },
  getByInterviewId: async (interviewId: string): Promise<DeepAnalysisRoadmapResponse> => {
    const res = await api.get(`/analysis/${interviewId}`);
    return res.data;
  },
  updateTaskStatus: async (
    analysisId: string,
    taskId: string,
    status: 'pending' | 'in_progress' | 'completed' | string
  ): Promise<DeepAnalysisRoadmapResponse> => {
    const res = await api.patch(`/analysis/${analysisId}/task/${taskId}`, { status });
    return res.data;
  },
  updatePreferences: async (
    analysisId: string,
    prefs: { target_interview_date?: string; daily_study_hours?: number }
  ): Promise<DeepAnalysisRoadmapResponse> => {
    const res = await api.patch(`/analysis/${analysisId}/preferences`, prefs);
    return res.data;
  }
};

export const readinessAPI = {
  get: async (): Promise<any> => {
    const res = await api.get('/readiness');
    return res.data;
  },
  recalculate: async (targetRole?: string): Promise<any> => {
    const qs = targetRole ? `?target_role=${encodeURIComponent(targetRole)}` : '';
    const res = await api.post(`/readiness/recalculate${qs}`);
    return res.data;
  },
  getHistory: async (): Promise<any[]> => {
    const res = await api.get('/readiness/history');
    return res.data;
  }
};

export const codingAPI = {
  create: async (data: CodingInterviewCreateRequest): Promise<CodingInterview> => {
    const res = await api.post('/coding/start', data);
    return res.data;
  },
  get: async (interviewId: string): Promise<CodingInterview> => {
    const res = await api.get(`/coding/${interviewId}`);
    return res.data;
  },
  list: async (): Promise<CodingInterview[]> => {
    const res = await api.get('/coding/list');
    return res.data;
  },
  nextProblem: async (interviewId: string): Promise<CodingQuestion> => {
    const res = await api.post(`/coding/${interviewId}/next`);
    return res.data;
  },
  runTests: async (data: { question_id: string; language: string; code: string; custom_input?: string }): Promise<CodeRunResult> => {
    const res = await api.post('/coding/run-tests', data);
    return res.data;
  },
  runCustom: async (data: { code: string; language: string; custom_input: string }): Promise<CustomRunResult> => {
    const res = await api.post('/coding/run-custom', data);
    return res.data;
  },
  submit: async (data: { question_id: string; language: string; code: string }): Promise<CodingSubmissionResult> => {
    const res = await api.post('/coding/submit', data);
    return res.data;
  },
  getResults: async (interviewId: string): Promise<CodingSubmissionResult> => {
    const res = await api.get(`/coding/${interviewId}/results`);
    return res.data;
  }
};

export const intelligenceAPI = {
  getMemorySummary: async (): Promise<any> => {
    const res = await api.get('/intelligence/memory-summary');
    return res.data;
  },
  getSessionComparison: async (interviewId: string): Promise<any> => {
    const res = await api.get(`/intelligence/session-comparison/${interviewId}`);
    return res.data;
  },
  getAnalyticsDashboard: async (params?: { date_from?: string; date_to?: string; session_a_id?: string; session_b_id?: string }): Promise<any> => {
    const qs = new URLSearchParams();
    if (params?.date_from) qs.set('date_from', params.date_from);
    if (params?.date_to) qs.set('date_to', params.date_to);
    if (params?.session_a_id) qs.set('session_a_id', params.session_a_id);
    if (params?.session_b_id) qs.set('session_b_id', params.session_b_id);
    const qsStr = qs.toString();
    const res = await api.get(`/intelligence/analytics-dashboard${qsStr ? '?' + qsStr : ''}`);
    return res.data;
  }
};

export default api;


