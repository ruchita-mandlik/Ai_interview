from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class SupportingSessionInfo(BaseModel):
    interview_id: str
    title: str
    date: str
    score: Optional[float] = None
    topic: Optional[str] = None
    difficulty: Optional[str] = None

class SupportingQuestionInfo(BaseModel):
    question_id: str
    question_number: int
    question_text: str
    category: Optional[str] = None
    skill: Optional[str] = None
    score: Optional[float] = None

class RepeatedWeaknessDetail(BaseModel):
    concept: str
    weakness: str = ""
    category: str = "General Technical"
    recurrence_count: int = 2
    first_observed_date: Optional[str] = None
    latest_observed_date: Optional[str] = None
    status: str = "active_weakness"  # active_weakness, improving, resolved
    average_score: float = 0.0
    latest_score: float = 0.0
    impact_description: str = "Recurring issue impacting interview performance."
    supporting_sessions: List[SupportingSessionInfo] = Field(default_factory=list)
    supporting_questions: List[SupportingQuestionInfo] = Field(default_factory=list)
    supporting_excerpts: List[str] = Field(default_factory=list)
    recommended_remediation: str = "Complete targeted practice questions."

    def __init__(self, **data: Any):
        if "weakness" not in data and "concept" in data:
            data["weakness"] = data["concept"]
        elif "concept" not in data and "weakness" in data:
            data["concept"] = data["weakness"]
        super().__init__(**data)

class OneTimeMistakeDetail(BaseModel):
    concept: str
    category: str = "General Technical"
    interview_id: str
    interview_title: str
    question_text: str
    observed_date: Optional[str] = None
    score: float = 0.0
    candidate_answer_excerpt: Optional[str] = None
    is_repeated: bool = False

class ImprovingSkillDetail(BaseModel):
    skill: str
    category: str = "General"
    baseline_score: float = 0.0
    first_score: float = 0.0
    latest_score: float = 0.0
    score_delta: float = 0.0
    improvement_delta: float = 0.0
    status: str = "improving"  # improving, mastered
    evaluation_count: int = 1
    evidence_summary: str = ""
    latest_verified_date: Optional[str] = None

    def __init__(self, **data: Any):
        if "first_score" not in data and "baseline_score" in data:
            data["first_score"] = data["baseline_score"]
        elif "baseline_score" not in data and "first_score" in data:
            data["baseline_score"] = data["first_score"]
        if "improvement_delta" not in data and "score_delta" in data:
            data["improvement_delta"] = data["score_delta"]
        elif "score_delta" not in data and "improvement_delta" in data:
            data["score_delta"] = data["improvement_delta"]
        super().__init__(**data)

class DecliningSkillDetail(BaseModel):
    skill: str
    category: str = "General"
    previous_average: float = 0.0
    recent_score: float = 0.0
    score_drop: float = 0.0
    evaluation_count: int = 1
    latest_observed_date: Optional[str] = None
    suggested_action: str = ""

class InsufficientEvidenceTopic(BaseModel):
    topic: str
    category: str = "General"
    attempts_count: int = 1
    latest_score: float = 0.0
    reason: str = "Tested fewer than 2 times. Additional evaluations needed for high confidence."

class ProgressOverTimePoint(BaseModel):
    session_id: str
    session_title: str
    date: str
    topic: str
    interview_type: str
    score: float
    score_change_from_previous: Optional[float] = None
    trend_direction: str = "baseline"  # up, down, flat, baseline

class NextBestActionItem(BaseModel):
    action_type: str  # REMEDIATE_WEAKNESS, PRACTICE_TOPIC, MOCK_INTERVIEW, CODING_CHALLENGE
    title: str
    priority: str = "HIGH"  # CRITICAL, HIGH, MEDIUM
    reason: str
    evidence_basis: str
    target_topic: Optional[str] = None
    deep_link: str = "interview-config.html"
    estimated_minutes: int = 25

class MemorySummaryResponse(BaseModel):
    user_id: str
    target_role: str
    total_completed_interviews: int = 0
    total_interviews_evaluated: int = 0
    total_answers_evaluated: int = 0
    overall_average_score: float = 0.0
    average_score: float = 0.0
    recurring_weaknesses: List[RepeatedWeaknessDetail] = Field(default_factory=list)
    one_time_mistakes: List[OneTimeMistakeDetail] = Field(default_factory=list)
    improved_skills: List[ImprovingSkillDetail] = Field(default_factory=list)
    declining_skills: List[DecliningSkillDetail] = Field(default_factory=list)
    insufficient_evidence_topics: List[InsufficientEvidenceTopic] = Field(default_factory=list)
    persistent_mistakes_count: int = 0
    next_best_action: Optional[NextBestActionItem] = None
    progress_over_time: List[ProgressOverTimePoint] = Field(default_factory=list)
    last_updated: str = ""

    def __init__(self, **data: Any):
        if "total_interviews_evaluated" not in data and "total_completed_interviews" in data:
            data["total_interviews_evaluated"] = data["total_completed_interviews"]
        elif "total_completed_interviews" not in data and "total_interviews_evaluated" in data:
            data["total_completed_interviews"] = data["total_interviews_evaluated"]
        if "average_score" not in data and "overall_average_score" in data:
            data["average_score"] = data["overall_average_score"]
        elif "overall_average_score" not in data and "average_score" in data:
            data["overall_average_score"] = data["average_score"]
        super().__init__(**data)

class SessionComparisonResponse(BaseModel):
    current_interview_id: str
    current_title: str
    current_session_role: str = ""
    current_score: Optional[float] = None
    current_session_score: Optional[float] = None
    current_date: str
    current_session_date: str = ""
    current_topic: str
    previous_interview_id: Optional[str] = None
    comparison_session_id: Optional[str] = None
    previous_title: Optional[str] = None
    comparison_session_role: Optional[str] = None
    previous_score: Optional[float] = None
    comparison_session_score: Optional[float] = None
    previous_date: Optional[str] = None
    comparison_session_date: Optional[str] = None
    previous_topic: Optional[str] = None
    score_change: Optional[float] = None
    score_delta: Optional[float] = None
    improvement_trend: str = "baseline"  # improving, declining, consistent, baseline
    trend_explanation: str
    is_baseline_session: bool = False
    repeated_mistakes: List[Dict[str, Any]] = Field(default_factory=list)
    newly_resolved_weaknesses: List[Dict[str, Any]] = Field(default_factory=list)
    skills_needing_practice: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_based_strengths: List[Dict[str, Any]] = Field(default_factory=list)
    next_recommended_actions: List[str] = Field(default_factory=list)

    def __init__(self, **data: Any):
        if "current_session_role" not in data:
            data["current_session_role"] = data.get("current_title", "Interview Session")
        if "current_session_score" not in data:
            data["current_session_score"] = data.get("current_score")
        if "current_session_date" not in data:
            data["current_session_date"] = data.get("current_date", "")
        if "comparison_session_id" not in data:
            data["comparison_session_id"] = data.get("previous_interview_id")
        if "comparison_session_role" not in data:
            data["comparison_session_role"] = data.get("previous_title")
        if "comparison_session_score" not in data:
            data["comparison_session_score"] = data.get("previous_score")
        if "comparison_session_date" not in data:
            data["comparison_session_date"] = data.get("previous_date")
        if "score_delta" not in data:
            data["score_delta"] = data.get("score_change")
        super().__init__(**data)

# --- Analytics Dashboard Specific Schemas ---

class ScoreTrajectoryItem(BaseModel):
    session_id: str
    session_title: str
    target_role: str
    topic: str
    difficulty: str
    date: str
    timestamp: str
    score: float
    score_change: Optional[float] = None
    trend_direction: str  # up, down, flat, baseline
    total_questions: int
    evaluations_count: int

class SkillPerformanceItem(BaseModel):
    skill: str
    category: str
    baseline_score: float
    latest_score: float
    score_delta: float
    evaluation_count: int
    session_count: int
    status: str  # improving, mastered, declining, stable, insufficient_evidence
    has_sufficient_evidence: bool

class WeaknessFrequencyItem(BaseModel):
    concept: str
    category: str
    session_occurrences: int  # distinct sessions count
    total_question_occurrences: int
    average_score: float
    latest_score: float
    status: str
    supporting_sessions: List[SupportingSessionInfo] = Field(default_factory=list)
    sample_evidence: Optional[str] = None

class ScoreDistributionBin(BaseModel):
    bin_label: str
    min_score: float
    max_score: float
    count: int
    percentage: float
    session_ids: List[str] = Field(default_factory=list)

class ImprovementTrendItem(BaseModel):
    date: str
    session_id: str
    session_title: str
    score: float
    cumulative_avg: float
    verified_gain_delta: Optional[float] = None
    evidence_status: str  # sufficient, insufficient_evidence, baseline

class SessionComparisonRubricItem(BaseModel):
    dimension: str
    weight_pct: int
    session_a_score: Optional[float] = None
    session_b_score: Optional[float] = None
    score_delta: Optional[float] = None

class GroupedSessionComparison(BaseModel):
    session_a_id: str
    session_a_title: str
    session_a_date: str
    session_a_score: Optional[float] = None
    session_b_id: Optional[str] = None
    session_b_title: Optional[str] = None
    session_b_date: Optional[str] = None
    session_b_score: Optional[float] = None
    overall_delta: Optional[float] = None
    rubric_comparison: List[SessionComparisonRubricItem] = Field(default_factory=list)
    skill_comparison: List[Dict[str, Any]] = Field(default_factory=list)
    repeated_mistakes: List[Dict[str, Any]] = Field(default_factory=list)
    newly_resolved_weaknesses: List[Dict[str, Any]] = Field(default_factory=list)

class AnalyticsDashboardResponse(BaseModel):
    user_id: str
    target_role: str
    total_sessions_recorded: int
    valid_evaluated_sessions: int
    excluded_incomplete_sessions: int
    exclusion_reason: Optional[str] = None
    overall_average_score: float
    highest_score: Optional[float] = None
    lowest_score: Optional[float] = None
    score_trajectory: List[ScoreTrajectoryItem] = Field(default_factory=list)
    skill_performance: List[SkillPerformanceItem] = Field(default_factory=list)
    weakness_frequency: List[WeaknessFrequencyItem] = Field(default_factory=list)
    score_distribution: List[ScoreDistributionBin] = Field(default_factory=list)
    improvement_trend: List[ImprovementTrendItem] = Field(default_factory=list)
    session_comparison: Optional[GroupedSessionComparison] = None
    filter_date_from: Optional[str] = None
    filter_date_to: Optional[str] = None
    available_sessions: List[Dict[str, Any]] = Field(default_factory=list)
