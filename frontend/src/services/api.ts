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
  PreparationPlanResponse
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
    total_questions: number;
    mode?: string;
    voice_name?: string;
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
  skipQuestion: async (interviewId: string): Promise<Question | null> => {
    const res = await api.post(`/interviews/${interviewId}/next`);
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

export default api;
