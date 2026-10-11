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
