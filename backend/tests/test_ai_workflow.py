import json
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
import httpx
from fastapi.testclient import TestClient

from backend.config.settings import settings
from backend.services.ai_service import AIService
from backend.schemas.evaluation import AIEvaluationResult

@pytest.fixture
def auth_header(client: TestClient):
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "Dynamic AI Tester",
            "email": "dynamic_ai@example.com",
            "password": "Password123!"
        }
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# =========================================================================
# 1. USER INPUT PROPAGATION TESTS
# =========================================================================

@patch("backend.services.ai_service.AIService._call_llm_api", new_callable=AsyncMock)
def test_user_personalization_inputs_reach_ai_service(mock_llm, client: TestClient, auth_header):
    """
    Verifies that all candidate inputs (role, experience, skills, JD, resume text,
    additional instructions, difficulty) are properly embedded in the prompt sent to Gemini.
    """
    mock_llm.return_value = json.dumps([
        {
            "question": "How do you programmatically configure eBPF maps for high-throughput packet filtering in Cilium?",
            "category": "Kubernetes",
            "skill": "eBPF",
            "difficulty": "Hard",
            "additional_instruction": "Explain BPF_MAP_TYPE_HASH vs BPF_MAP_TYPE_PERCPU_HASH."
        }
    ])

    payload = {
        "role": "Cloud Infrastructure Architect",
        "experience_level": "Senior",
        "topic": "Kubernetes",
        "interview_type": "System Design",
        "difficulty": "Hard",
        "total_questions": 3,
        "skills": ["eBPF", "Istio", "Cilium"],
        "job_description": "Architect zero-trust service mesh using Istio and eBPF with sub-millisecond latency.",
        "resume_text": "10+ years engineering Linux kernel networking, microservice platforms, and Kubernetes clusters.",
        "additional_instructions": "Focus on low-level Linux kernel networking and network partition resilience."
    }

    resp = client.post("/api/interviews", json=payload, headers=auth_header)
    assert resp.status_code == 201
    data = resp.json()

    # 1. Verify the AI call was executed
    assert mock_llm.called
    prompt_sent = mock_llm.call_args[0][0]

    # 2. Verify all user-specific inputs are embedded in the prompt
    assert "Cloud Infrastructure Architect" in prompt_sent
    assert "Senior" in prompt_sent
    assert "Kubernetes" in prompt_sent
    assert "Hard" in prompt_sent
    assert "System Design" in prompt_sent
    assert "eBPF, Istio, Cilium" in prompt_sent
    assert "Architect zero-trust service mesh using Istio and eBPF with sub-millisecond latency" in prompt_sent
    assert "10+ years engineering Linux kernel networking" in prompt_sent
    assert "Focus on low-level Linux kernel networking and network partition resilience" in prompt_sent

    # 3. Verify returned question matches AI output
    assert "first_question" in data
    assert "eBPF" in data["first_question"]["question"]
    assert data["first_question"]["difficulty"] == "Hard"

# =========================================================================
# 2. ANSWER EVALUATION & ADAPTIVE DIFFICULTY CONTEXT TESTS
# =========================================================================

@patch("backend.services.ai_service.AIService._call_llm_api", new_callable=AsyncMock)
def test_answer_evaluation_and_adaptive_progression_use_context(mock_llm, client: TestClient, auth_header):
    """
    Verifies that answer evaluation and the subsequent adaptive question use
    the candidate's actual submitted answer and question history.
    """
    # 1. Start interview
    mock_llm.return_value = json.dumps([
        {
            "question": "Explain how Go channels implement synchronization internally.",
            "category": "Concurrency",
            "skill": "Go",
            "difficulty": "Medium",
            "additional_instruction": "Discuss hchan struct and sudog queues."
        }
    ])

    start_res = client.post(
        "/api/interviews",
        json={
            "role": "Backend Go Engineer",
            "experience_level": "Intermediate",
            "topic": "Go Concurrency",
            "difficulty": "Medium",
            "total_questions": 2,
            "job_description": "Building high-performance distributed microservices in Go.",
            "additional_instructions": "Probe internal runtime mechanisms."
        },
        headers=auth_header
    )
    assert start_res.status_code == 201
    start_data = start_res.json()
    interview_id = start_data["interview"]["id"]
    q1_id = start_data["first_question"]["id"]

    # 2. Submit candidate answer
    candidate_answer = "Channels use an hchan struct with a circular ring buffer, a mutex lock, and two wait queues (recvq and sendq) composed of sudog goroutine representations."

    # Return structured rubric evaluation
    mock_llm.return_value = json.dumps({
        "technical_correctness": 95.0,
        "conceptual_completeness": 90.0,
        "response_relevance": 95.0,
        "structural_clarity": 92.0,
        "depth_of_understanding": 90.0,
        "overall_score": 93.0,
        "score_out_of_10": 9.3,
        "strengths": ["Accurate breakdown of hchan, wait queues, and sudog structures."],
        "missing_concepts": ["Channel closure semantics and zero-value reads."],
        "incorrect_claims": [],
        "actionable_feedback": "Explain channel closing behavior and deadlock avoidance.",
        "improved_sample_answer": "Channels are backed by hchan...",
        "feedback": "Outstanding architectural answer.",
        "model_answer": "In Go, channels are defined by runtime/chan.go hchan struct."
    })

    # Prepare next response for the subsequent adaptive question call
    async def mock_llm_side_effect(prompt: str):
        if "Evaluate the candidate's response" in prompt:
            return json.dumps({
                "technical_correctness": 95.0,
                "conceptual_completeness": 90.0,
                "response_relevance": 95.0,
                "structural_clarity": 92.0,
                "depth_of_understanding": 90.0,
                "overall_score": 93.0,
                "score_out_of_10": 9.3,
                "strengths": ["Accurate breakdown of hchan, wait queues, and sudog structures."],
                "missing_concepts": ["Channel closure semantics and zero-value reads."],
                "incorrect_claims": [],
                "actionable_feedback": "Explain channel closing behavior and deadlock avoidance.",
                "improved_sample_answer": "Channels are backed by hchan...",
                "feedback": "Outstanding architectural answer.",
                "model_answer": "In Go, channels are defined by runtime/chan.go hchan struct."
            })
        elif "Generate the next adaptive interview question" in prompt:
            # Verify candidate answer and omitted concepts are in prompt
            assert "circular ring buffer" in prompt
            assert "Channel closure semantics" in prompt
            assert "Target Next Difficulty: Hard" in prompt
            return json.dumps({
                "question": "What happens when a goroutine reads from or writes to a closed channel, and how does the select statement handle nil channels?",
                "category": "Concurrency",
                "skill": "Go Runtime",
                "difficulty": "Hard",
                "additional_instruction": "Explain panic conditions vs non-blocking select cases.",
                "adaptation_reason": "High mastery on Question 1 (93.0%). Escalating to Hard to test runtime edge cases."
            })
        return "{}"

    mock_llm.side_effect = mock_llm_side_effect

    ans_res = client.post(
        f"/api/interviews/{interview_id}/answer?question_id={q1_id}",
        json={"answer": candidate_answer},
        headers=auth_header
    )
    assert ans_res.status_code == 200
    ans_data = ans_res.json()

    assert ans_data["evaluation"]["score"] == 92.8
    assert "Accurate breakdown of hchan" in ans_data["evaluation"]["strengths"][0]
    assert "next_question" in ans_data
    assert ans_data["next_question"]["difficulty"] == "Hard"
    assert "closed channel" in ans_data["next_question"]["question"]

# =========================================================================
# 3. VOICE INTERVIEW CONVERSATIONAL RESPONSE TESTS
# =========================================================================

@patch("backend.services.ai_service.AIService._call_llm_api", new_callable=AsyncMock)
def test_voice_interview_conversational_response_flow(mock_llm, client: TestClient, auth_header):
    """
    Verifies that voice interviews generate conversational preludes, follow-ups,
    and communication notes using the candidate's spoken transcript.
    """
    mock_llm.return_value = json.dumps([
        {
            "question": "What is the primary difference between processes and threads?",
            "category": "OS",
            "skill": "Operating Systems",
            "difficulty": "Medium",
            "additional_instruction": "Mention address space sharing."
        }
    ])

    # 1. Start voice interview
    start_res = client.post(
        "/api/interviews",
        json={
            "role": "Systems Programmer",
            "experience_level": "Intermediate",
            "topic": "Operating Systems",
            "difficulty": "Medium",
            "mode": "voice",
            "voice_name": "en-US-Standard-C",
            "total_questions": 2
        },
        headers=auth_header
    )
    assert start_res.status_code == 201
    interview_id = start_res.json()["interview"]["id"]
    q1_id = start_res.json()["first_question"]["id"]

    # 2. Submit voice answer
    spoken_answer = "Processes have their own dedicated virtual memory space, whereas threads within a process share heap and global data but have their own stack and registers."

    async def mock_voice_side_effect(prompt: str):
        if "Evaluate the candidate's response" in prompt:
            return json.dumps({
                "technical_correctness": 90.0,
                "conceptual_completeness": 88.0,
                "response_relevance": 92.0,
                "structural_clarity": 90.0,
                "depth_of_understanding": 88.0,
                "overall_score": 90.0,
                "score_out_of_10": 9.0,
                "strengths": ["Clear definition of virtual memory separation."],
                "missing_concepts": ["Context switching overhead difference."],
                "incorrect_claims": [],
                "actionable_feedback": "Highlight context switch latency between processes vs threads.",
                "improved_sample_answer": "Processes possess isolated address spaces...",
                "feedback": "Crisp verbal articulation.",
                "model_answer": "Processes are isolated address spaces; threads share memory."
            })
        elif "interactive voice interview" in prompt:
            assert "virtual memory space" in prompt
            return json.dumps({
                "conversational_prelude": "Excellent point regarding address space isolation.",
                "is_follow_up": True,
                "question": "Following up on that, what makes a process context switch computationally more expensive than a thread context switch?",
                "category": "OS",
                "skill": "Kernel Architecture",
                "difficulty": "Hard",
                "additional_instruction": "Discuss TLB flushes and cache misses.",
                "adaptation_reason": "Candidate exhibited solid fundamentals. Probing deeper into context switch overhead.",
                "communication_notes": "Well-paced delivery with precise terminology."
            })
        return "{}"

    mock_llm.side_effect = mock_voice_side_effect

    voice_submit_res = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={
            "question_id": q1_id,
            "answer": spoken_answer,
            "transcript_raw": spoken_answer,
            "is_voice_submission": True,
            "audio_duration_seconds": 18.5
        },
        headers=auth_header
    )
    assert voice_submit_res.status_code == 200
    voice_data = voice_submit_res.json()

    assert voice_data["conversational_prelude"] == "Excellent point regarding address space isolation."
    assert voice_data["follow_up_question"] is not None
    assert "context switch" in voice_data["follow_up_question"]["question"]
    assert voice_data["evaluation"]["communication_notes"] == "Well-paced delivery with precise terminology."

# =========================================================================
# 4. STRICT ERROR HANDLING & NO-FALLBACK TESTS
# =========================================================================

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_api_quota_exhausted_returns_http_503(mock_post, client: TestClient, auth_header):
    """
    Verifies that when the Gemini API returns HTTP 429 (Resource Exhausted / Quota Limit),
    the application returns a clear HTTP 503 error instead of synthetic fallback questions.
    """
    mock_resp = httpx.Response(
        429,
        json={
            "error": {
                "code": 429,
                "message": "RESOURCE_EXHAUSTED: Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "quotaValue": "20"}]
                    }
                ]
            }
        },
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent")
    )
    mock_post.return_value = mock_resp

    resp = client.post(
        "/api/interviews",
        json={
            "role": "Distributed Systems Engineer",
            "experience_level": "Senior",
            "topic": "Raft",
            "difficulty": "Hard",
            "total_questions": 3
        },
        headers=auth_header
    )

    # Must return 503 Service Unavailable, NEVER 201 with fake synthetic questions
    assert resp.status_code == 503
    data = resp.json()
    assert "quota" in data["detail"].lower() or "429" in data["detail"]

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_api_timeout_returns_http_503(mock_post, client: TestClient, auth_header):
    """
    Verifies that when the Gemini API times out, the application returns HTTP 503.
    """
    mock_post.side_effect = httpx.TimeoutException("Connection timed out after 30s")

    resp = client.post(
        "/api/interviews",
        json={
            "role": "SRE Engineer",
            "experience_level": "Senior",
            "topic": "Observability",
            "difficulty": "Medium",
            "total_questions": 2
        },
        headers=auth_header
    )

    assert resp.status_code == 503
    data = resp.json()
    assert "timed out" in data["detail"].lower()

def test_missing_api_key_returns_http_503(client: TestClient, auth_header, monkeypatch):
    """
    Verifies that when no GenAI API keys are configured, the application returns HTTP 503.
    """
    monkeypatch.setattr(settings, "GENAI_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    monkeypatch.delenv("GENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    resp = client.post(
        "/api/interviews",
        json={
            "role": "Frontend Developer",
            "experience_level": "Junior",
            "topic": "React",
            "difficulty": "Easy",
            "total_questions": 2
        },
        headers=auth_header
    )

    assert resp.status_code == 503
    data = resp.json()
    assert "not configured" in data["detail"].lower()

# =========================================================================
# 5. FINAL REPORT DYNAMIC SYNTHESIS TESTS
# =========================================================================

@patch("backend.services.ai_service.AIService._call_llm_api", new_callable=AsyncMock)
def test_final_report_uses_interview_context_and_fails_safely(mock_llm, client: TestClient, auth_header):
    """
    Verifies that final diagnostic reports incorporate actual answers and evaluations,
    and raise 503 if the AI service fails.
    """
    # 1. Start interview
    mock_llm.return_value = json.dumps([
        {
            "question": "What is the role of index partitioning in PostgreSQL?",
            "category": "Databases",
            "skill": "PostgreSQL",
            "difficulty": "Medium",
            "additional_instruction": "Discuss B-Trees and partial indexes."
        }
    ])

    start_res = client.post(
        "/api/interviews",
        json={
            "role": "Database Administrator",
            "experience_level": "Senior",
            "topic": "PostgreSQL",
            "difficulty": "Medium",
            "total_questions": 1
        },
        headers=auth_header
    )
    assert start_res.status_code == 201
    interview_id = start_res.json()["interview"]["id"]
    q_id = start_res.json()["first_question"]["id"]

    # 2. Answer question
    mock_llm.return_value = json.dumps({
        "technical_correctness": 90.0,
        "conceptual_completeness": 85.0,
        "response_relevance": 90.0,
        "structural_clarity": 88.0,
        "depth_of_understanding": 86.0,
        "overall_score": 88.0,
        "score_out_of_10": 8.8,
        "strengths": ["Accurate explanation of partition pruning."],
        "missing_concepts": ["BRIN indexes for time-series data."],
        "incorrect_claims": [],
        "actionable_feedback": "Consider explaining BRIN indexes.",
        "improved_sample_answer": "Partitioning divides large tables...",
        "feedback": "Strong database fundamentals.",
        "model_answer": "Partitioning improves scan times via constraint exclusion."
    })

    client.post(
        f"/api/interviews/{interview_id}/answer?question_id={q_id}",
        json={"answer": "Partitioning breaks large tables into smaller physical tables so the query planner can prune unneeded partitions."},
        headers=auth_header
    )

    # 3. Request final report with mocked LLM response
    report_ai_payload = {
        "overall_score": 88.0,
        "technical_knowledge_score": 90.0,
        "communication_score": 88.0,
        "problem_solving_score": 85.0,
        "answer_quality_score": 88.0,
        "strong_topics": ["PostgreSQL Partitioning", "Query Optimization"],
        "weak_topics": ["BRIN Indexes"],
        "skill_gaps": ["BRIN Indexes", "Vacuum Tuning"],
        "recommendations": ["Deepen understanding of BRIN index trade-offs."],
        "communication_observations": "Clear technical delivery with appropriate DBA terminology.",
        "readiness_estimate": "High readiness for Senior Database Administrator.",
        "readiness_level": "Ready",
        "personalized_summary": "Candidate demonstrated strong production knowledge of partition pruning."
    }
    mock_llm.return_value = json.dumps(report_ai_payload)

    report_res = client.get(f"/api/ai/report/{interview_id}", headers=auth_header)
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert report_data["readiness_level"] == "Ready"
    assert report_data["overall_score"] == 88.0
    assert len(report_data["question_results"]) == 1
    assert "prune" in report_data["question_results"][0]["user_answer"]

    # 4. Verify that if the LLM fails, final report endpoint returns 503
    from fastapi import HTTPException
    mock_llm.side_effect = HTTPException(status_code=503, detail="Gemini API quota exceeded (HTTP 429)")
    fail_report_res = client.get(f"/api/ai/report/{interview_id}", headers=auth_header)
    assert fail_report_res.status_code == 503

# =========================================================================
# 5. REGRESSION TESTS: LIST-TYPE ACTIONABLE FEEDBACK & SCHEMA NORMALIZATION
# =========================================================================

def test_ai_evaluation_result_schema_normalizes_list_actionable_feedback():
    """
    Regression test: Verifies that AIEvaluationResult schema accepts actionable_feedback
    as a list of strings without raising a Pydantic ValidationError, and converts it
    consistently to a readable string.
    """
    raw_list_feedback = [
        "Structure your explanation with high-level trade-offs before code.",
        "Highlight memory alignment and caching benefits in contiguous arrays.",
        "Mention failure recovery and transaction rollbacks."
    ]

    result = AIEvaluationResult(
        technical_correctness=90.0,
        conceptual_completeness=85.0,
        response_relevance=92.0,
        structural_clarity=88.0,
        depth_of_understanding=85.0,
        overall_score=88.5,
        score_out_of_10=8.9,
        strengths=["Clear architectural framing", "Good trade-off analysis"],
        improvements=["Omitted transaction rollbacks"],
        missing_concepts=["Transaction rollbacks"],
        incorrect_claims=[],
        feedback="Strong candidate answer demonstrating practical experience.",
        actionable_feedback=raw_list_feedback,
        model_answer="A production-grade approach requires explicit rollback mechanisms."
    )

    assert isinstance(result.actionable_feedback, str)
    assert "• Structure your explanation" in result.actionable_feedback
    assert "• Highlight memory alignment" in result.actionable_feedback
    assert "• Mention failure recovery" in result.actionable_feedback
    assert isinstance(result.strengths, list)
    assert len(result.strengths) == 2


@pytest.mark.asyncio
@patch("backend.services.ai_service.AIService._call_llm_api", new_callable=AsyncMock)
async def test_ai_service_evaluate_candidate_answer_normalizes_gemini_list_output(mock_llm):
    """
    Regression test: Verifies that AIService.evaluate_candidate_answer robustly handles
    realistic Gemini responses where actionable_feedback is returned as an array of items.
    """
    gemini_output = {
        "technical_correctness": 88.0,
        "conceptual_completeness": 82.0,
        "response_relevance": 90.0,
        "structural_clarity": 85.0,
        "depth_of_understanding": 80.0,
        "overall_score": 85.5,
        "score_out_of_10": 8.6,
        "strengths": [
            "Accurately explained PagedAttention memory virtualization.",
            "Correctly identified external memory fragmentation bottlenecks."
        ],
        "missing_concepts": [
            "CUDA Virtual Memory Management APIs (cuMemCreate, cuMemMap).",
            "Continuous batching token budget limits."
        ],
        "incorrect_claims": [],
        "actionable_feedback": [
            "Study cuMemCreate and cuMemMap for upfront memory pool reservation.",
            "Detail how speculative candidate tree verification integrates with NCCL all-reduce."
        ],
        "improved_sample_answer": "Use 16-token physical blocks and pre-allocate the full memory pool upfront.",
        "feedback": "Impressive depth on GPU memory paging with clear understanding of KV fragmentation.",
        "model_answer": "PagedAttention eliminates internal fragmentation by allocating fixed blocks dynamically."
    }
    mock_llm.return_value = json.dumps(gemini_output)

    ai_eval = await AIService.evaluate_candidate_answer(
        question_text="How does PagedAttention eliminate memory fragmentation in LLM inference?",
        answer_text="It virtualizes KV cache into fixed size blocks so we don't need contiguous GPU memory.",
        topic="LLM Inference Systems",
        target_role="Staff AI Platform Architect",
        difficulty="Staff-Level Rigor"
    )

    assert isinstance(ai_eval.actionable_feedback, str)
    assert "• Study cuMemCreate" in ai_eval.actionable_feedback
    assert "• Detail how speculative candidate" in ai_eval.actionable_feedback
    assert isinstance(ai_eval.strengths, list)
    assert len(ai_eval.strengths) == 2
    assert isinstance(ai_eval.missing_concepts, list)
    assert len(ai_eval.missing_concepts) == 2


@patch("backend.services.ai_service.AIService._call_llm_api", new_callable=AsyncMock)
def test_submit_answer_route_with_gemini_list_actionable_feedback(mock_llm, client: TestClient, auth_header):
    """
    Regression test: Verifies end-to-end answer submission via API when Gemini returns
    actionable_feedback as a list of strings. Checks HTTP 200, response schema, and database persistence.
    """
    # 1. Start interview
    mock_llm.return_value = json.dumps([
        {
            "question": "Explain how PagedAttention handles KV cache memory allocation under high concurrency.",
            "category": "Distributed Systems",
            "skill": "GPU Systems",
            "difficulty": "Hard",
            "additional_instruction": "Mention virtual vs physical block mapping."
        }
    ])

    start_res = client.post(
        "/api/interviews",
        json={
            "role": "Senior AI Systems Engineer",
            "experience_level": "Senior",
            "topic": "GPU Systems",
            "difficulty": "Hard",
            "total_questions": 1
        },
        headers=auth_header
    )
    assert start_res.status_code == 201
    interview_data = start_res.json()
    interview_id = interview_data["interview"]["id"]
    q1_id = interview_data["first_question"]["id"]

    # 2. Mock Gemini response with list actionable_feedback
    gemini_eval_with_list = {
        "technical_correctness": 92.0,
        "conceptual_completeness": 88.0,
        "response_relevance": 95.0,
        "structural_clarity": 90.0,
        "depth_of_understanding": 88.0,
        "overall_score": 90.5,
        "score_out_of_10": 9.1,
        "strengths": [
            "Accurate differentiation of logical vs physical block tables.",
            "Clear understanding of copy-on-write fork operations."
        ],
        "missing_concepts": [
            "Cross-node KV cache sharing over RDMA/RoCE."
        ],
        "incorrect_claims": [],
        "actionable_feedback": [
            "Emphasize RDMA zero-copy primitives for distributed multi-GPU tiers.",
            "Quantify memory savings percentage from eliminating internal fragmentation."
        ],
        "improved_sample_answer": "PagedAttention maps logical token blocks to non-contiguous physical memory pages...",
        "feedback": "Comprehensive and authoritative technical response.",
        "model_answer": "PagedAttention separates logical sequential sequences from physical memory blocks."
    }
    mock_llm.return_value = json.dumps(gemini_eval_with_list)

    # 3. Submit answer
    ans_res = client.post(
        f"/api/interviews/{interview_id}/answer",
        json={
            "question_id": q1_id,
            "answer_text": "PagedAttention divides sequences into fixed blocks and maps them through a page table, avoiding pre-allocating contiguous memory."
        },
        headers=auth_header
    )

    # Must succeed with HTTP 200, without any Pydantic validation error
    assert ans_res.status_code == 200
    res_data = ans_res.json()

    # Check that actionable_feedback in response is a readable string
    eval_section = res_data.get("evaluation") or res_data
    assert "actionable_feedback" in eval_section
    feedback_str = eval_section["actionable_feedback"]
    assert isinstance(feedback_str, str)
    assert "• Emphasize RDMA zero-copy" in feedback_str
    assert "• Quantify memory savings" in feedback_str

    # Check strengths is a preserved list
    assert isinstance(eval_section["strengths"], list)
    assert len(eval_section["strengths"]) == 2

    # 4. Verify evaluation retrieval route also returns readable string
    get_eval_res = client.get(f"/api/evaluation/interview/{interview_id}", headers=auth_header)
    assert get_eval_res.status_code == 200
    get_data = get_eval_res.json()
    assert len(get_data["evaluations"]) == 1
    stored_eval = get_data["evaluations"][0]
    assert "actionable_feedback" in stored_eval
    assert "• Emphasize RDMA zero-copy" in stored_eval["actionable_feedback"]


# =========================================================================
# 7. GEMINI HTTP 429 QUOTA & IN-FLIGHT DEDUPLICATION TESTS
# =========================================================================

def test_parse_gemini_error_daily_quota():
    """Verifies that daily free-tier quota exhaustion is correctly detected."""
    payload = {
        "error": {
            "code": 429,
            "message": "Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.8-flash\nPlease retry in 13h52m50.224181862s.",
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [
                        {
                            "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                            "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                            "quotaValue": "20"
                        }
                    ]
                },
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "49970s"
                }
            ]
        }
    }
    info = AIService._parse_gemini_error(429, payload)
    assert info["is_daily_quota"] is True
    assert info["quota_limit"] == "20"
    assert info["retry_delay_seconds"] == 49970.0
    assert "hours" in info["friendly_retry_str"]


def test_parse_gemini_error_transient_rpm():
    """Verifies that transient rate limit bursts (RPM/TPM) with short retry delays are marked as transient."""
    payload = {
        "error": {
            "code": 429,
            "message": "Resource has been exhausted (e.g. check quota).",
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "4s"
                }
            ]
        }
    }
    info = AIService._parse_gemini_error(429, payload)
    assert info["is_daily_quota"] is False
    assert info["retry_delay_seconds"] == 4.0
    assert info["friendly_retry_str"] == "4 seconds"


@pytest.mark.asyncio
async def test_transient_rate_limit_exponential_backoff():
    """Verifies bounded exponential backoff retries transient 429 and returns successful result."""
    call_count = 0

    async def mock_post(url, json=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First attempt: transient 429 with 1s delay
            return httpx.Response(
                429,
                json={
                    "error": {
                        "code": 429,
                        "message": "Rate limit exceeded. Please wait.",
                        "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "1s"}]
                    }
                },
                request=httpx.Request("POST", url)
            )
        # Second attempt: success
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Dynamic AI interview response after transient backoff"}]}}]},
            request=httpx.Request("POST", url)
        )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with patch.object(settings, "GENAI_API_KEY", "test_gemini_key_12345"):
            with patch.object(settings, "GENAI_MODEL", "gemini-3.8-flash"):
                result = await AIService._execute_llm_call("Test prompt")
                assert "Dynamic AI interview response" in result
                assert call_count == 2


@pytest.mark.asyncio
async def test_daily_quota_exhausted_failover_to_active_free_tier():
    """
    Verifies that when primary model has daily quota exhausted (20 RPD cap),
    it does NOT sleep for hours, but smoothly falls over to active free-tier candidate models.
    """
    attempted_models = []

    async def mock_post(url, json=None):
        model_part = url.split("models/")[1].split(":")[0]
        attempted_models.append(model_part)
        if model_part == "gemini-3.8-flash":
            # 429 Daily Quota Exhaustion
            return httpx.Response(
                429,
                json={
                    "error": {
                        "code": 429,
                        "message": "Quota exceeded for 20 RPD",
                        "details": [
                            {
                                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                                "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "quotaValue": "20"}]
                            },
                            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "50000s"}
                        ]
                    }
                },
                request=httpx.Request("POST", url)
            )
        elif model_part == "gemini-3-flash-preview":
            # Active free tier succeeds
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": "Question from gemini-3-flash-preview"}]}}]},
                request=httpx.Request("POST", url)
            )
        return httpx.Response(404, request=httpx.Request("POST", url))

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with patch.object(settings, "GENAI_API_KEY", "test_gemini_key_12345"):
            with patch.object(settings, "GENAI_MODEL", "gemini-3.8-flash"):
                res = await AIService._execute_llm_call("Test prompt")
                assert "Question from gemini-3-flash-preview" in res
                assert "gemini-3.8-flash" in attempted_models
                assert "gemini-3-flash-preview" in attempted_models


@pytest.mark.asyncio
async def test_all_models_daily_quota_exhausted_user_error():
    """
    Verifies that when all free-tier models have exhausted their daily quota,
    a clear user-facing HTTP 503 is returned detailing the limit and reset window.
    """
    async def mock_post(url, json=None):
        return httpx.Response(
            429,
            json={
                "error": {
                    "code": 429,
                    "message": "Quota exceeded for free tier",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                            "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "quotaValue": "20"}]
                        },
                        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "49000s"}
                    ]
                }
            },
            request=httpx.Request("POST", url)
        )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with patch.object(settings, "GENAI_API_KEY", "test_gemini_key_12345"):
            with patch.object(settings, "GROQ_API_KEY", ""):
                with pytest.raises(Exception) as exc_info:
                    await AIService._execute_llm_call("Test prompt")
                err_detail = str(exc_info.value.detail)
                assert "daily free-tier quota exhausted" in err_detail
                assert "20 requests/day" in err_detail
                assert "hours" in err_detail


@pytest.mark.asyncio
async def test_in_flight_prompt_deduplication():
    """
    Verifies that multiple concurrent calls with identical prompt are deduplicated
    to a single underlying LLM execution.
    """
    execution_count = 0

    async def mock_execute(prompt):
        nonlocal execution_count
        execution_count += 1
        import asyncio
        await asyncio.sleep(0.1)
        return f"Deduplicated result for: {prompt}"

    with patch.object(AIService, "_execute_llm_call", side_effect=mock_execute):
        import asyncio
        results = await asyncio.gather(
            AIService._call_llm_api("dedup_test_prompt_unique_123"),
            AIService._call_llm_api("dedup_test_prompt_unique_123"),
            AIService._call_llm_api("dedup_test_prompt_unique_123")
        )
        assert len(results) == 3
        assert results[0] == results[1] == results[2]
        # Only 1 execution was actually performed
        assert execution_count == 1


