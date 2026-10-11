from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict

class CodingInterviewCreateRequest(BaseModel):
    target_role: str = Field(default="Software Engineer", description="Target job role")
    experience_level: str = Field(default="Intermediate", description="Beginner, Intermediate, Advanced")
    topic: str = Field(default="Data Structures & Algorithms", description="Topic/skills (DSA, Backend, Web APIs, System Logic)")
    difficulty: str = Field(default="Medium", description="Easy, Medium, Hard")
    language: str = Field(default="python", description="python, javascript, java, cpp")

class CodeRunRequest(BaseModel):
    question_id: str
    language: str = Field(default="python")
    code: str

class CodingSubmissionRequest(BaseModel):
    question_id: str
    language: str = Field(default="python")
    code: str

class TestCaseResultSchema(BaseModel):
    test_case_index: int
    input: str
    expected_output: str
    actual_output: str
    passed: bool
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    stdout: Optional[str] = None

class CodeRunResultSchema(BaseModel):
    total_test_cases: int
    passed_test_cases: int
    all_passed: bool
    results: List[TestCaseResultSchema]

class CodingQuestionSchema(BaseModel):
    id: str
    question_number: int
    title: str
    description: str
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    constraints: Optional[str] = None
    starter_code: str
    sample_test_cases: List[Dict[str, Any]] = []
    skill: Optional[str] = "Algorithms"
    difficulty: str

    model_config = ConfigDict(from_attributes=True)

class CodingSubmissionResultSchema(BaseModel):
    id: str
    question_id: str
    language: str
    submitted_code: str
    test_cases_passed: int
    total_test_cases: int
    test_case_results: List[TestCaseResultSchema] = []
    coding_score: float
    time_complexity: str
    space_complexity: str
    correctness_score: float
    code_quality_score: float
    edge_case_score: float
    strengths: List[str] = []
    detected_mistakes: List[str] = []
    optimization_suggestions: List[str] = []
    code_review: str
    model_solution: str
    submitted_at: str

class CodingInterviewResponse(BaseModel):
    id: str
    user_id: str
    title: str
    target_role: str
    experience_level: str
    topic: str
    difficulty: str
    language: str
    status: str
    total_score: Optional[float] = 0.0
    created_at: str
    questions: List[CodingQuestionSchema] = []
    submissions: List[CodingSubmissionResultSchema] = []

    model_config = ConfigDict(from_attributes=True)
