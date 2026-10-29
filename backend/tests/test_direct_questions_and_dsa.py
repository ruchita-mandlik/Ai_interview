import pytest
import re
from fastapi.testclient import TestClient
from backend.services.ai_service import AIService
from backend.services.coding_service import CodingService

def is_scenario_based(text: str) -> bool:
    """Detects if text contains typical lengthy fictional scenario phrases."""
    lower = text.lower()
    scenario_patterns = [
        r"imagine (that )?you are",
        r"suppose you are working at",
        r"consider a scenario where",
        r"you are a software engineer at an? [a-z0-9\-]+ (company|startup|platform|firm)",
        r"in a fast-paced e-commerce",
        r"at our company,",
        r"you have been tasked with building a system for a client who",
        r"during a peak shopping season",
        r"a legacy monolithic system",
    ]
    for pattern in scenario_patterns:
        if re.search(pattern, lower):
            return True
    return False

@pytest.fixture
def auth_headers(client: TestClient):
    reg = client.post("/api/auth/register", json={
        "name": "Direct Question Tester",
        "email": "direct_tester@example.com",
        "password": "Password123!"
    })
    token = reg.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_technical_question_generation_direct_llm():
    """Verify Gemini generates direct, normal technical interview questions dynamically."""
    questions = await AIService.generate_interview_questions(
        target_role="Java Backend Engineer",
        experience_level="Intermediate",
        topic="Java, Multithreading, Database Indexing",
        interview_type="Technical",
        difficulty="Medium",
        num_questions=3
    )

    assert len(questions) == 3
    for q in questions:
        q_text = q["question"]
        assert len(q_text) > 10
        # Verify it's a direct question and not a scenario story
        assert not is_scenario_based(q_text), f"Generated question was scenario-based: {q_text}"
        # Direct questions typically start with interrogative or direct imperative words
        direct_starts = ("what", "how", "explain", "why", "can you", "describe", "differentiate", "compare", "when", "which")
        assert q_text.lower().strip().startswith(direct_starts) or "?" in q_text

@pytest.mark.asyncio
async def test_technical_questions_easy_and_hard():
    """Verify difficulty complexity works for Easy and Hard technical questions."""
    easy_questions = await AIService.generate_interview_questions(
        target_role="Frontend Developer",
        experience_level="Junior",
        topic="JavaScript",
        interview_type="Technical",
        difficulty="Easy",
        num_questions=1
    )
    assert len(easy_questions) == 1
    easy_q = easy_questions[0]["question"]
    assert not is_scenario_based(easy_q)

    hard_questions = await AIService.generate_interview_questions(
        target_role="Distributed Systems Engineer",
        experience_level="Senior",
        topic="Distributed Consensus & Raft",
        interview_type="Technical",
        difficulty="Hard",
        num_questions=1
    )
    assert len(hard_questions) == 1
    hard_q = hard_questions[0]["question"]
    assert not is_scenario_based(hard_q)

@pytest.mark.asyncio
async def test_adaptive_follow_up_is_direct_and_short():
    """Verify adaptive follow-up logic produces direct, concise follow-ups without scenario fluff."""
    res = await AIService.generate_next_adaptive_question(
        target_role="Python Developer",
        experience_level="Intermediate",
        topic="Python Concurrency",
        interview_type="Technical",
        previous_question_text="What is the difference between threading and multiprocessing in Python?",
        candidate_answer="Threading uses threads and multiprocessing uses processes, but I am not sure about the GIL.",
        overall_score=70.0,
        previous_difficulty="Medium",
        next_question_number=2
    )
    q_text = res["question"]
    assert len(q_text) > 10
    assert not is_scenario_based(q_text), f"Follow-up was scenario-based: {q_text}"
    # Short and direct
    assert len(q_text.split()) < 50, f"Follow-up question was too lengthy: {q_text}"

def test_coding_interview_api_generates_standard_dsa(client: TestClient, auth_headers):
    """End-to-end test starting a coding interview via API to ensure standard DSA problems."""
    payload = {
        "target_role": "Software Engineer",
        "experience_level": "Intermediate",
        "topic": "Data Structures & Algorithms",
        "difficulty": "Easy",
        "language": "python"
    }
    res = client.post("/api/coding/start", json=payload, headers=auth_headers)
    assert res.status_code == 201
    data = res.json()
    assert "questions" in data and len(data["questions"]) > 0

    q = data["questions"][0]
    title = q["title"]
    desc = q["description"]

    # Problem description should NOT be a lengthy scenario
    assert not is_scenario_based(desc), f"Problem description was scenario-based: {desc}"
    # Check DSA characteristics
    assert "input_format" in q and q["input_format"]
    assert "output_format" in q and q["output_format"]
    assert "starter_code" in q and q["starter_code"]
    assert len(q["sample_test_cases"]) > 0
