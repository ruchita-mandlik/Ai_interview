import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.database import Base

class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_id = Column(String, ForeignKey("answers.id", ondelete="CASCADE"), unique=True, nullable=False)
    interview_id = Column(String, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(String, ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False)
    
    technical_correctness = Column(Float, nullable=False, default=0.0)  # Weight 35%
    conceptual_completeness = Column(Float, nullable=False, default=0.0) # Weight 25%
    response_relevance = Column(Float, nullable=False, default=0.0)     # Weight 15%
    structural_clarity = Column(Float, nullable=False, default=0.0)     # Weight 15%
    depth_of_understanding = Column(Float, nullable=False, default=0.0) # Weight 10%
    
    overall_score = Column(Float, nullable=False, default=0.0)
    
    strengths = Column(Text, nullable=True)     # JSON formatted array string
    improvements = Column(Text, nullable=True)  # JSON formatted array string
    missing_concepts = Column(Text, nullable=True) # JSON formatted array string
    incorrect_claims = Column(Text, nullable=True) # JSON formatted array string
    feedback = Column(Text, nullable=True)
    actionable_feedback = Column(Text, nullable=True)
    model_answer = Column(Text, nullable=True)
    communication_notes = Column(Text, nullable=True)
    evaluation_type = Column(String, nullable=True, default="technical")
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    answer = relationship("Answer", back_populates="evaluation")
    interview = relationship("Interview", back_populates="evaluations")
    question = relationship("InterviewQuestion", back_populates="evaluations")
