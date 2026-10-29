from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator

class QuestionEvidenceAnalysis(BaseModel):
    question_id: str
    question_number: int
    question_text: str
    candidate_answer_excerpt: str
    technical_correctness: float = Field(default=0.0, ge=0.0, le=10.0)
    conceptual_understanding: float = Field(default=0.0, ge=0.0, le=10.0)
    depth_and_clarity: float = Field(default=0.0, ge=0.0, le=10.0)
    reasoning_approach: float = Field(default=0.0, ge=0.0, le=10.0)
    completeness: float = Field(default=0.0, ge=0.0, le=10.0)
    key_strengths: List[str] = Field(default_factory=list)
    misconceptions: List[str] = Field(default_factory=list)
    missing_concepts: List[str] = Field(default_factory=list)
    poorly_explained_aspects: List[str] = Field(default_factory=list)
    coding_evaluation: Optional[Dict[str, Any]] = None

    @field_validator(
        'technical_correctness',
        'conceptual_understanding',
        'depth_and_clarity',
        'reasoning_approach',
        'completeness',
        mode='before'
    )
    @classmethod
    def normalize_score_10(cls, v: Any) -> float:
        if v is None:
            return 0.0
        try:
            val = float(v)
            if val > 10.0:
                val = val / 10.0
            return max(0.0, min(10.0, round(val, 1)))
        except (ValueError, TypeError):
            return 0.0

class RemediationPath(BaseModel):
    what_went_wrong: str
    what_to_learn: str
    what_to_practice: str
    how_to_verify: str

class EvidenceSkillGap(BaseModel):
    gap_id: str
    competency: str
    category: str
    finding_type: str = "CONFIRMED_WEAKNESS"  # CONFIRMED_WEAKNESS | UNCERTAIN_FINDING | UNTESTED_COMPETENCY
    confidence_level: str = "HIGH"           # HIGH | MEDIUM | LOW
    evidence_question_id: Optional[str] = None
    evidence_question_number: Optional[int] = None
    evidence_question_text: Optional[str] = None
    candidate_answer_excerpt: Optional[str] = None
    what_was_missing_or_incorrect: str
    why_it_matters: str
    correct_understanding: str
    priority: str = "HIGH"                  # CRITICAL | HIGH | MEDIUM
    remediation_path: RemediationPath

class EvidenceStrength(BaseModel):
    competency: str
    category: str
    evidence_question_number: Optional[int] = None
    candidate_excerpt: Optional[str] = None
    demonstrated_mastery: str

class UntestedCompetency(BaseModel):
    competency: str
    category: str
    importance_for_role: str
    recommended_next_step: str

class RoadmapTask(BaseModel):
    task_id: str
    phase_number: int
    day_or_sequence: int
    priority: str = "HIGH"                 # CRITICAL | HIGH | MEDIUM
    topic: str
    subtopics: List[str] = Field(default_factory=list)
    learning_objectives: List[str] = Field(default_factory=list)
    practical_exercise: str
    relevant_problems_or_questions: List[str] = Field(default_factory=list)
    estimated_duration_hours: float = 2.0
    expected_outcomes: str
    completion_criteria: str
    status: str = "pending"                # pending | in_progress | completed
    completed_at: Optional[str] = None

class RoadmapPhase(BaseModel):
    phase_number: int
    title: str
    duration_weeks: float
    focus_areas: List[str] = Field(default_factory=list)
    milestone: str

class DiagnosticReassessmentQuestion(BaseModel):
    id: str
    targeted_gap_id: str
    competency: str
    question_text: str
    expected_key_points: List[str] = Field(default_factory=list)
    benchmark_solution: str
    difficulty: str = "Medium"             # Easy | Medium | Hard

class DeepAnalysisRoadmapResponse(BaseModel):
    id: str
    interview_id: str
    user_id: str
    target_role: str
    target_difficulty: str
    target_interview_date: Optional[str] = None
    daily_study_hours: float
    readiness_score: float
    readiness_level: str
    executive_summary: str
    question_analyses: List[QuestionEvidenceAnalysis]
    skill_gaps: List[EvidenceSkillGap]
    strengths: List[EvidenceStrength]
    untested_competencies: List[UntestedCompetency]
    roadmap_phases: List[RoadmapPhase]
    roadmap_tasks: List[RoadmapTask]
    reassessment_questions: List[DiagnosticReassessmentQuestion]
    created_at: str
    updated_at: str

class TaskStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|in_progress|completed)$")

class PreferencesUpdateRequest(BaseModel):
    target_interview_date: Optional[str] = None
    daily_study_hours: Optional[float] = Field(default=None, ge=0.5, le=12.0)
