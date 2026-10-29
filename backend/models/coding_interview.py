import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database.database import Base

class CodingInterview(Base):
    __tablename__ = "coding_interviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    title = Column(String, nullable=False, default="AI Coding Interview")
    target_role = Column(String, nullable=False, default="Software Engineer")
    experience_level = Column(String, nullable=False, default="Intermediate")
    topic = Column(String, nullable=False, default="Data Structures & Algorithms")
    difficulty = Column(String, nullable=False, default="Medium")
    language = Column(String, nullable=False, default="python")
    
    status = Column(String, nullable=False, default="in_progress") # in_progress, completed
    total_score = Column(Float, nullable=True, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="coding_interviews")
    questions = relationship("CodingQuestion", back_populates="coding_interview", cascade="all, delete-orphan", order_by="CodingQuestion.question_number")
    submissions = relationship("CodingSubmission", back_populates="coding_interview", cascade="all, delete-orphan")


class CodingQuestion(Base):
    __tablename__ = "coding_questions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    coding_interview_id = Column(String, ForeignKey("coding_interviews.id", ondelete="CASCADE"), nullable=False)
    question_number = Column(Integer, nullable=False, default=1)
    
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False) # Problem description markdown
    input_format = Column(Text, nullable=True)
    output_format = Column(Text, nullable=True)
    constraints = Column(Text, nullable=True)
    starter_code = Column(Text, nullable=False) # Language-specific starter template
    sample_test_cases = Column(Text, nullable=False) # JSON string of list of sample test cases
    hidden_test_cases = Column(Text, nullable=False) # JSON string of list of hidden test cases
    
    skill = Column(String, nullable=True, default="Algorithms")
    difficulty = Column(String, nullable=False, default="Medium")
    hints = Column(Text, nullable=True) # JSON string list of progressive hints
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    coding_interview = relationship("CodingInterview", back_populates="questions")
    submissions = relationship("CodingSubmission", back_populates="coding_question", cascade="all, delete-orphan")


class CodingSubmission(Base):
    __tablename__ = "coding_submissions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    coding_interview_id = Column(String, ForeignKey("coding_interviews.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(String, ForeignKey("coding_questions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    language = Column(String, nullable=False, default="python")
    submitted_code = Column(Text, nullable=False)
    
    test_cases_passed = Column(Integer, nullable=False, default=0)
    total_test_cases = Column(Integer, nullable=False, default=0)
    test_case_results = Column(Text, nullable=True) # JSON array of detailed execution results
    
    coding_score = Column(Float, nullable=False, default=0.0)
    time_complexity = Column(String, nullable=True, default="O(N)")
    space_complexity = Column(String, nullable=True, default="O(1)")
    
    correctness_score = Column(Float, nullable=True, default=0.0)
    code_quality_score = Column(Float, nullable=True, default=0.0)
    edge_case_score = Column(Float, nullable=True, default=0.0)
    
    strengths = Column(Text, nullable=True) # JSON list
    detected_mistakes = Column(Text, nullable=True) # JSON list
    optimization_suggestions = Column(Text, nullable=True) # JSON list
    code_review = Column(Text, nullable=True)
    model_solution = Column(Text, nullable=True)
    
    submitted_at = Column(DateTime, default=datetime.utcnow)

    # Backward compatibility properties
    @property
    def question(self):
        return self.coding_question

    @property
    def code(self):
        return self.submitted_code

    # Relationships
    coding_interview = relationship("CodingInterview", back_populates="submissions")
    coding_question = relationship("CodingQuestion", back_populates="submissions")
    user = relationship("User", back_populates="coding_submissions")

