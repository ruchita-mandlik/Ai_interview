from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from backend.models import User
from backend.services.interview_service import InterviewService

class EvaluationService:
    @staticmethod
    async def process_answer(
        db: Session,
        interview_id: str,
        question_id: str,
        user: User,
        user_answer: str
    ) -> Dict[str, Any]:
        """
        Processes answer submission using InterviewService and AI adaptive evaluations.
        """
        return await InterviewService.submit_answer(
            db=db,
            interview_id=interview_id,
            question_id=question_id,
            user=user,
            answer_text=user_answer
        )
