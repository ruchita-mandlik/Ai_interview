import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database.database import Base

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    education = Column(String, nullable=True, default="Bachelor's Degree")
    skills = Column(Text, nullable=True, default="Java, OOP, DSA, SQL")  # Comma separated or JSON string
    experience_level = Column(String, nullable=False, default="Intermediate")
    target_role = Column(String, nullable=False, default="Java Developer")
    years_of_experience = Column(Integer, nullable=False, default=2)
    preferred_interview_type = Column(String, nullable=False, default="Technical")
    technical_interests = Column(Text, nullable=True, default="Backend, Cloud, Databases")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="candidate_profile")
