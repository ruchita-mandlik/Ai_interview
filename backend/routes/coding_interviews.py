import json
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User, CodingInterview, CodingQuestion, CodingSubmission
from backend.schemas.coding_interview import (
    CodingInterviewCreateRequest,
    CodeRunRequest,
    CustomRunRequest,
    CustomRunResultSchema,
    CodingSubmissionRequest,
    CodeRunResultSchema,
    CodingInterviewResponse,
    CodingQuestionSchema,
    CodingSubmissionResultSchema
)
from backend.services.coding_service import CodingService
from backend.utils.security import get_current_user

router = APIRouter(prefix="/api/coding", tags=["Coding Interviews"])

@router.post("/start", response_model=CodingInterviewResponse, status_code=status.HTTP_201_CREATED)
async def start_coding_interview(
    req: CodingInterviewCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    interview = await CodingService.create_coding_interview(db, current_user, req)
    return build_coding_interview_response(interview)


@router.get("/list", response_model=List[CodingInterviewResponse])
def list_coding_interviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns all coding assessments created by the authenticated user."""
    interviews = CodingService.list_coding_interviews(db, current_user.id)
    return [build_coding_interview_response(i) for i in interviews]


@router.get("/{interview_id}", response_model=CodingInterviewResponse)
def get_coding_interview(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    interview = CodingService.get_coding_interview(db, interview_id, current_user.id)
    return build_coding_interview_response(interview)


@router.post("/{interview_id}/next", response_model=CodingQuestionSchema)
async def generate_next_coding_problem(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates the next DSA problem in the existing coding interview session."""
    question = await CodingService.generate_next_problem(db, interview_id, current_user)
    return build_coding_question_schema(question)


@router.post("/run-tests", response_model=CodeRunResultSchema)
def run_sample_tests(
    req: CodeRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Runs candidate code against sample test cases and optional custom input in isolated sandbox."""
    return CodingService.run_sample_tests(db, req, current_user)


@router.post("/run-custom", response_model=CustomRunResultSchema)
def run_custom_input(
    req: CustomRunRequest,
    current_user: User = Depends(get_current_user)
):
    """Executes arbitrary code against candidate-supplied custom input string."""
    return CodingService.run_custom_input(req)


@router.post("/submit", response_model=CodingSubmissionResultSchema)
async def submit_coding_solution(
    req: CodingSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Executes full test suite (sample + hidden) and evaluates solution using real test evidence plus GenAI."""
    submission = await CodingService.submit_coding_solution(db, req, current_user)
    return build_submission_schema(submission)


@router.get("/{interview_id}/results", response_model=CodingSubmissionResultSchema)
def get_coding_results(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    interview = CodingService.get_coding_interview(db, interview_id, current_user.id)
    sub = db.query(CodingSubmission).filter(
        CodingSubmission.coding_interview_id == interview.id,
        CodingSubmission.user_id == current_user.id
    ).order_by(CodingSubmission.submitted_at.desc()).first()

    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No coding submission found for this interview")

    return build_submission_schema(sub)


def build_submission_schema(sub: CodingSubmission) -> CodingSubmissionResultSchema:
    test_results_raw = json.loads(sub.test_case_results or "[]")
    strengths_raw = json.loads(sub.strengths or "[]")
    mistakes_raw = json.loads(sub.detected_mistakes or "[]")
    suggestions_raw = json.loads(sub.optimization_suggestions or "[]")

    return CodingSubmissionResultSchema(
        id=sub.id,
        question_id=sub.question_id,
        language=sub.language,
        submitted_code=sub.submitted_code,
        test_cases_passed=sub.test_cases_passed,
        total_test_cases=sub.total_test_cases,
        test_case_results=test_results_raw,
        coding_score=sub.coding_score,
        time_complexity=sub.time_complexity or "O(N)",
        space_complexity=sub.space_complexity or "O(1)",
        correctness_score=sub.correctness_score or 0.0,
        code_quality_score=sub.code_quality_score or 0.0,
        edge_case_score=sub.edge_case_score or 0.0,
        strengths=strengths_raw,
        detected_mistakes=mistakes_raw,
        optimization_suggestions=suggestions_raw,
        code_review=sub.code_review or "",
        model_solution=sub.model_solution or "",
        submitted_at=sub.submitted_at.isoformat() if sub.submitted_at else ""
    )


def build_coding_question_schema(q: CodingQuestion) -> CodingQuestionSchema:
    hints_list = []
    if getattr(q, "hints", None):
        try:
            hints_list = json.loads(q.hints)
        except Exception:
            hints_list = [q.hints]

    return CodingQuestionSchema(
        id=q.id,
        question_number=q.question_number,
        title=q.title,
        description=q.description,
        input_format=q.input_format,
        output_format=q.output_format,
        constraints=q.constraints,
        starter_code=q.starter_code,
        hints=hints_list if isinstance(hints_list, list) else [],
        sample_test_cases=json.loads(q.sample_test_cases or "[]"),
        skill=q.skill,
        difficulty=q.difficulty
    )


def build_coding_interview_response(interview: CodingInterview) -> CodingInterviewResponse:
    q_schemas = [build_coding_question_schema(q) for q in interview.questions]
    sub_schemas = [build_submission_schema(s) for s in interview.submissions]

    return CodingInterviewResponse(
        id=interview.id,
        user_id=interview.user_id,
        title=interview.title,
        target_role=interview.target_role,
        experience_level=interview.experience_level,
        topic=interview.topic,
        difficulty=interview.difficulty,
        language=interview.language,
        status=interview.status,
        total_score=interview.total_score or 0.0,
        created_at=interview.created_at.isoformat() if interview.created_at else "",
        questions=q_schemas,
        submissions=sub_schemas
    )
