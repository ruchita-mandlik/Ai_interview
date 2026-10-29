import pytest
import json
from backend.models.interview import Interview
from backend.models.question import InterviewQuestion
from backend.models.answer import Answer
from backend.models.evaluation import Evaluation
from backend.models.user import User

@pytest.fixture
def empty_user_auth(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "New Candidate",
            "email": "new_candidate@example.com",
            "password": "password123",
            "target_role": "Software Developer",
            "experience_level": "Intermediate"
        }
    )
    assert reg.status_code in (200, 201), reg.text
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user_id}

@pytest.fixture
def active_user_auth(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "Active Candidate",
            "email": "active_candidate@example.com",
            "password": "password123",
            "target_role": "Backend Engineer",
            "experience_level": "Senior"
        }
    )
    assert reg.status_code in (200, 201), reg.text
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user_id}

def _seed_completed_interview_with_evals(db_session, user_id):
    interview = Interview(
        user_id=user_id,
        target_role="Backend Engineer",
        experience_level="Senior",
        topic="FastAPI & System Design",
        difficulty="Medium",
        num_questions=3,
        status="completed",
        total_score=85.0
    )
    db_session.add(interview)
    db_session.commit()
    db_session.refresh(interview)

    eval_data = [
        {
            "q": "Explain FastAPI dependency injection mechanism.",
            "ans": "FastAPI uses Depends to declare dependencies that are evaluated hierarchically and cached per-request.",
            "tc": 88.0, "cc": 85.0, "rr": 90.0, "sc": 82.0, "du": 85.0, "ov": 86.5,
            "missing": ["yield dependencies cleanup handling"],
            "incorrect": []
        },
        {
            "q": "How does PostgreSQL handle concurrency control with MVCC?",
            "ans": "Postgres creates new tuple versions upon update and relies on snapshot transaction isolation.",
            "tc": 92.0, "cc": 88.0, "rr": 95.0, "sc": 90.0, "du": 86.0, "ov": 90.4,
            "missing": ["VACUUM dead tuple cleanup"],
            "incorrect": []
        },
        {
            "q": "What is the difference between synchronous and asynchronous database sessions?",
            "ans": "Async sessions prevent thread blocking during I/O using asyncio event loops.",
            "tc": 80.0, "cc": 75.0, "rr": 85.0, "sc": 80.0, "du": 78.0, "ov": 79.5,
            "missing": ["connection pool starving in async loops"],
            "incorrect": []
        }
    ]

    for idx, ed in enumerate(eval_data, 1):
        q = InterviewQuestion(
            interview_id=interview.id,
            question_text=ed["q"],
            question_number=idx,
            category="Technical",
            difficulty="Medium",
            skill="Backend Architecture"
        )
        db_session.add(q)
        db_session.commit()
        db_session.refresh(q)

        a = Answer(
            interview_id=interview.id,
            question_id=q.id,
            user_id=user_id,
            answer_text=ed["ans"]
        )
        db_session.add(a)
        db_session.commit()
        db_session.refresh(a)

        ev = Evaluation(
            answer_id=a.id,
            interview_id=interview.id,
            question_id=q.id,
            technical_correctness=ed["tc"],
            conceptual_completeness=ed["cc"],
            response_relevance=ed["rr"],
            structural_clarity=ed["sc"],
            depth_of_understanding=ed["du"],
            overall_score=ed["ov"],
            strengths=json.dumps(["Solid architectural clarity", "Precise technical vocabulary"]),
            improvements=json.dumps(["Mention transaction rollback edge cases"]),
            missing_concepts=json.dumps(ed["missing"]),
            incorrect_claims=json.dumps(ed["incorrect"]),
            feedback="Strong demonstration of backend engineering fundamentals."
        )
        db_session.add(ev)
        db_session.commit()

    return interview

def test_readiness_empty_state_resolves_truthfully(client, empty_user_auth):
    """Verifies that an account with 0 interviews returns a truthful INSUFFICIENT data state, 0% score, and does not crash or hang."""
    res = client.get("/api/readiness", headers=empty_user_auth["headers"])
    assert res.status_code == 200, res.text
    data = res.json()

    # Truthful sufficiency state
    assert data["data_sufficiency"] == "INSUFFICIENT"
    assert "Insufficient Assessment Data" in data["data_sufficiency_explanation"]
    assert data["overall_readiness_score"] == 0.0
    assert data["readiness_score"] == 0.0
    assert data["readiness_stage"] == "Early Preparation"
    assert data["readiness_level"] == "Early Preparation"

    # All 5 dimensions are present and calibrated to 0 with Insufficient Data status
    assert len(data["dimensions"]) == 5
    for dim in data["dimensions"]:
        assert dim["score"] == 0.0
        assert dim["status"] == "Insufficient Data"
        assert dim["data_points_count"] == 0

    # Evidence breakdown is truthful (0 answers, 0 interviews)
    eb = data["evidence_breakdown"]
    assert eb["total_answers_analyzed"] == 0
    assert eb["total_interviews_evaluated"] == 0
    assert eb["evaluated_answers_count"] == 0
    assert eb["completed_interviews_count"] == 0

    # Next action directs candidate to initial mock
    nba = data["next_best_action"]
    assert nba["action_type"] == "TAKE_INITIAL_MOCK"
    assert nba["deep_link_tab"] == "interview"

def test_readiness_with_real_evaluations(client, db_session, active_user_auth):
    """Verifies that completed interviews with evaluations produce valid multidimensional telemetry and readiness scores."""
    user_id = active_user_auth["user_id"]
    _seed_completed_interview_with_evals(db_session, user_id)

    res = client.get("/api/readiness", headers=active_user_auth["headers"])
    assert res.status_code == 200, res.text
    data = res.json()

    # Should have calibrated score between 0 and 100
    assert 0.0 < data["overall_readiness_score"] <= 100.0
    assert data["data_sufficiency"] in ("MODERATE", "HIGH", "VERY_HIGH")

    # Dimensions telemetry must be populated and clamped to [0, 100]
    assert len(data["dimensions"]) == 5
    for dim in data["dimensions"]:
        assert 0.0 <= dim["score"] <= 100.0
        assert dim["status"] in ("Exceptional", "Proficient", "Developing", "Needs Remediation", "Insufficient Data")

    # Technical depth dimension should reflect the 3 evaluated answers
    tech_dim = next((d for d in data["dimensions"] if "Technical Depth" in d["name"]), None)
    assert tech_dim is not None
    assert tech_dim["data_points_count"] == 3
    assert tech_dim["score"] > 80.0

    # Evidence breakdown
    eb = data["evidence_breakdown"]
    assert eb["total_answers_analyzed"] == 3
    assert eb["total_interviews_evaluated"] == 1
    assert eb["evaluated_answers_count"] == 3
    assert eb["completed_interviews_count"] == 1

def test_recalculate_readiness_endpoint(client, db_session, active_user_auth):
    """Verifies that POST /api/readiness/recalculate triggers a fresh calculation and persists updated telemetry."""
    user_id = active_user_auth["user_id"]
    _seed_completed_interview_with_evals(db_session, user_id)

    # Initial calculation
    init_res = client.get("/api/readiness", headers=active_user_auth["headers"])
    assert init_res.status_code == 200
    init_data = init_res.json()

    # Recalculate
    recalc_res = client.post("/api/readiness/recalculate", headers=active_user_auth["headers"])
    assert recalc_res.status_code == 200, recalc_res.text
    recalc_data = recalc_res.json()

    assert recalc_data["overall_readiness_score"] == init_data["overall_readiness_score"]
    assert len(recalc_data["dimensions"]) == 5
    assert recalc_data["evidence_breakdown"]["total_answers_analyzed"] == 3

def test_cross_dashboard_consistency(client, db_session, active_user_auth):
    """Verifies that /api/dashboard, /api/analytics/overview, and /api/readiness report consistent scores."""
    user_id = active_user_auth["user_id"]
    _seed_completed_interview_with_evals(db_session, user_id)

    readiness_res = client.get("/api/readiness", headers=active_user_auth["headers"])
    assert readiness_res.status_code == 200
    r_score = readiness_res.json()["overall_readiness_score"]

    dashboard_res = client.get("/api/dashboard", headers=active_user_auth["headers"])
    assert dashboard_res.status_code == 200
    dash_stats = dashboard_res.json()["stats"]
    assert f"{r_score}%" == dash_stats["readiness_score"]

    analytics_res = client.get("/api/analytics/overview", headers=active_user_auth["headers"])
    assert analytics_res.status_code == 200
    analytics_data = analytics_res.json()
    assert analytics_data["readiness_score"] == r_score
