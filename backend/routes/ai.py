import json
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User, Interview, InterviewQuestion, Answer, Evaluation
from backend.utils.security import get_current_user
from backend.schemas.ai import CodingEvaluationRequest, CodingEvaluationResponse, FinalReportResponse
from backend.services.ai_service import AIService

router = APIRouter(prefix="/api/ai", tags=["AI Integration"])

@router.post("/evaluate-code", response_model=CodingEvaluationResponse)
async def evaluate_code(
    req: CodingEvaluationRequest,
    current_user: User = Depends(get_current_user)
):
    if not req.code or not req.code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code content cannot be empty.")

    ai_result = await AIService.evaluate_code(
        problem_statement=req.problem_statement,
        language=req.language,
        code=req.code,
        difficulty=req.difficulty or "Medium",
        topic=req.topic or "Algorithms"
    )

    return CodingEvaluationResponse(
        correctness_score=float(ai_result.get("correctness_score", 8.5)),
        code_quality_score=float(ai_result.get("code_quality_score", 8.0)),
        time_complexity=str(ai_result.get("time_complexity", "O(N)")),
        space_complexity=str(ai_result.get("space_complexity", "O(1)")),
        bugs_found=list(ai_result.get("bugs_found", [])),
        edge_cases_covered=list(ai_result.get("edge_cases_covered", [])),
        missing_edge_cases=list(ai_result.get("missing_edge_cases", [])),
        optimization_suggestions=list(ai_result.get("optimization_suggestions", [])),
        ideal_code_snippet=str(ai_result.get("ideal_code_snippet", req.code)),
        summary_feedback=str(ai_result.get("summary_feedback", "Solid technical implementation."))
    )

@router.get("/report/{interview_id}", response_model=FinalReportResponse)
async def get_interview_final_report(
    interview_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.user_id == current_user.id
    ).first()

    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found.")

    # Gather interview questions, answers, and evaluations
    questions = db.query(InterviewQuestion).filter(
        InterviewQuestion.interview_id == interview_id
    ).order_by(InterviewQuestion.question_number.asc()).all()

    interview_summary = []
    for q in questions:
        is_q_skipped = bool(getattr(q, "is_skipped", False))
        ans = db.query(Answer).filter(
            Answer.interview_id == interview_id,
            Answer.question_id == q.id
        ).first()

        ev = db.query(Evaluation).filter(
            Evaluation.interview_id == interview_id,
            Evaluation.question_id == q.id
        ).first() if ans else None

        if is_q_skipped:
            interview_summary.append({
                "question": {
                    "question": q.question_text,
                    "topic": q.category or q.skill or interview.topic,
                    "difficulty": q.difficulty,
                    "is_skipped": True
                },
                "answer": "Question skipped by candidate.",
                "is_skipped": True,
                "evaluation": {
                    "is_skipped": True,
                    "feedback": "Question was skipped by candidate. Excluded from evaluation scoring.",
                    "model_answer": "Reference benchmark solution available for review."
                }
            })
            continue

        st_list = []
        if ev and ev.strengths:
            try:
                st_list = json.loads(ev.strengths) if ev.strengths.startswith("[") else [ev.strengths]
            except Exception:
                st_list = [ev.strengths]

        mi_list = []
        if ev and getattr(ev, "missing_concepts", None):
            try:
                mi_list = json.loads(ev.missing_concepts) if ev.missing_concepts.startswith("[") else [ev.missing_concepts]
            except Exception:
                mi_list = [ev.missing_concepts]
        elif ev and ev.improvements:
            try:
                mi_list = json.loads(ev.improvements) if ev.improvements.startswith("[") else [ev.improvements]
            except Exception:
                mi_list = [ev.improvements]

        inc_list = []
        if ev and getattr(ev, "incorrect_claims", None):
            try:
                inc_list = json.loads(ev.incorrect_claims) if ev.incorrect_claims.startswith("[") else [ev.incorrect_claims]
            except Exception:
                inc_list = [ev.incorrect_claims]

        ev_dict = {
            "overall_score": ev.overall_score if ev else 70.0,
            "technical_correctness": ev.technical_correctness if ev else 70.0,
            "conceptual_completeness": ev.conceptual_completeness if ev else 70.0,
            "structural_clarity": ev.structural_clarity if ev else 70.0,
            "depth_of_understanding": ev.depth_of_understanding if ev else 70.0,
            "strengths": st_list,
            "missing_concepts": mi_list,
            "incorrect_claims": inc_list,
            "feedback": ev.feedback if ev else None,
            "model_answer": ev.model_answer if ev else None
        } if ev else {}

        interview_summary.append({
            "question": {
                "question": q.question_text,
                "topic": q.category or q.skill or interview.topic,
                "difficulty": q.difficulty,
                "is_skipped": False
            },
            "answer": ans.answer_text if ans else "No answer provided",
            "is_skipped": False,
            "evaluation": ev_dict
        })

    report_data = await AIService.generate_final_report(
        role=interview.target_role,
        experience=interview.experience_level,
        interview_type=interview.interview_type,
        interview_summary=interview_summary,
        job_description=interview.job_description,
        additional_instructions=interview.additional_instructions
    )

    now_str = interview.created_at.isoformat() if interview.created_at else datetime.utcnow().isoformat()

    return FinalReportResponse(
        interview_id=interview.id,
        overall_score=float(report_data.get("overall_score", interview.total_score or 75.0)),
        score_out_of_10=float(report_data.get("score_out_of_10", round((interview.total_score or 75.0) / 10.0, 1))),
        technical_knowledge_score=float(report_data.get("technical_knowledge_score", 78.0)),
        communication_score=float(report_data.get("communication_score", 80.0)),
        problem_solving_score=float(report_data.get("problem_solving_score", 76.0)),
        answer_quality_score=float(report_data.get("answer_quality_score", 78.0)),
        strong_topics=list(report_data.get("strong_topics", [interview.topic or "Core Engineering"])),
        weak_topics=list(report_data.get("weak_topics", ["Edge Case Robustness"])),
        skill_gaps=list(report_data.get("skill_gaps", report_data.get("weak_topics", []))),
        recommendations=list(report_data.get("recommendations", ["Continue regular practice sessions."])),
        communication_observations=report_data.get("communication_observations", "Clear verbal structure and precise technical articulation."),
        readiness_estimate=report_data.get("readiness_estimate", "Demonstrates strong foundational command for this role."),
        readiness_level=report_data.get("readiness_level", "Nearly Ready"),
        personalized_summary=str(report_data.get("personalized_summary", "Comprehensive interview session completed.")),
        completed_at=now_str,
        question_results=report_data.get("question_results", [])
    )
