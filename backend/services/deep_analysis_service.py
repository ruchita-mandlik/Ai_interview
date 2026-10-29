import json
import uuid
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.models.interview import Interview
from backend.models.question import InterviewQuestion
from backend.models.answer import Answer
from backend.models.evaluation import Evaluation
from backend.models.coding_interview import CodingSubmission
from backend.models.roadmap import InterviewAnalysisRoadmap
from backend.schemas.roadmap import (
    DeepAnalysisRoadmapResponse,
    QuestionEvidenceAnalysis,
    EvidenceSkillGap,
    EvidenceStrength,
    UntestedCompetency,
    RoadmapPhase,
    RoadmapTask,
    DiagnosticReassessmentQuestion,
    RemediationPath
)
from backend.services.ai_service import AIService

logger = logging.getLogger("uvicorn.error")

class DeepAnalysisService:
    @classmethod
    def _to_scale_10(cls, val: Any, default: float = 7.0) -> float:
        """Safely converts 0-100 or raw numbers into a 0.0 - 10.0 scale rubric score."""
        if val is None:
            return default
        try:
            f = float(val)
            if f > 10.0:
                f = f / 10.0
            return max(0.0, min(10.0, round(f, 1)))
        except (ValueError, TypeError):
            return default

    @classmethod
    async def get_or_generate_roadmap(
        cls,
        db: Session,
        interview_id: str,
        user_id: str,
        force_refresh: bool = False,
        target_interview_date: Optional[str] = None,
        daily_study_hours: Optional[float] = None
    ) -> InterviewAnalysisRoadmap:
        """Retrieves existing post-interview intelligence roadmap or generates a new evidence-based one."""
        existing = db.query(InterviewAnalysisRoadmap).filter(
            InterviewAnalysisRoadmap.interview_id == interview_id,
            InterviewAnalysisRoadmap.user_id == user_id
        ).first()

        if existing and not force_refresh:
            updated = False
            if target_interview_date and existing.target_interview_date != target_interview_date:
                existing.target_interview_date = target_interview_date
                updated = True
            if daily_study_hours and existing.daily_study_hours != daily_study_hours:
                existing.daily_study_hours = daily_study_hours
                cls._recalibrate_task_durations(existing, daily_study_hours)
                updated = True
            if updated:
                db.commit()
                db.refresh(existing)

            # Sync recurring weaknesses and resolved topics from memory
            try:
                from backend.services.interview_memory_service import InterviewMemoryService
                InterviewMemoryService.sync_roadmap_with_memory(db, user_id, existing)
            except Exception as e:
                logger.warning(f"Failed to sync roadmap with memory: {e}")

            return existing

        # Fetch Interview and related records
        interview = db.query(Interview).filter(
            Interview.id == interview_id,
            Interview.user_id == user_id
        ).first()
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found."
            )

        # Assemble Questions, Answers, Evaluations
        questions = db.query(InterviewQuestion).filter(
            InterviewQuestion.interview_id == interview_id
        ).order_by(InterviewQuestion.question_number).all()

        if not questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Interview {interview_id} does not contain any questions. Please complete an interview before generating deep analysis and roadmap."
            )

        qa_history: List[Dict[str, Any]] = []
        for q in questions:
            ans = db.query(Answer).filter(Answer.question_id == q.id).first()
            ev = db.query(Evaluation).filter(Evaluation.question_id == q.id).first()
            
            ev_dict = {}
            if ev:
                def safe_load(val):
                    if not val:
                        return []
                    try:
                        return json.loads(val) if isinstance(val, str) else val
                    except Exception:
                        return [str(val)]
                        
                ev_dict = {
                    "technical_correctness": ev.technical_correctness,
                    "conceptual_completeness": ev.conceptual_completeness,
                    "response_relevance": ev.response_relevance,
                    "structural_clarity": ev.structural_clarity,
                    "depth_of_understanding": ev.depth_of_understanding,
                    "overall_score": ev.overall_score,
                    "strengths": safe_load(ev.strengths),
                    "improvements": safe_load(ev.improvements),
                    "missing_concepts": safe_load(ev.missing_concepts),
                    "incorrect_claims": safe_load(ev.incorrect_claims),
                    "feedback": ev.feedback or "",
                    "actionable_feedback": ev.actionable_feedback or "",
                }

            qa_history.append({
                "question_id": q.id,
                "question_number": q.question_number,
                "question_text": q.question_text,
                "category": q.category or "General",
                "difficulty": q.difficulty or "Medium",
                "is_skipped": bool(q.is_skipped),
                "candidate_answer": ans.answer_text if ans else "(No answer submitted / Question skipped)",
                "existing_eval": ev_dict
            })

        # Fetch Coding Submissions if any exist for user
        coding_subs = db.query(CodingSubmission).filter(
            CodingSubmission.user_id == user_id
        ).order_by(CodingSubmission.submitted_at.desc()).limit(3).all()
        
        coding_data = []
        for cs in coding_subs:
            cq = getattr(cs, "coding_question", None)
            prob_title = cq.title if cq else "Coding Challenge"
            code_text = getattr(cs, "submitted_code", None) or getattr(cs, "code", "")
            coding_data.append({
                "problem_title": prob_title,
                "language": cs.language,
                "code": code_text,
                "test_cases_passed": cs.test_cases_passed,
                "total_test_cases": cs.total_test_cases,
                "coding_score": getattr(cs, "coding_score", 0.0),
                "time_complexity": getattr(cs, "time_complexity", "O(N)"),
                "detected_mistakes": getattr(cs, "detected_mistakes", "[]")
            })

        interview_context = {
            "target_role": interview.target_role or "Software Engineer",
            "experience_level": interview.experience_level or "Intermediate",
            "topic": interview.topic or "Technical",
            "difficulty": interview.difficulty or "Medium",
            "job_description": interview.job_description or "",
            "resume_text": interview.resume_text or ""
        }

        study_hours = daily_study_hours if daily_study_hours is not None else 2.0

        ai_payload = None
        try:
            ai_payload = await asyncio.wait_for(
                AIService.deep_analyze_interview_session(
                    interview_context=interview_context,
                    qa_history=qa_history,
                    coding_submissions=coding_data,
                    target_interview_date=target_interview_date,
                    daily_study_hours=study_hours
                ),
                timeout=45.0
            )
        except Exception as e:
            logger.warning(f"AI Deep Analysis live call exception: {e}. Synthesizing evidence-based roadmap from interview record.")
            ai_payload = cls._synthesize_evidence_based_roadmap(
                interview_context=interview_context,
                qa_history=qa_history,
                coding_submissions=coding_data,
                target_interview_date=target_interview_date,
                daily_study_hours=study_hours
            )

        if not ai_payload or not isinstance(ai_payload, dict):
            ai_payload = cls._synthesize_evidence_based_roadmap(
                interview_context=interview_context,
                qa_history=qa_history,
                coding_submissions=coding_data,
                target_interview_date=target_interview_date,
                daily_study_hours=study_hours
            )

        # Normalize and validate payload fields
        normalized = cls._normalize_roadmap_payload(ai_payload, qa_history, interview_context, study_hours)

        if existing:
            existing.target_role = interview.target_role
            existing.target_difficulty = interview.difficulty
            existing.target_interview_date = target_interview_date
            existing.daily_study_hours = study_hours
            existing.readiness_score = normalized["readiness_score"]
            existing.readiness_level = normalized["readiness_level"]
            existing.executive_summary = normalized["executive_summary"]
            existing.question_analyses = json.dumps(normalized["question_analyses"])
            existing.skill_gaps = json.dumps(normalized["skill_gaps"])
            existing.strengths = json.dumps(normalized["strengths"])
            existing.untested_competencies = json.dumps(normalized["untested_competencies"])
            existing.roadmap_phases = json.dumps(normalized["roadmap_phases"])
            existing.roadmap_tasks = json.dumps(normalized["roadmap_tasks"])
            existing.reassessment_questions = json.dumps(normalized["reassessment_questions"])
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            try:
                from backend.services.interview_memory_service import InterviewMemoryService
                InterviewMemoryService.sync_roadmap_with_memory(db, user_id, existing)
            except Exception as e:
                logger.warning(f"Failed to sync refreshed roadmap with memory: {e}")
            return existing
        else:
            roadmap_record = InterviewAnalysisRoadmap(
                id=str(uuid.uuid4()),
                interview_id=interview_id,
                user_id=user_id,
                target_role=interview.target_role,
                target_difficulty=interview.difficulty,
                target_interview_date=target_interview_date,
                daily_study_hours=study_hours,
                readiness_score=normalized["readiness_score"],
                readiness_level=normalized["readiness_level"],
                executive_summary=normalized["executive_summary"],
                question_analyses=json.dumps(normalized["question_analyses"]),
                skill_gaps=json.dumps(normalized["skill_gaps"]),
                strengths=json.dumps(normalized["strengths"]),
                untested_competencies=json.dumps(normalized["untested_competencies"]),
                roadmap_phases=json.dumps(normalized["roadmap_phases"]),
                roadmap_tasks=json.dumps(normalized["roadmap_tasks"]),
                reassessment_questions=json.dumps(normalized["reassessment_questions"]),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(roadmap_record)
            db.commit()
            db.refresh(roadmap_record)
            try:
                from backend.services.interview_memory_service import InterviewMemoryService
                InterviewMemoryService.sync_roadmap_with_memory(db, user_id, roadmap_record)
            except Exception as e:
                logger.warning(f"Failed to sync new roadmap with memory: {e}")
            return roadmap_record

    @classmethod
    def _normalize_roadmap_payload(
        cls,
        payload: Dict[str, Any],
        qa_history: List[Dict[str, Any]],
        context: Dict[str, Any],
        study_hours: float
    ) -> Dict[str, Any]:
        """Validates, sanitizes, and normalizes the AI analysis payload."""
        readiness_score = float(payload.get("readiness_score", 70.0))
        readiness_score = max(0.0, min(100.0, readiness_score))

        readiness_level = payload.get("readiness_level") or (
            "Interview Ready" if readiness_score >= 85
            else "Needs Targeted Preparation" if readiness_score >= 65
            else "Significant Remediation Required"
        )

        executive_summary = payload.get("executive_summary") or (
            f"Candidate completed an interview session for {context.get('target_role')}. "
            f"Overall performance demonstrated foundational understanding with specific areas requiring targeted deepening."
        )

        # Question analyses
        raw_qa = payload.get("question_analyses", [])
        question_analyses = []
        if isinstance(raw_qa, list):
            for idx, item in enumerate(raw_qa):
                if isinstance(item, dict):
                    q_num = item.get("question_number", idx + 1)
                    matched_q = next((q for q in qa_history if q["question_number"] == q_num), None)
                    q_id = matched_q["question_id"] if matched_q else str(uuid.uuid4())
                    q_text = matched_q["question_text"] if matched_q else item.get("question_text", f"Question {q_num}")
                    ans_excerpt = item.get("candidate_answer_excerpt") or (matched_q["candidate_answer"][:180] if matched_q else "")
                    
                    question_analyses.append({
                        "question_id": str(item.get("question_id") or q_id),
                        "question_number": int(q_num),
                        "question_text": q_text,
                        "candidate_answer_excerpt": ans_excerpt,
                        "technical_correctness": cls._to_scale_10(item.get("technical_correctness", 7.0)),
                        "conceptual_understanding": cls._to_scale_10(item.get("conceptual_understanding", 7.0)),
                        "depth_and_clarity": cls._to_scale_10(item.get("depth_and_clarity", 7.0)),
                        "reasoning_approach": cls._to_scale_10(item.get("reasoning_approach", 7.0)),
                        "completeness": cls._to_scale_10(item.get("completeness", 7.0)),
                        "key_strengths": item.get("key_strengths", []),
                        "misconceptions": item.get("misconceptions", []),
                        "missing_concepts": item.get("missing_concepts", []),
                        "poorly_explained_aspects": item.get("poorly_explained_aspects", []),
                        "coding_evaluation": item.get("coding_evaluation")
                    })

        # Skill gaps
        raw_gaps = payload.get("skill_gaps", [])
        skill_gaps = []
        if isinstance(raw_gaps, list):
            for i, gap in enumerate(raw_gaps):
                if isinstance(gap, dict):
                    rem = gap.get("remediation_path") or {}
                    if not isinstance(rem, dict):
                        rem = {
                            "what_went_wrong": str(rem),
                            "what_to_learn": "Study core reference principles and design patterns.",
                            "what_to_practice": "Implement end-to-end examples handling failure states.",
                            "how_to_verify": "Explain architectural trade-offs without referencing documentation."
                        }
                    
                    skill_gaps.append({
                        "gap_id": str(gap.get("gap_id") or f"gap_{i+1}"),
                        "competency": str(gap.get("competency") or f"Core Skill {i+1}"),
                        "category": str(gap.get("category") or "Technical"),
                        "finding_type": str(gap.get("finding_type") or "CONFIRMED_WEAKNESS"),
                        "confidence_level": str(gap.get("confidence_level") or "HIGH"),
                        "evidence_question_id": gap.get("evidence_question_id"),
                        "evidence_question_number": gap.get("evidence_question_number"),
                        "evidence_question_text": gap.get("evidence_question_text"),
                        "candidate_answer_excerpt": gap.get("candidate_answer_excerpt"),
                        "what_was_missing_or_incorrect": str(gap.get("what_was_missing_or_incorrect") or "Key conceptual precision omitted."),
                        "why_it_matters": str(gap.get("why_it_matters") or "Essential for robust real-world production systems and interview calibration."),
                        "correct_understanding": str(gap.get("correct_understanding") or "Standard engineering implementation and trade-off justification."),
                        "priority": str(gap.get("priority") or "HIGH"),
                        "remediation_path": {
                            "what_went_wrong": str(rem.get("what_went_wrong", "Incomplete conceptual explanation.")),
                            "what_to_learn": str(rem.get("what_to_learn", "Foundational principles.")),
                            "what_to_practice": str(rem.get("what_to_practice", "Targeted code and architecture implementation.")),
                            "how_to_verify": str(rem.get("how_to_verify", "Diagnostic mock problem verification."))
                        }
                    })

        # Strengths
        raw_strengths = payload.get("strengths", [])
        strengths = []
        if isinstance(raw_strengths, list):
            for s in raw_strengths:
                if isinstance(s, dict):
                    strengths.append({
                        "competency": str(s.get("competency", "Core Concept")),
                        "category": str(s.get("category", "General")),
                        "evidence_question_number": s.get("evidence_question_number"),
                        "candidate_excerpt": s.get("candidate_excerpt"),
                        "demonstrated_mastery": str(s.get("demonstrated_mastery", "Accurately articulated principles."))
                    })

        # Untested
        raw_untested = payload.get("untested_competencies", [])
        untested = []
        if isinstance(raw_untested, list):
            for u in raw_untested:
                if isinstance(u, dict):
                    untested.append({
                        "competency": str(u.get("competency", "System Design")),
                        "category": str(u.get("category", "Architecture")),
                        "importance_for_role": str(u.get("importance_for_role", "Crucial for senior engineering calibration.")),
                        "recommended_next_step": str(u.get("recommended_next_step", "Complete targeted mock session."))
                    })

        # Phases
        raw_phases = payload.get("roadmap_phases", [])
        roadmap_phases = []
        if isinstance(raw_phases, list) and len(raw_phases) > 0:
            for p in raw_phases:
                if isinstance(p, dict):
                    roadmap_phases.append({
                        "phase_number": int(p.get("phase_number", 1)),
                        "title": str(p.get("title", f"Phase {p.get('phase_number', 1)}")),
                        "duration_weeks": float(p.get("duration_weeks", 1.0)),
                        "focus_areas": p.get("focus_areas", []),
                        "milestone": str(p.get("milestone", "Complete phase learning checkpoints."))
                    })
        else:
            roadmap_phases = [
                {"phase_number": 1, "title": "Phase 1: Prerequisite & Core Concepts Remediation", "duration_weeks": 1.0, "focus_areas": ["Foundational Theory", "Syntax & Idioms"], "milestone": "Remediate confirmed answer misconceptions"},
                {"phase_number": 2, "title": "Phase 2: Deep Technical & Architectural Systems", "duration_weeks": 1.5, "focus_areas": ["Concurrency", "Data Consistency", "Trade-offs"], "milestone": "Master high-throughput system patterns"},
                {"phase_number": 3, "title": "Phase 3: Practical Coding & Problem Solving", "duration_weeks": 1.0, "focus_areas": ["Algorithmic Complexity", "Edge Cases"], "milestone": "Zero-defect timed coding implementations"},
                {"phase_number": 4, "title": "Phase 4: Mock Interviews & Final Calibration", "duration_weeks": 0.5, "focus_areas": ["Live Voice Articulation", "Rapid Problem Synthesis"], "milestone": "Pass mock technical calibration with >85%"}
            ]

        # Tasks
        raw_tasks = payload.get("roadmap_tasks", [])
        roadmap_tasks = []
        if isinstance(raw_tasks, list) and len(raw_tasks) > 0:
            for idx, t in enumerate(raw_tasks):
                if isinstance(t, dict):
                    roadmap_tasks.append({
                        "task_id": str(t.get("task_id") or f"task_{idx+1}"),
                        "phase_number": int(t.get("phase_number", 1)),
                        "day_or_sequence": int(t.get("day_or_sequence", idx + 1)),
                        "priority": str(t.get("priority", "HIGH")),
                        "topic": str(t.get("topic", "Core Fundamentals")),
                        "subtopics": t.get("subtopics", []),
                        "learning_objectives": t.get("learning_objectives", []),
                        "practical_exercise": str(t.get("practical_exercise", "Implement a reference scenario.")),
                        "relevant_problems_or_questions": t.get("relevant_problems_or_questions", []),
                        "estimated_duration_hours": float(t.get("estimated_duration_hours", 2.0)),
                        "expected_outcomes": str(t.get("expected_outcomes", "Mastery of topic concepts.")),
                        "completion_criteria": str(t.get("completion_criteria", "Pass self-verification test.")),
                        "status": str(t.get("status", "pending")),
                        "completed_at": t.get("completed_at")
                    })
        # Verify all 4 phases are populated
        present_phases = {t["phase_number"] for t in roadmap_tasks}
        role_name = context.get("target_role", "Software Engineer")
        topic_name = context.get("topic", "Engineering")

        if 1 not in present_phases:
            gap_item = skill_gaps[0] if skill_gaps else None
            gap_txt = gap_item["what_was_missing_or_incorrect"] if gap_item else f"Foundational {topic_name} mechanics"
            roadmap_tasks.append({
                "task_id": "task_p1_core",
                "phase_number": 1,
                "day_or_sequence": 1,
                "priority": "HIGH",
                "topic": f"Core Fundamentals: {gap_item['competency'] if gap_item else topic_name} Remediation",
                "subtopics": ["Concept Clarification", "Syntax Precision", "Failure Modes"],
                "learning_objectives": [f"Remediate verified answer gap: {gap_txt[:60]}", "Master core reference behavior"],
                "practical_exercise": gap_item["remediation_path"]["what_to_practice"] if gap_item else "Write test cases verifying edge cases.",
                "relevant_problems_or_questions": [f"Deep dive: {gap_item['evidence_question_text']}" if (gap_item and gap_item.get("evidence_question_text")) else f"Explain {topic_name} from first principles."],
                "estimated_duration_hours": study_hours,
                "expected_outcomes": "Demonstrated technical clarity on foundational concepts with zero factual errors.",
                "completion_criteria": "Explain the underlying mechanics without notes.",
                "status": "pending",
                "completed_at": None
            })

        if 2 not in present_phases:
            roadmap_tasks.append({
                "task_id": "task_p2_sys",
                "phase_number": 2,
                "day_or_sequence": 2,
                "priority": "HIGH",
                "topic": f"Advanced Systems: Concurrency & Scalability in {topic_name}",
                "subtopics": ["Thread Safety & Locks", "Memory Visibility & Latency", "Throughput Bottlenecks"],
                "learning_objectives": [f"Design thread-safe, scalable subsystems for {role_name}", "Analyze architectural failure modes"],
                "practical_exercise": f"Implement a thread-safe queuing or cache eviction component in {topic_name}.",
                "relevant_problems_or_questions": [f"How do you design a fault-tolerant component in {topic_name} under 10k concurrent requests?"],
                "estimated_duration_hours": round(study_hours * 1.2, 1),
                "expected_outcomes": "Architectural mastery of concurrency and memory consistency.",
                "completion_criteria": "Benchmark code demonstrates zero race conditions and bounded memory overhead.",
                "status": "pending",
                "completed_at": None
            })

        if 3 not in present_phases:
            roadmap_tasks.append({
                "task_id": "task_p3_dsa",
                "phase_number": 3,
                "day_or_sequence": 3,
                "priority": "HIGH",
                "topic": f"Applied Coding & DSA: Algorithmic Efficiency & Complex Edge Cases",
                "subtopics": ["Optimal Big-O Complexity", "Sliding Window / Two Pointers", "Custom Data Structures"],
                "learning_objectives": ["Implement optimal O(N) algorithms under timed constraints", "Zero runtime bugs on edge cases"],
                "practical_exercise": "Solve 2 timed algorithmic problems with full test coverage.",
                "relevant_problems_or_questions": ["Implement an LRU Cache with O(1) operations.", "Reverse nodes in k-Group in linked list."],
                "estimated_duration_hours": study_hours,
                "expected_outcomes": "Production-grade, modular code written within 25 minutes.",
                "completion_criteria": "All unit tests pass with optimal time and space complexity.",
                "status": "pending",
                "completed_at": None
            })

        if 4 not in present_phases:
            reassess_q = payload.get("reassessment_questions", [])
            q_text = reassess_q[0]["question_text"] if (reassess_q and isinstance(reassess_q, list)) else "Follow-up Technical Reassessment"
            roadmap_tasks.append({
                "task_id": "task_p4_mock",
                "phase_number": 4,
                "day_or_sequence": 4,
                "priority": "CRITICAL",
                "topic": f"Full Simulation & Calibration: End-to-End Mock Interview Loop",
                "subtopics": ["STAR/CAR Communication", "Time-Boxed Delivery", "Diagnostic Reassessment"],
                "learning_objectives": ["Articulate structured answers under simulated pressure", "Pass follow-up diagnostic questions"],
                "practical_exercise": f"Record a 15-minute mock simulation answering: '{str(q_text)[:70]}...'",
                "relevant_problems_or_questions": ["Deliver a crisp 3-minute architectural overview with trade-offs."],
                "estimated_duration_hours": study_hours,
                "expected_outcomes": "Confident, senior-level verbal articulation meeting Google/Microsoft calibration rubrics.",
                "completion_criteria": "Achieve >85% score on simulated reassessment panel.",
                "status": "pending",
                "completed_at": None
            })

        # Re-sort tasks by phase_number, then day_or_sequence, and re-index sequence continuously
        roadmap_tasks.sort(key=lambda x: (x.get("phase_number", 1), x.get("day_or_sequence", 1)))
        for idx, t in enumerate(roadmap_tasks):
            t["day_or_sequence"] = idx + 1

        # Reassessment questions
        raw_reassess = payload.get("reassessment_questions", [])
        reassessment_questions = []
        if isinstance(raw_reassess, list):
            for idx, rq in enumerate(raw_reassess):
                if isinstance(rq, dict):
                    reassessment_questions.append({
                        "id": str(rq.get("id") or f"reassess_{idx+1}"),
                        "targeted_gap_id": str(rq.get("targeted_gap_id") or (skill_gaps[0]["gap_id"] if skill_gaps else "gap_1")),
                        "competency": str(rq.get("competency") or "Target Competency"),
                        "question_text": str(rq.get("question_text") or "Explain how you would handle this scenario?"),
                        "expected_key_points": rq.get("expected_key_points", []),
                        "benchmark_solution": str(rq.get("benchmark_solution") or "Comprehensive solution addressing time, memory, and failure modes."),
                        "difficulty": str(rq.get("difficulty") or "Medium")
                    })

        return {
            "readiness_score": readiness_score,
            "readiness_level": readiness_level,
            "executive_summary": executive_summary,
            "question_analyses": question_analyses,
            "skill_gaps": skill_gaps,
            "strengths": strengths,
            "untested_competencies": untested,
            "roadmap_phases": roadmap_phases,
            "roadmap_tasks": roadmap_tasks,
            "reassessment_questions": reassessment_questions
        }

    @classmethod
    def _synthesize_evidence_based_roadmap(
        cls,
        interview_context: Dict[str, Any],
        qa_history: List[Dict[str, Any]],
        coding_submissions: Optional[List[Dict[str, Any]]],
        target_interview_date: Optional[str],
        daily_study_hours: float
    ) -> Dict[str, Any]:
        """Synthesizes genuine, evidence-based roadmap directly from actual interview answers & evaluations."""
        question_analyses = []
        skill_gaps = []
        strengths = []
        scores = []

        for q in qa_history:
            q_num = q["question_number"]
            q_text = q["question_text"]
            ans = q["candidate_answer"]
            ev = q.get("existing_eval") or {}
            is_skipped = q.get("is_skipped", False)

            c_score = cls._to_scale_10(ev.get("technical_correctness", 0.0 if is_skipped else 60.0))
            cmp_score = cls._to_scale_10(ev.get("conceptual_completeness", 0.0 if is_skipped else 60.0))
            d_score = cls._to_scale_10(ev.get("depth_of_understanding", 0.0 if is_skipped else 60.0))
            rr_score = cls._to_scale_10(ev.get("response_relevance", 0.0 if is_skipped else 60.0))
            ovr = float(ev.get("overall_score", 0.0 if is_skipped else 60.0))
            scores.append(ovr)

            q_strengths = ev.get("strengths") or []
            q_missing = ev.get("missing_concepts") or []
            q_incorrect = ev.get("incorrect_claims") or []
            q_improvements = ev.get("improvements") or []

            poorly_explained = []
            if c_score >= 6.5 and d_score < 6.0:
                poorly_explained.append("Concluded with plausible high-level terminology but omitted underlying operational mechanics.")

            if is_skipped:
                q_missing.append("Candidate passed/skipped question without providing conceptual rationale.")

            excerpt = ans[:200] if len(ans) > 200 else ans
            if is_skipped:
                excerpt = "[Question Skipped / No Candidate Answer]"

            question_analyses.append({
                "question_id": q["question_id"],
                "question_number": q_num,
                "question_text": q_text,
                "candidate_answer_excerpt": excerpt,
                "technical_correctness": c_score,
                "conceptual_understanding": cmp_score,
                "depth_and_clarity": d_score,
                "reasoning_approach": rr_score,
                "completeness": cmp_score,
                "key_strengths": q_strengths if isinstance(q_strengths, list) else [str(q_strengths)],
                "misconceptions": q_incorrect if isinstance(q_incorrect, list) else [str(q_incorrect)],
                "missing_concepts": q_missing if isinstance(q_missing, list) else [str(q_missing)],
                "poorly_explained_aspects": poorly_explained,
                "coding_evaluation": None
            })

            # Extract confirmed weaknesses with exact question quotes
            if q_incorrect:
                for inc in (q_incorrect if isinstance(q_incorrect, list) else [str(q_incorrect)]):
                    skill_gaps.append({
                        "gap_id": f"gap_conf_{q_num}_{len(skill_gaps)+1}",
                        "competency": q.get("category", "Core Technical Concept"),
                        "category": q.get("category", "Engineering"),
                        "finding_type": "CONFIRMED_WEAKNESS",
                        "confidence_level": "HIGH",
                        "evidence_question_id": q["question_id"],
                        "evidence_question_number": q_num,
                        "evidence_question_text": q_text,
                        "candidate_answer_excerpt": excerpt,
                        "what_was_missing_or_incorrect": inc,
                        "why_it_matters": f"Misunderstanding in {q.get('category')} leads to incorrect production implementations.",
                        "correct_understanding": f"Standard industry architecture requires rigorous handling of {q.get('category')}.",
                        "priority": "CRITICAL",
                        "remediation_path": {
                            "what_went_wrong": f"Candidate asserted: '{inc}' which is factually inaccurate.",
                            "what_to_learn": f"Deep-dive into official documentation and underlying runtime execution for {q.get('category')}.",
                            "what_to_practice": f"Re-implement an isolated benchmark test validating the true behavior of {q.get('category')}.",
                            "how_to_verify": f"Explain the internal life-cycle and performance characteristics without relying on flawed assumptions."
                        }
                    })

            if q_missing:
                for miss in (q_missing if isinstance(q_missing, list) else [str(q_missing)]):
                    skill_gaps.append({
                        "gap_id": f"gap_miss_{q_num}_{len(skill_gaps)+1}",
                        "competency": q.get("category", "System Principles"),
                        "category": q.get("category", "Architecture"),
                        "finding_type": "CONFIRMED_WEAKNESS" if not is_skipped else "UNCERTAIN_FINDING",
                        "confidence_level": "HIGH" if not is_skipped else "MEDIUM",
                        "evidence_question_id": q["question_id"],
                        "evidence_question_number": q_num,
                        "evidence_question_text": q_text,
                        "candidate_answer_excerpt": excerpt,
                        "what_was_missing_or_incorrect": f"Omitted essential concept: {miss}",
                        "why_it_matters": "Interview evaluators specifically look for these critical components to assess senior capability.",
                        "correct_understanding": f"A complete answer must explicitly detail {miss}.",
                        "priority": "HIGH",
                        "remediation_path": {
                            "what_went_wrong": f"Answer failed to cover: {miss}.",
                            "what_to_learn": f"Review key design patterns and failure modes surrounding {miss}.",
                            "what_to_practice": f"Structure answers using the STAR/CAR framework to ensure {miss} is addressed systematically.",
                            "how_to_verify": "Deliver a 3-minute structured verbal walkthrough without omitting key trade-offs."
                        }
                    })

            if q_improvements and not q_incorrect and not q_missing:
                for imp in (q_improvements if isinstance(q_improvements, list) else [str(q_improvements)]):
                    skill_gaps.append({
                        "gap_id": f"gap_imp_{q_num}_{len(skill_gaps)+1}",
                        "competency": q.get("category", "Core Technical Competency"),
                        "category": q.get("category", "Engineering"),
                        "finding_type": "CONFIRMED_WEAKNESS" if c_score < 7.0 else "UNCERTAIN_FINDING",
                        "confidence_level": "HIGH" if c_score < 7.0 else "MEDIUM",
                        "evidence_question_id": q["question_id"],
                        "evidence_question_number": q_num,
                        "evidence_question_text": q_text,
                        "candidate_answer_excerpt": excerpt,
                        "what_was_missing_or_incorrect": f"Targeted improvement area: {imp}",
                        "why_it_matters": f"Thorough mastery of {q.get('category')} is critical for production reliability and interview calibration.",
                        "correct_understanding": f"Deliver a complete, production-grade explanation addressing {imp}.",
                        "priority": "HIGH" if c_score < 7.5 else "MEDIUM",
                        "remediation_path": {
                            "what_went_wrong": f"Candidate omitted: {imp}.",
                            "what_to_learn": f"Review advanced operational principles for {q.get('category')}.",
                            "what_to_practice": f"Re-articulate the answer addressing {imp} with concrete code examples.",
                            "how_to_verify": f"Explain trade-offs and edge cases for {imp} without referencing notes."
                        }
                    })

            if not q_incorrect and not q_missing and not q_improvements and c_score < 8.0:
                skill_gaps.append({
                    "gap_id": f"gap_score_{q_num}_{len(skill_gaps)+1}",
                    "competency": q.get("category", "Core Technical Principles"),
                    "category": q.get("category", "Engineering"),
                    "finding_type": "UNCERTAIN_FINDING",
                    "confidence_level": "MEDIUM",
                    "evidence_question_id": q["question_id"],
                    "evidence_question_number": q_num,
                    "evidence_question_text": q_text,
                    "candidate_answer_excerpt": excerpt,
                    "what_was_missing_or_incorrect": f"Response provided foundational knowledge but lacked senior depth in {q.get('category')}.",
                    "why_it_matters": "Senior interviewers expect in-depth trade-off analysis and failure mode handling.",
                    "correct_understanding": f"Comprehensive architectural trade-off justification in {q.get('category')}.",
                    "priority": "HIGH",
                    "remediation_path": {
                        "what_went_wrong": "Explanation stayed at a surface level.",
                        "what_to_learn": f"Deepen knowledge of internal runtime execution and performance bottlenecks in {q.get('category')}.",
                        "what_to_practice": f"Construct end-to-end benchmark tests demonstrating mechanics in {q.get('category')}.",
                        "how_to_verify": "Deliver a structured presentation covering failure scenarios and mitigation strategies."
                    }
                })

            # Record strengths
            if q_strengths and ovr >= 6.5:
                for st in (q_strengths if isinstance(q_strengths, list) else [str(q_strengths)]):
                    strengths.append({
                        "competency": q.get("category", "Technical Competency"),
                        "category": q.get("category", "Engineering"),
                        "evidence_question_number": q_num,
                        "candidate_excerpt": excerpt,
                        "demonstrated_mastery": st
                    })

        # Untested Competencies
        role = interview_context.get("target_role", "Software Engineer")
        untested = [
            {
                "competency": "Distributed Caching & Eviction Policies",
                "category": "System Design",
                "importance_for_role": f"High relevance for {role} at scale.",
                "recommended_next_step": "Complete a dedicated System Design mock interview."
            },
            {
                "competency": "Database Query Optimization & Lock Contention",
                "category": "Data Architecture",
                "importance_for_role": "Critical for high-throughput transactional backends.",
                "recommended_next_step": "Review EXPLAIN ANALYZE queries and index structures."
            }
        ]

        avg_score = (sum(scores) / len(scores)) if scores else 65.0
        if avg_score > 10.0:
            readiness_score = round(avg_score, 1)
        else:
            readiness_score = round(avg_score * 10.0, 1)
        readiness_score = max(0.0, min(100.0, readiness_score))

        reassessment_questions = []
        for i, g in enumerate(skill_gaps[:4]):
            reassessment_questions.append({
                "id": f"reassess_{i+1}",
                "targeted_gap_id": g["gap_id"],
                "competency": g["competency"],
                "question_text": f"Follow-up Technical Reassessment: In {g['competency']}, how do you handle {g['what_was_missing_or_incorrect']} under production load?",
                "expected_key_points": [
                    "Directly address trade-offs and edge cases",
                    "Demonstrate correct architectural understanding",
                    "Explain failover and recovery mechanisms"
                ],
                "benchmark_solution": f"A comprehensive model response clearly identifies {g['correct_understanding']} with concrete metrics and fault tolerance.",
                "difficulty": "Medium"
            })

        # Generate sequenced tasks covering ALL 4 phases intelligently
        tasks = []
        seq = 1

        # Phase 1: Core Fundamentals & Misconception Remediation
        phase1_gaps = skill_gaps if skill_gaps else []
        for i, g in enumerate(phase1_gaps[:2]):
            tasks.append({
                "task_id": f"task_{seq}",
                "phase_number": 1,
                "day_or_sequence": seq,
                "priority": g["priority"],
                "topic": f"Core Fundamentals: {g['competency']} Remediation",
                "subtopics": ["Root Misconception Clarification", "Defensive Practices", "Core Language/API Mechanics"],
                "learning_objectives": [
                    f"Remediate verified answer gap: {g['what_was_missing_or_incorrect']}",
                    f"Master correct implementation: {g['correct_understanding']}"
                ],
                "practical_exercise": g["remediation_path"]["what_to_practice"],
                "relevant_problems_or_questions": [
                    f"Targeted review: {g['evidence_question_text']}" if g.get("evidence_question_text") else f"Re-explain {g['competency']} from first principles"
                ],
                "estimated_duration_hours": daily_study_hours,
                "expected_outcomes": g["remediation_path"]["how_to_verify"],
                "completion_criteria": f"Articulate a complete, flaw-free explanation of {g['competency']} resolving: {g['what_was_missing_or_incorrect']}.",
                "status": "pending",
                "completed_at": None
            })
            seq += 1

        if not tasks:
            tasks.append({
                "task_id": f"task_{seq}",
                "phase_number": 1,
                "day_or_sequence": seq,
                "priority": "HIGH",
                "topic": f"Core Fundamentals: {role} Core Theory & Runtime Lifecycle",
                "subtopics": ["Memory Management", "Type Systems", "Object Lifecycle"],
                "learning_objectives": [
                    f"Deepen precision on core {role} language fundamentals",
                    "Verify edge-case handling in standard runtime execution"
                ],
                "practical_exercise": "Write comprehensive unit tests asserting boundary behavior and failure modes.",
                "relevant_problems_or_questions": ["Explain runtime lifecycle and memory layout without referencing documentation."],
                "estimated_duration_hours": daily_study_hours,
                "expected_outcomes": "Demonstrated rock-solid technical articulation of core runtime primitives.",
                "completion_criteria": "Pass diagnostic self-assessment on runtime boundaries with zero hesitation.",
                "status": "pending",
                "completed_at": None
            })
            seq += 1

        # Phase 2: Advanced Concepts & System Architecture
        tasks.append({
            "task_id": f"task_{seq}",
            "phase_number": 2,
            "day_or_sequence": seq,
            "priority": "CRITICAL" if readiness_score < 75 else "HIGH",
            "topic": f"Advanced Systems: Concurrency, Scaling & Memory Models",
            "subtopics": ["Thread Safety & Locks", "Memory Visibility & Cache Invalidation", "Throughput Bottlenecks"],
            "learning_objectives": [
                f"Master production-grade concurrency patterns for {role}",
                "Analyze trade-offs between consistency, availability, and latency"
            ],
            "practical_exercise": f"Implement a thread-safe, bounded in-memory buffer or cache with eviction policies in {interview_context.get('topic', 'target language')}.",
            "relevant_problems_or_questions": [
                "How do you prevent lock contention and deadlocks under 10k RPS load?",
                "Compare optimistic locking vs pessimistic locking in high-write scenarios."
            ],
            "estimated_duration_hours": round(daily_study_hours * 1.2, 1),
            "expected_outcomes": "Ability to design highly concurrent, fault-tolerant system components without race conditions.",
            "completion_criteria": "Successfully implement and benchmark concurrency scenario with zero data races.",
            "status": "pending",
            "completed_at": None
        })
        seq += 1

        # Phase 3: Applied Coding & DSA
        tasks.append({
            "task_id": f"task_{seq}",
            "phase_number": 3,
            "day_or_sequence": seq,
            "priority": "HIGH",
            "topic": f"Applied Coding: Algorithmic Efficiency & Complex Edge Cases",
            "subtopics": ["Time & Space Complexity Optimization", "Sliding Window / Two Pointers", "Custom Data Structure Design"],
            "learning_objectives": [
                "Achieve optimal Big-O algorithmic complexity (O(N) time, O(1) space where applicable)",
                "Systematically handle boundary conditions (nulls, empty inputs, integer overflows, duplicates)"
            ],
            "practical_exercise": "Solve 2 medium-to-hard coding challenges timed within 25 minutes each, writing full test cases.",
            "relevant_problems_or_questions": [
                "Implement an LRU Cache with O(1) get and put operations.",
                "Find all anagrams in a string using sliding window hash frequency maps."
            ],
            "estimated_duration_hours": round(daily_study_hours * 1.0, 1),
            "expected_outcomes": "Clean, modular, production-ready code with zero edge-case bugs under timed constraints.",
            "completion_criteria": "All unit tests and edge cases pass with optimal time and space complexity.",
            "status": "pending",
            "completed_at": None
        })
        seq += 1

        # Phase 4: Full Mock Simulation & Calibration
        reassess_text = reassessment_questions[0]["question_text"] if reassessment_questions else f"Comprehensive {role} Technical Calibration"
        tasks.append({
            "task_id": f"task_{seq}",
            "phase_number": 4,
            "day_or_sequence": seq,
            "priority": "CRITICAL",
            "topic": f"Full Simulation & Calibration: End-to-End Mock Interview Loop",
            "subtopics": ["STAR/CAR Communication", "Rapid Conceptual Articulation", "Stress Testing Answers"],
            "learning_objectives": [
                "Deliver crisp, senior-level verbal responses without rambling or hesitation",
                "Successfully remediate all identified interview gaps in a simulated interview environment"
            ],
            "practical_exercise": f"Record a 15-minute simulated mock interview answering follow-up diagnostic questions: '{reassess_text[:80]}...'",
            "relevant_problems_or_questions": [
                q["question_text"] for q in reassessment_questions[:2]
            ] if reassessment_questions else ["Deliver a 3-minute architectural design walk-through under interviewer scrutiny."],
            "estimated_duration_hours": round(daily_study_hours * 1.0, 1),
            "expected_outcomes": "Demonstrated >85% interview calibration readiness across all rubric evaluation dimensions.",
            "completion_criteria": "Flawlessly answer all diagnostic reassessment questions with accurate industry benchmarks.",
            "status": "pending",
            "completed_at": None
        })


        return {
            "readiness_score": readiness_score,
            "readiness_level": "Interview Ready" if readiness_score >= 85 else ("Needs Targeted Preparation" if readiness_score >= 65 else "Significant Remediation Required"),
            "executive_summary": (
                f"Candidate completed technical interview for {role} ({interview_context.get('difficulty')}). "
                f"Identified {len(skill_gaps)} evidence-based skill gap areas and {len(strengths)} key demonstrated strengths. "
                "The customized roadmap prioritizes high-impact conceptual remediation first, followed by practical system implementation."
            ),
            "question_analyses": question_analyses,
            "skill_gaps": skill_gaps,
            "strengths": strengths,
            "untested_competencies": untested,
            "roadmap_phases": [
                {"phase_number": 1, "title": "Phase 1: Prerequisite & Core Concepts Remediation", "duration_weeks": 1.0, "focus_areas": ["Identified Misconceptions", "Essential Terminology"], "milestone": "Master confirmed weakness areas"},
                {"phase_number": 2, "title": "Phase 2: Deep Technical & Architectural Systems", "duration_weeks": 1.5, "focus_areas": ["Concurrency", "System Scalability"], "milestone": "Synthesize end-to-end architectures"},
                {"phase_number": 3, "title": "Phase 3: Practical Coding & Problem Solving", "duration_weeks": 1.0, "focus_areas": ["Algorithmic Efficiency", "Edge Case Testing"], "milestone": "Timed coding without hints"},
                {"phase_number": 4, "title": "Phase 4: Mock Interviews & Final Calibration", "duration_weeks": 0.5, "focus_areas": ["Simulated Panel Interviews", "Time Management"], "milestone": "Pass mock calibration with >85%"}
            ],
            "roadmap_tasks": tasks,
            "reassessment_questions": reassessment_questions
        }

    @classmethod
    def update_task_status(
        cls,
        db: Session,
        roadmap_id: str,
        task_id: str,
        new_status: str,
        user_id: str
    ) -> InterviewAnalysisRoadmap:
        """Toggles or updates the completion status of a roadmap task persistently."""
        roadmap = db.query(InterviewAnalysisRoadmap).filter(
            InterviewAnalysisRoadmap.id == roadmap_id,
            InterviewAnalysisRoadmap.user_id == user_id
        ).first()

        if not roadmap:
            # Fallback query by interview_id if caller passed interview_id
            roadmap = db.query(InterviewAnalysisRoadmap).filter(
                InterviewAnalysisRoadmap.interview_id == roadmap_id,
                InterviewAnalysisRoadmap.user_id == user_id
            ).first()

        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Roadmap not found."
            )

        tasks = json.loads(roadmap.roadmap_tasks) if roadmap.roadmap_tasks else []
        task_found = False
        completed_count = 0

        for t in tasks:
            if t.get("task_id") == task_id or t.get("id") == task_id:
                t["status"] = new_status
                if new_status == "completed":
                    t["completed_at"] = datetime.utcnow().isoformat()
                else:
                    t["completed_at"] = None
                task_found = True
            if t.get("status") == "completed":
                completed_count += 1

        if not task_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found in roadmap."
            )

        # Update readiness score based on task completions (progressive boost)
        total_tasks = len(tasks)
        if total_tasks > 0:
            completion_ratio = completed_count / total_tasks
            interview = db.query(Interview).filter(Interview.id == roadmap.interview_id).first()
            baseline_score = float(interview.total_score if (interview and interview.total_score is not None) else 65.0)
            if baseline_score > 10.0:
                base_pct = min(95.0, max(40.0, baseline_score))
            else:
                base_pct = min(95.0, max(40.0, baseline_score * 10.0))
            
            gap = 100.0 - base_pct
            adjusted_score = round(base_pct + (completion_ratio * gap), 1)
            roadmap.readiness_score = max(0.0, min(100.0, adjusted_score))
            if roadmap.readiness_score >= 85:
                roadmap.readiness_level = "Interview Ready"
            elif roadmap.readiness_score >= 65:
                roadmap.readiness_level = "Needs Targeted Preparation"
            else:
                roadmap.readiness_level = "Significant Remediation Required"

        roadmap.roadmap_tasks = json.dumps(tasks)
        roadmap.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(roadmap)
        return roadmap

    @classmethod
    def update_preferences(
        cls,
        db: Session,
        roadmap_id: str,
        user_id: str,
        target_interview_date: Optional[str] = None,
        daily_study_hours: Optional[float] = None
    ) -> InterviewAnalysisRoadmap:
        """Updates candidate schedule preferences and dynamically recalibrates task pacing."""
        roadmap = db.query(InterviewAnalysisRoadmap).filter(
            InterviewAnalysisRoadmap.id == roadmap_id,
            InterviewAnalysisRoadmap.user_id == user_id
        ).first()

        if not roadmap:
            roadmap = db.query(InterviewAnalysisRoadmap).filter(
                InterviewAnalysisRoadmap.interview_id == roadmap_id,
                InterviewAnalysisRoadmap.user_id == user_id
            ).first()

        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Roadmap not found."
            )

        if target_interview_date is not None:
            roadmap.target_interview_date = target_interview_date

        if daily_study_hours is not None:
            roadmap.daily_study_hours = daily_study_hours
            cls._recalibrate_task_durations(roadmap, daily_study_hours)

        roadmap.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(roadmap)
        return roadmap

    @classmethod
    def _recalibrate_task_durations(cls, roadmap: InterviewAnalysisRoadmap, daily_hours: float):
        """Recalibrates task hours and phase weeks according to available study hours and target date."""
        if not roadmap.roadmap_tasks:
            return
        try:
            tasks = json.loads(roadmap.roadmap_tasks)
            for t in tasks:
                t["estimated_duration_hours"] = round(float(daily_hours), 1)
            roadmap.roadmap_tasks = json.dumps(tasks)

            target_date_str = getattr(roadmap, 'target_interview_date', None)
            total_weeks = None
            if target_date_str:
                try:
                    dt = datetime.fromisoformat(target_date_str.split("T")[0])
                    now = datetime.utcnow()
                    delta_days = (dt - now).days
                    if delta_days > 2:
                        total_weeks = max(1.0, round(delta_days / 7.0, 1))
                except Exception:
                    pass

            if roadmap.roadmap_phases:
                phases = json.loads(roadmap.roadmap_phases)
                if total_weeks is not None:
                    weights = [0.30, 0.35, 0.20, 0.15]
                    for idx, p in enumerate(phases):
                        w = weights[idx] if idx < len(weights) else 0.25
                        p["duration_weeks"] = round(max(0.5, total_weeks * w), 1)
                else:
                    scale = 2.0 / max(0.5, daily_hours)
                    for p in phases:
                        base_weeks = float(p.get("duration_weeks", 1.0))
                        p["duration_weeks"] = round(max(0.5, base_weeks * scale), 1)
                roadmap.roadmap_phases = json.dumps(phases)
        except Exception as e:
            logger.warning(f"Error recalibrating roadmap tasks: {e}")

    @classmethod
    def to_response(cls, roadmap: InterviewAnalysisRoadmap) -> DeepAnalysisRoadmapResponse:
        """Serializes SQLAlchemy model to DeepAnalysisRoadmapResponse Pydantic schema."""
        def safe_json_load(text_val):
            if not text_val:
                return []
            try:
                return json.loads(text_val)
            except Exception:
                return []

        raw_qa = safe_json_load(roadmap.question_analyses)
        q_analyses = []
        for item in raw_qa:
            if isinstance(item, dict):
                item_copy = dict(item)
                for key in ["technical_correctness", "conceptual_understanding", "depth_and_clarity", "reasoning_approach", "completeness"]:
                    item_copy[key] = cls._to_scale_10(item_copy.get(key, 7.0))
                q_analyses.append(QuestionEvidenceAnalysis(**item_copy))
        
        gaps_raw = safe_json_load(roadmap.skill_gaps)
        skill_gaps = []
        for g in gaps_raw:
            rem = g.get("remediation_path") or {}
            rem_obj = RemediationPath(
                what_went_wrong=rem.get("what_went_wrong", ""),
                what_to_learn=rem.get("what_to_learn", ""),
                what_to_practice=rem.get("what_to_practice", ""),
                how_to_verify=rem.get("how_to_verify", "")
            )
            g_copy = dict(g)
            g_copy["remediation_path"] = rem_obj
            skill_gaps.append(EvidenceSkillGap(**g_copy))

        strengths = [EvidenceStrength(**item) for item in safe_json_load(roadmap.strengths)]
        untested = [UntestedCompetency(**item) for item in safe_json_load(roadmap.untested_competencies)]
        phases = [RoadmapPhase(**item) for item in safe_json_load(roadmap.roadmap_phases)]
        tasks = [RoadmapTask(**item) for item in safe_json_load(roadmap.roadmap_tasks)]
        reassessment = [DiagnosticReassessmentQuestion(**item) for item in safe_json_load(roadmap.reassessment_questions)]

        return DeepAnalysisRoadmapResponse(
            id=roadmap.id,
            interview_id=roadmap.interview_id,
            user_id=roadmap.user_id,
            target_role=roadmap.target_role,
            target_difficulty=roadmap.target_difficulty,
            target_interview_date=roadmap.target_interview_date,
            daily_study_hours=roadmap.daily_study_hours,
            readiness_score=roadmap.readiness_score,
            readiness_level=roadmap.readiness_level,
            executive_summary=roadmap.executive_summary,
            question_analyses=q_analyses,
            skill_gaps=skill_gaps,
            strengths=strengths,
            untested_competencies=untested,
            roadmap_phases=phases,
            roadmap_tasks=tasks,
            reassessment_questions=reassessment,
            created_at=roadmap.created_at.isoformat() if roadmap.created_at else "",
            updated_at=roadmap.updated_at.isoformat() if roadmap.updated_at else ""
        )
