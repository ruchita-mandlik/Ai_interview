import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User
from backend.utils.security import get_current_user
from backend.schemas.readiness import ReadinessIntelligenceResponse
from backend.services.readiness_service import ReadinessIntelligenceService

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/readiness", tags=["Readiness Intelligence"])

@router.get("", response_model=ReadinessIntelligenceResponse)
def get_readiness_intelligence(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves current multidimensional AI interview readiness intelligence for the candidate."""
    snapshot = ReadinessIntelligenceService.get_latest_readiness(db, current_user)
    return ReadinessIntelligenceService.to_response(snapshot)

@router.post("/recalculate", response_model=ReadinessIntelligenceResponse)
def recalculate_readiness_intelligence(
    target_role: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Recalculates evidence-based readiness score using latest interview, coding, and roadmap telemetry."""
    snapshot = ReadinessIntelligenceService.calculate_and_persist_readiness(
        db=db,
        user=current_user,
        target_role_override=target_role
    )
    return ReadinessIntelligenceService.to_response(snapshot)

@router.get("/history", response_model=List[ReadinessIntelligenceResponse])
def get_readiness_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves chronological history of readiness intelligence snapshots."""
    snapshots = ReadinessIntelligenceService.get_readiness_history(db, current_user)
    return [ReadinessIntelligenceService.to_response(s) for s in snapshots]
