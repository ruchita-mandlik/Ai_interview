from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict

class UserRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirm_password: Optional[str] = None
    target_role: Optional[str] = "Java Developer"
    experience_level: Optional[str] = "Intermediate"
    skills: Optional[str] = "Java, OOP, DSA, SQL"
    preferred_topics: Optional[List[str]] = None

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    target_role: Optional[str] = "Java Developer"
    experience_level: Optional[str] = "Intermediate"
    preferred_topics: Optional[List[str]] = ["Java", "OOP", "DSA", "SQL"]
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
