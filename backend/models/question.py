import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.database.database import Base

class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    
    question_number = Column(Integer, nullable=False, default=1)
    question_text = Column(Text, nullable=False)
    category = Column(String, nullable=True, default="General")
    skill = Column(String, nullable=True, default="Core Knowledge")
    difficulty = Column(String, nullable=False, default="Medium")
    additional_instruction = Column(Text, nullable=True)
    adaptation_reason = Column(Text, nullable=True)  # AI Adaptive Engine decision rationale
    adaptive_action = Column(String, nullable=True, default="NEXT_TOPIC")  # INCREASE_DIFFICULTY, FOLLOW_UP, SIMPLIFY, CLARIFY, NEXT_TOPIC
    assessment_objective = Column(Text, nullable=True)  # Targeted evaluation goal for this question
    is_follow_up = Column(Boolean, default=False, nullable=True)
    is_skipped = Column(Boolean, default=False, nullable=True)
    parent_question_id = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    interview = relationship("Interview", back_populates="questions")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="question", cascade="all, delete-orphan")
