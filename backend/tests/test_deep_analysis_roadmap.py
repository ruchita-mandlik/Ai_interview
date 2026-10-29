import pytest
from unittest.mock import patch, AsyncMock
from backend.models.interview import Interview
from backend.models.question import InterviewQuestion
from backend.models.answer import Answer
from backend.models.evaluation import Evaluation

@pytest.fixture
def auth_header(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "Roadmap Candidate",
            "email": "roadmap_candidate@example.com",
            "password": "securepassword123",
            "target_role": "Backend Engineer",
            "experience_level": "Senior"
        }
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def _create_mock_interview_with_qa(db_session, user_id, answers_data, role="Backend Engineer", difficulty="Hard"):
    interview = Interview(
        user_id=user_id,
        target_role=role,
        experience_level="Senior",
        topic="Distributed Systems",
        difficulty=difficulty,
        num_questions=len(answers_data),
        status="completed",
        total_score=8.0
    )
    db_session.add(interview)
    db_session.commit()
    db_session.refresh(interview)

    for idx, item in enumerate(answers_data, 1):
        q = InterviewQuestion(
            interview_id=interview.id,
            question_number=idx,
            question_text=item["question_text"],
            category=item.get("category", "Distributed Systems"),
            difficulty=difficulty,
            is_skipped=item.get("is_skipped", False)
        )
        db_session.add(q)
        db_session.commit()
        db_session.refresh(q)

        ans = Answer(
            interview_id=interview.id,
            question_id=q.id,
            user_id=user_id,
            answer_text=item.get("answer_text", "")
        )
        db_session.add(ans)
        db_session.commit()
        db_session.refresh(ans)

        ev = Evaluation(
            answer_id=ans.id,
            interview_id=interview.id,
            question_id=q.id,
            technical_correctness=item.get("correctness", 8.0),
            conceptual_completeness=item.get("completeness", 8.0),
            depth_of_understanding=item.get("depth", 8.0),
            response_relevance=8.0,
            overall_score=item.get("overall", 8.0),
            strengths=item.get("strengths", "[]"),
            improvements=item.get("improvements", "[]"),
            missing_concepts=item.get("missing_concepts", "[]"),
            incorrect_claims=item.get("incorrect_claims", "[]")
        )
        db_session.add(ev)
        db_session.commit()

    return interview

@patch("backend.services.ai_service.AIService.deep_analyze_interview_session", new_callable=AsyncMock)
def test_strong_interview_generates_high_readiness_and_strengths(mock_deep_ai, client, auth_header, db_session):
    me_resp = client.get("/api/auth/me", headers=auth_header)
    user_id = me_resp.json()["id"]

    mock_deep_ai.return_value = {
        "readiness_score": 92.0,
        "readiness_level": "Interview Ready",
        "executive_summary": "Candidate demonstrated exceptional architectural mastery and deep trade-off reasoning in distributed consensus and raft algorithms.",
        "question_analyses": [
            {
                "question_id": "q1",
                "question_number": 1,
                "question_text": "How does Raft maintain consensus during leader election splits?",
                "candidate_answer_excerpt": "Raft uses randomized election timeouts to prevent split votes...",
                "technical_correctness": 9.5,
                "conceptual_understanding": 9.0,
                "depth_and_clarity": 9.0,
                "reasoning_approach": 9.0,
                "completeness": 9.5,
                "key_strengths": ["Clear explanation of randomized election timeouts", "Accurate description of term numbering"],
                "misconceptions": [],
                "missing_concepts": [],
                "poorly_explained_aspects": [],
                "coding_evaluation": None
            }
        ],
        "skill_gaps": [],
        "strengths": [
            {
                "competency": "Distributed Consensus & Raft",
                "category": "Architecture",
                "evidence_question_number": 1,
                "candidate_excerpt": "Raft uses randomized election timeouts to prevent split votes...",
                "demonstrated_mastery": "Articulated heartbeat mechanics and term quorum accurately."
            }
        ],
        "untested_competencies": [
            {
                "competency": "Geo-distributed Latency Optimization",
                "category": "Infrastructure",
                "importance_for_role": "Relevant for global cluster deployments.",
                "recommended_next_step": "Review multi-region active-active patterns."
            }
        ],
        "roadmap_phases": [
            {
                "phase_number": 1,
                "title": "Phase 1: Advanced Distributed Topologies",
                "duration_weeks": 1.0,
                "focus_areas": ["Multi-region Replication", "Split-brain Tolerance"],
                "milestone": "Master geo-distributed quorum configurations"
            }
        ],
        "roadmap_tasks": [
            {
                "task_id": "task_1",
                "phase_number": 1,
                "day_or_sequence": 1,
                "priority": "MEDIUM",
                "topic": "Multi-Region Paxos vs Raft",
                "subtopics": ["WAN latency", "Quorum Leases"],
                "learning_objectives": ["Evaluate latency impacts of WAN quorums"],
                "practical_exercise": "Simulate network partitions across 3 simulated cloud regions.",
                "relevant_problems_or_questions": ["Design an active-active cross-region KV store"],
                "estimated_duration_hours": 2.0,
                "expected_outcomes": "Zero data loss under regional network partition.",
                "completion_criteria": "Implement quorum lease renewal protocol.",
                "status": "pending"
            }
        ],
        "reassessment_questions": [
            {
                "id": "reassess_1",
                "targeted_gap_id": "gap_none",
                "competency": "Distributed Consensus",
                "question_text": "How do you avoid cascading leader elections across WAN links?",
                "expected_key_points": ["Pre-vote phase", "Lease timers"],
                "benchmark_solution": "Incorporate a Pre-Vote protocol phase before incrementing term.",
                "difficulty": "Hard"
            }
        ]
    }

    interview = _create_mock_interview_with_qa(
        db_session,
        user_id,
        [
            {
                "question_text": "How does Raft maintain consensus during leader election splits?",
                "answer_text": "Raft uses randomized election timeouts to prevent split votes. When a follower suspects the leader died, it transitions to candidate...",
                "correctness": 9.5,
                "completeness": 9.0,
                "depth": 9.0,
                "overall": 9.2,
                "strengths": '["Randomized timeouts", "Term numbering"]'
            }
        ]
    )

    resp = client.post(f"/api/analysis/{interview.id}/generate", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()

    assert data["readiness_score"] >= 90.0
    assert data["readiness_level"] == "Interview Ready"
    assert len(data["strengths"]) == 1
    assert data["strengths"][0]["competency"] == "Distributed Consensus & Raft"
    assert "randomized election timeouts" in data["strengths"][0]["candidate_excerpt"]
    assert len(data["roadmap_tasks"]) >= 1
    assert data["roadmap_tasks"][0]["priority"] == "MEDIUM"

@patch("backend.services.ai_service.AIService.deep_analyze_interview_session", new_callable=AsyncMock)
def test_weak_interview_captures_exact_evidence_and_misconceptions(mock_deep_ai, client, auth_header, db_session):
    me_resp = client.get("/api/auth/me", headers=auth_header)
    user_id = me_resp.json()["id"]

    mock_deep_ai.return_value = {
        "readiness_score": 45.0,
        "readiness_level": "Significant Remediation Required",
        "executive_summary": "Candidate exhibited fundamental misconceptions regarding database indexing, claiming indexes increase write throughput without locks.",
        "question_analyses": [
            {
                "question_id": "q1",
                "question_number": 1,
                "question_text": "How do B-Tree indexes impact database write and read performance?",
                "candidate_answer_excerpt": "Indexes make both reads and writes faster because the database doesn't need to check for duplicates.",
                "technical_correctness": 3.0,
                "conceptual_understanding": 3.5,
                "depth_and_clarity": 4.0,
                "reasoning_approach": 3.0,
                "completeness": 4.0,
                "key_strengths": [],
                "misconceptions": ["Belief that indexes improve write performance by avoiding duplicate checks"],
                "missing_concepts": ["B-Tree node balancing overhead on writes", "Write amplification and write lock contention"],
                "poorly_explained_aspects": ["Trade-off between read speed and write overhead"],
                "coding_evaluation": None
            }
        ],
        "skill_gaps": [
            {
                "gap_id": "gap_btree_1",
                "competency": "Database Indexing & Write Amplification",
                "category": "Storage Engines",
                "finding_type": "CONFIRMED_WEAKNESS",
                "confidence_level": "HIGH",
                "evidence_question_id": "q1",
                "evidence_question_number": 1,
                "evidence_question_text": "How do B-Tree indexes impact database write and read performance?",
                "candidate_answer_excerpt": "Indexes make both reads and writes faster because the database doesn't need to check for duplicates.",
                "what_was_missing_or_incorrect": "Candidate incorrectly stated that indexes make writes faster, failing to recognize index maintenance write amplification.",
                "why_it_matters": "In high-write OLTP systems, adding redundant indexes severely degrades insert throughput and causes lock contention.",
                "correct_understanding": "B-Tree indexes speed up lookups (O(log N)) but add substantial overhead to writes because every INSERT/UPDATE requires traversing and rebalancing the tree.",
                "priority": "CRITICAL",
                "remediation_path": {
                    "what_went_wrong": "Asserted that indexes speed up writes.",
                    "what_to_learn": "B-Tree node page splits, write amplification, and WAL logging.",
                    "what_to_practice": "Benchmark INSERT throughput on a table with 0 indexes vs 5 indexes in PostgreSQL.",
                    "how_to_verify": "Explain exact write pipeline trade-offs during a live technical review."
                }
            }
        ],
        "strengths": [],
        "untested_competencies": [
            {
                "competency": "Transaction Isolation Levels (MVCC)",
                "category": "Databases",
                "importance_for_role": "Vital for data integrity under concurrent access.",
                "recommended_next_step": "Test isolation anomalies: dirty reads vs phantom reads."
            }
        ],
        "roadmap_phases": [
            {
                "phase_number": 1,
                "title": "Phase 1: Remediation of Storage Engine Fundamentals",
                "duration_weeks": 1.0,
                "focus_areas": ["B-Tree Internals", "Write Amplification"],
                "milestone": "Master database write vs read cost mechanics"
            }
        ],
        "roadmap_tasks": [
            {
                "task_id": "task_btree",
                "phase_number": 1,
                "day_or_sequence": 1,
                "priority": "CRITICAL",
                "topic": "B-Tree Page Splits and Write Overhead",
                "subtopics": ["Clustered vs Secondary Indexes", "WAL Logging", "Fill Factor"],
                "learning_objectives": ["Understand why indexes degrade write performance"],
                "practical_exercise": "Profile an unindexed table vs multi-indexed table using pg_stat_user_tables.",
                "relevant_problems_or_questions": ["Explain how to optimize high-volume bulk inserts"],
                "estimated_duration_hours": 2.0,
                "expected_outcomes": "Clear articulation of write penalties.",
                "completion_criteria": "Verify write latency increase with automated benchmark.",
                "status": "pending"
            }
        ],
        "reassessment_questions": [
            {
                "id": "reassess_btree_1",
                "targeted_gap_id": "gap_btree_1",
                "competency": "Database Indexing",
                "question_text": "What happens at the disk storage level when you insert a row into a table with 4 secondary B-Tree indexes?",
                "expected_key_points": ["Base heap tuple write", "4 secondary tree traversals", "Potential node splits"],
                "benchmark_solution": "Each secondary index must be updated with a new leaf entry pointing to the heap tuple TID, causing additional I/O and possible page splits.",
                "difficulty": "Medium"
            }
        ]
    }

    interview = _create_mock_interview_with_qa(
        db_session,
        user_id,
        [
            {
                "question_text": "How do B-Tree indexes impact database write and read performance?",
                "answer_text": "Indexes make both reads and writes faster because the database doesn't need to check for duplicates.",
                "correctness": 3.0,
                "completeness": 3.5,
                "depth": 3.0,
                "overall": 3.2,
                "incorrect_claims": '["Indexes make writes faster"]',
                "missing_concepts": '["Node splits", "Write amplification"]'
            }
        ]
    )

    resp = client.post(f"/api/analysis/{interview.id}/generate", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()

    assert data["readiness_score"] < 60.0
    assert len(data["skill_gaps"]) == 1
    gap = data["skill_gaps"][0]
    assert gap["finding_type"] == "CONFIRMED_WEAKNESS"
    assert gap["priority"] == "CRITICAL"
    assert gap["evidence_question_number"] == 1
    assert "make both reads and writes faster" in gap["candidate_answer_excerpt"]
    assert "remediation_path" in gap
    assert gap["remediation_path"]["what_went_wrong"] != ""
    assert len(data["reassessment_questions"]) >= 1

@patch("backend.services.ai_service.AIService.deep_analyze_interview_session", side_effect=Exception("Offline test"))
def test_interactive_task_status_toggle_and_score_recalibration(mock_ai, client, auth_header, db_session):
    me_resp = client.get("/api/auth/me", headers=auth_header)
    user_id = me_resp.json()["id"]

    interview = _create_mock_interview_with_qa(
        db_session,
        user_id,
        [
            {
                "question_text": "Explain connection pooling.",
                "answer_text": "Connection pooling reuses open socket connections.",
                "correctness": 7.0,
                "completeness": 7.0,
                "depth": 6.5,
                "overall": 6.8,
                "missing_concepts": '["Connection starvation", "Timeout configuration"]'
            }
        ]
    )

    # Generate initial roadmap using fallback synthesis
    resp = client.post(f"/api/analysis/{interview.id}/generate", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["roadmap_tasks"]) > 0
    task_id = data["roadmap_tasks"][0]["task_id"]
    analysis_id = data["id"]
    initial_score = data["readiness_score"]

    # Toggle task to completed
    patch_resp = client.patch(
        f"/api/analysis/{analysis_id}/task/{task_id}",
        json={"status": "completed"},
        headers=auth_header
    )
    assert patch_resp.status_code == 200
    updated_data = patch_resp.json()
    updated_task = next(t for t in updated_data["roadmap_tasks"] if t["task_id"] == task_id)
    assert updated_task["status"] == "completed"
    assert updated_task["completed_at"] is not None
    assert updated_data["readiness_score"] >= initial_score

    # Toggle back to pending
    patch_resp2 = client.patch(
        f"/api/analysis/{analysis_id}/task/{task_id}",
        json={"status": "pending"},
        headers=auth_header
    )
    assert patch_resp2.status_code == 200
    pending_task = next(t for t in patch_resp2.json()["roadmap_tasks"] if t["task_id"] == task_id)
    assert pending_task["status"] == "pending"
    assert pending_task["completed_at"] is None

@patch("backend.services.ai_service.AIService.deep_analyze_interview_session", side_effect=Exception("Offline test"))
def test_preferences_update_recalibrates_durations(mock_ai, client, auth_header, db_session):
    me_resp = client.get("/api/auth/me", headers=auth_header)
    user_id = me_resp.json()["id"]

    interview = _create_mock_interview_with_qa(
        db_session,
        user_id,
        [
            {
                "question_text": "What is an idempotent API?",
                "answer_text": "An API where calling it multiple times results in the same server state.",
                "correctness": 8.5,
                "completeness": 8.0,
                "depth": 8.0,
                "overall": 8.2,
                "strengths": '["Understands HTTP PUT/DELETE idempotency"]'
            }
        ]
    )

    gen_resp = client.post(f"/api/analysis/{interview.id}/generate", headers=auth_header)
    analysis_id = gen_resp.json()["id"]

    # Update preferences: 4.5 hours daily study time and a specific target interview date
    pref_resp = client.patch(
        f"/api/analysis/{analysis_id}/preferences",
        json={
            "target_interview_date": "2026-11-20",
            "daily_study_hours": 4.5
        },
        headers=auth_header
    )
    assert pref_resp.status_code == 200
    data = pref_resp.json()
    assert data["target_interview_date"] == "2026-11-20"
    assert data["daily_study_hours"] == 4.5
    for task in data["roadmap_tasks"]:
        assert task["estimated_duration_hours"] == 4.5

def test_gemini_failure_resilient_evidence_synthesis(client, auth_header, db_session):
    """Verifies that if Gemini encounters HTTP 503 or quota limits, the system safely synthesizes an evidence-based roadmap."""
    me_resp = client.get("/api/auth/me", headers=auth_header)
    user_id = me_resp.json()["id"]

    interview = _create_mock_interview_with_qa(
        db_session,
        user_id,
        [
            {
                "question_text": "Explain thread safety in Java HashMaps.",
                "answer_text": "HashMap is not thread safe. Multiple threads put keys simultaneously and collide.",
                "category": "Java Concurrency",
                "correctness": 7.0,
                "completeness": 6.5,
                "depth": 6.0,
                "overall": 6.5,
                "incorrect_claims": '["Collision causes infinite loops in Java 8"]',
                "missing_concepts": '["ConcurrentHashMap segment locking", "Compare-and-swap (CAS) primitives"]',
                "strengths": '["Correctly identified HashMap as not thread safe"]'
            }
        ],
        role="Java Backend Engineer"
    )

    with patch("backend.services.ai_service.AIService.deep_analyze_interview_session", side_effect=Exception("Gemini quota 429/503 simulated")):
        resp = client.post(f"/api/analysis/{interview.id}/generate", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_role"] == "Java Backend Engineer"
        assert len(data["question_analyses"]) == 1
        assert "HashMap is not thread safe" in data["question_analyses"][0]["candidate_answer_excerpt"]
        assert len(data["skill_gaps"]) >= 1
        assert "Java Concurrency" in data["skill_gaps"][0]["competency"]
        assert len(data["roadmap_tasks"]) >= 1

@patch("backend.services.ai_service.AIService.deep_analyze_interview_session", side_effect=Exception("Offline test"))
def test_different_candidates_receive_meaningfully_different_roadmaps(mock_ai, client, auth_header, db_session):
    """Verifies that different candidates with different answers receive distinct evidence-based roadmaps."""
    me_resp = client.get("/api/auth/me", headers=auth_header)
    user_id = me_resp.json()["id"]

    # Candidate 1: Java & Concurrency Focus
    interview1 = _create_mock_interview_with_qa(
        db_session,
        user_id,
        [
            {
                "question_text": "How do virtual threads work in Java Project Loom?",
                "answer_text": "Virtual threads are lightweight threads managed by the JVM rather than OS kernel.",
                "category": "Java Loom",
                "correctness": 8.0,
                "completeness": 7.5,
                "depth": 7.0,
                "overall": 7.5,
                "missing_concepts": '["Carrier thread pinning", "Synchronized block blocking"]'
            }
        ],
        role="Java Architect"
    )

    # Candidate 2: Frontend & React Focus
    interview2 = _create_mock_interview_with_qa(
        db_session,
        user_id,
        [
            {
                "question_text": "Explain React fiber reconciliation and concurrent rendering.",
                "answer_text": "Fiber allows React to break rendering work into units and pause them.",
                "category": "React Internals",
                "correctness": 8.0,
                "completeness": 7.5,
                "depth": 7.0,
                "overall": 7.5,
                "missing_concepts": '["Double buffering workInProgress tree", "useTransition priority lanes"]'
            }
        ],
        role="Frontend Architect"
    )

    resp1 = client.post(f"/api/analysis/{interview1.id}/generate", headers=auth_header)
    resp2 = client.post(f"/api/analysis/{interview2.id}/generate", headers=auth_header)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    data1 = resp1.json()
    data2 = resp2.json()

    assert data1["target_role"] == "Java Architect"
    assert data2["target_role"] == "Frontend Architect"
    assert data1["skill_gaps"][0]["competency"] != data2["skill_gaps"][0]["competency"]
    assert "Java Loom" in data1["skill_gaps"][0]["competency"]
    assert "React Internals" in data2["skill_gaps"][0]["competency"]
