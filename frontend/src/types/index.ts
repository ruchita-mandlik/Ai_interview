export interface User {
  id: string;
  name: string;
  email: string;
  target_role: string;
  experience_level: string;
  preferred_topics: string[];
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Interview {
  id: string;
  user_id: string;
  role: string;
  experience_level: string;
  difficulty: string;
  interview_type: string;
  topics: string[];
  total_questions: number;
  completed_questions: number;
  overall_score: number;
  status: string;
  started_at: string;
  completed_at?: string | null;
  mode?: string;
  voice_name?: string;
  interviewer_intro?: string;
}

export interface Question {
  id: string;
  interview_id: string;
  question: string;
  topic: string;
  difficulty: string;
  question_type: string;
  expected_points: string[];
  created_at: string;
  is_follow_up?: boolean;
  parent_question_id?: string | null;
  spoken_intro?: string;
}

export interface Evaluation {
  id: string;
  answer_id: string;
  score: number;
  correctness: number;
  technical_depth: number;
  clarity: number;
  completeness: number;
  strengths: string[];
  weaknesses: string[];
  missing_points: string[];
  ideal_answer: string;
  improvement_tip: string;
  communication_notes?: string;
  evaluated_at: string;
}

export interface AnswerResponse {
  id: string;
  interview_id: string;
  question_id: string;
  user_id: string;
  answer: string;
  transcript_raw?: string;
  is_voice_submission?: boolean;
  audio_duration_seconds?: number;
  submitted_at: string;
  evaluation: Evaluation;
  next_question?: Question | null;
  follow_up_question?: Question | null;
  conversational_prelude?: string;
  interview_completed: boolean;
}

export interface PerformanceTrendPoint {
  date: string;
  score: number;
  interview_type: string;
}

export interface TopicPerformance {
  topic: string;
  score: number;
  total_questions: number;
}

export interface DifficultyPerformance {
  difficulty: string;
  score: number;
  total_questions: number;
}

export interface TypePerformance {
  interview_type: string;
  score: number;
  count: number;
}

export interface OverviewAnalyticsResponse {
  interviews_completed: number;
  average_score: number;
  best_score: number;
  questions_answered: number;
  readiness_score: number;
  readiness_explanation: string;
  strongest_topic: string;
  weakest_topic: string;
  recent_improvement: number;
  weak_topics: string[];
  performance_trend: PerformanceTrendPoint[];
  topic_performance: TopicPerformance[];
  difficulty_performance: DifficultyPerformance[];
  type_performance: TypePerformance[];
}

export interface CodingEvaluationResponse {
  correctness_score: number;
  code_quality_score: number;
  time_complexity: string;
  space_complexity: string;
  bugs_found: string[];
  edge_cases_covered: string[];
  missing_edge_cases: string[];
  optimization_suggestions: string[];
  ideal_code_snippet: string;
  summary_feedback: string;
}

export interface FinalReportResponse {
  interview_id: string;
  overall_score: number;
  technical_knowledge_score: number;
  communication_score: number;
  problem_solving_score: number;
  answer_quality_score: number;
  strong_topics: string[];
  weak_topics: string[];
  recommendations: string[];
  personalized_summary: string;
  completed_at: string;
}

export interface PreparationPlanDay {
  day: number;
  topic: string;
  concepts: string[];
  practice_questions: string[];
  difficulty: string;
  estimated_time: string;
}

export interface PreparationPlanResponse {
  user_id: string;
  created_at: string;
  plan: PreparationPlanDay[];
  overall_readiness_assessment: string;
}
