import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models.user import User
from backend.models.resume_analysis import ResumeJDAnalysis
from backend.schemas.resume_analysis import ResumeAnalysisResponse, ResumeJDAnalysisResult
from backend.services.ai_service import AIService
from backend.routes.auth import get_current_user
from backend.utils.pdf_extractor import extract_text_from_pdf

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/resume-analysis", tags=["Resume & JD Intelligence"])

def _format_analysis_response(record: ResumeJDAnalysis) -> ResumeAnalysisResponse:
    return ResumeAnalysisResponse(
        id=record.id,
        resume_filename=record.resume_filename,
        job_title=record.job_title,
        job_description=record.job_description,
        matched_skills=json.loads(record.matched_skills or "[]"),
        missing_skills=json.loads(record.missing_skills or "[]"),
        priority_skills=json.loads(record.priority_skills or "[]"),
        match_percentage=record.match_percentage,
        analysis_summary=record.analysis_summary or "",
        extracted_resume_skills=json.loads(record.extracted_resume_skills or "[]"),
        extracted_jd_skills=json.loads(record.extracted_jd_skills or "[]"),
        created_at=record.created_at
    )

@router.post("/analyze", response_model=ResumeAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def analyze_resume_and_jd(
    file: UploadFile = File(...),
    job_description: str = Form(...),
    job_title: Optional[str] = Form("Software Engineer"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload candidate PDF resume and Job Description text.
    Extracts skills, analyzes match, and stores results in PostgreSQL.
    """
    if not job_description or len(job_description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid Job Description with at least 10 characters."
        )

    # 1. Extract text securely from PDF file
    resume_text, filename = extract_text_from_pdf(file)

    # 2. Call GenAI / Heuristic Analysis Service
    analysis_result: ResumeJDAnalysisResult = await AIService.analyze_resume_and_jd(
        resume_text=resume_text,
        job_description=job_description,
        job_title=job_title or "Software Engineer"
    )

    # 3. Store analysis in DB
    analysis_record = ResumeJDAnalysis(
        user_id=current_user.id,
        resume_filename=filename,
        resume_text=resume_text,
        job_title=job_title or "Software Engineer",
        job_description=job_description,
        extracted_resume_skills=json.dumps(analysis_result.extracted_resume_skills),
        extracted_jd_skills=json.dumps(analysis_result.extracted_jd_skills),
        matched_skills=json.dumps(analysis_result.matched_skills),
        missing_skills=json.dumps(analysis_result.missing_skills),
        priority_skills=json.dumps(analysis_result.priority_skills),
        match_percentage=analysis_result.match_percentage,
        analysis_summary=analysis_result.analysis_summary
    )

    db.add(analysis_record)
    db.commit()
    db.refresh(analysis_record)

    logger.info(f"Resume+JD Analysis saved for user {current_user.id} with ID {analysis_record.id}")

    return _format_analysis_response(analysis_record)

@router.get("/user/latest", response_model=Optional[ResumeAnalysisResponse])
def get_latest_user_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns candidate's most recent Resume + JD analysis."""
    record = db.query(ResumeJDAnalysis).filter(
        ResumeJDAnalysis.user_id == current_user.id
    ).order_by(ResumeJDAnalysis.created_at.desc()).first()

    if not record:
        return None

    return _format_analysis_response(record)

@router.get("/{analysis_id}", response_model=ResumeAnalysisResponse)
def get_resume_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch specific Resume + JD analysis by ID."""
    record = db.query(ResumeJDAnalysis).filter(
        ResumeJDAnalysis.id == analysis_id,
        ResumeJDAnalysis.user_id == current_user.id
    ).first()

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Resume & Job Description analysis record not found"
        )

    return _format_analysis_response(record)
