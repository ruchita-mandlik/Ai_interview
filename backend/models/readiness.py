import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database.database import Base

class ReadinessIntelligenceSnapshot(Base):
    __tablename__ = "readiness_intelligence_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    target_role = Column(String, nullable=False, default="Software Developer")
    experience_level = Column(String, nullable=False, default="Intermediate")

    overall_readiness_score = Column(Float, nullable=False, default=0.0)
    readiness_stage = Column(String, nullable=False, default="Early Preparation")
    data_sufficiency = Column(String, nullable=False, default="INSUFFICIENT")  # INSUFFICIENT, MODERATE, HIGH, VERY_HIGH
    data_sufficiency_explanation = Column(Text, nullable=False)

    # Serialized JSON structures
    dimension_scores = Column(Text, nullable=False, default="{}")
    skill_scores = Column(Text, nullable=False, default="[]")
    persistent_weaknesses = Column(Text, nullable=False, default="[]")
    next_best_action = Column(Text, nullable=False, default="{}")
    evidence_breakdown = Column(Text, nullable=False, default="{}")
    historical_trend = Column(Text, nullable=False, default="[]")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="readiness_snapshots")
