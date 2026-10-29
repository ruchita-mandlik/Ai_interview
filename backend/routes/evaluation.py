import json
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User, Interview, Answer, Evaluation, InterviewQuestion
from backend.utils.security import get_current_user
from backend.services.interview_service import InterviewService

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])

@router.get("/interview/{interview_id}")
def get_interview_evaluations(
    interview_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    evaluations = db.query(Evaluation).filter(Evaluation.interview_id == interview_id).all()
    results = []

    for ev in evaluations:
        q = db.query(InterviewQuestion).filter(InterviewQuestion.id == ev.question_id).first()
        ans = db.query(Answer).filter(Answer.id == ev.answer_id).first()

        strengths_list = json.loads(ev.strengths) if ev.strengths else []
        improvements_list = json.loads(ev.improvements) if ev.improvements else []

        results.append({
            "evaluation_id": ev.id,
            "question_number": q.question_number if q else 1,
            "question_text": q.question_text if q else "",
            "candidate_answer": ans.answer_text if ans else "",
            "technical_correctness": ev.technical_correctness,
            "conceptual_completeness": ev.conceptual_completeness,
            "response_relevance": ev.response_relevance,
            "structural_clarity": ev.structural_clarity,
            "depth_of_understanding": ev.depth_of_understanding,
            "overall_score": ev.overall_score,
            "strengths": strengths_list,
            "improvements": improvements_list,
            "feedback": ev.feedback or "",
            "actionable_feedback": ev.actionable_feedback or "",
            "model_answer": ev.model_answer or ""
        })

    skipped_questions = db.query(InterviewQuestion).filter(
        InterviewQuestion.interview_id == interview_id,
        InterviewQuestion.is_skipped == True
    ).order_by(InterviewQuestion.question_number.asc()).all()

    skipped_results = [
        {
            "question_id": sq.id,
            "question_number": sq.question_number,
            "question_text": sq.question_text,
            "category": sq.category or sq.skill or interview.topic,
            "difficulty": sq.difficulty,
            "is_skipped": True,
            "status": "skipped",
            "adaptation_reason": sq.adaptation_reason or "Question skipped by candidate."
        }
        for sq in skipped_questions
    ]

    if interview.status == "completed" and (interview.total_score is None or interview.total_score == 0.0) and len(evaluations) > 0:
        interview.total_score = InterviewService.calculate_interview_final_score(db, interview.id)
        db.commit()

    session_comparison = None
    if interview.status == "completed":
        try:
            from backend.services.interview_memory_service import InterviewMemoryService
            comp = InterviewMemoryService.compare_session_to_previous(db, current_user.id, interview.id)
            session_comparison = comp.model_dump()
        except Exception:
            session_comparison = None

    return {
        "interview_id": interview.id,
        "title": interview.title,
        "total_score": interview.total_score,
        "status": interview.status,
        "evaluations": results,
        "skipped_questions": skipped_results,
        "session_comparison": session_comparison
    }

@router.get("/answer/{answer_id}")
def get_answer_evaluation(
    answer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    answer = db.query(Answer).filter(Answer.id == answer_id).first()
    if not answer or answer.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Answer not found")

    ev = db.query(Evaluation).filter(Evaluation.answer_id == answer_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluation not yet generated for this answer")

    q = db.query(InterviewQuestion).filter(InterviewQuestion.id == ev.question_id).first()

    return {
        "evaluation_id": ev.id,
        "question_text": q.question_text if q else "",
        "candidate_answer": answer.answer_text,
        "technical_correctness": ev.technical_correctness,
        "conceptual_completeness": ev.conceptual_completeness,
        "response_relevance": ev.response_relevance,
        "structural_clarity": ev.structural_clarity,
        "depth_of_understanding": ev.depth_of_understanding,
        "overall_score": ev.overall_score,
        "strengths": json.loads(ev.strengths) if ev.strengths else [],
        "improvements": json.loads(ev.improvements) if ev.improvements else [],
        "feedback": ev.feedback or "",
        "actionable_feedback": ev.actionable_feedback or "",
        "model_answer": ev.model_answer or ""
    }
