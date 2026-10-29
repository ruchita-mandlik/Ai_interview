import pytest
from unittest.mock import patch, AsyncMock
from backend.models.interview import Interview
from backend.models.question import InterviewQuestion
from backend.models.evaluation import Evaluation
from backend.schemas.evaluation import AdaptiveAction
from backend.services.ai_service import AIService


@pytest.fixture
def auth_token(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "Flow Engineer",
            "email": "flow.engineer@interviewai.io",
            "password": "Password123!"
        }
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.generate_interview_questions", new_callable=AsyncMock)
def test_standard_mock_interview_linear_flow(mock_gen_all, mock_eval, mock_adaptive_q, client, auth_token, db_session):
    """
    Standard Mock Interview (is_adaptive=False):
    - Generates all questions upfront via generate_interview_questions
    - Does NOT call generate_next_adaptive_question
    - Advances linearly through the pre-generated questions
    """
    mock_questions = [
        {"question": "What is polymorphism?", "topic": "Java", "difficulty": "Medium", "expected_answer": "Ability of object to take many forms"},
        {"question": "Explain Java memory model.", "topic": "Java", "difficulty": "Medium", "expected_answer": "Heap and stack distinction"},
        {"question": "How does Garbage Collection work?", "topic": "Java", "difficulty": "Medium", "expected_answer": "Mark and sweep cycles"}
    ]
    mock_gen_all.return_value = mock_questions

    # 1. Create standard mock interview
    response = client.post(
        "/api/interviews",
        headers=auth_token,
        json={
            "role": "Java Developer",
            "experience_level": "Intermediate (2-5 Yrs)",
            "difficulty": "Medium",
            "interview_type": "Technical",
            "topics": ["Java"],
            "total_questions": 3,
            "is_adaptive": False
        }
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["interview"]["is_adaptive"] is False
    assert data["first_question"]["question"] == "What is polymorphism?"
    mock_gen_all.assert_called_once()
    mock_adaptive_q.assert_not_called()

    interview_id = data["interview"]["id"]
    first_q_id = data["first_question"]["id"]

    # Verify all 3 questions were generated in DB
    db_questions = db_session.query(InterviewQuestion).filter(InterviewQuestion.interview_id == interview_id).order_by(InterviewQuestion.question_number).all()
    assert len(db_questions) == 3

    # 2. Submit answer to Q1
    mock_eval.return_value = {
        "score": 85.0,
        "overall_score": 85.0,
        "score_out_of_10": 8.5,
        "evaluation_type": "detailed",
        "strengths": ["Clear terminology"],
        "improvements": ["Could mention runtime vs compile time"],
        "actionable_feedback": "Mention method overriding and overloading.",
        "technical_correctness": 88.0,
        "conceptual_completeness": 84.0,
        "structural_clarity": 85.0,
        "depth_of_understanding": 83.0,
        "missing_concepts": [],
        "incorrect_claims": [],
        "feedback": "Solid understanding of polymorphism.",
        "model_answer": "Polymorphism allows objects to be treated as instances of their parent class."
    }

    ans_res = client.post(
        f"/api/interviews/{interview_id}/answer?question_id={first_q_id}",
        headers=auth_token,
        json={"answer": "Polymorphism is when a class has multiple forms via overloading and overriding."}
    )

    assert ans_res.status_code == 200, ans_res.text
    ans_data = ans_res.json()
    # In standard interview, next question is the second pre-generated question
    assert ans_data["interview_completed"] is False
    assert ans_data["next_question"]["question"] == "Explain Java memory model."
    # Adaptive engine must NOT have been called
    mock_adaptive_q.assert_not_called()


@patch("backend.services.ai_service.AIService.generate_interview_questions", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_adaptive_interview_dynamic_branching(mock_eval, mock_adaptive_q, mock_gen_initial, client, auth_token, db_session):
    """
    Adaptive Interview (is_adaptive=True):
    - Generates 1 baseline question upfront
    - Evaluates actual candidate answer
    - Dynamically selects adaptive action and calls generate_next_adaptive_question
    """
    mock_base_q = {
        "question": "What is an index in PostgreSQL and how does B-Tree indexing work?",
        "topic": "PostgreSQL",
        "difficulty": "Medium",
        "expected_answer": "B-Tree maintains balanced sorted search tree"
    }
    mock_gen_initial.return_value = [mock_base_q]
    mock_adaptive_q.return_value = {
        "action": "NEXT_TOPIC",
        "updated_difficulty": "Medium",
        "decision_rationale": "Baseline starting question",
        "next_question": mock_base_q["question"],
        "category": "PostgreSQL",
        "identified_knowledge_gaps": []
    }

    response = client.post(
        "/api/interviews/adaptive/start",
        headers=auth_token,
        json={
            "role": "Backend Engineer",
            "experience_level": "Senior (5+ Yrs)",
            "difficulty": "Medium",
            "interview_type": "Technical",
            "topics": ["PostgreSQL"],
            "total_questions": 3
        }
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["is_adaptive"] is True
    assert data["questions"][0]["question"] == mock_base_q["question"]
    interview_id = data["id"]
    q1_id = data["questions"][0]["id"]

    # Candidate gives an answer missing write overhead
    mock_eval.return_value = {
        "score": 65.0,
        "overall_score": 65.0,
        "score_out_of_10": 6.5,
        "evaluation_type": "detailed",
        "strengths": ["Understands search efficiency"],
        "improvements": ["Did not mention write amplification and concurrency lock contention"],
        "actionable_feedback": "Consider the impact on INSERT/UPDATE workloads and WAL logging.",
        "missing_concepts": ["Write Amplification", "WAL Overhead"],
        "technical_correctness": 70.0,
        "conceptual_completeness": 60.0,
        "structural_clarity": 75.0,
        "depth_of_understanding": 60.0,
        "incorrect_claims": [],
        "feedback": "Adequate read understanding but lacks write trade-offs.",
        "model_answer": "B-trees speed up lookups but add write amplification and require vacuuming."
    }

    mock_challenge_q = {
        "action": AdaptiveAction.CHALLENGE_REASONING.value,
        "updated_difficulty": "Medium",
        "decision_rationale": "Candidate omitted write trade-offs. Challenging them on 10,000 INSERT/s workload.",
        "next_question": "If your table receives 10,000 INSERTs/sec, what is the exact performance and storage cost of adding 5 B-Tree indexes?",
        "assessment_objective": "Evaluate understanding of write amplification and index maintenance overhead.",
        "identified_knowledge_gaps": ["Write Amplification", "WAL Overhead"]
    }
    mock_adaptive_q.return_value = mock_challenge_q

    ans_res = client.post(
        f"/api/interviews/{interview_id}/answer?question_id={q1_id}",
        headers=auth_token,
        json={"answer": "Indexes make lookups fast like a phonebook, using O(log n) searches."}
    )

    assert ans_res.status_code == 200, ans_res.text
    ans_data = ans_res.json()
    assert ans_data["interview_completed"] is False
    assert ans_data["adaptive_action"] == "CHALLENGE_REASONING"
    assert "10,000 INSERTs/sec" in ans_data["next_question"]["question"]
    assert "Write Amplification" in ans_data["knowledge_gaps"]


@patch("backend.services.ai_service.AIService.generate_interview_questions", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
def test_distinguish_interviews_in_list(mock_adaptive_q, mock_gen_all, client, auth_token):
    """Verify standard and adaptive interviews are correctly distinguished in list endpoint"""
    mock_gen_all.return_value = [{"question": "Std Q1", "topic": "General", "difficulty": "Easy", "expected_answer": "Ans"}]
    mock_adaptive_q.return_value = {
        "action": "NEXT_TOPIC",
        "updated_difficulty": "Medium",
        "decision_rationale": "Base",
        "next_question": "Adaptive Q1",
        "category": "General",
        "identified_knowledge_gaps": []
    }

    # 1. Create standard interview
    client.post(
        "/api/interviews",
        headers=auth_token,
        json={
            "role": "QA Engineer",
            "experience_level": "Junior (0-2 Yrs)",
            "difficulty": "Easy",
            "interview_type": "Technical",
            "topics": ["Testing"],
            "total_questions": 1,
            "is_adaptive": False
        }
    )

    # 2. Create adaptive interview
    client.post(
        "/api/interviews",
        headers=auth_token,
        json={
            "role": "QA Engineer",
            "experience_level": "Junior (0-2 Yrs)",
            "difficulty": "Easy",
            "interview_type": "Technical",
            "topics": ["Testing"],
            "total_questions": 1,
            "is_adaptive": True
        }
    )

    res = client.get("/api/interviews", headers=auth_token)
    assert res.status_code == 200
    interviews = res.json()
    assert len(interviews) == 2
    adaptive_flags = [i.get("is_adaptive") for i in interviews]
    assert True in adaptive_flags
    assert False in adaptive_flags
