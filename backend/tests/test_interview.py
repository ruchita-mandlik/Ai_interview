from unittest.mock import patch, AsyncMock
import pytest

@pytest.fixture
def auth_header(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "Interview Tester",
            "email": "tester@example.com",
            "password": "password123"
        }
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@patch("backend.services.ai_service.AIService.generate_interview_questions", new_callable=AsyncMock)
def test_create_interview(mock_gen_q, client, auth_header):
    mock_gen_q.return_value = [
        {
            "question": "What is the difference between ArrayList and LinkedList?",
            "category": "Java",
            "skill": "Java Collections",
            "difficulty": "Medium",
            "additional_instruction": "Explain internal structure and performance."
        }
    ]

    resp = client.post(
        "/api/interviews/start",
        json={
            "interview_type": "Technical",
            "target_role": "Java Developer",
            "experience_level": "Intermediate",
            "topic": "Java",
            "difficulty": "Medium",
            "num_questions": 2
        },
        headers=auth_header
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["target_role"] == "Java Developer"
    assert len(data["questions"]) == 1
    assert data["questions"][0]["question_text"] == "What is the difference between ArrayList and LinkedList?"

@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.generate_interview_questions", new_callable=AsyncMock)
def test_adaptive_interview_flow(mock_gen_q, mock_eval, mock_adaptive_q, client, auth_header):
    mock_gen_q.return_value = [
        {
            "question": "What is immutability in Java?",
            "category": "Java",
            "skill": "Java Core",
            "difficulty": "Easy",
            "additional_instruction": "Mention String and final keyword."
        }
    ]

    start_resp = client.post(
        "/api/interviews/start",
        json={
            "interview_type": "Technical",
            "target_role": "Java Developer",
            "experience_level": "Intermediate",
            "topic": "Java",
            "difficulty": "Easy",
            "num_questions": 2
        },
        headers=auth_header
    )
    interview_id = start_resp.json()["id"]
    question_id = start_resp.json()["questions"][0]["id"]

    from backend.schemas.evaluation import AIEvaluationResult
    mock_eval.return_value = AIEvaluationResult(
        technical_correctness=92.0,
        conceptual_completeness=88.0,
        response_relevance=95.0,
        structural_clarity=85.0,
        depth_of_understanding=85.0,
        overall_score=90.0,
        strengths=["Great explanation of final class and fields."],
        improvements=["Could mention String pool."],
        feedback="Excellent response with clear concepts.",
        model_answer="An immutable object cannot be modified once created."
    )

    mock_adaptive_q.return_value = {
        "question": "How do you implement thread-safe singleton in Java?",
        "category": "Java Design Patterns",
        "skill": "Java",
        "difficulty": "Medium",
        "additional_instruction": "Discuss double-checked locking and enum singleton.",
        "adaptation_reason": "Excellent performance (90.0%). Escalating difficulty to Medium."
    }

    ans_resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={
            "question_id": question_id,
            "answer_text": "Immutability means an object's state cannot be changed after creation."
        },
        headers=auth_header
    )
    assert ans_resp.status_code == 200
    res_data = ans_resp.json()
    assert res_data["overall_score"] == 90.0
    assert res_data["is_last_question"] is False
    assert res_data["next_question"]["question_text"] == "How do you implement thread-safe singleton in Java?"
    assert res_data["next_question"]["difficulty"] == "Medium"
    assert "Escalating difficulty" in res_data["next_question"]["adaptation_reason"]

    comp_resp = client.post(
        f"/api/interviews/{interview_id}/complete",
        headers=auth_header
    )
    assert comp_resp.status_code == 200
    assert comp_resp.json()["total_score"] == 90.0


@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.generate_interview_questions", new_callable=AsyncMock)
def test_skip_question_advances_and_marks_db(mock_gen_q, mock_adaptive_q, client, auth_header, db_session):
    mock_gen_q.return_value = [
        {
            "question": "Explain FastAPI dependency injection mechanism.",
            "category": "FastAPI",
            "skill": "FastAPI",
            "difficulty": "Medium",
            "additional_instruction": "Mention Depends and yield dependencies."
        }
    ]

    start_resp = client.post(
        "/api/interviews/start",
        json={
            "interview_type": "Technical",
            "target_role": "Backend Engineer",
            "experience_level": "Senior",
            "topic": "Python, FastAPI",
            "skills": ["FastAPI", "PostgreSQL"],
            "job_description": "Building high-throughput microservices",
            "difficulty": "Hard",
            "num_questions": 3
        },
        headers=auth_header
    )
    assert start_resp.status_code == 201
    start_data = start_resp.json()
    interview_id = start_data["id"]
    q1_id = start_data["questions"][0]["id"]

    mock_adaptive_q.return_value = {
        "question": "How do you handle database connection pooling with Async SQLAlchemy in FastAPI?",
        "category": "Databases",
        "skill": "PostgreSQL",
        "difficulty": "Hard",
        "additional_instruction": "Discuss connection recycling and pool size.",
        "adaptation_reason": "Candidate skipped FastAPI DI; shifting to database connection pooling."
    }

    # Execute Skip on Question 1
    skip_resp = client.post(
        f"/api/interviews/{interview_id}/next?question_id={q1_id}",
        headers=auth_header
    )
    assert skip_resp.status_code == 200
    skip_data = skip_resp.json()

    # Verify response contract
    assert skip_data["status"] == "in_progress"
    assert skip_data["interview_completed"] is False
    assert skip_data["skipped_question_id"] == q1_id
    assert skip_data["next_question"]["question_number"] == 2
    assert skip_data["next_question"]["question_text"] == "How do you handle database connection pooling with Async SQLAlchemy in FastAPI?"
    assert skip_data["question_text"] == skip_data["next_question"]["question_text"]

    # Verify context passed to adaptive question generator
    mock_adaptive_q.assert_awaited_once()
    called_kwargs = mock_adaptive_q.call_args.kwargs
    assert called_kwargs["target_role"] == "Backend Engineer"
    assert called_kwargs["job_description"] == "Building high-throughput microservices"
    assert "FastAPI" in called_kwargs["skills"]
    assert called_kwargs["next_question_number"] == 2

    # Verify database persistence of is_skipped on Q1
    from backend.models.question import InterviewQuestion
    q1_db = db_session.query(InterviewQuestion).filter(InterviewQuestion.id == q1_id).first()
    assert q1_db.is_skipped is True

    # Verify Q2 is in DB with is_skipped=False
    q2_db = db_session.query(InterviewQuestion).filter(
        InterviewQuestion.interview_id == interview_id,
        InterviewQuestion.question_number == 2
    ).first()
    assert q2_db is not None
    assert q2_db.is_skipped is False


@patch("backend.services.ai_service.AIService.generate_interview_questions", new_callable=AsyncMock)
def test_skip_last_question_transitions_to_completion(mock_gen_q, client, auth_header, db_session):
    mock_gen_q.return_value = [
        {
            "question": "What is Python GIL?",
            "category": "Python",
            "skill": "Python Core",
            "difficulty": "Medium",
            "additional_instruction": "Explain concurrency implications."
        }
    ]

    start_resp = client.post(
        "/api/interviews/start",
        json={
            "interview_type": "Technical",
            "target_role": "Python Developer",
            "experience_level": "Intermediate",
            "topic": "Python",
            "difficulty": "Medium",
            "num_questions": 1  # 1-question interview so skipping it is the last question
        },
        headers=auth_header
    )
    assert start_resp.status_code == 201
    interview_id = start_resp.json()["id"]
    q1_id = start_resp.json()["questions"][0]["id"]

    # Skip the only/last question
    skip_resp = client.post(
        f"/api/interviews/{interview_id}/next",
        headers=auth_header
    )
    assert skip_resp.status_code == 200
    skip_data = skip_resp.json()

    assert skip_data["status"] == "completed"
    assert skip_data["interview_completed"] is True
    assert skip_data["next_question"] is None
    assert skip_data["skipped_question_id"] == q1_id

    # Verify interview in DB is completed
    from backend.models.interview import Interview
    inv_db = db_session.query(Interview).filter(Interview.id == interview_id).first()
    assert inv_db.status == "completed"
    assert inv_db.total_score == 0.0


@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.generate_interview_questions", new_callable=AsyncMock)
def test_skipped_questions_excluded_from_answer_scoring(mock_gen_q, mock_eval, mock_adaptive_q, client, auth_header):
    mock_gen_q.return_value = [
        {
            "question": "Explain REST vs GraphQL.",
            "category": "APIs",
            "skill": "Web Services",
            "difficulty": "Medium",
            "additional_instruction": "Compare payloads and over-fetching."
        }
    ]

    start_resp = client.post(
        "/api/interviews/start",
        json={
            "interview_type": "Technical",
            "target_role": "Full Stack Engineer",
            "experience_level": "Intermediate",
            "topic": "API Design",
            "difficulty": "Medium",
            "num_questions": 2
        },
        headers=auth_header
    )
    interview_id = start_resp.json()["id"]
    q1_id = start_resp.json()["questions"][0]["id"]

    # Candidate answers Question 1 with high score 90.0%
    from backend.schemas.evaluation import AIEvaluationResult
    mock_eval.return_value = AIEvaluationResult(
        technical_correctness=90.0,
        conceptual_completeness=90.0,
        response_relevance=90.0,
        structural_clarity=90.0,
        depth_of_understanding=90.0,
        overall_score=90.0,
        strengths=["Clear differentiation of endpoints and overfetching."],
        improvements=[],
        feedback="Solid understanding.",
        model_answer="REST uses resource URIs whereas GraphQL uses a flexible query document."
    )

    mock_adaptive_q.return_value = {
        "question": "How does GraphQL handle schema stitching and federation?",
        "category": "GraphQL",
        "skill": "Architecture",
        "difficulty": "Hard",
        "additional_instruction": "Discuss subgraphs and gateway routing.",
        "adaptation_reason": "High score on Q1; advancing to federation."
    }

    ans_resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={"question_id": q1_id, "answer_text": "REST exposes resource-oriented endpoints while GraphQL allows specific querying."},
        headers=auth_header
    )
    assert ans_resp.status_code == 200

    # Skip Question 2 (which is the last question)
    skip_resp = client.post(
        f"/api/interviews/{interview_id}/next",
        headers=auth_header
    )
    assert skip_resp.status_code == 200
    assert skip_resp.json()["interview_completed"] is True

    # Verify evaluations endpoint: score is based strictly on evaluated Q1 (90.0%), and skipped_questions lists Q2
    eval_resp = client.get(
        f"/api/evaluation/interview/{interview_id}",
        headers=auth_header
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["total_score"] == 90.0
    assert len(eval_data["evaluations"]) == 1
    assert len(eval_data["skipped_questions"]) == 1
    assert eval_data["skipped_questions"][0]["question_number"] == 2
    assert eval_data["skipped_questions"][0]["is_skipped"] is True


@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.generate_interview_questions", new_callable=AsyncMock)
def test_skip_question_api_failure_returns_http_500(mock_gen_q, mock_adaptive_q, client, auth_header):
    mock_gen_q.return_value = [
        {
            "question": "What is Docker containerization?",
            "category": "DevOps",
            "skill": "Containers",
            "difficulty": "Easy",
            "additional_instruction": "Explain cgroups and namespaces."
        }
    ]

    start_resp = client.post(
        "/api/interviews/start",
        json={
            "interview_type": "Technical",
            "target_role": "DevOps Engineer",
            "experience_level": "Junior",
            "topic": "DevOps",
            "difficulty": "Easy",
            "num_questions": 3
        },
        headers=auth_header
    )
    interview_id = start_resp.json()["id"]

    mock_adaptive_q.side_effect = Exception("Gemini service connection timeout")

    skip_resp = client.post(
        f"/api/interviews/{interview_id}/next",
        headers=auth_header
    )
    assert skip_resp.status_code == 500
    assert "Failed to advance question" in skip_resp.json()["detail"]

