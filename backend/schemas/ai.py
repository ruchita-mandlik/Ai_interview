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

class FinalReportResponse(BaseModel):
    interview_id: str
    overall_score: float
    technical_knowledge_score: float
    communication_score: float
    problem_solving_score: float
    answer_quality_score: float
    strong_topics: List[str]
    weak_topics: List[str]
    recommendations: List[str]
    personalized_summary: str
    completed_at: str

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
