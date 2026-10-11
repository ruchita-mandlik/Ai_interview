import json
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User, CandidateProfile
from backend.utils.security import hash_password, verify_password, create_access_token, get_current_user
from backend.utils.validators import validate_email, validate_password, validate_non_empty
from backend.schemas.auth import UserRegisterRequest, UserLoginRequest, UserResponse, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def _parse_skills(skills_str: Optional[str]) -> List[str]:
    if not skills_str:
        return ["Java", "OOP", "DSA", "SQL"]
    try:
        val = json.loads(skills_str)
        if isinstance(val, list):
            return [str(v) for v in val]
    except Exception:
        pass
    return [s.strip() for s in skills_str.split(",") if s.strip()]

def _build_user_response(user: User, profile: Optional[CandidateProfile] = None) -> UserResponse:
    target_role = profile.target_role if profile and profile.target_role else "Java Developer"
    experience_level = profile.experience_level if profile and profile.experience_level else "Intermediate"
    preferred_topics = _parse_skills(profile.skills if profile else None)

    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        target_role=target_role,
        experience_level=experience_level,
        preferred_topics=preferred_topics,
        created_at=user.created_at.isoformat() if user.created_at else ""
    )

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    clean_email = validate_email(req.email)
    clean_password = validate_password(req.password)
    clean_name = validate_non_empty(req.name, "Full Name")

    if req.confirm_password and req.password != req.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password and confirm password do not match"
        )

    # Check for duplicate email
    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists"
        )

    # Create User
    user = User(
        name=clean_name,
        email=clean_email,
        password_hash=hash_password(clean_password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Skills string
    skills_val = req.skills
    if req.preferred_topics:
        skills_val = ", ".join(req.preferred_topics)

    # Create Candidate Profile
    profile = CandidateProfile(
        user_id=user.id,
        full_name=user.name,
        email=user.email,
        target_role=req.target_role or "Java Developer",
        experience_level=req.experience_level or "Intermediate",
        skills=skills_val or "Java, OOP, DSA, SQL"
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(access_token=token, token_type="bearer", user=_build_user_response(user, profile))

@router.post("/login", response_model=TokenResponse)
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    clean_email = validate_email(req.email)
    user = db.query(User).filter(User.email == clean_email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email address or password"
        )

    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(access_token=token, token_type="bearer", user=_build_user_response(user, profile))

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    return _build_user_response(current_user, profile)
