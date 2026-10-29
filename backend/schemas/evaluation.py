from enum import Enum
import json
from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


def _normalize_to_str(v: Any, default: Optional[str] = None) -> Optional[str]:
    """
    Normalizes a string or list of strings into a clean, human-readable string.
    Lists of strings are formatted as clear bullet points.
    """
    if v is None:
        return default
    if isinstance(v, list):
        items = [str(x).strip() for x in v if x is not None and str(x).strip()]
        if not items:
            return default
        if len(items) == 1:
            return items[0]
        return "\n".join(f"• {x}" if not x.startswith(("•", "-", "*")) else x for x in items)
    if isinstance(v, str):
        cleaned = v.strip()
        return cleaned if cleaned else default
    return str(v).strip() or default


def _normalize_to_str_list(v: Any, default: Optional[List[str]] = None) -> List[str]:
    """
    Normalizes input into a list of strings.
    Handles single strings, JSON-encoded strings, and lists of dicts/primitives.
    """
    if default is None:
        default = []
    if v is None:
        return default
    if isinstance(v, list):
        res = []
        for item in v:
            if item is None:
                continue
            if isinstance(item, dict):
                text = item.get("point") or item.get("concept") or item.get("text") or str(item)
                s = str(text).strip()
                if s:
                    res.append(s)
            else:
                s = str(item).strip()
                if s:
                    res.append(s)
        return res
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return default
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if x is not None and str(x).strip()]
            except Exception:
                pass
        return [s]
    return [str(v).strip()]


class AdaptiveAction(str, Enum):
    INCREASE_DIFFICULTY = "INCREASE_DIFFICULTY"
    CHALLENGE_REASONING = "CHALLENGE_REASONING"
    FOLLOW_UP = "FOLLOW_UP"
    SIMPLIFY = "SIMPLIFY"
    CLARIFY = "CLARIFY"
    REVISIT_WEAKNESS = "REVISIT_WEAKNESS"
    NEXT_TOPIC = "NEXT_TOPIC"


class AdaptiveDecision(BaseModel):
    action: AdaptiveAction = Field(default=AdaptiveAction.NEXT_TOPIC, description="Selected adaptive interview action")
    updated_difficulty: str = Field(default="Medium", description="Updated difficulty: Easy, Medium, or Hard")
    decision_rationale: str = Field(default="", description="Concise user-facing explanation for why this question/difficulty was chosen")
    next_question: Optional[str] = Field(default=None, description="Next question text (or follow-up/clarification question)")
    assessment_objective: Optional[str] = Field(default=None, description="What this question aims to evaluate")
    category: Optional[str] = Field(default=None, description="Category/domain of the question")
    skill: Optional[str] = Field(default=None, description="Primary skill being evaluated")
    additional_instruction: Optional[str] = Field(default=None, description="Guidance for candidate answering")
    identified_knowledge_gaps: List[str] = Field(default=[], description="Newly detected or reinforced knowledge gaps")
    conversational_prelude: Optional[str] = Field(default=None, description="Natural conversational transition for voice/chat")
    is_terminal: bool = Field(default=False, description="True if no questions remain or interview is completed")

    @field_validator("decision_rationale", "next_question", "assessment_objective", "category", "skill", "additional_instruction", "conversational_prelude", mode="before")
    @classmethod
    def validate_optional_strings(cls, v: Any) -> Optional[str]:
        return _normalize_to_str(v, default=None)

    @field_validator("identified_knowledge_gaps", mode="before")
    @classmethod
    def validate_knowledge_gaps(cls, v: Any) -> List[str]:
        return _normalize_to_str_list(v)

    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, v: Any) -> AdaptiveAction:
        if isinstance(v, AdaptiveAction):
            return v
        if not v:
            return AdaptiveAction.NEXT_TOPIC
        raw_str = str(v).strip().upper()
        if "CHALLENG" in raw_str:
            return AdaptiveAction.CHALLENGE_REASONING
        if "REVISIT" in raw_str or "WEAKNESS" in raw_str:
            return AdaptiveAction.REVISIT_WEAKNESS
        if "INCREASE" in raw_str or "HARD" in raw_str or "DEEPEN" in raw_str or "ESCALAT" in raw_str:
            return AdaptiveAction.INCREASE_DIFFICULTY
        if "FOLLOW" in raw_str or "PROBE" in raw_str:
            return AdaptiveAction.FOLLOW_UP
        if "SIMPLIF" in raw_str or "EASY" in raw_str or "REDUC" in raw_str:
            return AdaptiveAction.SIMPLIFY
        if "CLARIF" in raw_str or "AMBIG" in raw_str:
            return AdaptiveAction.CLARIFY
        return AdaptiveAction.NEXT_TOPIC


class AIEvaluationResult(BaseModel):
    technical_correctness: float = Field(..., ge=0, le=100)
    conceptual_completeness: float = Field(..., ge=0, le=100)
    response_relevance: float = Field(..., ge=0, le=100)
    structural_clarity: float = Field(..., ge=0, le=100)
    depth_of_understanding: float = Field(..., ge=0, le=100)
    overall_score: float = Field(..., ge=0, le=100)
    score_out_of_10: Optional[float] = None
    strengths: List[str] = []
    improvements: List[str] = []
    missing_concepts: List[str] = []
    incorrect_claims: List[str] = []
    feedback: str
    actionable_feedback: Optional[Union[str, List[str]]] = None
    model_answer: str
    improved_sample_answer: Optional[str] = None
    evaluation_type: Optional[str] = "technical"
    communication_notes: Optional[str] = None

    @field_validator("actionable_feedback", mode="before")
    @classmethod
    def validate_actionable_feedback(cls, v: Any) -> Optional[str]:
        return _normalize_to_str(v, default=None)

    @field_validator("feedback", "model_answer", mode="before")
    @classmethod
    def validate_string_fields(cls, v: Any) -> str:
        res = _normalize_to_str(v, default="")
        return res or ""

    @field_validator("improved_sample_answer", "communication_notes", mode="before")
    @classmethod
    def validate_optional_strings(cls, v: Any) -> Optional[str]:
        return _normalize_to_str(v, default=None)

    @field_validator("strengths", "improvements", "missing_concepts", "incorrect_claims", mode="before")
    @classmethod
    def validate_list_fields(cls, v: Any) -> List[str]:
        return _normalize_to_str_list(v)

    @field_validator(
        "technical_correctness",
        "conceptual_completeness",
        "response_relevance",
        "structural_clarity",
        "depth_of_understanding",
        "overall_score",
        mode="before"
    )
    @classmethod
    def validate_scores(cls, v: Any) -> float:
        if v is None:
            return 0.0
        try:
            if isinstance(v, str):
                v = v.replace("%", "").strip()
            f = float(v)
            return min(100.0, max(0.0, f))
        except (ValueError, TypeError):
            return 0.0

    @field_validator("score_out_of_10", mode="before")
    @classmethod
    def validate_score_out_of_10(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            if isinstance(v, str):
                v = v.replace("%", "").strip()
            f = float(v)
            return min(10.0, max(0.0, f))
        except (ValueError, TypeError):
            return None


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
    score_out_of_10: Optional[float] = None
    strengths: List[str] = []
    improvements: List[str] = []
    missing_concepts: List[str] = []
    incorrect_claims: List[str] = []
    feedback: str
    actionable_feedback: Optional[Union[str, List[str]]] = None
    model_answer: str
    improved_sample_answer: Optional[str] = None
    evaluation_type: Optional[str] = "technical"
    communication_notes: Optional[str] = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)

    @field_validator("actionable_feedback", mode="before")
    @classmethod
    def validate_actionable_feedback(cls, v: Any) -> Optional[str]:
        return _normalize_to_str(v, default=None)

    @field_validator("feedback", "model_answer", mode="before")
    @classmethod
    def validate_string_fields(cls, v: Any) -> str:
        res = _normalize_to_str(v, default="")
        return res or ""

    @field_validator("improved_sample_answer", "communication_notes", mode="before")
    @classmethod
    def validate_optional_strings(cls, v: Any) -> Optional[str]:
        return _normalize_to_str(v, default=None)

    @field_validator("strengths", "improvements", "missing_concepts", "incorrect_claims", mode="before")
    @classmethod
    def validate_list_fields(cls, v: Any) -> List[str]:
        return _normalize_to_str_list(v)
