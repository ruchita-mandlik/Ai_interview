from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User, CandidateProfile
from backend.utils.security import get_current_user
from backend.schemas.ai import PreparationPlanResponse, PreparationPlanDay, RecommendationResponse
from backend.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])

@router.get("/plan", response_model=PreparationPlanResponse)
async def get_preparation_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    role = profile.target_role if profile and profile.target_role else "Software Developer"
    experience = profile.experience_level if profile and profile.experience_level else "Intermediate"

    rec_doc = await RecommendationService.get_or_generate_plan(
        db=db,
        user_id=current_user.id,
        role=role,
        experience=experience
    )

    raw_plan = rec_doc.get("plan", [])
    plan_days = []
    for item in raw_plan:
        plan_days.append(PreparationPlanDay(
            day=int(item.get("day", 1)),
            topic=item.get("topic", "Core Fundamentals"),
            concepts=item.get("concepts", []),
            practice_questions=item.get("practice_questions", []),
            difficulty=item.get("difficulty", "Medium"),
            estimated_time=item.get("estimated_time", "2 Hours")
        ))

    return PreparationPlanResponse(
        user_id=current_user.id,
        created_at=rec_doc.get("updated_at", datetime.utcnow().isoformat()),
        plan=plan_days,
        overall_readiness_assessment=rec_doc.get("overall_readiness_assessment", "Your readiness plan is ready.")
    )

@router.get("", response_model=RecommendationResponse)
async def get_general_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    role = profile.target_role if profile and profile.target_role else "Software Developer"
    experience = profile.experience_level if profile and profile.experience_level else "Intermediate"

    rec_doc = await RecommendationService.get_or_generate_plan(
        db=db,
        user_id=current_user.id,
        role=role,
        experience=experience
    )

    return RecommendationResponse(
        recommended_topics=rec_doc.get("recommended_topics", ["Algorithms", "System Design"]),
        recommended_questions=rec_doc.get("recommended_questions", []),
        recommended_difficulty=rec_doc.get("recommended_difficulty", "Medium"),
        study_priorities=rec_doc.get("study_priorities", ["Algorithms", "System Design"])
    )
