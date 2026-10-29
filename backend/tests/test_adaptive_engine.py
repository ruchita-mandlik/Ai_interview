import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException

from backend.schemas.evaluation import AdaptiveAction, AdaptiveDecision
from backend.services.ai_service import AIService
from backend.models.interview import Interview
from backend.models.question import InterviewQuestion
from backend.models.answer import Answer
from backend.models.evaluation import Evaluation


@pytest.fixture
def auth_header(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "Adaptive Engineer",
            "email": "adaptive.engineer@enterprise.ai",
            "password": "ProductionPassword123!"
        }
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def setup_interview_helper(client, auth_header):
    """Helper to spin up an interview with custom parameters."""
    def _create(
        role="Principal Distributed Systems Architect",
        experience="Lead / Staff",
        difficulty="Medium",
        num_questions=3,
        job_description="Architecting high-throughput low-latency event-driven microservices with Raft consensus.",
        skills=["Distributed Consensus", "Raft", "Kafka", "Fault Tolerance"],
        interview_type="System Design"
    ):
        with patch("backend.services.ai_service.AIService.generate_interview_questions", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {
                    "question": "How does Raft handle log replication and network partitions?",
                    "category": "Distributed Systems",
                    "skill": "Raft Consensus",
                    "difficulty": difficulty,
                    "additional_instruction": "Detail leader election and split-brain prevention."
                }
            ]
            resp = client.post(
                "/api/interviews/start",
                json={
                    "interview_type": interview_type,
                    "target_role": role,
                    "experience_level": experience,
                    "difficulty": difficulty,
                    "num_questions": num_questions,
                    "job_description": job_description,
                    "technical_skills": skills
                },
                headers=auth_header
            )
            assert resp.status_code == 201
            return resp.json()
    return _create


# =====================================================================
# 1. TEST STRONG ANSWER -> INCREASE_DIFFICULTY
# =====================================================================
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_strong_answer_increases_difficulty(mock_eval, mock_adaptive_q, client, auth_header, setup_interview_helper):
    """A strong, architecturally rigorous answer should trigger INCREASE_DIFFICULTY."""
    interview_data = setup_interview_helper(difficulty="Medium")
    interview_id = interview_data["id"]
    first_q = interview_data["questions"][0]

    mock_eval.return_value = {
        "score": 95,
        "strengths": ["Clear breakdown of Raft term numbers", "Explained quorum heartbeats and election timeouts"],
        "weaknesses": [],
        "missing_concepts": [],
        "incorrect_claims": [],
        "actionable_feedback": "Mastery level understanding of leader election.",
        "technical_correctness": 96,
        "conceptual_completeness": 94,
        "structural_clarity": 95,
        "depth_of_understanding": 95,
        "model_answer": "Benchmark explanation of split-brain prevention via strict majorities."
    }

    mock_adaptive_q.return_value = {
        "action": AdaptiveAction.INCREASE_DIFFICULTY.value,
        "updated_difficulty": "Hard",
        "decision_rationale": "Candidate demonstrated deep mastery of Raft. Escalating to distributed consensus failure modes and Byzantine fault tolerance.",
        "next_question": "How would you handle cascading leader failures during concurrent partition healing in a geo-distributed multi-datacenter cluster?",
        "assessment_objective": "Evaluate understanding of consensus edge cases and cross-WAN latency trade-offs.",
        "identified_knowledge_gaps": []
    }

    resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={
            "question_id": first_q["id"],
            "answer_text": "In Raft, a leader requires a strict majority quorum (N/2 + 1) to commit log entries. During network partitions, minority partitions cannot achieve quorum so they reject commits, preventing split-brain anomalies."
        },
        headers=auth_header
    )

    assert resp.status_code == 200
    data = resp.json()

    assert data["evaluation"]["score"] == 95
    assert data["adaptive_action"] == "INCREASE_DIFFICULTY"
    assert data["current_difficulty"] == "Hard"
    assert "Escalating" in data["decision_rationale"]
    assert data["next_question"]["difficulty"] == "Hard"
    assert data["next_question"]["adaptive_action"] == "INCREASE_DIFFICULTY"
    assert "cascading leader failures" in data["next_question"]["question_text"]


# =====================================================================
# 2. TEST PARTIALLY CORRECT ANSWER -> FOLLOW_UP
# =====================================================================
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_partially_correct_answer_triggers_follow_up(mock_eval, mock_adaptive_q, client, auth_header, setup_interview_helper):
    """A partially correct answer should trigger FOLLOW_UP to probe missing concepts."""
    interview_data = setup_interview_helper(difficulty="Medium")
    interview_id = interview_data["id"]
    first_q = interview_data["questions"][0]

    mock_eval.return_value = {
        "score": 68,
        "strengths": ["Understands basic quorum principle"],
        "weaknesses": ["Did not mention term numbers or how stale leaders are stepped down"],
        "missing_concepts": ["Term number validation", "Leader step-down on higher term"],
        "incorrect_claims": [],
        "actionable_feedback": "Address term number monotonic progression.",
        "technical_correctness": 70,
        "conceptual_completeness": 65,
        "structural_clarity": 70,
        "depth_of_understanding": 67,
        "model_answer": "Full consensus protocol handling stale leaders."
    }

    mock_adaptive_q.return_value = {
        "action": AdaptiveAction.FOLLOW_UP.value,
        "updated_difficulty": "Medium",
        "decision_rationale": "Candidate understood basic quorum but omitted how stale leaders detect partition reconnection. Probing term number synchronization.",
        "next_question": "When the network heals, how does the old isolated leader discover that it is no longer valid and safely revert to follower status?",
        "assessment_objective": "Assess comprehension of Raft term monotonicity and leader step-down mechanism.",
        "identified_knowledge_gaps": ["Term number validation"]
    }

    resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={
            "question_id": first_q["id"],
            "answer_text": "Raft uses a majority vote so the bigger side can still write and the small side stops."
        },
        headers=auth_header
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["adaptive_action"] == "FOLLOW_UP"
    assert data["current_difficulty"] == "Medium"
    assert "Term number validation" in data["knowledge_gaps"]
    assert "old isolated leader discover" in data["next_question"]["question_text"]
    assert data["next_question"]["is_follow_up"] is True


# =====================================================================
# 3. TEST WEAK ANSWER -> SIMPLIFY
# =====================================================================
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_weak_answer_triggers_simplify(mock_eval, mock_adaptive_q, client, auth_header, setup_interview_helper):
    """A weak answer (<60%) should trigger SIMPLIFY and reduce difficulty."""
    interview_data = setup_interview_helper(difficulty="Hard")
    interview_id = interview_data["id"]
    first_q = interview_data["questions"][0]

    mock_eval.return_value = {
        "score": 42,
        "strengths": ["Recognizes that distributed systems have multiple servers"],
        "weaknesses": ["Confuses consensus with database replication", "Does not understand split brain"],
        "missing_concepts": ["Quorum calculation", "Log matching property", "Consensus state machine"],
        "incorrect_claims": ["Stated that any node can write at any time without coordinating"],
        "actionable_feedback": "Review the core difference between single-leader replication and consensus protocols.",
        "technical_correctness": 40,
        "conceptual_completeness": 45,
        "structural_clarity": 45,
        "depth_of_understanding": 38,
        "model_answer": "Fundamental concepts of distributed consensus."
    }

    mock_adaptive_q.return_value = {
        "action": AdaptiveAction.SIMPLIFY.value,
        "updated_difficulty": "Medium",
        "decision_rationale": "Candidate showed fundamental confusion about consensus vs replication. De-escalating to test basic replication concepts first.",
        "next_question": "What is the primary difference between synchronous and asynchronous primary-backup replication?",
        "assessment_objective": "Verify foundational comprehension of replication consistency and durability guarantees.",
        "identified_knowledge_gaps": ["Distributed consensus fundamentals", "Quorum calculations"]
    }

    resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={
            "question_id": first_q["id"],
            "answer_text": "I think Raft just copies all the data to backup servers whenever someone updates something."
        },
        headers=auth_header
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["adaptive_action"] == "SIMPLIFY"
    assert data["current_difficulty"] == "Medium"
    assert data["next_question"]["difficulty"] == "Medium"
    assert "synchronous and asynchronous" in data["next_question"]["question_text"]


# =====================================================================
# 4. TEST AMBIGUOUS ANSWER -> CLARIFY
# =====================================================================
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_ambiguous_answer_triggers_clarify(mock_eval, mock_adaptive_q, client, auth_header, setup_interview_helper):
    """An ambiguous or brief answer should prompt CLARIFY before punitive scoring."""
    interview_data = setup_interview_helper(difficulty="Medium")
    interview_id = interview_data["id"]
    first_q = interview_data["questions"][0]

    mock_eval.return_value = {
        "score": 58,
        "strengths": ["Touched on heartbeats"],
        "weaknesses": ["Vague on specifics of leader election vs normal operation"],
        "missing_concepts": ["Election timeout range", "Heartbeat RPC payload"],
        "incorrect_claims": [],
        "actionable_feedback": "Clarify what you mean by 'messages constantly go back and forth'.",
        "technical_correctness": 60,
        "conceptual_completeness": 55,
        "structural_clarity": 55,
        "depth_of_understanding": 60,
        "model_answer": "Clear explanation of AppendEntries RPCs."
    }

    mock_adaptive_q.return_value = {
        "action": AdaptiveAction.CLARIFY.value,
        "updated_difficulty": "Medium",
        "decision_rationale": "Candidate's response was ambiguous regarding whether they were referring to client requests or internal heartbeat RPCs. Asking for clarification.",
        "next_question": "When you mention 'servers send pings', are you referring to the leader's AppendEntries heartbeat or candidate RequestVote RPCs?",
        "assessment_objective": "Clarify candidate's mental model between leader maintenance and election phases.",
        "identified_knowledge_gaps": ["Raft RPC communication modes"]
    }

    resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={
            "question_id": first_q["id"],
            "answer_text": "Servers send pings so they know what happened."
        },
        headers=auth_header
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["adaptive_action"] == "CLARIFY"
    assert "AppendEntries heartbeat" in data["next_question"]["question_text"]


# =====================================================================
# 5. TEST REPEATED WEAKNESS & KNOWLEDGE GAP ACCUMULATION
# =====================================================================
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_repeated_weakness_and_gap_accumulation(mock_eval, mock_adaptive_q, client, auth_header, setup_interview_helper):
    """Knowledge gaps should accumulate across consecutive questions in session state."""
    interview_data = setup_interview_helper(num_questions=4)
    interview_id = interview_data["id"]
    q1 = interview_data["questions"][0]

    # Question 1: Misses concurrency / race conditions
    mock_eval.return_value = {
        "score": 50,
        "strengths": [],
        "weaknesses": ["No lock ordering"],
        "missing_concepts": ["Race conditions", "Deadlock prevention"],
        "incorrect_claims": [],
        "actionable_feedback": "Study deadlock detection.",
        "technical_correctness": 50,
        "conceptual_completeness": 50,
        "structural_clarity": 50,
        "depth_of_understanding": 50,
        "model_answer": "Proper concurrency locking."
    }

    mock_adaptive_q.return_value = {
        "action": AdaptiveAction.FOLLOW_UP.value,
        "updated_difficulty": "Medium",
        "decision_rationale": "Identified gap in concurrency controls.",
        "next_question": "How do you avoid deadlock when two threads acquire resource A and resource B in reverse order?",
        "assessment_objective": "Test lock ordering knowledge.",
        "identified_knowledge_gaps": ["Deadlock prevention", "Lock hierarchy"]
    }

    resp1 = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={"question_id": q1["id"], "answer_text": "I just synchronize the whole class."},
        headers=auth_header
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert "Deadlock prevention" in data1["knowledge_gaps"]

    q2 = data1["next_question"]

    # Question 2: Another weak answer on concurrency
    mock_eval.return_value = {
        "score": 45,
        "strengths": [],
        "weaknesses": ["Still misses lock hierarchy"],
        "missing_concepts": ["Deterministic lock ordering", "tryLock with timeouts"],
        "incorrect_claims": [],
        "actionable_feedback": "Review resource acquisition ordering.",
        "technical_correctness": 45,
        "conceptual_completeness": 45,
        "structural_clarity": 45,
        "depth_of_understanding": 45,
        "model_answer": "Deterministic ordering pattern."
    }

    mock_adaptive_q.return_value = {
        "action": AdaptiveAction.SIMPLIFY.value,
        "updated_difficulty": "Easy",
        "decision_rationale": "Candidate shows repeated weakness in concurrency primitives.",
        "next_question": "What is the simplest way to make an immutable class in Java to avoid multithreading issues altogether?",
        "assessment_objective": "Test basic thread-safety via immutability.",
        "identified_knowledge_gaps": ["Lock hierarchy", "Deterministic lock ordering"]
    }

    resp2 = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={"question_id": q2["id"], "answer_text": "I would just put sleep for 1 second before lock."},
        headers=auth_header
    )
    assert resp2.status_code == 200
    data2 = resp2.json()

    # Accumulated knowledge gaps must contain gaps from both answers
    gaps = data2["knowledge_gaps"]
    assert "Deadlock prevention" in gaps
    assert "Deterministic lock ordering" in gaps
    assert data2["current_difficulty"] == "Easy"


# =====================================================================
# 6. TEST IDEMPOTENCY & DUPLICATE SUBMISSION PROTECTION
# =====================================================================
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_idempotent_answer_submission(mock_eval, mock_adaptive_q, client, auth_header, setup_interview_helper):
    """Submitting the exact same answer twice must return cached results without duplicate LLM calls or duplicate DB records."""
    interview_data = setup_interview_helper(difficulty="Medium")
    interview_id = interview_data["id"]
    q1 = interview_data["questions"][0]

    mock_eval.return_value = {
        "score": 85,
        "strengths": ["Solid explanation of quorum"],
        "weaknesses": [],
        "missing_concepts": [],
        "incorrect_claims": [],
        "actionable_feedback": "Great concise answer.",
        "technical_correctness": 88,
        "conceptual_completeness": 84,
        "structural_clarity": 85,
        "depth_of_understanding": 85,
        "model_answer": "Model quorum explanation."
    }

    mock_adaptive_q.return_value = {
        "action": AdaptiveAction.INCREASE_DIFFICULTY.value,
        "updated_difficulty": "Hard",
        "decision_rationale": "Strong answer on quorum. Escalating to consensus edge cases.",
        "next_question": "Explain how joint consensus handles dynamic cluster membership changes.",
        "assessment_objective": "Dynamic membership reconfiguration.",
        "identified_knowledge_gaps": []
    }

    payload = {
        "question_id": q1["id"],
        "answer_text": "Quorum is computed as floor(n/2) + 1 to guarantee intersection of any two majorities."
    }

    # First submission
    resp1 = client.post(f"/api/interviews/{interview_id}/answer", json=payload, headers=auth_header)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert mock_eval.call_count == 1
    assert mock_adaptive_q.call_count == 1

    # Second identical submission (e.g. double-click or network retry)
    resp2 = client.post(f"/api/interviews/{interview_id}/answer", json=payload, headers=auth_header)
    assert resp2.status_code == 200
    data2 = resp2.json()

    # The AI service should NOT have been called a second time
    assert mock_eval.call_count == 1
    assert mock_adaptive_q.call_count == 1

    # Responses must match identically
    assert data1["evaluation"]["score"] == data2["evaluation"]["score"]
    assert data1["next_question"]["id"] == data2["next_question"]["id"]


# =====================================================================
# 7. TEST TERMINAL STATE AND QUESTION LIMITS
# =====================================================================
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_terminal_state_on_last_question(mock_eval, mock_adaptive_q, client, auth_header, setup_interview_helper):
    """When the question limit is reached, interview_completed must be True and no extra question generated."""
    # Set interview with only 1 total question
    interview_data = setup_interview_helper(num_questions=1)
    interview_id = interview_data["id"]
    q1 = interview_data["questions"][0]

    mock_eval.return_value = {
        "score": 90,
        "strengths": ["Excellent comprehensive explanation"],
        "weaknesses": [],
        "missing_concepts": [],
        "incorrect_claims": [],
        "actionable_feedback": "Outstanding performance.",
        "technical_correctness": 90,
        "conceptual_completeness": 90,
        "structural_clarity": 90,
        "depth_of_understanding": 90,
        "model_answer": "Perfect answer."
    }

    resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={"question_id": q1["id"], "answer_text": "Detailed complete technical answer."},
        headers=auth_header
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["interview_completed"] is True
    assert data["is_last_question"] is True
    assert data["next_question"] is None
    # Adaptive question generator should NOT be called when session limit reached
    assert mock_adaptive_q.call_count == 0


# =====================================================================
# 8. TEST ARBITRARY JOB ROLES AND PROMPT CONTEXT INGESTION
# =====================================================================
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_arbitrary_job_roles_and_rich_context(mock_eval, mock_adaptive_q, client, auth_header, setup_interview_helper):
    """The engine should seamlessly accept arbitrary user-defined job roles and domain requirements."""
    custom_role = "Senior Bioinformatician & Genomic Data Scientist"
    custom_skills = ["Nextflow", "AlphaFold", "Variant Calling", "BWA-MEM", "VCF Annotation"]
    custom_jd = "Deploying petabyte-scale genomic pipelines on Kubernetes with workflow automation."

    interview_data = setup_interview_helper(
        role=custom_role,
        skills=custom_skills,
        job_description=custom_jd,
        interview_type="Genomics Pipeline Architecture"
    )
    interview_id = interview_data["id"]
    q1 = interview_data["questions"][0]

    mock_eval.return_value = {
        "score": 88,
        "strengths": ["Accurately detailed BWA-MEM alignment indexing"],
        "weaknesses": [],
        "missing_concepts": [],
        "incorrect_claims": [],
        "actionable_feedback": "Solid pipeline engineering knowledge.",
        "technical_correctness": 90,
        "conceptual_completeness": 86,
        "structural_clarity": 88,
        "depth_of_understanding": 88,
        "model_answer": "Complete genomic alignment workflow."
    }

    mock_adaptive_q.return_value = {
        "action": AdaptiveAction.INCREASE_DIFFICULTY.value,
        "updated_difficulty": "Hard",
        "decision_rationale": "Strong knowledge of variant calling alignment. Escalating to distributed container orchestration and scatter-gather parallelization.",
        "next_question": "How do you optimize Nextflow scatter-gather sharding for whole-genome sequencing (WGS) across dynamic spot instances without data corruption on node preemption?",
        "assessment_objective": "Assess fault tolerance and cloud cost optimization for petabyte WGS pipelines.",
        "identified_knowledge_gaps": []
    }

    resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={
            "question_id": q1["id"],
            "answer_text": "We shard FASTQ files into chunks, align with BWA-MEM using reference Burrows-Wheeler index, and merge BAM files using Picard."
        },
        headers=auth_header
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["adaptive_action"] == "INCREASE_DIFFICULTY"
    assert "Nextflow scatter-gather" in data["next_question"]["question_text"]


# =====================================================================
# 9. TEST QUOTA AND PROVIDER ERROR HANDLING (NO FAKE EVALUATIONS)
# =====================================================================
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_gemini_quota_error_returns_503_without_fake_evaluation(mock_eval, client, auth_header, setup_interview_helper):
    """When Gemini returns 429 quota exhaustion or fails, the API must return 503 and NEVER fabricate fake evaluations."""
    interview_data = setup_interview_helper()
    interview_id = interview_data["id"]
    q1 = interview_data["questions"][0]

    mock_eval.side_effect = HTTPException(
        status_code=503,
        detail="AI evaluation service is temporarily unavailable due to upstream rate limits (RESOURCE_EXHAUSTED). Please retry shortly."
    )

    resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={"question_id": q1["id"], "answer_text": "My technical answer."},
        headers=auth_header
    )

    assert resp.status_code == 503
    assert "upstream rate limits" in resp.json()["detail"]


# =====================================================================
# 10. TEST VOICE INTERVIEW COMPATIBILITY
# =====================================================================
@patch("backend.services.ai_service.AIService.generate_voice_conversational_response", new_callable=AsyncMock)
@patch("backend.services.ai_service.AIService.evaluate_candidate_answer", new_callable=AsyncMock)
def test_voice_interview_submission_flow(mock_eval, mock_voice_res, client, auth_header, setup_interview_helper):
    """Submissions with voice transcript metadata should be stored and evaluated seamlessly."""
    interview_data = setup_interview_helper()
    interview_id = interview_data["id"]
    q1 = interview_data["questions"][0]

    mock_eval.return_value = {
        "score": 82,
        "strengths": ["Spoke clearly about distributed consensus"],
        "weaknesses": [],
        "missing_concepts": [],
        "incorrect_claims": [],
        "actionable_feedback": "Concise verbal delivery.",
        "technical_correctness": 84,
        "conceptual_completeness": 80,
        "structural_clarity": 82,
        "depth_of_understanding": 82,
        "model_answer": "Clear spoken answer."
    }

    mock_voice_res.return_value = {
        "action": AdaptiveAction.NEXT_TOPIC.value,
        "adaptive_action": AdaptiveAction.NEXT_TOPIC.value,
        "updated_difficulty": "Medium",
        "difficulty": "Medium",
        "decision_rationale": "Candidate gave a solid spoken response. Advancing to the next scheduled topic.",
        "adaptation_reason": "Candidate gave a solid spoken response. Advancing to the next scheduled topic.",
        "next_question": "Now let us turn to distributed caching strategies. How do you mitigate cache thundering herd?",
        "question": "Now let us turn to distributed caching strategies. How do you mitigate cache thundering herd?",
        "assessment_objective": "Evaluate distributed cache stampede mitigation techniques.",
        "identified_knowledge_gaps": [],
        "communication_notes": "Clear verbal explanation with confident pacing."
    }

    resp = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={
            "question_id": q1["id"],
            "answer_text": "In Raft, heartbeats maintain leadership without resetting the election timer.",
            "transcript_raw": "in raft heart beats maintain leadership without resetting the election timer",
            "is_voice_submission": True,
            "audio_duration_seconds": 14.5
        },
        headers=auth_header
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["adaptive_action"] == "NEXT_TOPIC"
    assert "distributed caching" in data["next_question"]["question_text"]


# =====================================================================
# 11. TEST SKIP / PASS ADVANCES WITH ADAPTIVE NEXT TOPIC
# =====================================================================
@patch("backend.services.ai_service.AIService.generate_next_adaptive_question", new_callable=AsyncMock)
def test_skip_question_advances_adaptively(mock_adaptive_q, client, auth_header, setup_interview_helper):
    """Skipping a question should transition with NEXT_TOPIC and assign an objective."""
    interview_data = setup_interview_helper(num_questions=3)
    interview_id = interview_data["id"]
    q1 = interview_data["questions"][0]

    mock_adaptive_q.return_value = {
        "action": AdaptiveAction.NEXT_TOPIC.value,
        "updated_difficulty": "Medium",
        "decision_rationale": "Candidate skipped the previous topic. Transitioning to database indexing and query optimization.",
        "next_question": "How does a B-Tree index support both point queries and range scans efficiently?",
        "assessment_objective": "Test understanding of index data structures.",
        "identified_knowledge_gaps": ["Skipped consensus topic"]
    }

    resp = client.post(
        f"/api/interviews/{interview_id}/skip",
        json={"question_id": q1["id"]},
        headers=auth_header
    )

    assert resp.status_code == 200
    data = resp.json()
    next_q = data["next_question"]
    assert next_q is not None
    assert next_q["adaptive_action"] == "NEXT_TOPIC"
    assert "B-Tree index" in next_q["question_text"]
