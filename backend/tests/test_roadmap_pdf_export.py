import io
import json
import pytest
import pypdf
from datetime import datetime

from backend.models.user import User
from backend.models.interview import Interview
from backend.models.roadmap import InterviewAnalysisRoadmap


@pytest.fixture
def candidate_auth(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "Jordan PDF Candidate",
            "email": "jordan_pdf@example.com",
            "password": "securepassword123",
            "target_role": "Senior Cloud Architect",
            "experience_level": "Senior"
        }
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_saved_roadmap(db_session, client, candidate_auth):
    me_resp = client.get("/api/auth/me", headers=candidate_auth)
    user_id = me_resp.json()["id"]

    interview = Interview(
        user_id=user_id,
        target_role="Senior Cloud Architect",
        experience_level="Senior",
        topic="Cloud Systems & Microservices",
        difficulty="Hard",
        num_questions=5,
        status="completed",
        total_score=78.5
    )
    db_session.add(interview)
    db_session.commit()
    db_session.refresh(interview)

    roadmap = InterviewAnalysisRoadmap(
        id="roadmap-pdf-test-1",
        interview_id=interview.id,
        user_id=user_id,
        target_role="Senior Cloud Architect",
        target_difficulty="Hard",
        target_interview_date="2026-12-15",
        daily_study_hours=2.5,
        readiness_score=78.5,
        readiness_level="Targeted Preparation Recommended",
        executive_summary="Candidate demonstrated solid mastery of event-driven cloud patterns but exhibited critical gaps in zero-downtime database migrations and multi-region consensus.",
        skill_gaps=json.dumps([
            {
                "gap_id": "gap-1",
                "competency": "Zero-Downtime Schema Migrations",
                "category": "Database Engineering",
                "finding_type": "CONFIRMED_WEAKNESS",
                "priority": "CRITICAL",
                "what_was_missing_or_incorrect": "Did not utilize expand-contract pattern for schema changes across active replica clusters.",
                "why_it_matters": "Leads to column lockouts and catastrophic downtime during production deployments.",
                "correct_understanding": "Adopt backward-compatible phased migrations: add column, dual-write, backfill, cutover.",
                "remediation_path": {
                    "what_went_wrong": "Attempted destructive alter table directly on production table.",
                    "what_to_learn": "Expand-contract migration patterns with gh-ost / pt-online-schema-change.",
                    "what_to_practice": "Execute simulated zero-downtime column rename under continuous load generator.",
                    "how_to_verify": "Zero dropped queries during migration under 500 RPS benchmark."
                }
            }
        ]),
        strengths=json.dumps([
            {
                "competency": "Asynchronous Event Streaming",
                "category": "Cloud Architecture",
                "demonstrated_mastery": "Articulated clear idempotent consumer patterns and Kafka dead-letter queues."
            }
        ]),
        roadmap_phases=json.dumps([
            {
                "phase_number": 1,
                "title": "Database Reliability & Schema Evolution",
                "duration_weeks": 1.5,
                "focus_areas": ["PostgreSQL", "Online Migrations", "Locks"],
                "milestone": "Master zero-downtime database migrations under load."
            },
            {
                "phase_number": 2,
                "title": "Distributed Multi-Region Consensus",
                "duration_weeks": 2.0,
                "focus_areas": ["Raft", "Multi-Region Replication", "Latency"],
                "milestone": "Architect active-active consensus clusters."
            }
        ]),
        roadmap_tasks=json.dumps([
            {
                "task_id": "task-1",
                "phase_number": 1,
                "day_or_sequence": 1,
                "priority": "CRITICAL",
                "topic": "Expand and Contract Schema Pattern",
                "learning_objectives": ["Understand phased column migrations", "Manage dual writes"],
                "practical_exercise": "Simulate column rename using dual-write views and triggers in PostgreSQL.",
                "estimated_duration_hours": 2.5,
                "expected_outcomes": "Zero table lockouts during write bursts.",
                "completion_criteria": "Successful zero-downtime migration test with continuous test traffic.",
                "status": "completed"
            },
            {
                "task_id": "task-2",
                "phase_number": 1,
                "day_or_sequence": 2,
                "priority": "HIGH",
                "topic": "Online Schema Change Tools (gh-ost)",
                "learning_objectives": ["Binlog streaming", "Ghost tables"],
                "practical_exercise": "Deploy gh-ost test against simulated 1M row database.",
                "estimated_duration_hours": 2.5,
                "expected_outcomes": "Non-blocking index generation.",
                "completion_criteria": "Verify row copy completion without replication lag spike.",
                "status": "pending"
            }
        ]),
        reassessment_questions=json.dumps([
            {
                "id": "retest-1",
                "targeted_gap_id": "gap-1",
                "competency": "Zero-Downtime Migrations",
                "difficulty": "Hard",
                "question_text": "How do you rename a column on a 100-million-row production PostgreSQL table without taking downtime or locks?",
                "expected_key_points": ["Add new nullable column", "Dual write in application code", "Backfill historical rows", "Cutover read path", "Deprecate old column"],
                "benchmark_solution": "Use expand-contract pattern: add new column, deploy app with dual writing, backfill asynchronously in batches, switch reads to new column, remove old column."
            }
        ])
    )
    db_session.add(roadmap)
    db_session.commit()
    db_session.refresh(roadmap)

    return {"interview": interview, "roadmap": roadmap}


def test_export_interview_roadmap_pdf_success(client, candidate_auth, sample_saved_roadmap):
    interview_id = sample_saved_roadmap["interview"].id

    resp = client.get(f"/api/analysis/{interview_id}/export/pdf", headers=candidate_auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="InterviewAI_Roadmap_Analysis.pdf"' in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF-")

    # Inspect generated PDF contents using pypdf
    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) >= 1

    extracted_text = " ".join([page.extract_text() for page in reader.pages])
    normalized_text = " ".join(extracted_text.split())

    # Candidate and Role verification
    assert "Jordan PDF Candidate" in normalized_text or "jordan_pdf@example.com" in normalized_text
    assert "Senior Cloud Architect" in normalized_text
    assert "78.5%" in normalized_text
    assert "Targeted Preparation Recommended" in normalized_text

    # Diagnostic & Gaps verification
    assert "Zero-Downtime Schema Migrations" in normalized_text
    assert "Expand and Contract Schema Pattern" in normalized_text
    assert "gh-ost" in normalized_text

    # Tasks and Completion Status
    assert "Day 1" in normalized_text
    assert "[✔] Done" in normalized_text or "Done" in normalized_text
    assert "[ ] Pending" in normalized_text or "Pending" in normalized_text

    # Reassessment Questions
    assert "How do you rename a column on a 100-million-row production PostgreSQL table" in normalized_text

    # Confidential Branding and Footer
    assert "InterviewAI" in normalized_text
    assert "Page 1 of" in normalized_text


def test_export_latest_roadmap_pdf_success(client, candidate_auth, sample_saved_roadmap):
    resp = client.get("/api/analysis/latest/export/pdf", headers=candidate_auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="InterviewAI_Roadmap_Analysis.pdf"' in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF-")

    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) >= 1
    extracted_text = " ".join([page.extract_text() for page in reader.pages])
    assert "Senior Cloud Architect" in extracted_text


def test_export_roadmap_pdf_multipage_handling(client, candidate_auth, db_session, sample_saved_roadmap):
    roadmap = sample_saved_roadmap["roadmap"]

    # Expand tasks and gaps to create multi-page document
    large_tasks = []
    for phase_idx in range(1, 5):
        for seq_idx in range(1, 6):
            large_tasks.append({
                "task_id": f"task-{phase_idx}-{seq_idx}",
                "phase_number": phase_idx,
                "day_or_sequence": seq_idx,
                "priority": "CRITICAL" if seq_idx == 1 else "HIGH",
                "topic": f"Comprehensive Engineering Module {phase_idx}.{seq_idx} - Deep Systems Architecture",
                "learning_objectives": [f"Deep dive into design tradeoff {seq_idx}A", f"Analyze system failure model {seq_idx}B"],
                "practical_exercise": f"Implement comprehensive test harness for phase {phase_idx} milestone {seq_idx}.",
                "estimated_duration_hours": 2.5,
                "completion_criteria": f"Achieve 100% pass on stress assertion harness {seq_idx}.",
                "status": "completed" if seq_idx == 1 else "pending"
            })
    roadmap.roadmap_tasks = json.dumps(large_tasks)
    db_session.commit()

    resp = client.get(f"/api/analysis/{roadmap.interview_id}/export/pdf", headers=candidate_auth)
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF-")

    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) > 1, f"Expected multi-page PDF, got {len(reader.pages)} page(s)"

    # Verify running header and page numbering on page 2
    page2_text = reader.pages[1].extract_text()
    assert "InterviewAI" in page2_text
    assert f"Page 2 of {len(reader.pages)}" in page2_text


def test_export_roadmap_pdf_empty_candidate_returns_404(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "Empty Candidate",
            "email": "empty_candidate@example.com",
            "password": "securepassword123",
            "target_role": "Junior Engineer",
            "experience_level": "Junior"
        }
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Latest PDF with no interviews
    resp = client.get("/api/analysis/latest/export/pdf", headers=headers)
    assert resp.status_code == 404
    assert "No preparation roadmap found" in resp.json()["detail"]

    # Non-existent interview ID
    resp_id = client.get("/api/analysis/non-existent-interview-id/export/pdf", headers=headers)
    assert resp_id.status_code == 404
    assert "not found" in resp_id.json()["detail"].lower()


def test_export_roadmap_pdf_unauthorized(client):
    resp = client.get("/api/analysis/latest/export/pdf")
    assert resp.status_code == 401

    resp2 = client.get("/api/analysis/some-id/export/pdf")
    assert resp2.status_code == 401


def test_export_roadmap_pdf_special_characters_safety(client, candidate_auth, db_session, sample_saved_roadmap):
    roadmap = sample_saved_roadmap["roadmap"]

    # Inject tricky characters like XML entities and symbols
    roadmap.target_role = "C++ & Python <Staff> Architect \"Core\""
    roadmap.executive_summary = "Candidate handles <template> metaprogramming & multi-threading safely: x < 10 && y > 20 'single quotes'."
    db_session.commit()

    resp = client.get(f"/api/analysis/{roadmap.interview_id}/export/pdf", headers=candidate_auth)
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF-")

    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    full_text = " ".join([page.extract_text() for page in reader.pages])
    assert "C++ & Python" in full_text or "C++" in full_text
