import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, Boolean
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
    
    job_description = Column(Text, nullable=True)
    resume_text = Column(Text, nullable=True)
    skills = Column(Text, nullable=True)
    additional_instructions = Column(Text, nullable=True)
    
    resume_analysis_id = Column(String, ForeignKey("resume_jd_analyses.id", ondelete="SET NULL"), nullable=True)
    
    status = Column(String, nullable=False, default="in_progress") # in_progress, completed
    total_score = Column(Float, nullable=True, default=0.0)
    current_difficulty = Column(String, nullable=True, default="Medium")
    knowledge_gaps = Column(Text, nullable=True, default="[]")
    duration_minutes = Column(Integer, nullable=False, default=20)
    mode = Column(String, nullable=False, default="text") # "voice" or "text"
    voice_name = Column(String, nullable=True, default="default")
    is_adaptive = Column(Boolean, nullable=True, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="interviews")
    resume_analysis = relationship("ResumeJDAnalysis", back_populates="interviews")
    questions = relationship("InterviewQuestion", back_populates="interview", cascade="all, delete-orphan", order_by="InterviewQuestion.question_number")
    answers = relationship("Answer", back_populates="interview", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="interview", cascade="all, delete-orphan")
    analysis_roadmap = relationship("InterviewAnalysisRoadmap", back_populates="interview", uselist=False, cascade="all, delete-orphan")

