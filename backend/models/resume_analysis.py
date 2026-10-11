import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.database import Base

class ResumeJDAnalysis(Base):
    __tablename__ = "resume_jd_analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    resume_filename = Column(String, nullable=False, default="resume.pdf")
    resume_text = Column(Text, nullable=False)
    job_title = Column(String, nullable=True, default="Software Engineer")
    job_description = Column(Text, nullable=False)

    extracted_resume_skills = Column(Text, nullable=True)  # JSON array string
    extracted_jd_skills = Column(Text, nullable=True)      # JSON array string
    matched_skills = Column(Text, nullable=True)            # JSON array string
    missing_skills = Column(Text, nullable=True)            # JSON array string
    priority_skills = Column(Text, nullable=True)           # JSON array string

    match_percentage = Column(Float, nullable=False, default=0.0)
    analysis_summary = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="resume_analyses")
    interviews = relationship("Interview", back_populates="resume_analysis")
