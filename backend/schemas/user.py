from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    target_role: Optional[str] = "Software Developer"
    experience_level: Optional[str] = "Intermediate"
    preferred_topics: Optional[List[str]] = []

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    target_role: Optional[str] = None
    experience_level: Optional[str] = None
    preferred_topics: Optional[List[str]] = None

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    target_role: str
    experience_level: str
    preferred_topics: List[str]
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
