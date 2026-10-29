import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.models.user import User
from backend.models.candidate_profile import CandidateProfile
from backend.models.interview import Interview
from backend.models.question import InterviewQuestion
from backend.models.answer import Answer
from backend.models.evaluation import Evaluation
from backend.models.coding_interview import CodingInterview, CodingSubmission
from backend.models.roadmap import InterviewAnalysisRoadmap
from backend.models.readiness import ReadinessIntelligenceSnapshot
from backend.schemas.readiness import (
    DimensionScore,
    SkillReadiness,
    PersistentWeaknessItem,
    NextBestAction,
    HistoricalTrendPoint,
    EvidenceBreakdown,
    ReadinessIntelligenceResponse
)

logger = logging.getLogger("uvicorn.error")

class ReadinessIntelligenceService:
    @classmethod
    def calculate_and_persist_readiness(
        cls,
        db: Session,
        user: User,
        target_role_override: Optional[str] = None
    ) -> ReadinessIntelligenceSnapshot:
        """Calculates evidence-based multidimensional readiness index and persists historical snapshot."""
        profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
        target_role = target_role_override or (profile.target_role if profile and profile.target_role else "Software Developer")
        experience_level = profile.experience_level if profile and profile.experience_level else "Intermediate"

        # 1. Fetch all user interviews
        all_interviews = db.query(Interview).filter(Interview.user_id == user.id).order_by(Interview.created_at.asc()).all()
        completed_interviews = [i for i in all_interviews if i.status == "completed" and i.total_score is not None]

        # 2. Fetch all evaluations & answers
        evaluations = db.query(Evaluation).join(Interview).filter(Interview.user_id == user.id).all()
        answers = db.query(Answer).filter(Answer.user_id == user.id).all()

        # 3. Fetch all coding submissions
        coding_subs = db.query(CodingSubmission).filter(CodingSubmission.user_id == user.id).order_by(CodingSubmission.submitted_at.asc()).all()

        # 4. Fetch all roadmaps
        roadmaps = db.query(InterviewAnalysisRoadmap).filter(InterviewAnalysisRoadmap.user_id == user.id).all()

        # Compile evidence counts
        n_int = len(completed_interviews)
        n_ans = len(evaluations)
        n_code = len(coding_subs)

        total_roadmap_tasks = 0
        completed_roadmap_tasks = 0
        critical_tasks_done = 0
        pending_critical_tasks = []

        all_roadmap_gaps = []
        for rm in roadmaps:
            if rm.roadmap_tasks:
                try:
                    tasks = json.loads(rm.roadmap_tasks)
                    for t in tasks:
                        total_roadmap_tasks += 1
                        if t.get("status") == "completed":
                            completed_roadmap_tasks += 1
                            if t.get("priority") == "CRITICAL":
                                critical_tasks_done += 1
                        elif t.get("priority") == "CRITICAL":
                            pending_critical_tasks.append(t)
                except Exception:
                    pass

            if rm.skill_gaps:
                try:
                    gaps = json.loads(rm.skill_gaps)
                    all_roadmap_gaps.extend(gaps)
                except Exception:
                    pass

        # 5. Data Sufficiency Evaluation
        total_evidence_points = n_ans + n_code + completed_roadmap_tasks
        if n_int == 0 and n_code == 0:
            data_sufficiency = "INSUFFICIENT"
            sufficiency_explanation = (
                "Insufficient Assessment Data: Complete at least 1 technical mock interview or code challenge "
                f"to calibrate your readiness score for {target_role}."
            )
        elif n_int == 1 and total_evidence_points < 8:
            data_sufficiency = "MODERATE"
            sufficiency_explanation = (
                f"Calibrated using 1 completed session ({n_ans} evaluated answers). "
                "Complete 2 more mock sessions to establish high-confidence trend telemetry."
            )
        elif n_int >= 2 and total_evidence_points < 20:
            data_sufficiency = "HIGH"
            sufficiency_explanation = (
                f"High Evidence Confidence: Calibrated using {n_int} completed interviews, {n_ans} evaluated answers, "
                f"{n_code} coding submissions, and {completed_roadmap_tasks} completed roadmap milestones."
            )
        else:
            data_sufficiency = "VERY_HIGH"
            sufficiency_explanation = (
                f"Comprehensive Telemetry: Calibrated using {n_int} completed interviews, {n_ans} answer evaluations, "
                f"{n_code} coding challenges, and {completed_roadmap_tasks} verified roadmap milestones."
            )

        def to_pct(score_val: Optional[float]) -> float:
            if score_val is None:
                return 0.0
            val = float(score_val)
            if val <= 10.0:
                val = val * 10.0
            return max(0.0, min(100.0, val))

        # 6. Multidimensional Scoring
        # Dimension 1: Technical Mastery & Depth
        if evaluations:
            tc_scores = [to_pct(e.technical_correctness) for e in evaluations]
            du_scores = [to_pct(e.depth_of_understanding) for e in evaluations]
            dim1_score = round((sum(tc_scores) / len(tc_scores) * 0.6) + (sum(du_scores) / len(du_scores) * 0.4), 1)
            dim1_status = cls._get_status_from_score(dim1_score)
            dim1_evidence = (
                f"Evaluated across {len(evaluations)} answers: average technical correctness "
                f"{round(sum(tc_scores)/len(tc_scores), 1)}%, conceptual depth "
                f"{round(sum(du_scores)/len(du_scores), 1)}%."
            )
        else:
            dim1_score = 0.0
            dim1_status = "Insufficient Data"
            dim1_evidence = "No technical interview answers evaluated yet."

        # Dimension 2: Conceptual Completeness & Trade-offs
        if evaluations:
            cc_scores = [to_pct(e.conceptual_completeness) for e in evaluations]
            rr_scores = [to_pct(e.response_relevance) for e in evaluations]
            dim2_score = round((sum(cc_scores) / len(cc_scores) * 0.6) + (sum(rr_scores) / len(rr_scores) * 0.4), 1)
            dim2_status = cls._get_status_from_score(dim2_score)
            dim2_evidence = (
                f"Evaluated across {len(evaluations)} answers: conceptual completeness "
                f"{round(sum(cc_scores)/len(cc_scores), 1)}% with relevance "
                f"{round(sum(rr_scores)/len(rr_scores), 1)}%."
            )
        else:
            dim2_score = 0.0
            dim2_status = "Insufficient Data"
            dim2_evidence = "No conceptual questions evaluated yet."

        # Dimension 3: Communication & Reasoning Clarity
        if evaluations:
            sc_scores = [to_pct(e.structural_clarity) for e in evaluations]
            dim3_score = round(sum(sc_scores) / len(sc_scores), 1)
            dim3_status = cls._get_status_from_score(dim3_score)
            dim3_evidence = (
                f"Evaluated across {len(evaluations)} responses: structural clarity and articulation "
                f"{round(sum(sc_scores)/len(sc_scores), 1)}%."
            )
        else:
            dim3_score = 0.0
            dim3_status = "Insufficient Data"
            dim3_evidence = "No communication data recorded yet."

        # Dimension 4: Coding & Algorithmic Problem-Solving
        if coding_subs:
            c_scores = [cs.coding_score for cs in coding_subs if cs.coding_score is not None]
            total_cases = sum(cs.total_test_cases or 0 for cs in coding_subs)
            passed_cases = sum(cs.test_cases_passed or 0 for cs in coding_subs)
            pass_rate = (passed_cases / total_cases * 100.0) if total_cases > 0 else 0.0
            avg_c = (sum(c_scores) / len(c_scores)) if c_scores else pass_rate
            dim4_score = round(avg_c, 1)
            dim4_status = cls._get_status_from_score(dim4_score)
            dim4_evidence = (
                f"Evaluated across {len(coding_subs)} coding submissions: "
                f"{passed_cases}/{total_cases} test cases passed ({round(pass_rate, 1)}%), avg score {dim4_score}%."
            )
        else:
            dim4_score = 0.0
            dim4_status = "Insufficient Data"
            dim4_evidence = "No code sandbox or coding interview submissions evaluated yet."

        # Dimension 5: Preparation Consistency & Roadmap Execution
        if total_roadmap_tasks > 0:
            task_ratio = completed_roadmap_tasks / total_roadmap_tasks
            base_prep = task_ratio * 100.0
            crit_bonus = min(15.0, critical_tasks_done * 5.0)
            dim5_score = round(min(100.0, base_prep + crit_bonus), 1)
            dim5_status = cls._get_status_from_score(dim5_score)
            dim5_evidence = (
                f"Roadmap execution: {completed_roadmap_tasks}/{total_roadmap_tasks} tasks completed "
                f"({round(task_ratio*100, 1)}%), including {critical_tasks_done} critical remediation milestones."
            )
        else:
            dim5_score = 0.0
            dim5_status = "Insufficient Data"
            dim5_evidence = "No active preparation roadmap tasks generated or tracked yet."

        # Calculate Overall Readiness using evidence weights
        if n_int == 0 and n_code == 0:
            overall_readiness = 0.0
        else:
            # Dynamic reweighting if coding or roadmap is not yet active
            weights = {
                "tech": 0.25,
                "concept": 0.20,
                "comm": 0.15,
                "coding": 0.20 if coding_subs else 0.0,
                "prep": 0.20 if total_roadmap_tasks > 0 else 0.0
            }
            active_weight_sum = sum(weights.values())
            if active_weight_sum > 0:
                overall_readiness = round(
                    (dim1_score * weights["tech"] +
                     dim2_score * weights["concept"] +
                     dim3_score * weights["comm"] +
                     dim4_score * weights["coding"] +
                     dim5_score * weights["prep"]) / active_weight_sum,
                    1
                )
            else:
                overall_readiness = 0.0

        # Stage calculation
        if overall_readiness >= 85.0:
            readiness_stage = "Interview Calibrated"
        elif overall_readiness >= 70.0:
            readiness_stage = "Target Practice"
        elif overall_readiness >= 50.0:
            readiness_stage = "Developing Competence"
        else:
            readiness_stage = "Early Preparation"

        dimensions_list = [
            {
                "name": "Technical Depth & Correctness",
                "score": dim1_score,
                "weight": 0.25,
                "status": dim1_status,
                "evidence_summary": dim1_evidence,
                "data_points_count": len(evaluations)
            },
            {
                "name": "Conceptual Completeness & Architecture",
                "score": dim2_score,
                "weight": 0.20,
                "status": dim2_status,
                "evidence_summary": dim2_evidence,
                "data_points_count": len(evaluations)
            },
            {
                "name": "Communication & Reasoning Clarity",
                "score": dim3_score,
                "weight": 0.15,
                "status": dim3_status,
                "evidence_summary": dim3_evidence,
                "data_points_count": len(evaluations)
            },
            {
                "name": "Coding & Algorithmic Problem-Solving",
                "score": dim4_score,
                "weight": 0.20,
                "status": dim4_status,
                "evidence_summary": dim4_evidence,
                "data_points_count": len(coding_subs)
            },
            {
                "name": "Preparation Consistency & Roadmap Execution",
                "score": dim5_score,
                "weight": 0.20,
                "status": dim5_status,
                "evidence_summary": dim5_evidence,
                "data_points_count": total_roadmap_tasks
            }
        ]

        # 7. Skill-Wise Readiness & Trends
        skill_dict: Dict[str, List[Dict[str, Any]]] = {}
        for ev in evaluations:
            q = db.query(InterviewQuestion).filter(InterviewQuestion.id == ev.question_id).first()
            s_name = q.skill if q and q.skill else (q.category if q and q.category else "Core Knowledge")
            cat = q.category if q and q.category else "Technical"
            d_str = ev.created_at.strftime("%Y-%m-%d") if ev.created_at else None
            
            skill_dict.setdefault(s_name, []).append({
                "score": to_pct(ev.overall_score),
                "category": cat,
                "date": d_str
            })

        for cs in coding_subs:
            s_name = "Algorithms & Data Structures"
            cat = "Coding"
            d_str = cs.submitted_at.strftime("%Y-%m-%d") if cs.submitted_at else None
            skill_dict.setdefault(s_name, []).append({
                "score": to_pct(cs.coding_score),
                "category": cat,
                "date": d_str
            })

        skill_readiness_list = []
        for s_name, attempts in skill_dict.items():
            scs = [a["score"] for a in attempts]
            s_avg = round(sum(scs) / len(scs), 1)
            
            # Trend calculation
            if len(scs) >= 2:
                mid = len(scs) // 2
                first_half = sum(scs[:mid]) / mid
                second_half = sum(scs[mid:]) / (len(scs) - mid)
                if second_half - first_half >= 5.0:
                    trend = "improving"
                elif first_half - second_half >= 5.0:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            conf = "HIGH" if len(scs) >= 3 else ("MODERATE" if len(scs) == 2 else "LOW")
            last_dt = attempts[-1]["date"] if attempts else None

            skill_readiness_list.append({
                "skill": s_name,
                "category": attempts[0]["category"] if attempts else "General",
                "score": s_avg,
                "sample_count": len(scs),
                "trend": trend,
                "last_tested_date": last_dt,
                "confidence": conf
            })

        skill_readiness_list.sort(key=lambda x: x["score"], reverse=True)

        # 8. Persistent Weaknesses Identification
        # Collect gaps with their source questions and answers
        gap_occurrences: Dict[str, Dict[str, Any]] = {}
        for ev in evaluations:
            raw_missing = ev.missing_concepts
            raw_incorrect = ev.incorrect_claims
            q = db.query(InterviewQuestion).filter(InterviewQuestion.id == ev.question_id).first()
            ans = db.query(Answer).filter(Answer.id == ev.answer_id).first()
            q_txt = q.question_text if q else "Interview Question"
            ans_txt = ans.answer_text if ans else ""
            session_title = ev.interview.title if ev.interview else "Mock Session"
            session_dt = ev.created_at.strftime("%Y-%m-%d") if ev.created_at else None

            items_to_check = []
            if raw_missing:
                try:
                    loaded = json.loads(raw_missing) if isinstance(raw_missing, str) else raw_missing
                    if isinstance(loaded, list):
                        items_to_check.extend([(item, "Missing Concept") for item in loaded])
                except Exception:
                    pass

            if raw_incorrect:
                try:
                    loaded = json.loads(raw_incorrect) if isinstance(raw_incorrect, str) else raw_incorrect
                    if isinstance(loaded, list):
                        items_to_check.extend([(item, "Misconception") for item in loaded])
                except Exception:
                    pass

            for item_text, g_type in items_to_check:
                # Key by simplified concept root
                key = item_text.strip()[:60]
                if key not in gap_occurrences:
                    gap_occurrences[key] = {
                        "name": item_text,
                        "category": q.category if q and q.category else "Technical",
                        "count": 0,
                        "sessions": set(),
                        "dates": [],
                        "excerpts": []
                    }
                gap_occurrences[key]["count"] += 1
                gap_occurrences[key]["sessions"].add(session_title)
                if session_dt:
                    gap_occurrences[key]["dates"].append(session_dt)
                if ans_txt and len(gap_occurrences[key]["excerpts"]) < 2:
                    gap_occurrences[key]["excerpts"].append(ans_txt[:160] + "...")

        # Also incorporate roadmap skill gaps
        for rg in all_roadmap_gaps:
            rg_title = rg.get("what_was_missing_or_incorrect") or rg.get("competency") or ""
            key = rg_title.strip()[:60]
            if key in gap_occurrences:
                gap_occurrences[key]["count"] += 1
                if rg.get("candidate_answer_excerpt") and len(gap_occurrences[key]["excerpts"]) < 2:
                    gap_occurrences[key]["excerpts"].append(rg["candidate_answer_excerpt"][:160] + "...")

        persistent_weaknesses_list = []
        for key, g_data in gap_occurrences.items():
            # If recurring across multiple sessions/questions or confirmed high severity
            if g_data["count"] >= 2 or len(g_data["sessions"]) >= 2:
                dates = sorted(g_data["dates"])
                persistent_weaknesses_list.append({
                    "weakness_name": g_data["name"],
                    "category": g_data["category"],
                    "recurrence_count": g_data["count"],
                    "first_observed_date": dates[0] if dates else None,
                    "latest_observed_date": dates[-1] if dates else None,
                    "affected_sessions": list(g_data["sessions"]),
                    "evidence_excerpts": g_data["excerpts"],
                    "impact_on_target_role": f"Repeated misconception or omission in {g_data['category']} directly compromises senior evaluation criteria.",
                    "recommended_remediation": f"Complete targeted diagnostic drills on {g_data['category']}.",
                    "target_roadmap_task_id": None
                })

        persistent_weaknesses_list.sort(key=lambda x: x["recurrence_count"], reverse=True)

        # 9. Next Best Preparation Action Determination
        if n_int == 0 and n_code == 0:
            next_action = {
                "action_type": "TAKE_INITIAL_MOCK",
                "title": f"Take Your First {target_role} Mock Interview",
                "priority": "CRITICAL",
                "rationale": "No interview evaluations exist yet. Take an initial mock interview to establish your baseline readiness score.",
                "evidence_basis": "Zero completed sessions recorded.",
                "deep_link_tab": "interview",
                "target_item_id": None,
                "estimated_minutes": 25
            }
        elif persistent_weaknesses_list:
            top_pw = persistent_weaknesses_list[0]
            next_action = {
                "action_type": "REMEDIATE_PERSISTENT_WEAKNESS",
                "title": f"Remediate Persistent Weakness: {top_pw['weakness_name'][:40]}",
                "priority": "CRITICAL",
                "rationale": f"This gap appeared in {top_pw['recurrence_count']} separate evaluation instances across your interviews.",
                "evidence_basis": f"Observed in {', '.join(top_pw['affected_sessions'][:2])}.",
                "deep_link_tab": "plan",
                "target_item_id": top_pw.get("target_roadmap_task_id"),
                "estimated_minutes": 35
            }
        elif pending_critical_tasks:
            top_crit = pending_critical_tasks[0]
            next_action = {
                "action_type": "PRACTICE_ROADMAP_TASK",
                "title": f"Complete Critical Roadmap Task: {top_crit.get('topic', 'Core Remediation')}",
                "priority": "CRITICAL",
                "rationale": "High-priority preparation milestone identified by AI audit of your interview answers.",
                "evidence_basis": top_crit.get("expected_outcomes") or "Directly targets confirmed answer gaps.",
                "deep_link_tab": "plan",
                "target_item_id": top_crit.get("task_id"),
                "estimated_minutes": int(top_crit.get("estimated_duration_hours", 2.0) * 60)
            }
        elif n_code == 0:
            next_action = {
                "action_type": "CODE_SANDBOX_CHALLENGE",
                "title": "Complete a Live Algorithmic Challenge in Code Sandbox",
                "priority": "HIGH",
                "rationale": "No practical coding telemetry recorded. Demonstrating timed code correctness boosts your readiness index.",
                "evidence_basis": "Coding & Problem-Solving dimension currently has 0 submissions.",
                "deep_link_tab": "sandbox",
                "target_item_id": None,
                "estimated_minutes": 30
            }
        elif n_int < 3:
            next_action = {
                "action_type": "TAKE_INITIAL_MOCK",
                "title": f"Complete Calibration Mock #{n_int + 1} ({target_role})",
                "priority": "HIGH",
                "rationale": "Expand evidence confidence and calibrate response consistency across broader topic depth.",
                "evidence_basis": f"Currently calibrated on {n_int} sessions. 3 sessions required for high trend confidence.",
                "deep_link_tab": "voice" if n_int % 2 == 1 else "interview",
                "target_item_id": None,
                "estimated_minutes": 25
            }
        else:
            next_action = {
                "action_type": "DIAGNOSTIC_REASSESSMENT",
                "title": "Run Timed Diagnostic Reassessment Suite",
                "priority": "MEDIUM",
                "rationale": "Verify that previous gaps have been mastered under timed conditions.",
                "evidence_basis": f"Demonstrated {overall_readiness}% readiness across {n_int} completed interviews.",
                "deep_link_tab": "plan",
                "target_item_id": None,
                "estimated_minutes": 20
            }

        # 10. Historical Trend Points
        chronological_sessions = []
        for i in completed_interviews:
            dt = i.created_at.strftime("%Y-%m-%d") if i.created_at else "Recent"
            i_score = to_pct(i.total_score)
            chronological_sessions.append({
                "date": dt,
                "overall_score": i_score,
                "technical_score": i_score,
                "coding_score": 0.0,
                "session_type": i.interview_type or "Technical",
                "session_title": i.title or "Mock Interview",
                "created_at": i.created_at
            })

        for cs in coding_subs:
            dt = cs.submitted_at.strftime("%Y-%m-%d") if cs.submitted_at else "Recent"
            c_score = to_pct(cs.coding_score)
            chronological_sessions.append({
                "date": dt,
                "overall_score": c_score,
                "technical_score": c_score,
                "coding_score": c_score,
                "session_type": "Coding",
                "session_title": cs.question.title if cs.question else "Code Challenge",
                "created_at": cs.submitted_at
            })

        chronological_sessions.sort(key=lambda x: x["created_at"])
        trend_points = [
            {
                "date": s["date"],
                "overall_score": s["overall_score"],
                "technical_score": s["technical_score"],
                "coding_score": s["coding_score"],
                "session_type": s["session_type"],
                "session_title": s["session_title"]
            }
            for s in chronological_sessions[-10:]
        ]

        evidence_breakdown_dict = {
            "total_interviews_evaluated": n_int,
            "total_answers_analyzed": n_ans,
            "total_coding_submissions": n_code,
            "total_roadmap_tasks_completed": completed_roadmap_tasks,
            "recurring_gap_count": len(persistent_weaknesses_list),
            "demonstrated_mastery_count": len([s for s in skill_readiness_list if s["score"] >= 80.0]),
            "evaluated_answers_count": n_ans,
            "completed_interviews_count": n_int,
            "calculation_formula_explanation": (
                "Weighted synthesis: 25% Technical Depth, 20% Conceptual Completeness, "
                "15% Structural Clarity, 20% Coding Accuracy, 20% Roadmap Execution."
            )
        }

        # Save snapshot
        snapshot = ReadinessIntelligenceSnapshot(
            id=str(uuid.uuid4()),
            user_id=user.id,
            target_role=target_role,
            experience_level=experience_level,
            overall_readiness_score=overall_readiness,
            readiness_stage=readiness_stage,
            data_sufficiency=data_sufficiency,
            data_sufficiency_explanation=sufficiency_explanation,
            dimension_scores=json.dumps(dimensions_list),
            skill_scores=json.dumps(skill_readiness_list),
            persistent_weaknesses=json.dumps(persistent_weaknesses_list),
            next_best_action=json.dumps(next_action),
            evidence_breakdown=json.dumps(evidence_breakdown_dict),
            historical_trend=json.dumps(trend_points),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    @classmethod
    def get_latest_readiness(cls, db: Session, user: User) -> ReadinessIntelligenceSnapshot:
        """Retrieves most recent snapshot or recalculates automatically if outdated or corrupt."""
        latest = db.query(ReadinessIntelligenceSnapshot).filter(
            ReadinessIntelligenceSnapshot.user_id == user.id
        ).order_by(ReadinessIntelligenceSnapshot.created_at.desc()).first()

        needs_recalc = False
        if not latest:
            needs_recalc = True
        elif latest.overall_readiness_score > 100.0:
            needs_recalc = True
        else:
            # Check if an evaluation was completed after this snapshot was created
            last_eval = db.query(Evaluation).join(Interview).filter(Interview.user_id == user.id).order_by(Evaluation.created_at.desc()).first()
            if last_eval and last_eval.created_at and latest.created_at and last_eval.created_at > latest.created_at:
                needs_recalc = True

        if needs_recalc:
            return cls.calculate_and_persist_readiness(db, user)
        return latest

    @classmethod
    def get_readiness_history(cls, db: Session, user: User) -> List[ReadinessIntelligenceSnapshot]:
        """Retrieves chronological historical snapshots for audit and progression tracking."""
        return db.query(ReadinessIntelligenceSnapshot).filter(
            ReadinessIntelligenceSnapshot.user_id == user.id
        ).order_by(ReadinessIntelligenceSnapshot.created_at.asc()).all()

    @classmethod
    def to_response(cls, snapshot: ReadinessIntelligenceSnapshot) -> ReadinessIntelligenceResponse:
        """Serializes SQLAlchemy model to ReadinessIntelligenceResponse Pydantic schema with sanitization."""
        def safe_load(val, default):
            if not val:
                return default
            try:
                return json.loads(val)
            except Exception:
                return default

        def clean_pct(val: Any) -> float:
            if val is None:
                return 0.0
            v = float(val)
            if v > 100.0:
                v = v / 10.0
            return max(0.0, min(100.0, round(v, 1)))

        raw_dims = safe_load(snapshot.dimension_scores, [])
        dims = []
        for d in raw_dims:
            if isinstance(d, dict):
                d["score"] = clean_pct(d.get("score"))
                dims.append(DimensionScore(**d))

        raw_skills = safe_load(snapshot.skill_scores, [])
        skills = []
        for s in raw_skills:
            if isinstance(s, dict):
                s["score"] = clean_pct(s.get("score"))
                skills.append(SkillReadiness(**s))
        raw_pw = safe_load(snapshot.persistent_weaknesses, [])
        pw = []
        for p in raw_pw:
            if isinstance(p, dict):
                try:
                    pw.append(PersistentWeaknessItem(**p))
                except Exception:
                    pass
            elif isinstance(p, str) and p.strip():
                pw.append(PersistentWeaknessItem(weakness_name=p.strip()))
        next_act = NextBestAction(**safe_load(snapshot.next_best_action, {
            "title": "Start Mock Interview",
            "action_type": "TAKE_INITIAL_MOCK",
            "priority": "HIGH",
            "rationale": "Calibrate your performance.",
            "evidence_basis": "No data yet.",
            "deep_link_tab": "interview",
            "estimated_minutes": 25
        }))

        ev_raw = safe_load(snapshot.evidence_breakdown, {
            "calculation_formula_explanation": "Multidimensional synthesis."
        })
        if "evaluated_answers_count" not in ev_raw:
            ev_raw["evaluated_answers_count"] = ev_raw.get("total_answers_analyzed", 0)
        if "completed_interviews_count" not in ev_raw:
            ev_raw["completed_interviews_count"] = ev_raw.get("total_interviews_evaluated", 0)
        ev_breakdown = EvidenceBreakdown(**ev_raw)

        raw_trend = safe_load(snapshot.historical_trend, [])
        trend = []
        for t in raw_trend:
            if isinstance(t, dict):
                t["overall_score"] = clean_pct(t.get("overall_score"))
                t["technical_score"] = clean_pct(t.get("technical_score"))
                t["coding_score"] = clean_pct(t.get("coding_score"))
                trend.append(HistoricalTrendPoint(**t))

        overall_score = clean_pct(snapshot.overall_readiness_score)

        return ReadinessIntelligenceResponse(
            id=snapshot.id,
            user_id=snapshot.user_id,
            target_role=snapshot.target_role,
            experience_level=snapshot.experience_level,
            overall_readiness_score=overall_score,
            readiness_stage=snapshot.readiness_stage,
            data_sufficiency=snapshot.data_sufficiency,
            data_sufficiency_explanation=snapshot.data_sufficiency_explanation,
            dimensions=dims,
            skills=skills,
            persistent_weaknesses=pw,
            next_best_action=next_act,
            evidence_breakdown=ev_breakdown,
            historical_trend=trend,
            calculated_at=snapshot.created_at.isoformat() if snapshot.created_at else "",
            readiness_score=overall_score,
            readiness_level=snapshot.readiness_stage,
            readiness_explanation=snapshot.data_sufficiency_explanation
        )

    @staticmethod
    def _get_status_from_score(score: float) -> str:
        if score >= 85.0:
            return "Exceptional"
        elif score >= 70.0:
            return "Proficient"
        elif score >= 50.0:
            return "Developing"
        return "Needs Remediation"

# Compatibility alias
ReadinessService = ReadinessIntelligenceService
