from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict

class CandidateProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    education: Optional[str] = None
    skills: Optional[str] = None
    experience_level: Optional[str] = None
    target_role: Optional[str] = None
    years_of_experience: Optional[int] = None
    preferred_interview_type: Optional[str] = None
    technical_interests: Optional[str] = None

class CandidateProfileResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    email: str
    education: Optional[str] = "Bachelor's Degree"
    skills: Optional[str] = "Java, OOP, DSA, SQL"
    experience_level: Optional[str] = "Intermediate"
    target_role: Optional[str] = "Java Developer"
    years_of_experience: Optional[int] = 2
    preferred_interview_type: Optional[str] = "Technical"
    technical_interests: Optional[str] = "Backend, Cloud, Databases"

    model_config = ConfigDict(from_attributes=True)
