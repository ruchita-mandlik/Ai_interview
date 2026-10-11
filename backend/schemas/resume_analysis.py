from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class ResumeJDAnalysisResult(BaseModel):
    matched_skills: List[str] = Field(default_factory=list, description="Skills present in both resume and job description")
    missing_skills: List[str] = Field(default_factory=list, description="Required skills from job description missing in resume")
    priority_skills: List[str] = Field(default_factory=list, description="High-priority focus skills for interview personalization")
    match_percentage: float = Field(default=0.0, description="Overall match percentage between 0 and 100")
    analysis_summary: str = Field(default="", description="Detailed summary of candidate suitability and key focus areas")
    extracted_resume_skills: List[str] = Field(default_factory=list, description="All skills extracted from candidate resume")
    extracted_jd_skills: List[str] = Field(default_factory=list, description="All required skills extracted from Job Description")

class ResumeAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    resume_filename: str
    job_title: Optional[str] = "Software Engineer"
    job_description: str
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    priority_skills: List[str] = Field(default_factory=list)
    match_percentage: float
    analysis_summary: Optional[str] = ""
    extracted_resume_skills: List[str] = Field(default_factory=list)
    extracted_jd_skills: List[str] = Field(default_factory=list)
    created_at: datetime
