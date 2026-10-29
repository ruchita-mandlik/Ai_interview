from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class CodingEvaluationRequest(BaseModel):
    problem_statement: str
    language: str
    code: str
    difficulty: Optional[str] = "Medium"
    topic: Optional[str] = "Algorithms"

class CodingEvaluationResponse(BaseModel):
    correctness_score: float
    code_quality_score: float
    time_complexity: str
    space_complexity: str
    bugs_found: List[str]
    edge_cases_covered: List[str]
    missing_edge_cases: List[str]
    optimization_suggestions: List[str]
    ideal_code_snippet: str
    summary_feedback: str

class QuestionResultItem(BaseModel):
    question_number: int
    question: str
    topic: Optional[str] = "General"
    difficulty: Optional[str] = "Medium"
    user_answer: str
    score: Optional[float] = 0.0
    score_out_of_10: Optional[float] = None
    strengths: List[str] = []
    missing_concepts: List[str] = []
    incorrect_claims: List[str] = []
    feedback: Optional[str] = None
    model_answer: Optional[str] = None
    is_skipped: Optional[bool] = False
    status: Optional[str] = "answered"

class FinalReportResponse(BaseModel):
    interview_id: str
    overall_score: float
    score_out_of_10: Optional[float] = None
    technical_knowledge_score: float
    communication_score: float
    problem_solving_score: float
    answer_quality_score: float
    strong_topics: List[str] = []
    weak_topics: List[str] = []
    skill_gaps: List[str] = []
    recommendations: List[str] = []
    communication_observations: Optional[str] = None
    readiness_estimate: Optional[str] = None
    readiness_level: Optional[str] = None
    personalized_summary: str
    completed_at: str
    question_results: List[QuestionResultItem] = []

class PreparationPlanDay(BaseModel):
    day: int
    topic: str
    concepts: List[str]
    practice_questions: List[str]
    difficulty: str
    estimated_time: str

class PreparationPlanResponse(BaseModel):
    user_id: str
    created_at: str
    plan: List[PreparationPlanDay]
    overall_readiness_assessment: str

class RecommendationResponse(BaseModel):
    recommended_topics: List[str]
    recommended_questions: List[str]
    recommended_difficulty: str
    study_priorities: List[str]
