import json
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.models import User, Answer, Evaluation
from backend.utils.security import get_current_user
from backend.schemas.question import EvaluationResponse

router = APIRouter(prefix="/api/answers", tags=["Answers"])

@router.get("/interview/{interview_id}", response_model=List[Dict[str, Any]])
def get_answers_for_interview(
    interview_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    answers = (
        db.query(Answer)
        .filter(Answer.interview_id == interview_id, Answer.user_id == current_user.id)
        .order_by(Answer.submitted_at.asc())
        .all()
    )
    
    result = []
    for a in answers:
        ev = a.evaluation
        eval_resp = None
        if ev:
            strengths_list = json.loads(ev.strengths) if ev.strengths else []
            improvements_list = json.loads(ev.improvements) if ev.improvements else []
            eval_resp = {
                "id": ev.id,
                "answer_id": a.id,
                "score": ev.overall_score,
                "correctness": ev.technical_correctness,
                "technical_depth": ev.depth_of_understanding,
                "clarity": ev.structural_clarity,
                "completeness": ev.conceptual_completeness,
                "strengths": strengths_list,
                "weaknesses": improvements_list,
                "missing_points": improvements_list,
                "ideal_answer": ev.model_answer or "",
                "improvement_tip": improvements_list[0] if improvements_list else "",
                "evaluated_at": ev.created_at.isoformat() if ev.created_at else ""
            }
        result.append({
            "id": a.id,
            "interview_id": a.interview_id,
            "question_id": a.question_id,
            "user_id": a.user_id,
            "answer": a.answer_text,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else "",
            "evaluation": eval_resp
        })
        
    return result
