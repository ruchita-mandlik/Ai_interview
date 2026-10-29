import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models.user import User
from backend.models.interview import Interview
from backend.utils.security import get_current_user
from backend.schemas.intelligence import (
    MemorySummaryResponse,
    SessionComparisonResponse,
    AnalyticsDashboardResponse
)
from backend.services.interview_memory_service import InterviewMemoryService

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/intelligence", tags=["Intelligence & Memory"])


@router.get("/memory-summary", response_model=MemorySummaryResponse)
def get_user_memory_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the persistent interview memory and progress intelligence summary
    for the authenticated user. Guarantees strict user-level data isolation.
    """
    try:
        return InterviewMemoryService.get_user_memory_summary(db=db, user=current_user)
    except Exception as e:
        logger.error(f"Failed to compute memory summary for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve memory summary: {str(e)}"
        )


@router.get("/session-comparison/{interview_id}", response_model=SessionComparisonResponse)
def get_session_comparison(
    interview_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compares the specified interview session with the candidate's previous
    relevant interview session, highlighting score trends, repeated mistakes,
    and newly resolved weaknesses.
    """
    # Verify ownership
    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.user_id == current_user.id
    ).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found or does not belong to you."
        )

    try:
        return InterviewMemoryService.compare_session_to_previous(
            db=db,
            user_id=current_user.id,
            interview_id=interview_id
        )
    except Exception as e:
        logger.error(f"Failed to compute session comparison for interview {interview_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate session comparison: {str(e)}"
        )


@router.get("/analytics-dashboard", response_model=AnalyticsDashboardResponse)
def get_analytics_dashboard(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session_a_id: Optional[str] = None,
    session_b_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns full interactive analytics dashboard data with verified metrics,
    score trajectory, skill-wise performance, weakness frequency, distribution bins,
    and grouped session comparisons.
    """
    try:
        return InterviewMemoryService.get_analytics_dashboard(
            db=db,
            user=current_user,
            date_from=date_from,
            date_to=date_to,
            session_a_id=session_a_id,
            session_b_id=session_b_id
        )
    except Exception as e:
        logger.error(f"Failed to generate analytics dashboard for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate analytics dashboard: {str(e)}"
        )
