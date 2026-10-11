from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.models import User, Interview, InterviewQuestion
from backend.utils.security import get_current_user
from backend.schemas.question import QuestionResponse

router = APIRouter(prefix="/api/questions", tags=["Questions"])

@router.get("/interview/{interview_id}", response_model=List[QuestionResponse])
def get_questions_for_interview(
    interview_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview or interview.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Interview not found")
        
    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.interview_id == interview_id)
        .order_by(InterviewQuestion.question_number.asc())
        .all()
    )
    
    return [
        QuestionResponse(
            id=q.id,
            interview_id=q.interview_id,
            question=q.question_text,
            topic=q.category or q.skill or interview.topic,
            difficulty=q.difficulty,
            question_type="Technical",
            expected_points=[q.adaptation_reason] if q.adaptation_reason else [],
            created_at=q.created_at.isoformat() if q.created_at else ""
        )
        for q in questions
    ]
