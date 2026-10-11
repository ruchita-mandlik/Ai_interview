from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class AnswerSubmitRequest(BaseModel):
    question_id: Optional[str] = Field(default=None, description="Question ID")
    answer_text: Optional[str] = Field(default=None, description="Candidate's answer text")
    answer: Optional[str] = Field(default=None, description="Alias for answer text")
    transcript_raw: Optional[str] = Field(default=None, description="Raw speech recognition transcript before user edits")
    is_voice_submission: Optional[bool] = Field(default=False, description="Whether answer was captured via voice")
    audio_duration_seconds: Optional[float] = Field(default=None, description="Duration of speech in seconds")

    def get_answer(self) -> str:
        return (self.answer_text or self.answer or "").strip()

class AnswerResponse(BaseModel):
    id: str
    interview_id: str
    question_id: str
    user_id: str
    answer_text: str
    transcript_raw: Optional[str] = None
    is_voice_submission: Optional[bool] = False
    audio_duration_seconds: Optional[float] = None
    submitted_at: str

    model_config = ConfigDict(from_attributes=True)
