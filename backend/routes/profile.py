from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User, CandidateProfile
from backend.utils.security import get_current_user
from backend.schemas.profile import CandidateProfileUpdate, CandidateProfileResponse

router = APIRouter(prefix="/api/profile", tags=["Candidate Profile"])

@router.get("", response_model=CandidateProfileResponse)
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    if not profile:
        profile = CandidateProfile(
            user_id=current_user.id,
            full_name=current_user.name,
            email=current_user.email
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile

@router.put("/update", response_model=CandidateProfileResponse)
@router.post("/update", response_model=CandidateProfileResponse)
def update_profile(
    req: CandidateProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    if not profile:
        profile = CandidateProfile(user_id=current_user.id, full_name=current_user.name, email=current_user.email)
        db.add(profile)

    if req.full_name is not None:
        profile.full_name = req.full_name.strip()
        current_user.name = req.full_name.strip()
    if req.email is not None:
        profile.email = req.email.strip()
    if req.education is not None:
        profile.education = req.education
    if req.skills is not None:
        profile.skills = req.skills
    if req.experience_level is not None:
        profile.experience_level = req.experience_level
    if req.target_role is not None:
        profile.target_role = req.target_role
    if req.years_of_experience is not None:
        profile.years_of_experience = req.years_of_experience
    if req.preferred_interview_type is not None:
        profile.preferred_interview_type = req.preferred_interview_type
    if req.technical_interests is not None:
        profile.technical_interests = req.technical_interests

    db.commit()
    db.refresh(profile)
    return profile
