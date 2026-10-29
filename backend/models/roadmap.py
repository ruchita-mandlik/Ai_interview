import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database.database import Base

class InterviewAnalysisRoadmap(Base):
    __tablename__ = "interview_analysis_roadmaps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    target_role = Column(String, nullable=False, default="Software Engineer")
    target_difficulty = Column(String, nullable=False, default="Medium")
    target_interview_date = Column(String, nullable=True)  # YYYY-MM-DD
    daily_study_hours = Column(Float, nullable=False, default=2.0)

    readiness_score = Column(Float, nullable=False, default=0.0)  # 0 to 100
    readiness_level = Column(String, nullable=False, default="Needs Preparation")  # e.g., Ready, High Potential, Needs Targeted Preparation

    executive_summary = Column(Text, nullable=False)
    
    # Serialized JSON structures
    question_analyses = Column(Text, nullable=False, default="[]")  # List of deep question analyses with quotes
    skill_gaps = Column(Text, nullable=False, default="[]")         # Evidence-linked gaps (CONFIRMED_WEAKNESS, UNCERTAIN, UNTESTED)
    strengths = Column(Text, nullable=False, default="[]")          # Evidence-backed strong areas
    untested_competencies = Column(Text, nullable=False, default="[]")
    
    roadmap_phases = Column(Text, nullable=False, default="[]")     # Sequenced learning phases
    roadmap_tasks = Column(Text, nullable=False, default="[]")       # Granular tasks with exercises & completion criteria
    reassessment_questions = Column(Text, nullable=False, default="[]") # Diagnostic retest questions
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    interview = relationship("Interview", back_populates="analysis_roadmap")
    user = relationship("User", back_populates="analysis_roadmaps")
