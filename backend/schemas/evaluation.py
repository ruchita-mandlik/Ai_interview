from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

class AIEvaluationResult(BaseModel):
    technical_correctness: float = Field(..., ge=0, le=100)
    conceptual_completeness: float = Field(..., ge=0, le=100)
    response_relevance: float = Field(..., ge=0, le=100)
    structural_clarity: float = Field(..., ge=0, le=100)
    depth_of_understanding: float = Field(..., ge=0, le=100)
    overall_score: float = Field(..., ge=0, le=100)
    strengths: List[str] = []
    improvements: List[str] = []
    feedback: str
    model_answer: str

class EvaluationResponse(BaseModel):
    id: str
    answer_id: str
    interview_id: str
    question_id: str
    technical_correctness: float
    conceptual_completeness: float
    response_relevance: float
    structural_clarity: float
    depth_of_understanding: float
    overall_score: float
    strengths: List[str]
    improvements: List[str]
    feedback: str
    model_answer: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)
