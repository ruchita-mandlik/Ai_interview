from unittest.mock import patch, AsyncMock
import pytest

@pytest.fixture
def auth_header(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "Integration User",
            "email": "integration@example.com",
            "password": "password123",
            "target_role": "Full Stack Engineer",
            "experience_level": "Senior"
        }
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_user_profile_endpoints(client, auth_header):
    # GET profile
    res = client.get("/api/users/profile", headers=auth_header)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Integration User"
    assert data["email"] == "integration@example.com"
    assert data["target_role"] == "Full Stack Engineer"

    # PUT profile update
    update_res = client.put(
        "/api/users/profile",
        json={
            "target_role": "Lead Architect",
            "experience_level": "Lead",
            "preferred_topics": ["Distributed Systems", "Cloud"]
        },
        headers=auth_header
    )
    assert update_res.status_code == 200
    up_data = update_res.json()
    assert up_data["target_role"] == "Lead Architect"
    assert up_data["experience_level"] == "Lead"

def test_analytics_overview_endpoint(client, auth_header):
    res = client.get("/api/analytics/overview", headers=auth_header)
    assert res.status_code == 200
    data = res.json()
    assert "interviews_completed" in data
    assert "average_score" in data
    assert "best_score" in data
    assert "topic_performance" in data
    assert "difficulty_performance" in data
    assert "performance_trend" in data
    assert "readiness_score" in data

@patch("backend.services.ai_service.AIService.generate_clarification_or_hint", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.generate_interview_questions", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
def test_spa_interview_flow(mock_adaptive_q, mock_eval, mock_gen_q, mock_clarify, client, auth_header):
    mock_clarify.return_value = {
        "clarification": "Focus on horizontal scaling and partitioning strategies.",
        "hint": "Think about partition keys and consumer group rebalancing.",
        "focus_areas": ["Partitioning", "Offset Management", "Consumer Groups"]
    }
    mock_gen_q.return_value = [
        {
            "question": "Explain how event-driven architecture handles scale.",
            "category": "System Design",
            "skill": "Architecture",
            "difficulty": "Hard",
            "additional_instruction": "Mention message brokers like Kafka."
        }
    ]

    # 1. Create interview via SPA payload
    create_res = client.post(
        "/api/interviews",
        json={
            "role": "Lead Architect",
            "experience_level": "Senior",
            "difficulty": "Hard",
            "interview_type": "Technical",
            "topics": ["System Design", "Microservices"],
            "total_questions": 3
        },
        headers=auth_header
    )
    assert create_res.status_code == 201
    create_data = create_res.json()
    assert "interview" in create_data
    assert "first_question" in create_data
    interview_id = create_data["interview"]["id"]
    first_q_id = create_data["first_question"]["id"]
    assert create_data["interview"]["role"] == "Lead Architect"
    assert create_data["first_question"]["question"] == "Explain how event-driven architecture handles scale."

    # 2. Submit answer via SPA query param & body
    from backend.schemas.evaluation import AIEvaluationResult
    mock_eval.return_value = AIEvaluationResult(
        technical_correctness=95.0,
        conceptual_completeness=90.0,
        response_relevance=95.0,
        structural_clarity=90.0,
        depth_of_understanding=92.0,
        overall_score=93.0,
        strengths=["Clear partitioning and consumer group explanation."],
        improvements=["Could mention dead-letter queues."],
        feedback="Superb explanation of asynchronous decoupling.",
        model_answer="Event-driven systems decouple producers and consumers..."
    )
    mock_adaptive_q.return_value = {
        "question": "What happens when an event consumer fails?",
        "category": "Fault Tolerance",
        "skill": "System Design",
        "difficulty": "Hard",
        "additional_instruction": "Discuss retry queues and DLQs.",
        "adaptation_reason": "High performance (93.0%). Testing resilience patterns."
    }

    ans_res = client.post(
        f"/api/interviews/{interview_id}/answer?question_id={first_q_id}",
        json={"answer": "We use Kafka with partitioned topics and consumer groups."},
        headers=auth_header
    )
    assert ans_res.status_code == 200
    ans_data = ans_res.json()
    assert "evaluation" in ans_data
    assert ans_data["evaluation"]["score"] == 93.0
    assert ans_data["evaluation"]["correctness"] == 95.0
    assert "next_question" in ans_data
    assert ans_data["next_question"]["question"] == "What happens when an event consumer fails?"

    # 3. Request clarification / hint for current question
    clarify_res = client.post(
        f"/api/interviews/{interview_id}/clarify",
        json={"question_id": first_q_id, "query": "What focus areas should I prioritize?"},
        headers=auth_header
    )
    assert clarify_res.status_code == 200
    clarify_data = clarify_res.json()
    assert "clarification" in clarify_data
    assert "hint" in clarify_data
    assert "focus_areas" in clarify_data

    # 4. Skip question
    mock_adaptive_q.return_value = {
        "question": "How do you achieve idempotency in distributed transactions?",
        "category": "Consistency",
        "skill": "System Design",
        "difficulty": "Hard",
        "additional_instruction": "Mention outbox pattern.",
        "adaptation_reason": "Skipped. Escalating to distributed transactions."
    }
    skip_res = client.post(f"/api/interviews/{interview_id}/next", headers=auth_header)
    assert skip_res.status_code == 200
    skip_data = skip_res.json()
    assert skip_data["question"] == "How do you achieve idempotency in distributed transactions?"

@patch("backend.services.ai_service.AIService.evaluate_code", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.generate_preparation_plan", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.generate_final_report", new_callable=AsyncMock)
def test_ai_report_and_code_eval_endpoints(mock_report, mock_plan, mock_eval_code, client, auth_header):
    mock_eval_code.return_value = {
        "correctness_score": 9.0,
        "code_quality_score": 8.5,
        "time_complexity": "O(N)",
        "space_complexity": "O(1)",
        "bugs_found": [],
        "edge_cases_covered": ["Empty list", "Single node"],
        "missing_edge_cases": [],
        "optimization_suggestions": [],
        "ideal_code_snippet": "def reverseList(head): ...",
        "summary_feedback": "Clean iterative pointer manipulation."
    }
    mock_plan.return_value = {
        "plan": [
            {
                "day": i,
                "topic": f"Topic {i}",
                "concepts": ["Concept A", "Concept B"],
                "practice_questions": ["Question A"],
                "difficulty": "Medium",
                "estimated_time": "2 Hours"
            }
            for i in range(1, 8)
        ],
        "overall_readiness_assessment": "Targeted 7-day preparation plan.",
        "recommended_topics": ["Distributed Systems", "Caching"],
        "recommended_difficulty": "Medium",
        "study_priorities": ["System Design"]
    }
    # 1. Code evaluation
    code_res = client.post(
        "/api/ai/evaluate-code",
        json={
            "problem_statement": "Reverse a linked list",
            "language": "python",
            "code": "def reverseList(head): return head",
            "difficulty": "Easy",
            "topic": "Linked Lists"
        },
        headers=auth_header
    )
    assert code_res.status_code == 200
    code_data = code_res.json()
    assert "correctness_score" in code_data
    assert "code_quality_score" in code_data
    assert "time_complexity" in code_data

    # 2. Preparation plan
    plan_res = client.get("/api/recommendations/plan", headers=auth_header)
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert "plan" in plan_data
    assert len(plan_data["plan"]) == 7
    assert "overall_readiness_assessment" in plan_data

    # 3. Recommendations overview
    rec_res = client.get("/api/recommendations", headers=auth_header)
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert "recommended_topics" in rec_data
    assert "recommended_difficulty" in rec_data
