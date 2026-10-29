import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User, Interview
from backend.models.roadmap import InterviewAnalysisRoadmap
from backend.utils.security import get_current_user
from backend.schemas.roadmap import (
    DeepAnalysisRoadmapResponse,
    TaskStatusUpdateRequest,
    PreferencesUpdateRequest
)
from backend.services.deep_analysis_service import DeepAnalysisService
from backend.services.roadmap_pdf_service import RoadmapPDFService

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/analysis", tags=["Deep Interview Analysis & Roadmap"])

@router.get("/list/all", response_model=List[DeepAnalysisRoadmapResponse])
def list_user_roadmaps(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves all generated roadmaps for the current user."""
    roadmaps = db.query(InterviewAnalysisRoadmap).filter(
        InterviewAnalysisRoadmap.user_id == current_user.id
    ).order_by(InterviewAnalysisRoadmap.created_at.desc()).all()
    return [DeepAnalysisService.to_response(r) for r in roadmaps]

@router.post("/{interview_id}/generate", response_model=DeepAnalysisRoadmapResponse)
async def generate_deep_analysis_and_roadmap(
    interview_id: str,
    force_refresh: bool = Query(default=False),
    target_interview_date: Optional[str] = Query(default=None),
    daily_study_hours: Optional[float] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generates or retrieves deep interview performance analysis and personalized preparation roadmap."""
    roadmap = await DeepAnalysisService.get_or_generate_roadmap(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id,
        force_refresh=force_refresh,
        target_interview_date=target_interview_date,
        daily_study_hours=daily_study_hours
    )
    return DeepAnalysisService.to_response(roadmap)

@router.get("/latest", response_model=DeepAnalysisRoadmapResponse)
async def get_latest_analysis_and_roadmap(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves the most recent interview analysis and roadmap for the current user."""
    # First check if there is an existing roadmap
    latest_roadmap = db.query(InterviewAnalysisRoadmap).filter(
        InterviewAnalysisRoadmap.user_id == current_user.id
    ).order_by(InterviewAnalysisRoadmap.created_at.desc()).first()

    if latest_roadmap:
        return DeepAnalysisService.to_response(latest_roadmap)

    # If no roadmap exists yet, look for the most recent completed interview with answers
    latest_interview = db.query(Interview).filter(
        Interview.user_id == current_user.id,
        Interview.status == "completed"
    ).order_by(Interview.created_at.desc()).first()

    # Fallback to any interview session if none is marked completed yet
    if not latest_interview:
        latest_interview = db.query(Interview).filter(
            Interview.user_id == current_user.id
        ).order_by(Interview.created_at.desc()).first()

    if not latest_interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interview sessions found for candidate."
        )

    roadmap = await DeepAnalysisService.get_or_generate_roadmap(
        db=db,
        interview_id=latest_interview.id,
        user_id=current_user.id,
        force_refresh=False
    )
    return DeepAnalysisService.to_response(roadmap)

@router.get("/latest/export/pdf")
async def export_latest_roadmap_pdf(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generates and downloads a clean, publication-ready PDF for the candidate's latest roadmap."""
    latest_roadmap = db.query(InterviewAnalysisRoadmap).filter(
        InterviewAnalysisRoadmap.user_id == current_user.id
    ).order_by(InterviewAnalysisRoadmap.created_at.desc()).first()

    if not latest_roadmap:
        latest_interview = db.query(Interview).filter(
            Interview.user_id == current_user.id,
            Interview.status == "completed"
        ).order_by(Interview.created_at.desc()).first()

        if not latest_interview:
            latest_interview = db.query(Interview).filter(
                Interview.user_id == current_user.id
            ).order_by(Interview.created_at.desc()).first()

        if not latest_interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No preparation roadmap found. Please complete an interview first to generate a personalized roadmap."
            )

        try:
            latest_roadmap = await DeepAnalysisService.get_or_generate_roadmap(
                db=db,
                interview_id=latest_interview.id,
                user_id=current_user.id,
                force_refresh=False
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to generate latest roadmap for PDF: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate preparation roadmap for PDF export."
            )

    try:
        pdf_bytes = RoadmapPDFService.generate_roadmap_pdf(latest_roadmap, current_user)
    except Exception as e:
        logger.error(f"Error compiling PDF for latest roadmap: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compile PDF document."
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="InterviewAI_Roadmap_Analysis.pdf"'
        }
    )

@router.get("/{interview_id}/export/pdf")
async def export_interview_roadmap_pdf(
    interview_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generates and downloads a clean, publication-ready PDF for the specified interview roadmap."""
    if interview_id == "latest":
        return await export_latest_roadmap_pdf(current_user=current_user, db=db)

    roadmap = db.query(InterviewAnalysisRoadmap).filter(
        InterviewAnalysisRoadmap.interview_id == interview_id,
        InterviewAnalysisRoadmap.user_id == current_user.id
    ).first()

    if not roadmap:
        interview = db.query(Interview).filter(
            Interview.id == interview_id,
            Interview.user_id == current_user.id
        ).first()

        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview session '{interview_id}' not found. Please complete an interview first to generate a roadmap."
            )

        try:
            roadmap = await DeepAnalysisService.get_or_generate_roadmap(
                db=db,
                interview_id=interview_id,
                user_id=current_user.id,
                force_refresh=False
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to generate roadmap before PDF export: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate preparation roadmap for PDF export."
            )

    if not roadmap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preparation roadmap found for this session. Please generate or complete an interview first."
        )

    try:
        pdf_bytes = RoadmapPDFService.generate_roadmap_pdf(roadmap, current_user)
    except Exception as e:
        logger.error(f"Error compiling PDF for roadmap {roadmap.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compile PDF document."
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="InterviewAI_Roadmap_Analysis.pdf"'
        }
    )

@router.get("/{interview_id}", response_model=DeepAnalysisRoadmapResponse)
async def get_interview_analysis_and_roadmap(
    interview_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves post-interview analysis and preparation roadmap for a specific interview."""
    roadmap = await DeepAnalysisService.get_or_generate_roadmap(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id,
        force_refresh=False
    )
    return DeepAnalysisService.to_response(roadmap)

@router.patch("/{analysis_id}/task/{task_id}", response_model=DeepAnalysisRoadmapResponse)
async def update_roadmap_task_status(
    analysis_id: str,
    task_id: str,
    body: TaskStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates the status (pending, in_progress, completed) of a preparation roadmap task."""
    roadmap = DeepAnalysisService.update_task_status(
        db=db,
        roadmap_id=analysis_id,
        task_id=task_id,
        new_status=body.status,
        user_id=current_user.id
    )
    return DeepAnalysisService.to_response(roadmap)

@router.patch("/{analysis_id}/preferences", response_model=DeepAnalysisRoadmapResponse)
async def update_roadmap_preferences(
    analysis_id: str,
    body: PreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates target interview date and daily study hours with dynamic schedule recalibration."""
    roadmap = DeepAnalysisService.update_preferences(
        db=db,
        roadmap_id=analysis_id,
        user_id=current_user.id,
        target_interview_date=body.target_interview_date,
        daily_study_hours=body.daily_study_hours
    )
    return DeepAnalysisService.to_response(roadmap)
