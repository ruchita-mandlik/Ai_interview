import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.database import Base

class Interview(Base):
    __tablename__ = "interviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    title = Column(String, nullable=False, default="Technical Mock Interview")
    interview_type = Column(String, nullable=False, default="Technical")
    target_role = Column(String, nullable=False, default="Software Developer")
    experience_level = Column(String, nullable=False, default="Intermediate")
    topic = Column(String, nullable=False, default="Java")
    difficulty = Column(String, nullable=False, default="Medium")
    num_questions = Column(Integer, nullable=False, default=5)
    
    resume_analysis_id = Column(String, ForeignKey("resume_jd_analyses.id", ondelete="SET NULL"), nullable=True)
    
    status = Column(String, nullable=False, default="in_progress") # in_progress, completed
    total_score = Column(Float, nullable=True, default=0.0)
    duration_minutes = Column(Integer, nullable=False, default=20)
    mode = Column(String, nullable=False, default="text") # "voice" or "text"
    voice_name = Column(String, nullable=True, default="default")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="interviews")
    resume_analysis = relationship("ResumeJDAnalysis", back_populates="interviews")
    questions = relationship("InterviewQuestion", back_populates="interview", cascade="all, delete-orphan", order_by="InterviewQuestion.question_number")
    answers = relationship("Answer", back_populates="interview", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="interview", cascade="all, delete-orphan")

