from pydantic import BaseModel
from typing import List, Optional

class QuestionResponse(BaseModel):
    id: str
    interview_id: str
    question: str
    topic: str
    difficulty: str
    question_type: str
    expected_points: List[str]
    created_at: str

class AnswerSubmitRequest(BaseModel):
    answer: str

class EvaluationResponse(BaseModel):
    id: str
    answer_id: str
    score: float
    correctness: float
    technical_depth: float
    clarity: float
    completeness: float
    strengths: List[str]
    weaknesses: List[str]
    missing_points: List[str]
    ideal_answer: str
    improvement_tip: str
    evaluated_at: str

class AnswerResponse(BaseModel):
    id: str
    interview_id: str
    question_id: str
    user_id: str
    answer: str
    submitted_at: str
    evaluation: Optional[EvaluationResponse] = None
    next_question: Optional[QuestionResponse] = None
    follow_up_question: Optional[QuestionResponse] = None
    interview_completed: bool = False
