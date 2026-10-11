from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class PerformanceTrendPoint(BaseModel):
    date: str
    score: float
    interview_type: str

class TopicPerformance(BaseModel):
    topic: str
    score: float
    total_questions: int

class DifficultyPerformance(BaseModel):
    difficulty: str
    score: float
    total_questions: int

class TypePerformance(BaseModel):
    interview_type: str
    score: float
    count: int

class OverviewAnalyticsResponse(BaseModel):
    interviews_completed: int
    average_score: float
    best_score: float
    questions_answered: int
    readiness_score: float
    readiness_explanation: str
    strongest_topic: str
    weakest_topic: str
    recent_improvement: float
    weak_topics: List[str]
    performance_trend: List[PerformanceTrendPoint]
    topic_performance: List[TopicPerformance]
    difficulty_performance: List[DifficultyPerformance]
    type_performance: List[TypePerformance]
