from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator

class DimensionScore(BaseModel):
    name: str
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    weight: float = Field(default=0.2, ge=0.0, le=1.0)
    status: str = "Developing"  # Exceptional, Proficient, Developing, Needs Remediation, Insufficient Data
    evidence_summary: str
    data_points_count: int = 0

    @field_validator("score", mode="before")
    @classmethod
    def normalize_dimension_score(cls, v: Any) -> float:
        if v is None:
            return 0.0
        val = float(v)
        if val > 100.0:
            val = val / 10.0
        return max(0.0, min(100.0, round(val, 1)))

class SkillReadiness(BaseModel):
    skill: str
    category: str = "General"
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    sample_count: int = 0
    trend: str = "stable"  # improving, stable, declining, untested
    last_tested_date: Optional[str] = None
    confidence: str = "LOW"  # HIGH, MODERATE, LOW

    @field_validator("score", mode="before")
    @classmethod
    def normalize_skill_score(cls, v: Any) -> float:
        if v is None:
            return 0.0
        val = float(v)
        if val > 100.0:
            val = val / 10.0
        return max(0.0, min(100.0, round(val, 1)))

class PersistentWeaknessItem(BaseModel):
    weakness_name: str
    category: str = "General"
    recurrence_count: int = 1
    first_observed_date: Optional[str] = None
    latest_observed_date: Optional[str] = None
    affected_sessions: List[str] = Field(default_factory=list)
    evidence_excerpts: List[str] = Field(default_factory=list)
    impact_on_target_role: str = "Directly affects core technical proficiency benchmark."
    recommended_remediation: str = "Review underlying principles and complete targeted practice questions."
    target_roadmap_task_id: Optional[str] = None

class NextBestAction(BaseModel):
    action_type: str = "TAKE_INITIAL_MOCK"  # PRACTICE_ROADMAP_TASK, REMEDIATE_PERSISTENT_WEAKNESS, CODE_SANDBOX_CHALLENGE, DIAGNOSTIC_REASSESSMENT, TAKE_INITIAL_MOCK
    title: str
    priority: str = "HIGH"  # CRITICAL, HIGH, MEDIUM
    rationale: str
    evidence_basis: str
    deep_link_tab: str = "interview"  # interview, voice, plan, sandbox, analytics
    target_item_id: Optional[str] = None
    estimated_minutes: int = 30

class HistoricalTrendPoint(BaseModel):
    date: str
    overall_score: float
    technical_score: float
    coding_score: float
    session_type: str
    session_title: str

    @field_validator("overall_score", "technical_score", "coding_score", mode="before")
    @classmethod
    def normalize_trend_score(cls, v: Any) -> float:
        if v is None:
            return 0.0
        val = float(v)
        if val > 100.0:
            val = val / 10.0
        return max(0.0, min(100.0, round(val, 1)))

class EvidenceBreakdown(BaseModel):
    total_interviews_evaluated: int = 0
    total_answers_analyzed: int = 0
    total_coding_submissions: int = 0
    total_roadmap_tasks_completed: int = 0
    recurring_gap_count: int = 0
    demonstrated_mastery_count: int = 0
    calculation_formula_explanation: str
    # Compatibility aliases
    evaluated_answers_count: int = 0
    completed_interviews_count: int = 0

class ReadinessIntelligenceResponse(BaseModel):
    id: str
    user_id: str
    target_role: str
    experience_level: str
    overall_readiness_score: float = Field(default=0.0, ge=0.0, le=100.0)
    readiness_stage: str
    data_sufficiency: str  # INSUFFICIENT, MODERATE, HIGH, VERY_HIGH
    data_sufficiency_explanation: str
    dimensions: List[DimensionScore]
    skills: List[SkillReadiness]
    persistent_weaknesses: List[PersistentWeaknessItem]
    next_best_action: NextBestAction
    evidence_breakdown: EvidenceBreakdown
    historical_trend: List[HistoricalTrendPoint]
    calculated_at: str

    # Compatibility aliases for frontend components
    readiness_score: float = Field(default=0.0, ge=0.0, le=100.0)
    readiness_level: str = "Calibrated"
    readiness_explanation: str = ""

    @field_validator("overall_readiness_score", "readiness_score", mode="before")
    @classmethod
    def normalize_overall_score(cls, v: Any) -> float:
        if v is None:
            return 0.0
        val = float(v)
        if val > 100.0:
            val = val / 10.0
        return max(0.0, min(100.0, round(val, 1)))
