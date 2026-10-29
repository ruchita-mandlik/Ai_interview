import json
import uuid
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.models import (
    User,
    CandidateProfile,
    Interview,
    InterviewQuestion,
    Answer,
    Evaluation,
    InterviewAnalysisRoadmap
)
from backend.services.interview_memory_service import InterviewMemoryService
from backend.services.deep_analysis_service import DeepAnalysisService
from backend.utils.security import hash_password, create_access_token


def create_test_user(db: Session, email: str, name: str, role: str = "Backend Developer") -> User:
    user = User(
        id=str(uuid.uuid4()),
        name=name,
        email=email,
        password_hash=hash_password("password123")
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = CandidateProfile(
        id=str(uuid.uuid4()),
        user_id=user.id,
        full_name=name,
        email=email,
        target_role=role,
        skills="Python, SQL, System Design"
    )
    db.add(profile)
    db.commit()
    return user


def create_interview_with_evaluation(
    db: Session,
    user_id: str,
    title: str,
    topic: str,
    score: float,
    created_at: datetime,
    question_text: str,
    skill: str,
    missing_concepts: list,
    incorrect_claims: list,
    improvements: list,
    answer_text: str = "Candidate sample answer"
) -> Interview:
    interview = Interview(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=title,
        interview_type="Technical",
        topic=topic,
        difficulty="Medium",
        target_role="Backend Developer",
        status="completed",
        total_score=score,
        created_at=created_at
    )
    db.add(interview)
    db.flush()

    question = InterviewQuestion(
        id=str(uuid.uuid4()),
        interview_id=interview.id,
        question_number=1,
        question_text=question_text,
        category=topic,
        skill=skill,
        difficulty="Medium"
    )
    db.add(question)
    db.flush()

    answer = Answer(
        id=str(uuid.uuid4()),
        interview_id=interview.id,
        question_id=question.id,
        user_id=user_id,
        answer_text=answer_text
    )
    db.add(answer)
    db.flush()

    evaluation = Evaluation(
        id=str(uuid.uuid4()),
        interview_id=interview.id,
        question_id=question.id,
        answer_id=answer.id,
        technical_correctness=score,
        conceptual_completeness=score,
        response_relevance=score,
        structural_clarity=score,
        depth_of_understanding=score,
        overall_score=score,
        strengths=json.dumps(["Understands high-level purpose"]),
        improvements=json.dumps(improvements),
        missing_concepts=json.dumps(missing_concepts),
        incorrect_claims=json.dumps(incorrect_claims),
        feedback="Test question feedback",
        model_answer="Test ideal model answer",
        created_at=created_at
    )
    db.add(evaluation)
    db.commit()
    db.refresh(interview)
    return interview


def test_empty_interview_history(db_session: Session):
    """Verifies clean, non-fabricated response when candidate has 0 completed interviews."""
    user = create_test_user(db_session, "empty@example.com", "Empty Candidate")

    summary = InterviewMemoryService.get_user_memory_summary(db_session, user)

    assert summary.user_id == user.id
    assert summary.total_completed_interviews == 0
    assert summary.total_answers_evaluated == 0
    assert summary.overall_average_score == 0.0
    assert summary.recurring_weaknesses == []
    assert summary.one_time_mistakes == []
    assert summary.improved_skills == []
    assert summary.declining_skills == []
    assert summary.persistent_mistakes_count == 0
    assert summary.next_best_action is not None
    assert summary.next_best_action.action_type == "TAKE_INITIAL_MOCK"


def test_one_time_mistake_vs_repeated_weakness_detection(db_session: Session):
    """
    Verifies that a mistake in session 1 is flagged as a one-time mistake,
    and when the same mistake repeats in session 2, it is upgraded to a recurring weakness.
    """
    user = create_test_user(db_session, "candidate1@example.com", "Candidate One")
    now = datetime.utcnow()

    # Session 1: Candidate struggles with Deadlock Prevention (score: 45%)
    i1 = create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 1 - OS Concurrency",
        topic="Operating Systems",
        score=45.0,
        created_at=now - timedelta(days=2),
        question_text="Explain Coffman conditions and how to prevent deadlocks in multi-threaded systems.",
        skill="Concurrency & Locking",
        missing_concepts=["Hold and Wait Condition", "Circular Wait Condition"],
        incorrect_claims=["Claimed mutexes prevent deadlocks automatically"],
        improvements=["Circular wait elimination"]
    )

    summary1 = InterviewMemoryService.get_user_memory_summary(db_session, user)
    assert summary1.total_completed_interviews == 1
    assert summary1.overall_average_score == 45.0
    # Because it is only in 1 session / 1 question, it should be categorized as one_time_mistakes
    assert len(summary1.recurring_weaknesses) == 0
    assert len(summary1.one_time_mistakes) > 0
    assert any("circular wait" in m.concept.lower() for m in summary1.one_time_mistakes)

    # Session 2: Candidate again struggles with Circular Wait and Deadlock (score: 50%)
    i2 = create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 2 - Distributed Locks",
        topic="Operating Systems",
        score=50.0,
        created_at=now - timedelta(days=1),
        question_text="How would you design a resource hierarchy to guarantee no circular wait?",
        skill="Concurrency & Locking",
        missing_concepts=["Circular Wait Condition"],
        incorrect_claims=[],
        improvements=["Circular wait elimination"]
    )

    summary2 = InterviewMemoryService.get_user_memory_summary(db_session, user)
    assert summary2.total_completed_interviews == 2
    # Now Circular Wait was observed across 2 sessions -> Must be detected as recurring weakness!
    assert len(summary2.recurring_weaknesses) >= 1
    rw = next(w for w in summary2.recurring_weaknesses if "circular wait" in w.concept.lower())
    assert rw.recurrence_count >= 2
    assert rw.status == "active_weakness"
    assert len(rw.supporting_sessions) >= 2
    assert summary2.persistent_mistakes_count >= 1
    # Next Best Action should target this repeated weakness
    assert summary2.next_best_action.action_type == "REMEDIATE_WEAKNESS"
    assert "circular wait" in summary2.next_best_action.title.lower() or "remediate" in summary2.next_best_action.title.lower()


def test_verified_improvement_detection(db_session: Session):
    """
    Verifies that when a candidate scores poorly on a skill earlier,
    and subsequently scores >= 75% on that skill, it is detected as an improved skill.
    """
    user = create_test_user(db_session, "improver@example.com", "Improving Candidate")
    now = datetime.utcnow()

    # Session 1: Poor score on SQL Indexing (40%)
    create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 1 - Database Fundamentals",
        topic="Database",
        score=40.0,
        created_at=now - timedelta(days=5),
        question_text="What is a B-Tree index and how does composite indexing work?",
        skill="SQL & Indexing",
        missing_concepts=["Leftmost Prefix Rule"],
        incorrect_claims=[],
        improvements=["Review composite index left prefix rule"]
    )

    # Session 2: Poor score again on SQL Indexing (50%)
    create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 2 - Query Optimization",
        topic="Database",
        score=50.0,
        created_at=now - timedelta(days=3),
        question_text="Why did the query perform a full table scan despite having an index?",
        skill="SQL & Indexing",
        missing_concepts=["Leftmost Prefix Rule"],
        incorrect_claims=[],
        improvements=["Review composite index left prefix rule"]
    )

    # Session 3: Candidate studied and performs strongly on SQL Indexing (88%)
    create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 3 - Advanced Indexing",
        topic="Database",
        score=88.0,
        created_at=now - timedelta(days=1),
        question_text="Explain B-tree balancing and leftmost prefix execution plans.",
        skill="SQL & Indexing",
        missing_concepts=[],
        incorrect_claims=[],
        improvements=["Solid mastery demonstrated"]
    )

    summary = InterviewMemoryService.get_user_memory_summary(db_session, user)

    assert summary.total_completed_interviews == 3
    # Improved skills should now contain SQL & Indexing
    assert len(summary.improved_skills) >= 1
    sql_skill = next(s for s in summary.improved_skills if "SQL" in s.skill or "Indexing" in s.skill)
    assert sql_skill.latest_score == 88.0
    assert sql_skill.score_delta > 0
    assert sql_skill.status in ("improving", "mastered")
    assert "improved from" in sql_skill.evidence_summary.lower()


def test_session_to_session_comparison(db_session: Session):
    """
    Tests session-to-session comparison:
    - Session 1 is baseline.
    - Session 2 compares against session 1, detecting repeated mistakes and score drop/gain.
    """
    user = create_test_user(db_session, "compare@example.com", "Comparison Candidate")
    now = datetime.utcnow()

    # Session 1: Baseline (Score: 65%)
    i1 = create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 1 - Java OOP",
        topic="Java",
        score=65.0,
        created_at=now - timedelta(days=3),
        question_text="Explain polymorphism and dynamic method dispatch in Java.",
        skill="OOP Design",
        missing_concepts=["VTable Lookups"],
        incorrect_claims=[],
        improvements=["Explain vtable dispatch"]
    )

    # Baseline comparison check
    comp1 = InterviewMemoryService.compare_session_to_previous(db_session, user.id, i1.id)
    assert comp1.is_baseline_session is True
    assert comp1.current_score == 65.0
    assert comp1.previous_score is None
    assert comp1.score_change is None
    assert "baseline" in comp1.trend_explanation.lower()

    # Session 2: Score 80% (+15%)
    i2 = create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 2 - Java OOP Deep Dive",
        topic="Java",
        score=80.0,
        created_at=now - timedelta(days=1),
        question_text="How does JVM handle interface method dispatch vs virtual methods?",
        skill="OOP Design",
        missing_concepts=[],
        incorrect_claims=[],
        improvements=[]
    )

    comp2 = InterviewMemoryService.compare_session_to_previous(db_session, user.id, i2.id)
    assert comp2.is_baseline_session is False
    assert comp2.current_score == 80.0
    assert comp2.previous_score == 65.0
    assert comp2.score_change == 15.0
    assert comp2.improvement_trend == "improving"
    assert len(comp2.newly_resolved_weaknesses) >= 1
    assert comp2.newly_resolved_weaknesses[0]["status"] == "resolved"


def test_strict_user_data_isolation(db_session: Session):
    """
    Verifies that User A's evaluations, weaknesses, and memory are never leaked
    or mixed with User B's data.
    """
    user_a = create_test_user(db_session, "user_a@example.com", "User Alice")
    user_b = create_test_user(db_session, "user_b@example.com", "User Bob")
    now = datetime.utcnow()

    # User A has 2 failed interviews on "Memory Leak Detection"
    create_interview_with_evaluation(
        db=db_session,
        user_id=user_a.id,
        title="Alice Interview 1",
        topic="Performance",
        score=35.0,
        created_at=now - timedelta(days=2),
        question_text="How do you profile a heap dump to detect memory leaks?",
        skill="Memory Profiling",
        missing_concepts=["Dominator Tree Analysis"],
        incorrect_claims=[],
        improvements=["Dominator tree inspection"]
    )
    create_interview_with_evaluation(
        db=db_session,
        user_id=user_a.id,
        title="Alice Interview 2",
        topic="Performance",
        score=40.0,
        created_at=now - timedelta(days=1),
        question_text="What causes GC pauses in high-throughput JVM applications?",
        skill="Memory Profiling",
        missing_concepts=["Dominator Tree Analysis"],
        incorrect_claims=[],
        improvements=["Dominator tree inspection"]
    )

    # User B has 1 interview with 95% on "System Design"
    i_b = create_interview_with_evaluation(
        db=db_session,
        user_id=user_b.id,
        title="Bob System Design",
        topic="System Design",
        score=95.0,
        created_at=now,
        question_text="Design a distributed rate limiter using Redis token buckets.",
        skill="Distributed Systems",
        missing_concepts=[],
        incorrect_claims=[],
        improvements=[]
    )

    summary_a = InterviewMemoryService.get_user_memory_summary(db_session, user_a)
    summary_b = InterviewMemoryService.get_user_memory_summary(db_session, user_b)

    # Alice's stats
    assert summary_a.user_id == user_a.id
    assert summary_a.total_completed_interviews == 2
    assert summary_a.persistent_mistakes_count >= 1

    # Bob's stats MUST BE STRICTLY ISOLATED
    assert summary_b.user_id == user_b.id
    assert summary_b.total_completed_interviews == 1
    assert summary_b.overall_average_score == 95.0
    assert summary_b.persistent_mistakes_count == 0
    assert len(summary_b.recurring_weaknesses) == 0
    # None of Alice's memory leak concepts should exist in Bob's data
    for w in summary_b.recurring_weaknesses:
        assert "dominator" not in w.concept.lower()
    for m in summary_b.one_time_mistakes:
        assert "dominator" not in m.concept.lower()

    # Bob comparing his session should NOT see Alice's previous sessions
    comp_b = InterviewMemoryService.compare_session_to_previous(db_session, user_b.id, i_b.id)
    assert comp_b.is_baseline_session is True
    assert comp_b.previous_interview_id is None


def test_roadmap_sync_with_memory(db_session: Session):
    """
    Verifies that when a roadmap is created or synchronized,
    active recurring weaknesses are automatically scheduled into tasks,
    and verified resolved skills update pending tasks to completed.
    """
    user = create_test_user(db_session, "roadmap_sync@example.com", "Roadmap Candidate")
    now = datetime.utcnow()

    # Candidate has recurring weakness in "CAP Theorem" across 2 sessions
    create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 1",
        topic="System Design",
        score=45.0,
        created_at=now - timedelta(days=3),
        question_text="Explain PACELC and CAP theorem trade-offs.",
        skill="Distributed Systems",
        missing_concepts=["PACELC Latency Trade-off"],
        incorrect_claims=[],
        improvements=["PACELC theorem"]
    )
    i2 = create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 2",
        topic="System Design",
        score=50.0,
        created_at=now - timedelta(days=2),
        question_text="How does DynamoDB handle network partitions?",
        skill="Distributed Systems",
        missing_concepts=["PACELC Latency Trade-off"],
        incorrect_claims=[],
        improvements=["PACELC theorem"]
    )

    # Create dummy roadmap record
    roadmap = InterviewAnalysisRoadmap(
        id=str(uuid.uuid4()),
        interview_id=i2.id,
        user_id=user.id,
        target_role="Backend Developer",
        target_difficulty="Medium",
        readiness_score=50.0,
        readiness_level="Needs Targeted Preparation",
        executive_summary="Summary",
        question_analyses=json.dumps([]),
        skill_gaps=json.dumps([]),
        strengths=json.dumps([]),
        untested_competencies=json.dumps([]),
        roadmap_phases=json.dumps([]),
        roadmap_tasks=json.dumps([
            {
                "task_id": "existing-task-1",
                "phase_number": 1,
                "day_or_sequence": 1,
                "priority": "HIGH",
                "topic": "General Database Systems",
                "subtopics": [],
                "learning_objectives": [],
                "practical_exercise": "Practice queries",
                "relevant_problems_or_questions": [],
                "estimated_duration_hours": 1.5,
                "expected_outcomes": "Outcome",
                "completion_criteria": "Pass test",
                "status": "pending",
                "completed_at": None
            }
        ]),
        reassessment_questions=json.dumps([]),
        created_at=now,
        updated_at=now
    )
    db_session.add(roadmap)
    db_session.commit()

    # Sync roadmap with memory
    InterviewMemoryService.sync_roadmap_with_memory(db_session, user.id, roadmap)

    tasks_after_sync = json.loads(roadmap.roadmap_tasks)
    assert len(tasks_after_sync) >= 2
    # One of the new tasks must remediate PACELC
    remediation_task = next((t for t in tasks_after_sync if "pacelc" in t["topic"].lower()), None)
    assert remediation_task is not None
    assert remediation_task["status"] == "pending"


def test_api_endpoints_integration(client: TestClient, db_session: Session):
    """
    Tests HTTP endpoints:
    - GET /api/intelligence/memory-summary
    - GET /api/intelligence/session-comparison/{id}
    - GET /api/dashboard contains memory_intelligence
    """
    user = create_test_user(db_session, "api_test@example.com", "API Candidate")
    token = create_access_token(data={"sub": user.id})
    headers = {"Authorization": f"Bearer {token}"}
    now = datetime.utcnow()

    # Initially empty memory summary
    res_empty = client.get("/api/intelligence/memory-summary", headers=headers)
    assert res_empty.status_code == 200
    data_empty = res_empty.json()
    assert data_empty["total_completed_interviews"] == 0
    assert data_empty["overall_average_score"] == 0.0

    # Add 1 completed interview
    i1 = create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="API Mock 1",
        topic="Python",
        score=78.0,
        created_at=now - timedelta(days=1),
        question_text="How does GIL affect multi-threaded CPU-bound programs in Python?",
        skill="Concurrency",
        missing_concepts=[],
        incorrect_claims=[],
        improvements=["Mention multiprocessing alternative"]
    )

    # Verify session comparison via API
    res_comp = client.get(f"/api/intelligence/session-comparison/{i1.id}", headers=headers)
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["current_interview_id"] == i1.id
    assert comp_data["is_baseline_session"] is True
    assert comp_data["current_score"] == 78.0

    # Verify /api/dashboard endpoint includes memory_intelligence
    res_dash = client.get("/api/dashboard", headers=headers)
    assert res_dash.status_code == 200
    dash_data = res_dash.json()
    assert "memory_intelligence" in dash_data
    assert dash_data["memory_intelligence"] is not None
    assert dash_data["memory_intelligence"]["total_completed_interviews"] == 1
    assert dash_data["memory_intelligence"]["overall_average_score"] == 78.0

    # Test unauthorized user accessing Alice's interview comparison
    user2 = create_test_user(db_session, "stranger@example.com", "Stranger")
    token2 = create_access_token(data={"sub": user2.id})
    headers2 = {"Authorization": f"Bearer {token2}"}

    res_forbidden = client.get(f"/api/intelligence/session-comparison/{i1.id}", headers=headers2)
    assert res_forbidden.status_code in (403, 404)


def test_analytics_dashboard_aggregation_and_ordering(db_session: Session):
    user = create_test_user(db_session, "timeline_user@example.com", "Timeline User")
    now = datetime.utcnow()

    # Create 3 interviews with strictly non-chronological insertion to verify sorting
    # Day -5 (Score 75)
    create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 2",
        topic="Python",
        score=75.0,
        created_at=now - timedelta(days=5),
        question_text="Q2",
        skill="Data Structures",
        missing_concepts=["Graph traversal"],
        incorrect_claims=[],
        improvements=[]
    )
    # Day -10 (Score 60)
    create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 1",
        topic="Python",
        score=60.0,
        created_at=now - timedelta(days=10),
        question_text="Q1",
        skill="Data Structures",
        missing_concepts=["Binary Search"],
        incorrect_claims=[],
        improvements=[]
    )
    # Day -1 (Score 90)
    create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Session 3",
        topic="Python",
        score=90.0,
        created_at=now - timedelta(days=1),
        question_text="Q3",
        skill="Data Structures",
        missing_concepts=[],
        incorrect_claims=[],
        improvements=["Excellent asymptotic analysis"]
    )

    analytics = InterviewMemoryService.get_analytics_dashboard(db_session, user)

    assert analytics.valid_evaluated_sessions == 3
    assert analytics.excluded_incomplete_sessions == 0
    assert analytics.overall_average_score == 75.0
    assert analytics.highest_score == 90.0
    assert analytics.lowest_score == 60.0

    # Verify chronological ordering (Day -10, Day -5, Day -1)
    trajectory = analytics.score_trajectory
    assert len(trajectory) == 3
    assert trajectory[0].session_title == "Session 1"
    assert trajectory[0].score == 60.0
    assert trajectory[0].score_change is None
    assert trajectory[0].trend_direction == "baseline"

    assert trajectory[1].session_title == "Session 2"
    assert trajectory[1].score == 75.0
    assert trajectory[1].score_change == 15.0
    assert trajectory[1].trend_direction == "up"

    assert trajectory[2].session_title == "Session 3"
    assert trajectory[2].score == 90.0
    assert trajectory[2].score_change == 15.0
    assert trajectory[2].trend_direction == "up"

    # Verify skill performance baseline vs latest
    assert len(analytics.skill_performance) >= 1
    ds_skill = next(s for s in analytics.skill_performance if "Data Structures" in s.skill)
    assert ds_skill.has_sufficient_evidence is True
    assert ds_skill.evaluation_count == 3
    assert ds_skill.latest_score >= ds_skill.baseline_score


def test_analytics_dashboard_zero_vs_missing_scores(db_session: Session):
    user = create_test_user(db_session, "zero_score_user@example.com", "Zero Score User")
    now = datetime.utcnow()

    # Session 1: completed with genuine 0.0 score
    create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Failed Session",
        topic="Algorithms",
        score=0.0,
        created_at=now - timedelta(days=3),
        question_text="Dynamic Programming Question",
        skill="Dynamic Programming",
        missing_concepts=["Memoization table"],
        incorrect_claims=["Claimed O(1) for exponential recurrence"],
        improvements=[]
    )

    # Session 2: completed with 80.0 score
    create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Passing Session",
        topic="Algorithms",
        score=80.0,
        created_at=now - timedelta(days=1),
        question_text="Greedy Algorithm Question",
        skill="Dynamic Programming",
        missing_concepts=[],
        incorrect_claims=[],
        improvements=[]
    )

    # Session 3: incomplete session (in_progress, missing score and evaluation)
    incomplete_interview = Interview(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title="Incomplete Session",
        topic="Algorithms",
        status="in_progress",
        total_score=None,
        created_at=now
    )
    db_session.add(incomplete_interview)
    db_session.commit()

    analytics = InterviewMemoryService.get_analytics_dashboard(db_session, user)

    # Incomplete session excluded, valid completed sessions included
    assert analytics.valid_evaluated_sessions == 2
    assert analytics.excluded_incomplete_sessions == 1
    assert "excluded" in analytics.exclusion_reason.lower()

    # Genuine 0.0 score is preserved in calculation
    assert analytics.lowest_score == 0.0
    assert analytics.highest_score == 80.0
    assert analytics.overall_average_score == 40.0  # (0.0 + 80.0) / 2

    # Check score distribution: genuine 0.0 should be counted in "Below 50%" bin
    below_50_bin = next(b for b in analytics.score_distribution if "Below 50%" in b.bin_label)
    assert below_50_bin.count == 1
    assert below_50_bin.percentage == 50.0


def test_analytics_dashboard_no_duplicate_weakness_in_one_session(db_session: Session):
    user = create_test_user(db_session, "dedup_user@example.com", "Dedup User")
    now = datetime.utcnow()

    # Create 1 interview with 3 questions all reporting the SAME weakness: "Index Fragmentation"
    interview = Interview(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title="Database Session",
        topic="SQL",
        status="completed",
        total_score=55.0,
        created_at=now
    )
    db_session.add(interview)
    db_session.flush()

    for idx in range(1, 4):
        q = InterviewQuestion(
            id=str(uuid.uuid4()),
            interview_id=interview.id,
            question_number=idx,
            question_text=f"Database Question {idx}",
            skill="Database Indexing"
        )
        db_session.add(q)
        db_session.flush()

        ans = Answer(
            id=str(uuid.uuid4()),
            interview_id=interview.id,
            question_id=q.id,
            user_id=user.id,
            answer_text="Sample candidate answer on indexing"
        )
        db_session.add(ans)
        db_session.flush()

        ev = Evaluation(
            id=str(uuid.uuid4()),
            interview_id=interview.id,
            question_id=q.id,
            answer_id=ans.id,
            overall_score=5.5,
            missing_concepts=json.dumps(["Index Fragmentation", "B-Tree Depth"]),
            improvements=json.dumps(["Explain Index Fragmentation"]),
            incorrect_claims=json.dumps([])
        )
        db_session.add(ev)
    db_session.commit()

    analytics = InterviewMemoryService.get_analytics_dashboard(db_session, user)

    # In weakness_frequency, "Index Fragmentation" must count as 1 distinct session occurrence
    frag_weakness = next((w for w in analytics.weakness_frequency if "Index Fragmentation" in w.concept), None)
    assert frag_weakness is not None
    assert frag_weakness.session_occurrences == 1  # Exactly 1 session! NOT 3!
    assert frag_weakness.total_question_occurrences == 3  # But appeared in 3 questions


def test_analytics_dashboard_date_filtering(db_session: Session):
    user = create_test_user(db_session, "date_filter_user@example.com", "Filter User")
    now = datetime.utcnow()

    # Session 1: 45 days ago
    create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Old Session",
        topic="Java",
        score=65.0,
        created_at=now - timedelta(days=45),
        question_text="Old Java Question",
        skill="Java Core",
        missing_concepts=["Garbage Collection"],
        incorrect_claims=[],
        improvements=[]
    )

    # Session 2: 10 days ago
    create_interview_with_evaluation(
        db=db_session,
        user_id=user.id,
        title="Recent Session",
        topic="Java",
        score=85.0,
        created_at=now - timedelta(days=10),
        question_text="Recent Java Question",
        skill="Java Core",
        missing_concepts=[],
        incorrect_claims=[],
        improvements=[]
    )

    # Query with date_from set to 20 days ago
    filter_date = (now - timedelta(days=20)).strftime("%Y-%m-%d")
    analytics_filtered = InterviewMemoryService.get_analytics_dashboard(
        db=db_session,
        user=user,
        date_from=filter_date
    )

    # Old session is filtered out, only recent session is included
    assert analytics_filtered.valid_evaluated_sessions == 1
    assert analytics_filtered.overall_average_score == 85.0
    assert analytics_filtered.score_trajectory[0].session_title == "Recent Session"


def test_analytics_dashboard_api_endpoint_and_user_isolation(client: TestClient, db_session: Session):
    user_a = create_test_user(db_session, "user_a@example.com", "User A")
    user_b = create_test_user(db_session, "user_b@example.com", "User B")
    now = datetime.utcnow()

    # User A creates 2 interviews
    create_interview_with_evaluation(
        db=db_session,
        user_id=user_a.id,
        title="User A Session 1",
        topic="System Design",
        score=70.0,
        created_at=now - timedelta(days=2),
        question_text="Design Rate Limiter",
        skill="System Design",
        missing_concepts=["Token Bucket algorithm"],
        incorrect_claims=[],
        improvements=[]
    )
    create_interview_with_evaluation(
        db=db_session,
        user_id=user_a.id,
        title="User A Session 2",
        topic="System Design",
        score=82.0,
        created_at=now - timedelta(days=1),
        question_text="Design Cache",
        skill="System Design",
        missing_concepts=[],
        incorrect_claims=[],
        improvements=[]
    )

    # User B creates 1 interview with completely different score
    create_interview_with_evaluation(
        db=db_session,
        user_id=user_b.id,
        title="User B Confidential Session",
        topic="Security",
        score=99.0,
        created_at=now,
        question_text="Cryptography Question",
        skill="Cryptography",
        missing_concepts=[],
        incorrect_claims=[],
        improvements=[]
    )

    token_a = create_access_token(data={"sub": user_a.id})
    headers_a = {"Authorization": f"Bearer {token_a}"}

    res = client.get("/api/intelligence/analytics-dashboard", headers=headers_a)
    assert res.status_code == 200
    data = res.json()

    # User A should only see 2 sessions with average 76.0
    assert data["valid_evaluated_sessions"] == 2
    assert data["overall_average_score"] == 76.0
    for sess in data["score_trajectory"]:
        assert "User A" in sess["session_title"]
        assert "User B" not in sess["session_title"]

