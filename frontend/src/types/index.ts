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
  title?: string;
  experience_level: string;
  difficulty: string;
  interview_type: string;
  topics: string[];
  topic?: string;
  total_questions: number;
  completed_questions: number;
  overall_score: number;
  total_score?: number;
  status: string;
  started_at: string;
  created_at?: string;
  completed_at?: string | null;
  mode?: string;
  voice_name?: string;
  interviewer_intro?: string;
  job_description?: string;
  resume_text?: string;
  skills?: string | string[];
  additional_instructions?: string;
  current_difficulty?: string;
  knowledge_gaps?: string[];
  is_adaptive?: boolean;
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
  additional_instruction?: string;
  adaptation_reason?: string;
  adaptive_action?: string;
  assessment_objective?: string;
  category?: string;
  skill?: string;
  is_skipped?: boolean;
}

export interface Evaluation {
  id: string;
  answer_id: string;
  score: number;
  score_out_of_10?: number;
  correctness: number;
  technical_depth: number;
  clarity: number;
  completeness: number;
  strengths: string[];
  weaknesses: string[];
  missing_points: string[];
  missing_concepts?: string[];
  incorrect_claims?: string[];
  ideal_answer: string;
  improved_sample_answer?: string;
  improvement_tip: string;
  actionable_feedback?: string;
  evaluation_type?: string;
  communication_notes?: string;
  evaluated_at: string;
}

export interface AdaptiveDecision {
  action: string;
  updated_difficulty: string;
  decision_rationale: string;
  next_question?: string | null;
  assessment_objective?: string | null;
  category?: string;
  skill?: string;
  additional_instruction?: string | null;
  identified_knowledge_gaps: string[];
  conversational_prelude?: string;
  is_terminal: boolean;
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
  adaptive_action?: string;
  decision_rationale?: string;
  assessment_objective?: string;
  current_difficulty?: string;
  knowledge_gaps?: string[];
  adaptive_decision?: AdaptiveDecision;
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

export interface QuestionResultItem {
  question_number: number;
  question: string;
  topic?: string;
  difficulty?: string;
  user_answer: string;
  score: number;
  score_out_of_10?: number;
  strengths: string[];
  missing_concepts: string[];
  incorrect_claims: string[];
  feedback?: string;
  model_answer?: string;
  is_skipped?: boolean;
  status?: string;
}

export interface FinalReportResponse {
  interview_id: string;
  overall_score: number;
  score_out_of_10?: number;
  technical_knowledge_score: number;
  communication_score: number;
  problem_solving_score: number;
  answer_quality_score: number;
  strong_topics: string[];
  weak_topics: string[];
  skill_gaps?: string[];
  recommendations: string[];
  communication_observations?: string;
  readiness_estimate?: string;
  readiness_level?: string;
  personalized_summary: string;
  completed_at: string;
  question_results?: QuestionResultItem[];
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

export interface QuestionEvidenceAnalysis {
  question_id: string;
  question_number: number;
  question_text: string;
  candidate_answer_excerpt: string;
  technical_correctness: number;
  conceptual_understanding: number;
  depth_and_clarity: number;
  reasoning_approach: number;
  completeness: number;
  key_strengths: string[];
  misconceptions: string[];
  missing_concepts: string[];
  poorly_explained_aspects: string[];
  coding_evaluation?: {
    logic?: string;
    edge_cases?: string;
    time_complexity?: string;
    space_complexity?: string;
    correctness?: string;
  } | null;
}

export interface RemediationPath {
  what_went_wrong: string;
  what_to_learn: string;
  what_to_practice: string;
  how_to_verify: string;
}

export interface EvidenceSkillGap {
  gap_id: string;
  competency: string;
  category: string;
  finding_type: 'CONFIRMED_WEAKNESS' | 'UNCERTAIN_FINDING' | 'UNTESTED_COMPETENCY' | string;
  confidence_level: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  evidence_question_id?: string | null;
  evidence_question_number?: number | null;
  evidence_question_text?: string | null;
  candidate_answer_excerpt?: string | null;
  what_was_missing_or_incorrect: string;
  why_it_matters: string;
  correct_understanding: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | string;
  remediation_path: RemediationPath;
}

export interface EvidenceStrength {
  competency: string;
  category: string;
  evidence_question_number?: number | null;
  candidate_excerpt?: string | null;
  demonstrated_mastery: string;
}

export interface UntestedCompetency {
  competency: string;
  category: string;
  importance_for_role: string;
  recommended_next_step: string;
}

export interface RoadmapTask {
  task_id: string;
  phase_number: number;
  day_or_sequence: number;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | string;
  topic: string;
  subtopics: string[];
  learning_objectives: string[];
  practical_exercise: string;
  relevant_problems_or_questions: string[];
  estimated_duration_hours: number;
  expected_outcomes: string;
  completion_criteria: string;
  status: 'pending' | 'in_progress' | 'completed' | string;
  completed_at?: string | null;
}

export interface RoadmapPhase {
  phase_number: number;
  title: string;
  duration_weeks: number;
  focus_areas: string[];
  milestone: string;
}

export interface DiagnosticReassessmentQuestion {
  id: string;
  targeted_gap_id: string;
  competency: string;
  question_text: string;
  expected_key_points: string[];
  benchmark_solution: string;
  difficulty: 'Easy' | 'Medium' | 'Hard' | string;
}

export interface DeepAnalysisRoadmapResponse {
  id: string;
  interview_id: string;
  user_id: string;
  target_role: string;
  target_difficulty: string;
  target_interview_date?: string | null;
  daily_study_hours: number;
  readiness_score: number;
  readiness_level: string;
  executive_summary: string;
  question_analyses: QuestionEvidenceAnalysis[];
  skill_gaps: EvidenceSkillGap[];
  strengths: EvidenceStrength[];
  untested_competencies: UntestedCompetency[];
  roadmap_phases: RoadmapPhase[];
  roadmap_tasks: RoadmapTask[];
  reassessment_questions: DiagnosticReassessmentQuestion[];
  created_at: string;
  updated_at: string;
}

export interface TestCaseSample {
  input: string;
  expected_output: string;
  explanation?: string;
}

export interface CodingQuestion {
  id: string;
  question_number: number;
  title: string;
  description: string;
  input_format?: string;
  output_format?: string;
  constraints?: string;
  starter_code: string;
  hints?: string[];
  sample_test_cases: TestCaseSample[];
  skill?: string;
  difficulty: string;
}

export interface TestCaseResult {
  test_case_index: number;
  input: string;
  expected_output: string;
  actual_output: string;
  passed: boolean;
  execution_time_ms: number;
  error?: string | null;
  stdout?: string | null;
}

export interface CustomRunResult {
  input: string;
  actual_output: string;
  execution_time_ms: number;
  error?: string | null;
  stdout?: string | null;
}

export interface CodeRunResult {
  total_test_cases: number;
  passed_test_cases: number;
  all_passed: boolean;
  results: TestCaseResult[];
  custom_result?: CustomRunResult | null;
}

export interface CodingSubmissionResult {
  id: string;
  question_id: string;
  language: string;
  submitted_code: string;
  test_cases_passed: number;
  total_test_cases: number;
  test_case_results: TestCaseResult[];
  coding_score: number;
  time_complexity: string;
  space_complexity: string;
  correctness_score: number;
  code_quality_score: number;
  edge_case_score: number;
  strengths: string[];
  detected_mistakes: string[];
  optimization_suggestions: string[];
  code_review: string;
  model_solution: string;
  submitted_at: string;
}

export interface CodingInterview {
  id: string;
  user_id: string;
  title: string;
  target_role: string;
  experience_level: string;
  topic: string;
  difficulty: string;
  language: string;
  status: string;
  total_score?: number;
  created_at: string;
  questions: CodingQuestion[];
  submissions: CodingSubmissionResult[];
}

export interface CodingInterviewCreateRequest {
  target_role: string;
  experience_level: string;
  topic: string;
  difficulty: string;
  language: string;
}

