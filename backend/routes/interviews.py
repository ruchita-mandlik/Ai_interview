from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User, Interview, Answer, Evaluation
from backend.utils.security import get_current_user
from backend.schemas.interview import (
    InterviewCreateRequest,
    InterviewResponse,
    QuestionSchema,
    SPAInterviewCreateResponse
)
from backend.schemas.answer import AnswerSubmitRequest
from backend.services.interview_service import InterviewService
from backend.services.ai_service import AIService

router = APIRouter(prefix="/api/interviews", tags=["Interviews"])

def _format_interview_response(interview: Interview, db: Session, user_name: Optional[str] = None) -> InterviewResponse:
    topics_list = [t.strip() for t in (interview.topic or "").split(",") if t.strip()]
    completed_answers_count = db.query(Answer).filter(Answer.interview_id == interview.id).count()
    mode = getattr(interview, "mode", "text") or "text"
    voice_name = getattr(interview, "voice_name", "default") or "default"
    intro_text = AIService.generate_interviewer_intro(interview.target_role, interview.topic, user_name)

    q_list = [
        QuestionSchema(
            id=q.id,
            interview_id=q.interview_id,
            question_number=q.question_number,
            question_text=q.question_text,
            question=q.question_text,
            category=q.category,
            topic=q.category or q.skill or interview.topic,
            skill=q.skill,
            difficulty=q.difficulty,
            question_type="Technical",
            expected_points=[q.adaptation_reason] if q.adaptation_reason else [],
            additional_instruction=q.additional_instruction,
            adaptation_reason=q.adaptation_reason,
            is_follow_up=bool(getattr(q, "is_follow_up", False)),
            parent_question_id=getattr(q, "parent_question_id", None),
            spoken_intro=f"Question #{q.question_number}: {q.question_text}",
            created_at=q.created_at.isoformat() if q.created_at else ""
        )
        for q in interview.questions
    ]

    return InterviewResponse(
        id=interview.id,
        user_id=interview.user_id,
        title=interview.title,
        interview_type=interview.interview_type,
        target_role=interview.target_role,
        role=interview.target_role,
        experience_level=interview.experience_level,
        topic=interview.topic,
        topics=topics_list if topics_list else [interview.topic],
        difficulty=interview.difficulty,
        num_questions=interview.num_questions,
        total_questions=interview.num_questions,
        completed_questions=completed_answers_count,
        status=interview.status,
        total_score=interview.total_score or 0.0,
        overall_score=interview.total_score or 0.0,
        duration_minutes=interview.duration_minutes,
        mode=mode,
        voice_name=voice_name,
        interviewer_intro=intro_text,
        created_at=interview.created_at.isoformat() if interview.created_at else "",
        started_at=interview.created_at.isoformat() if interview.created_at else "",
        completed_at=interview.created_at.isoformat() if interview.status == "completed" else None,
        questions=q_list
    )

@router.post("/start", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
async def start_interview(
    req: InterviewCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Legacy and multi-page endpoint for starting an interview session."""
    try:
        interview = await InterviewService.create_interview(db, current_user, req)
        return _format_interview_response(interview, db, current_user.name)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create interview: {str(e)}")

@router.post("", response_model=SPAInterviewCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_interview_spa(
    req: InterviewCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """React SPA endpoint for creating an interview session (supporting Voice Simulator and Written modes)."""
    try:
        interview = await InterviewService.create_interview(db, current_user, req)
        formatted = _format_interview_response(interview, db, current_user.name)
        first_q = formatted.questions[0] if formatted.questions else None
        return SPAInterviewCreateResponse(
            interview=formatted,
            first_question=first_q,
            interviewer_intro=formatted.interviewer_intro
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create interview: {str(e)}")

@router.get("", response_model=List[InterviewResponse])
def list_interviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    interviews = db.query(Interview).filter(Interview.user_id == current_user.id).order_by(Interview.created_at.desc()).all()
    return [_format_interview_response(i, db, current_user.name) for i in interviews]

@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    interview = InterviewService.get_interview(db, interview_id, current_user.id)
    return _format_interview_response(interview, db, current_user.name)

@router.post("/{interview_id}/answer")
async def submit_answer(
    interview_id: str,
    req: AnswerSubmitRequest,
    question_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    qid = question_id or req.question_id
    atext = req.get_answer()

    if not qid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question ID must be specified.")
    if not atext:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Answer text cannot be empty.")

    try:
        eval_result = await InterviewService.submit_answer(
            db=db,
            interview_id=interview_id,
            question_id=qid,
            user=current_user,
            answer_text=atext,
            transcript_raw=req.transcript_raw,
            is_voice_submission=bool(req.is_voice_submission),
            audio_duration_seconds=req.audio_duration_seconds
        )
        return eval_result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Answer submission failed: {str(e)}")

@router.post("/{interview_id}/next")
async def skip_interview_question(
    interview_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Skips the active question and adapts to the next question."""
    try:
        return await InterviewService.skip_question(db, interview_id, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to advance question: {str(e)}")

@router.post("/{interview_id}/complete")
def complete_interview(
    interview_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return InterviewService.complete_interview(db, interview_id, current_user.id)
