from typing import Optional, List, Any, Union
from pydantic import BaseModel, Field, ConfigDict

class InterviewCreateRequest(BaseModel):
    interview_type: Optional[str] = Field(default="Technical", description="Technical, HR, Behavioral, or System Design")
    target_role: Optional[str] = Field(default=None, description="Target job role")
    role: Optional[str] = Field(default=None, description="Target job role (alias)")
    experience_level: Optional[str] = Field(default="Intermediate", description="Beginner, Intermediate, Advanced, etc.")
    topic: Optional[str] = Field(default=None, description="Topic/skills")
    topics: Optional[List[str]] = Field(default=None, description="List of topics")
    skills: Optional[List[str]] = Field(default=None, description="Target skills or technologies")
    difficulty: Optional[str] = Field(default="Medium", description="Easy, Medium, Hard, Adaptive")
    num_questions: Optional[int] = Field(default=None, description="Number of questions")
    total_questions: Optional[int] = Field(default=None, description="Total questions (alias)")
    resume_analysis_id: Optional[str] = Field(default=None, description="Optional ID of Resume+JD analysis")
    job_description: Optional[str] = Field(default=None, description="Custom job description or requirements")
    resume_text: Optional[str] = Field(default=None, description="Optional candidate resume text or profile details")
    additional_instructions: Optional[str] = Field(default=None, description="Additional guidelines or special instructions for interviewer")
    mode: Optional[str] = Field(default="text", description="Interview mode: 'voice' or 'text'")
    voice_name: Optional[str] = Field(default="default", description="Selected voice identifier for TTS")
    is_adaptive: Optional[bool] = Field(default=None, description="Whether this is an adaptive AI interview or standard mock practice")

    def get_role(self) -> str:
        return self.role or self.target_role or "Software Developer"

    def get_topic(self) -> str:
        if self.topic:
            return self.topic
        if self.topics:
            return ", ".join(self.topics)
        if self.skills:
            return ", ".join(self.skills)
        return "General"

    def get_skills_list(self) -> List[str]:
        if self.skills:
            return self.skills
        if self.topics:
            return self.topics
        if self.topic:
            return [s.strip() for s in self.topic.split(",") if s.strip()]
        return []

    def get_num_questions(self) -> int:
        return self.total_questions or self.num_questions or 5

    def get_mode(self) -> str:
        return (self.mode or "text").lower()


class QuestionSchema(BaseModel):
    id: str
    interview_id: Optional[str] = None
    question_number: int = 1
    question_text: str
    question: Optional[str] = None  # SPA alias
    category: Optional[str] = "General"
    topic: Optional[str] = "General"  # SPA alias
    skill: Optional[str] = "Technical"
    difficulty: Optional[str] = "Medium"
    question_type: Optional[str] = "Technical"
    expected_points: Optional[List[str]] = []
    additional_instruction: Optional[str] = None
    adaptation_reason: Optional[str] = None
    adaptive_action: Optional[str] = "NEXT_TOPIC"
    assessment_objective: Optional[str] = None
    is_follow_up: Optional[bool] = False
    is_skipped: Optional[bool] = False
    parent_question_id: Optional[str] = None
    spoken_intro: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SkipQuestionResponse(BaseModel):
    status: str = "in_progress"
    interview_completed: bool = False
    skipped_question_id: Optional[str] = None
    next_question: Optional[QuestionSchema] = None
    id: Optional[str] = None
    question_number: Optional[int] = None
    question_text: Optional[str] = None
    question: Optional[str] = None
    category: Optional[str] = None
    topic: Optional[str] = None
    skill: Optional[str] = None
    difficulty: Optional[str] = None
    question_type: Optional[str] = None
    expected_points: Optional[List[str]] = []
    additional_instruction: Optional[str] = None
    adaptation_reason: Optional[str] = None
    adaptive_action: Optional[str] = "NEXT_TOPIC"
    assessment_objective: Optional[str] = None
    is_follow_up: Optional[bool] = False
    is_skipped: Optional[bool] = False
    spoken_intro: Optional[str] = None
    created_at: Optional[str] = None
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class InterviewResponse(BaseModel):
    id: str
    user_id: str
    title: str
    interview_type: str
    target_role: str
    role: Optional[str] = None
    experience_level: str
    topic: str
    topics: Optional[List[str]] = []
    difficulty: str
    current_difficulty: Optional[str] = "Medium"
    knowledge_gaps: Optional[Union[List[str], str]] = []
    num_questions: int
    total_questions: Optional[int] = None
    completed_questions: Optional[int] = 0
    status: str
    total_score: Optional[float] = 0.0
    overall_score: Optional[float] = 0.0
    duration_minutes: int = 20
    mode: Optional[str] = "text"
    voice_name: Optional[str] = "default"
    is_adaptive: Optional[bool] = False
    interviewer_intro: Optional[str] = None
    job_description: Optional[str] = None
    resume_text: Optional[str] = None
    skills: Optional[Union[List[str], str]] = None
    additional_instructions: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    questions: List[QuestionSchema] = []

    model_config = ConfigDict(from_attributes=True)


class SPAInterviewCreateResponse(BaseModel):
    interview: InterviewResponse
    first_question: Optional[QuestionSchema] = None
    interviewer_intro: Optional[str] = None
