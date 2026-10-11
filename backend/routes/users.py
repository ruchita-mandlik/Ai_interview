import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User, CandidateProfile
from backend.utils.security import get_current_user
from backend.schemas.user import UserResponse, UserProfileUpdate

router = APIRouter(prefix="/api/users", tags=["Users"])

def parse_topics(skills_str: Optional[str]) -> List[str]:
    if not skills_str:
        return ["Java", "OOP", "DSA", "SQL"]
    try:
        # Check if json list
        val = json.loads(skills_str)
        if isinstance(val, list):
            return [str(v) for v in val]
    except Exception:
        pass
    # Comma-separated
    return [s.strip() for s in skills_str.split(",") if s.strip()]

@router.get("/profile", response_model=UserResponse)
def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    if not profile:
        profile = CandidateProfile(
            user_id=current_user.id,
            full_name=current_user.name,
            email=current_user.email,
            target_role="Java Developer",
            experience_level="Intermediate",
            skills="Java, OOP, DSA, SQL"
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        target_role=profile.target_role or "Java Developer",
        experience_level=profile.experience_level or "Intermediate",
        preferred_topics=parse_topics(profile.skills),
        created_at=current_user.created_at.isoformat() if current_user.created_at else ""
    )

@router.put("/profile", response_model=UserResponse)
def update_user_profile(
    req: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    if not profile:
        profile = CandidateProfile(
            user_id=current_user.id,
            full_name=current_user.name,
            email=current_user.email
        )
        db.add(profile)

    if req.name is not None and req.name.strip():
        current_user.name = req.name.strip()
        profile.full_name = req.name.strip()

    if req.target_role is not None:
        profile.target_role = req.target_role.strip()

    if req.experience_level is not None:
        profile.experience_level = req.experience_level.strip()

    if req.preferred_topics is not None:
        profile.skills = ", ".join(req.preferred_topics)

    db.commit()
    db.refresh(current_user)
    db.refresh(profile)

    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        target_role=profile.target_role or "Java Developer",
        experience_level=profile.experience_level or "Intermediate",
        preferred_topics=parse_topics(profile.skills),
        created_at=current_user.created_at.isoformat() if current_user.created_at else ""
    )
