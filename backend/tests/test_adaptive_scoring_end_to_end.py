import pytest
from unittest.mock import patch, AsyncMock
from backend.models.interview import Interview
from backend.models.question import InterviewQuestion
from backend.models.evaluation import Evaluation
from backend.models.answer import Answer
from backend.schemas.evaluation import AIEvaluationResult
from backend.services.interview_service import InterviewService


@pytest.fixture
def auth_header_scoring(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "Scoring Verification Engineer",
            "email": "scoring.engineer@interviewai.io",
            "password": "Password123!"
        }
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_adaptive_scoring_high_scores_5_questions(mock_eval, mock_adaptive_q, client, auth_header_scoring, db_session):
    """
    Verifies end-to-end scoring when all 5 adaptive questions are answered with high scores.
    Expected: Individual evaluations are saved, aggregated accurately to 90.0%, and persisted to DB.
    """
    # 1. Start adaptive interview with 5 questions
    start_resp = client.post(
        "/api/interviews/adaptive/start",
        headers=auth_header_scoring,
        json={
            "target_role": "Senior Distributed Systems Engineer",
            "experience_level": "Senior",
            "topic": "Distributed Consensus",
            "difficulty": "Hard",
            "num_questions": 5
        }
    )
    assert start_resp.status_code == 201
    interview_data = start_resp.json()
    interview_id = interview_data["id"]
    q1 = interview_data["questions"][0]

    # Scores for 5 questions: 90, 85, 95, 88, 92 -> average = 90.0%
    scores = [90.0, 85.0, 95.0, 88.0, 92.0]
    current_q_id = q1["id"]

    for idx, expected_score in enumerate(scores, start=1):
        mock_eval.return_value = AIEvaluationResult(
            technical_correctness=expected_score,
            conceptual_completeness=expected_score,
            response_relevance=expected_score,
            structural_clarity=expected_score,
            depth_of_understanding=expected_score,
            overall_score=expected_score,
            strengths=[f"Strong mastery on Question {idx}."],
            improvements=[],
            feedback=f"High quality answer on Question {idx}.",
            model_answer="Reference implementation."
        )

        next_q_num = idx + 1
        mock_adaptive_q.return_value = {
            "question": f"Adaptive Question #{next_q_num} on consensus trade-offs.",
            "category": "Distributed Systems",
            "skill": "Consensus",
            "difficulty": "Hard",
            "additional_instruction": "Analyze Raft vs Paxos.",
            "adaptation_reason": f"Strong score {expected_score}% on Q{idx}."
        }

        ans_resp = client.post(
            f"/api/interviews/{interview_id}/answer",
            headers=auth_header_scoring,
            json={
                "question_id": current_q_id,
                "answer_text": f"Detailed architectural explanation of consensus protocol for question {idx}."
            }
        )
        assert ans_resp.status_code == 200
        ans_data = ans_resp.json()

        if idx < 5:
            assert ans_data["is_last_question"] is False
            assert ans_data["interview_completed"] is False
            assert ans_data["next_question"] is not None
            current_q_id = ans_data["next_question"]["id"]
        else:
            # 5th question is the terminal question
            assert ans_data["is_last_question"] is True
            assert ans_data["interview_completed"] is True
            assert ans_data["total_score"] == 90.0
            assert ans_data["final_score"] == 90.0
            assert ans_data["status"] == "completed"

    # 2. Verify database persistence
    db_session.expire_all()
    inv_db = db_session.query(Interview).filter(Interview.id == interview_id).first()
    assert inv_db is not None
    assert inv_db.status == "completed"
    assert inv_db.total_score == 90.0

    # 3. Verify GET /api/interviews/{id} returns the 90.0% score
    get_resp = client.get(f"/api/interviews/{interview_id}", headers=auth_header_scoring)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["total_score"] == 90.0
    assert get_data["overall_score"] == 90.0
    assert get_data["status"] == "completed"

    # 4. Verify GET /api/evaluation/interview/{id} returns evaluations and total_score
    eval_resp = client.get(f"/api/evaluation/interview/{interview_id}", headers=auth_header_scoring)
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["total_score"] == 90.0
    assert len(eval_data["evaluations"]) == 5
    assert len(eval_data["skipped_questions"]) == 0


@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_adaptive_scoring_low_scores_aggregation(mock_eval, mock_adaptive_q, client, auth_header_scoring, db_session):
    """
    Verifies score aggregation for lower performance answers.
    Scores: 30, 40, 25, 35, 45 -> average = 35.0%
    """
    start_resp = client.post(
        "/api/interviews/adaptive/start",
        headers=auth_header_scoring,
        json={
            "target_role": "Junior Backend Developer",
            "experience_level": "Junior",
            "topic": "Python Internals",
            "difficulty": "Easy",
            "num_questions": 5
        }
    )
    assert start_resp.status_code == 201
    interview_id = start_resp.json()["id"]
    current_q_id = start_resp.json()["questions"][0]["id"]

    scores = [30.0, 40.0, 25.0, 35.0, 45.0]

    for idx, expected_score in enumerate(scores, start=1):
        mock_eval.return_value = AIEvaluationResult(
            technical_correctness=expected_score,
            conceptual_completeness=expected_score,
            response_relevance=expected_score,
            structural_clarity=expected_score,
            depth_of_understanding=expected_score,
            overall_score=expected_score,
            strengths=["Attempted question."],
            improvements=["Need deeper understanding of runtime memory model."],
            feedback="Needs improvement.",
            model_answer="Standard reference answer."
        )

        mock_adaptive_q.return_value = {
            "question": f"Adaptive Question #{idx+1} foundational concept.",
            "category": "Python",
            "skill": "Syntax",
            "difficulty": "Easy",
            "adaptation_reason": "Provide foundational support."
        }

        ans_resp = client.post(
            f"/api/interviews/{interview_id}/answer",
            headers=auth_header_scoring,
            json={
                "question_id": current_q_id,
                "answer_text": f"Brief response for question {idx}."
            }
        )
        assert ans_resp.status_code == 200
        ans_data = ans_resp.json()

        if idx < 5:
            current_q_id = ans_data["next_question"]["id"]
        else:
            assert ans_data["is_last_question"] is True
            assert ans_data["total_score"] == 35.0

    db_session.expire_all()
    inv_db = db_session.query(Interview).filter(Interview.id == interview_id).first()
    assert inv_db.total_score == 35.0


@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_adaptive_scoring_partially_answered_and_skipped(mock_eval, mock_adaptive_q, client, auth_header_scoring, db_session):
    """
    Verifies that skipped questions do NOT insert artificial 0% evaluations and that
    the final score is the true average of answered questions (e.g. 3 answered out of 5).
    Scores: Q1=80.0%, Q2=90.0%, Q3=85.0%, Q4=Skipped, Q5=Skipped -> average = 85.0%
    """
    start_resp = client.post(
        "/api/interviews/adaptive/start",
        headers=auth_header_scoring,
        json={
            "target_role": "Full Stack Engineer",
            "experience_level": "Intermediate",
            "topic": "System Design",
            "difficulty": "Medium",
            "num_questions": 5
        }
    )
    interview_id = start_resp.json()["id"]
    current_q_id = start_resp.json()["questions"][0]["id"]

    answered_scores = [80.0, 90.0, 85.0]

    # Answer Questions 1, 2, 3
    for idx, s in enumerate(answered_scores, start=1):
        mock_eval.return_value = AIEvaluationResult(
            technical_correctness=s,
            conceptual_completeness=s,
            response_relevance=s,
            structural_clarity=s,
            depth_of_understanding=s,
            overall_score=s,
            strengths=[f"Good explanation for Q{idx}."],
            improvements=[],
            feedback="Competent answer.",
            model_answer="Model answer."
        )

        mock_adaptive_q.return_value = {
            "question": f"Question #{idx+1} topic.",
            "category": "System Design",
            "skill": "Scalability",
            "difficulty": "Medium",
            "adaptation_reason": f"Progressing after Q{idx}."
        }

        ans_resp = client.post(
            f"/api/interviews/{interview_id}/answer",
            headers=auth_header_scoring,
            json={"question_id": current_q_id, "answer_text": f"Solid answer for question {idx}."}
        )
        assert ans_resp.status_code == 200
        current_q_id = ans_resp.json()["next_question"]["id"]

    # Now on Question 4: Skip Q4
    mock_adaptive_q.return_value = {
        "question": "Question #5 final topic.",
        "category": "System Design",
        "skill": "Caches",
        "difficulty": "Medium",
        "adaptation_reason": "Skipped Q4; moving to Q5."
    }

    skip_q4_resp = client.post(
        f"/api/interviews/{interview_id}/next?question_id={current_q_id}",
        headers=auth_header_scoring
    )
    assert skip_q4_resp.status_code == 200
    q5_id = skip_q4_resp.json()["next_question"]["id"]

    # Now on Question 5 (final question): Skip Q5
    skip_q5_resp = client.post(
        f"/api/interviews/{interview_id}/next?question_id={q5_id}",
        headers=auth_header_scoring
    )
    assert skip_q5_resp.status_code == 200
    skip_q5_data = skip_q5_resp.json()

    assert skip_q5_data["interview_completed"] is True
    assert skip_q5_data["status"] == "completed"
    assert skip_q5_data["total_score"] == 85.0

    # Verify DB
    db_session.expire_all()
    inv_db = db_session.query(Interview).filter(Interview.id == interview_id).first()
    assert inv_db.status == "completed"
    assert inv_db.total_score == 85.0

    # Verify Evaluations API
    eval_resp = client.get(f"/api/evaluation/interview/{interview_id}", headers=auth_header_scoring)
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["total_score"] == 85.0
    assert len(eval_data["evaluations"]) == 3
    assert len(eval_data["skipped_questions"]) == 2


@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_ai_evaluation_service_failure_returns_503_without_corrupting_interview(mock_eval, client, auth_header_scoring, db_session):
    """
    Verifies that when AI evaluation fails or times out, the system explicitly returns 503 / 500
    and NEVER silently creates a 0% evaluation or completes the interview with 0%.
    """
    start_resp = client.post(
        "/api/interviews/adaptive/start",
        headers=auth_header_scoring,
        json={
            "target_role": "Cloud Architect",
            "experience_level": "Senior",
            "topic": "AWS Solutions",
            "difficulty": "Hard",
            "num_questions": 3
        }
    )
    interview_id = start_resp.json()["id"]
    q1_id = start_resp.json()["questions"][0]["id"]

    from fastapi import HTTPException
    mock_eval.side_effect = HTTPException(status_code=503, detail="Gemini AI service unavailable due to upstream timeout.")

    ans_resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        headers=auth_header_scoring,
        json={"question_id": q1_id, "answer_text": "AWS Multi-region active-active VPC peering."}
    )
    assert ans_resp.status_code == 503
    assert "Gemini AI service unavailable" in ans_resp.json()["detail"]

    # Verify DB has NO evaluations and interview is still in_progress
    db_session.expire_all()
    eval_count = db_session.query(Evaluation).filter(Evaluation.interview_id == interview_id).count()
    assert eval_count == 0

    inv_db = db_session.query(Interview).filter(Interview.id == interview_id).first()
    assert inv_db.status == "in_progress"
    assert inv_db.total_score == 0.0


def test_deduplication_of_evaluations_by_question_id(db_session):
    """
    Verifies that InterviewService.calculate_interview_final_score deduplicates evaluations
    by question_id and takes the latest score without double counting.
    """
    user_id = "test-user-scoring-dedup"
    interview = Interview(
        id="test-scoring-dedup-inv",
        user_id=user_id,
        target_role="Data Engineer",
        topic="Spark",
        num_questions=3,
        status="in_progress",
        total_score=0.0
    )
    db_session.add(interview)
    db_session.flush()

    q1 = InterviewQuestion(id="q1-dedup", interview_id=interview.id, question_number=1, question_text="What is an RDD?")
    q2 = InterviewQuestion(id="q2-dedup", interview_id=interview.id, question_number=2, question_text="What is a DataFrame?")
    db_session.add_all([q1, q2])
    db_session.flush()

    ans1_old = Answer(id="ans1-dedup-old", interview_id=interview.id, question_id=q1.id, user_id=user_id, answer_text="RDD attempt 1.")
    ans1_new = Answer(id="ans1-dedup-new", interview_id=interview.id, question_id=q1.id, user_id=user_id, answer_text="RDD attempt 2.")
    ans2 = Answer(id="ans2-dedup", interview_id=interview.id, question_id=q2.id, user_id=user_id, answer_text="DataFrame is organized into named columns.")
    db_session.add_all([ans1_old, ans1_new, ans2])
    db_session.flush()

    # Old evaluation for q1: score = 50.0
    ev1_old = Evaluation(
        id="ev1-old",
        answer_id=ans1_old.id,
        interview_id=interview.id,
        question_id=q1.id,
        technical_correctness=50.0,
        conceptual_completeness=50.0,
        response_relevance=50.0,
        structural_clarity=50.0,
        depth_of_understanding=50.0,
        overall_score=50.0
    )
    # New evaluation for q1: score = 90.0 (e.g. re-evaluated)
    ev1_new = Evaluation(
        id="ev1-new",
        answer_id=ans1_new.id,
        interview_id=interview.id,
        question_id=q1.id,
        technical_correctness=90.0,
        conceptual_completeness=90.0,
        response_relevance=90.0,
        structural_clarity=90.0,
        depth_of_understanding=90.0,
        overall_score=90.0
    )
    # Evaluation for q2: score = 80.0
    ev2 = Evaluation(
        id="ev2-dedup",
        answer_id=ans2.id,
        interview_id=interview.id,
        question_id=q2.id,
        technical_correctness=80.0,
        conceptual_completeness=80.0,
        response_relevance=80.0,
        structural_clarity=80.0,
        depth_of_understanding=80.0,
        overall_score=80.0
    )
    db_session.add_all([ev1_old, ev1_new, ev2])
    db_session.commit()

    # Expected: ev1_new (90.0) replaces ev1_old (50.0), plus ev2 (80.0) -> average = 85.0%
    score = InterviewService.calculate_interview_final_score(db_session, interview.id)
    assert score == 85.0
    assert interview.total_score == 85.0


@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_manual_end_interview_calculates_valid_score(mock_eval, mock_adaptive_q, client, auth_header_scoring, db_session):
    """
    Verifies that early completion via POST /api/interviews/{id}/complete computes and returns
    the valid average score of answered questions and marks status=completed.
    """
    start_resp = client.post(
        "/api/interviews/adaptive/start",
        headers=auth_header_scoring,
        json={
            "target_role": "DevOps Engineer",
            "experience_level": "Intermediate",
            "topic": "Kubernetes",
            "difficulty": "Medium",
            "num_questions": 5
        }
    )
    interview_id = start_resp.json()["id"]
    q1_id = start_resp.json()["questions"][0]["id"]

    # Answer Q1 with 70.0%
    mock_eval.return_value = AIEvaluationResult(
        technical_correctness=70.0,
        conceptual_completeness=70.0,
        response_relevance=70.0,
        structural_clarity=70.0,
        depth_of_understanding=70.0,
        overall_score=70.0,
        strengths=["Core understanding of Pods."],
        improvements=["Explain StatefulSets."],
        feedback="Fair response.",
        model_answer="Pods are smallest deployable units."
    )

    mock_adaptive_q.return_value = {
        "question": "What is a Kubernetes Service?",
        "category": "Kubernetes",
        "skill": "Networking",
        "difficulty": "Medium",
        "adaptation_reason": "Moving to networking."
    }

    ans1_resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        headers=auth_header_scoring,
        json={"question_id": q1_id, "answer_text": "A pod encapsulates one or more containers."}
    )
    q2_id = ans1_resp.json()["next_question"]["id"]

    # Answer Q2 with 80.0%
    mock_eval.return_value = AIEvaluationResult(
        technical_correctness=80.0,
        conceptual_completeness=80.0,
        response_relevance=80.0,
        structural_clarity=80.0,
        depth_of_understanding=80.0,
        overall_score=80.0,
        strengths=["Clear networking explanation."],
        improvements=[],
        feedback="Good answer.",
        model_answer="Services provide stable endpoints."
    )

    ans2_resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        headers=auth_header_scoring,
        json={"question_id": q2_id, "answer_text": "Services abstract pod IP address dynamism."}
    )
    assert ans2_resp.status_code == 200

    # User clicks "End Interview Now" -> calls /complete
    complete_resp = client.post(
        f"/api/interviews/{interview_id}/complete",
        headers=auth_header_scoring
    )
    assert complete_resp.status_code == 200
    complete_data = complete_resp.json()

    # Expected: (70.0 + 80.0) / 2 = 75.0%
    assert complete_data["status"] == "completed"
    assert complete_data["total_score"] == 75.0
    assert complete_data["final_score"] == 75.0
    assert complete_data["answered_count"] == 2
    assert complete_data["evaluations_count"] == 2
