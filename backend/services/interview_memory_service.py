import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from backend.models.user import User
from backend.models.candidate_profile import CandidateProfile
from backend.models.interview import Interview
from backend.models.question import InterviewQuestion
from backend.models.answer import Answer
from backend.models.evaluation import Evaluation
from backend.models.roadmap import InterviewAnalysisRoadmap
from backend.schemas.intelligence import (
    MemorySummaryResponse,
    RepeatedWeaknessDetail,
    OneTimeMistakeDetail,
    ImprovingSkillDetail,
    DecliningSkillDetail,
    InsufficientEvidenceTopic,
    ProgressOverTimePoint,
    NextBestActionItem,
    SessionComparisonResponse,
    SupportingSessionInfo,
    SupportingQuestionInfo,
    ScoreTrajectoryItem,
    SkillPerformanceItem,
    WeaknessFrequencyItem,
    ScoreDistributionBin,
    ImprovementTrendItem,
    SessionComparisonRubricItem,
    GroupedSessionComparison,
    AnalyticsDashboardResponse
)

logger = logging.getLogger("uvicorn.error")


def _to_percentage(score: Any) -> float:
    """Safely converts score (which could be 0-10 or 0-100) to standard 0.0 - 100.0%."""
    if score is None:
        return 0.0
    try:
        val = float(score)
        if val <= 10.0 and val > 0.0:
            val = val * 10.0
        return max(0.0, min(100.0, round(val, 1)))
    except (ValueError, TypeError):
        return 0.0


def _safe_json_list(val: Any) -> List[str]:
    """Safely unpacks JSON string or returns list of strings."""
    if not val:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if x]
    if isinstance(val, str):
        try:
            loaded = json.loads(val)
            if isinstance(loaded, list):
                return [str(x).strip() for x in loaded if x]
            return [val.strip()]
        except Exception:
            return [val.strip()]
    return []


def _normalize_concept_key(text: str) -> str:
    """Normalizes concept text to a canonical key for comparison."""
    if not text:
        return ""
    cleaned = text.lower().strip()
    for char in [".", ",", ";", ":", "!", "?", "'", '"', "-", "_", "(", ")"]:
        cleaned = cleaned.replace(char, " ")
    return " ".join(cleaned.split())


def _canonical_skill_name(name: str) -> str:
    """Normalizes skill and topic names to clean canonical titles."""
    if not name:
        return "General Technical"
    n = name.strip()
    mapping = {
        "java": "Java",
        "python": "Python",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "react": "React",
        "sql": "SQL",
        "nosql": "NoSQL",
        "dsa": "Data Structures & Algorithms",
        "data structures": "Data Structures",
        "algorithms": "Algorithms",
        "system design": "System Design",
        "oop": "Object-Oriented Programming",
        "object oriented programming": "Object-Oriented Programming",
        "dbms": "DBMS",
        "operating systems": "Operating Systems",
        "networking": "Computer Networks"
    }
    lower = n.lower()
    if lower in mapping:
        return mapping[lower]
    return " ".join(w.capitalize() for w in n.split())


class InterviewMemoryService:
    """
    Production-quality engine managing candidate interview memory,
    repeated weakness detection, progressive skill verification,
    and session-to-session comparisons.
    """

    @classmethod
    def get_user_memory_summary(cls, db: Session, user: User) -> MemorySummaryResponse:
        """
        Synthesizes historical memory across all user interviews with strict data isolation.
        Distinguishes one-time mistakes from repeated weaknesses, identifies improving
        and declining skills, and surfaces the next best preparation action.
        """
        # Fetch candidate profile for target role
        profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
        target_role = profile.target_role if profile and profile.target_role else (user.target_role or "Software Developer")

        # 1. Fetch all completed interviews for this user (strictly isolated)
        interviews = db.query(Interview).filter(
            Interview.user_id == user.id,
            Interview.status == "completed"
        ).order_by(Interview.created_at.asc()).all()

        # If total_score is None, ensure score is calculated
        from backend.services.interview_service import InterviewService
        for i in interviews:
            if i.total_score is None or i.total_score == 0.0:
                calc_sc = InterviewService.calculate_interview_final_score(db, i.id)
                if calc_sc > 0:
                    i.total_score = calc_sc

        # 2. Collect all evaluations and answers
        evaluations = db.query(Evaluation).join(Interview).filter(
            Interview.user_id == user.id
        ).order_by(Evaluation.created_at.asc()).all()

        total_completed = len(interviews)
        total_answers = len(evaluations)
        scores = [float(i.total_score) for i in interviews if i.total_score is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        # Handle empty history
        if total_completed == 0:
            return MemorySummaryResponse(
                user_id=user.id,
                target_role=target_role,
                total_completed_interviews=0,
                total_answers_evaluated=0,
                overall_average_score=0.0,
                recurring_weaknesses=[],
                one_time_mistakes=[],
                improved_skills=[],
                declining_skills=[],
                insufficient_evidence_topics=[],
                persistent_mistakes_count=0,
                next_best_action=NextBestActionItem(
                    action_type="TAKE_INITIAL_MOCK",
                    title=f"Take Your First {target_role} Practice Session",
                    priority="CRITICAL",
                    reason="No historical interview records exist yet. Complete an initial mock session to establish your baseline memory.",
                    evidence_basis="Zero completed sessions recorded.",
                    target_topic=None,
                    deep_link="interview-config.html",
                    estimated_minutes=20
                ),
                progress_over_time=[],
                last_updated=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            )

        # 3. Analyze weaknesses and mistakes across sessions
        # Map: normalized_concept -> occurrence details
        concept_records: Dict[str, Dict[str, Any]] = {}
        # Skill-level tracking: skill_name -> list of { "date": datetime, "score": float, "session_id": str }
        skill_history: Dict[str, List[Dict[str, Any]]] = {}

        for ev in evaluations:
            q = ev.question
            ans = ev.answer
            interview = ev.interview
            if not q or not interview:
                continue

            q_score = _to_percentage(ev.overall_score)
            s_name = q.skill if q.skill else (q.category if q.category else interview.topic or "Technical Fundamentals")
            cat_name = q.category if q.category else (interview.topic or "Technical")

            # Track skill score chronologically
            skill_history.setdefault(s_name, []).append({
                "date": ev.created_at or interview.created_at,
                "score": q_score,
                "session_id": interview.id,
                "session_title": interview.title,
                "category": cat_name
            })

            # Check if this evaluation reveals mistakes or gaps
            is_low_score = (q_score < 70.0)
            missing = _safe_json_list(ev.missing_concepts)
            incorrect = _safe_json_list(ev.incorrect_claims)
            improvements = _safe_json_list(ev.improvements)

            # Combine explicit gap statements
            weakness_signals = []
            for m in missing:
                weakness_signals.append((m, "Missing Concept"))
            for inc in incorrect:
                weakness_signals.append((inc, "Misconception"))
            for imp in improvements:
                weakness_signals.append((imp, "Improvement"))

            # If score is low but no explicit strings were parsed, use the question's assessed objective or skill
            if is_low_score and not weakness_signals:
                label = f"Deficiency in {s_name} ({q.difficulty} difficulty)"
                weakness_signals.append((label, "Low Score Evaluation"))

            date_str = (ev.created_at or interview.created_at).strftime("%Y-%m-%d") if (ev.created_at or interview.created_at) else ""
            ans_excerpt = (ans.answer_text[:140] + "...") if ans and ans.answer_text else ""

            for signal_text, signal_type in weakness_signals:
                c_key = _normalize_concept_key(signal_text)
                if not c_key or len(c_key) < 4:
                    continue

                if c_key not in concept_records:
                    concept_records[c_key] = {
                        "concept": signal_text,
                        "category": cat_name,
                        "skill": s_name,
                        "session_ids": set(),
                        "sessions_info": [],
                        "questions_info": [],
                        "excerpts": [],
                        "dates": [],
                        "scores": [],
                        "latest_score": q_score,
                        "subsequent_strong_scores": []
                    }

                rec = concept_records[c_key]
                rec["scores"].append(q_score)
                rec["latest_score"] = q_score

                if interview.id not in rec["session_ids"]:
                    rec["session_ids"].add(interview.id)
                    rec["sessions_info"].append({
                        "interview_id": interview.id,
                        "title": interview.title,
                        "date": date_str,
                        "score": round(float(interview.total_score or q_score), 1),
                        "topic": interview.topic,
                        "difficulty": interview.difficulty
                    })

                rec["questions_info"].append({
                    "question_id": q.id,
                    "question_number": q.question_number,
                    "question_text": q.question_text,
                    "category": q.category,
                    "skill": q.skill,
                    "score": q_score
                })

                if ans_excerpt and ans_excerpt not in rec["excerpts"] and len(rec["excerpts"]) < 3:
                    rec["excerpts"].append(ans_excerpt)
                if date_str:
                    rec["dates"].append(date_str)

        # 4. Also check for subsequent positive evidence on the same skills to detect resolutions
        for c_key, rec in concept_records.items():
            skill_associated = rec["skill"]
            earliest_gap_date = min(rec["dates"]) if rec["dates"] else ""
            
            # Check if there are subsequent evaluations in this skill with score >= 75%
            all_skill_attempts = skill_history.get(skill_associated, [])
            for att in all_skill_attempts:
                att_date_str = att["date"].strftime("%Y-%m-%d") if att.get("date") else ""
                if att_date_str >= earliest_gap_date and att["score"] >= 75.0:
                    rec["subsequent_strong_scores"].append(att["score"])

        # 5. Distinguish Repeated Weaknesses vs One-Time Mistakes
        recurring_weaknesses: List[RepeatedWeaknessDetail] = []
        one_time_mistakes: List[OneTimeMistakeDetail] = []

        for c_key, rec in concept_records.items():
            session_count = len(rec["session_ids"])
            question_count = len(rec["questions_info"])
            avg_concept_score = round(sum(rec["scores"]) / len(rec["scores"]), 1) if rec["scores"] else 0.0

            # Determine status based on subsequent verified evidence
            has_subsequent_strong = len(rec["subsequent_strong_scores"]) > 0
            if has_subsequent_strong and max(rec["subsequent_strong_scores"]) >= 85.0:
                status = "resolved"
            elif has_subsequent_strong:
                status = "improving"
            else:
                status = "active_weakness"

            # Repeated weakness condition: observed in 2+ sessions, OR 2+ distinct questions
            if session_count >= 2 or question_count >= 2:
                dates_sorted = sorted(rec["dates"]) if rec["dates"] else ["Recent"]
                first_date = dates_sorted[0]
                latest_date = dates_sorted[-1]

                supporting_sess = [SupportingSessionInfo(**s) for s in rec["sessions_info"]]
                supporting_qs = [SupportingQuestionInfo(**q) for q in rec["questions_info"]]

                impact_desc = (
                    f"Observed {question_count} times across {session_count} interview session(s). "
                    f"Average evaluation score: {avg_concept_score}%."
                )
                remediation = f"Focus preparation on {rec['skill']} with hands-on practice before retesting."

                recurring_weaknesses.append(RepeatedWeaknessDetail(
                    concept=rec["concept"],
                    category=rec["category"],
                    recurrence_count=max(session_count, question_count),
                    first_observed_date=first_date,
                    latest_observed_date=latest_date,
                    status=status,
                    average_score=avg_concept_score,
                    latest_score=rec["latest_score"],
                    impact_description=impact_desc,
                    supporting_sessions=supporting_sess,
                    supporting_questions=supporting_qs,
                    supporting_excerpts=rec["excerpts"],
                    recommended_remediation=remediation
                ))
            else:
                # One-time mistake (isolated to 1 session / 1 question)
                s_info = rec["sessions_info"][0] if rec["sessions_info"] else {}
                q_info = rec["questions_info"][0] if rec["questions_info"] else {}
                one_time_mistakes.append(OneTimeMistakeDetail(
                    concept=rec["concept"],
                    category=rec["category"],
                    interview_id=s_info.get("interview_id", ""),
                    interview_title=s_info.get("title", "Technical Practice"),
                    question_text=q_info.get("question_text", "Interview question"),
                    observed_date=rec["dates"][0] if rec["dates"] else "Recent",
                    score=rec["scores"][0] if rec["scores"] else 0.0,
                    candidate_answer_excerpt=rec["excerpts"][0] if rec["excerpts"] else None,
                    is_repeated=False
                ))

        # Sort repeated weaknesses by recurrence count descending, then lowest score
        recurring_weaknesses.sort(key=lambda w: (w.recurrence_count, -w.average_score), reverse=True)

        # 6. Analyze Skill Trends: Improving, Declining, Insufficient Evidence
        improved_skills: List[ImprovingSkillDetail] = []
        declining_skills: List[DecliningSkillDetail] = []
        insufficient_evidence: List[InsufficientEvidenceTopic] = []

        for s_name, attempts in skill_history.items():
            cat = attempts[0].get("category", "General")
            count = len(attempts)
            all_scs = [a["score"] for a in attempts]
            latest_sc = all_scs[-1]

            if count < 2:
                insufficient_evidence.append(InsufficientEvidenceTopic(
                    topic=s_name,
                    category=cat,
                    attempts_count=count,
                    latest_score=latest_sc,
                    reason=f"Tested only {count} time. Additional evaluations needed for high statistical confidence."
                ))
            else:
                mid = count // 2
                baseline_sc = round(sum(all_scs[:mid]) / mid, 1)
                recent_avg = round(sum(all_scs[mid:]) / (count - mid), 1)
                delta = round(recent_avg - baseline_sc, 1)

                latest_dt_str = attempts[-1]["date"].strftime("%Y-%m-%d") if attempts[-1].get("date") else None

                if delta >= 5.0 or (latest_sc >= 80.0 and baseline_sc < 70.0):
                    status = "mastered" if latest_sc >= 85.0 else "improving"
                    evidence_summary = (
                        f"Score improved from {baseline_sc}% to {latest_sc}% (+{round(latest_sc - baseline_sc, 1)}%) "
                        f"across {count} evaluations."
                    )
                    improved_skills.append(ImprovingSkillDetail(
                        skill=s_name,
                        category=cat,
                        baseline_score=baseline_sc,
                        latest_score=latest_sc,
                        score_delta=round(latest_sc - baseline_sc, 1),
                        status=status,
                        evaluation_count=count,
                        evidence_summary=evidence_summary,
                        latest_verified_date=latest_dt_str
                    ))
                elif delta <= -5.0:
                    declining_skills.append(DecliningSkillDetail(
                        skill=s_name,
                        category=cat,
                        previous_average=baseline_sc,
                        recent_score=latest_sc,
                        score_drop=abs(delta),
                        evaluation_count=count,
                        latest_observed_date=latest_dt_str,
                        suggested_action=f"Review recent mistakes in {s_name} and schedule a focused drill."
                    ))

        improved_skills.sort(key=lambda s: s.score_delta, reverse=True)
        declining_skills.sort(key=lambda s: s.score_drop, reverse=True)

        # 7. Progress Over Time Chronological Points
        progress_points: List[ProgressOverTimePoint] = []
        prev_score: Optional[float] = None

        for idx, interview in enumerate(interviews):
            sc = round(float(interview.total_score or 0.0), 1)
            d_str = interview.created_at.strftime("%Y-%m-%d") if interview.created_at else "Recent"
            delta = round(sc - prev_score, 1) if prev_score is not None else None

            if delta is None:
                trend = "baseline"
            elif delta > 1.0:
                trend = "up"
            elif delta < -1.0:
                trend = "down"
            else:
                trend = "flat"

            progress_points.append(ProgressOverTimePoint(
                session_id=interview.id,
                session_title=interview.title,
                date=d_str,
                topic=interview.topic or "Technical",
                interview_type=interview.interview_type or "Technical",
                score=sc,
                score_change_from_previous=delta,
                trend_direction=trend
            ))
            prev_score = sc

        # 8. Synthesize Next Best Action with explicit reason
        active_weaknesses = [w for w in recurring_weaknesses if w.status == "active_weakness"]
        if active_weaknesses:
            top_w = active_weaknesses[0]
            next_action = NextBestActionItem(
                action_type="REMEDIATE_WEAKNESS",
                title=f"Remediate Repeated Weakness: {top_w.concept[:45]}",
                priority="CRITICAL",
                reason=f"This concept appeared as a gap across {top_w.recurrence_count} separate evaluations (average score: {top_w.average_score}%).",
                evidence_basis=f"Observed in {', '.join([s.title for s in top_w.supporting_sessions[:2]])}.",
                target_topic=top_w.category,
                deep_link="roadmap.html",
                estimated_minutes=25
            )
        elif declining_skills:
            top_dec = declining_skills[0]
            next_action = NextBestActionItem(
                action_type="PRACTICE_TOPIC",
                title=f"Reinforce Declining Skill: {top_dec.skill}",
                priority="HIGH",
                reason=f"Performance dropped by {top_dec.score_drop}% compared to earlier sessions (now at {top_dec.recent_score}%).",
                evidence_basis=f"Score dropped from {top_dec.previous_average}% in recent evaluations.",
                target_topic=top_dec.skill,
                deep_link="interview-config.html",
                estimated_minutes=20
            )
        elif insufficient_evidence:
            top_ins = insufficient_evidence[0]
            next_action = NextBestActionItem(
                action_type="PRACTICE_TOPIC",
                title=f"Calibrate Telemetry for: {top_ins.topic}",
                priority="MEDIUM",
                reason=f"{top_ins.topic} has only been tested {top_ins.attempts_count} time. Additional sessions establish high-confidence mastery.",
                evidence_basis=f"Single attempt score: {top_ins.latest_score}%.",
                target_topic=top_ins.topic,
                deep_link="interview-config.html",
                estimated_minutes=20
            )
        else:
            next_action = NextBestActionItem(
                action_type="MOCK_INTERVIEW",
                title=f"Advance to Senior {target_role} Simulation",
                priority="MEDIUM",
                reason="All tracked skills are showing consistent or improving performance with zero active recurring weaknesses.",
                evidence_basis=f"Average interview score: {avg_score}%.",
                target_topic=None,
                deep_link="adaptive-interview.html",
                estimated_minutes=30
            )

        return MemorySummaryResponse(
            user_id=user.id,
            target_role=target_role,
            total_completed_interviews=total_completed,
            total_answers_evaluated=total_answers,
            overall_average_score=avg_score,
            recurring_weaknesses=recurring_weaknesses,
            one_time_mistakes=one_time_mistakes,
            improved_skills=improved_skills,
            declining_skills=declining_skills,
            insufficient_evidence_topics=insufficient_evidence,
            persistent_mistakes_count=len(active_weaknesses),
            next_best_action=next_action,
            progress_over_time=progress_points,
            last_updated=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        )

    @classmethod
    def compare_session_to_previous(
        cls,
        db: Session,
        user_id: str,
        interview_id: str
    ) -> SessionComparisonResponse:
        """
        Performs a like-for-like comparison between a specific completed interview
        and the candidate's previous relevant session.
        """
        current_interview = db.query(Interview).filter(
            Interview.id == interview_id,
            Interview.user_id == user_id
        ).first()

        if not current_interview:
            raise ValueError(f"Interview {interview_id} not found for this candidate.")

        # Ensure current score is computed
        current_score = None
        if current_interview.total_score is not None:
            current_score = round(float(current_interview.total_score), 1)

        current_date_str = current_interview.created_at.strftime("%b %d, %Y") if current_interview.created_at else "Recent"
        current_topic = current_interview.topic or "Technical"

        # Search for previous completed interview
        # 1. Match same topic
        prev_interview = db.query(Interview).filter(
            Interview.user_id == user_id,
            Interview.id != interview_id,
            Interview.status == "completed",
            Interview.topic == current_interview.topic,
            Interview.created_at < current_interview.created_at
        ).order_by(Interview.created_at.desc()).first()

        # 2. Fallback to same target_role or any prior completed interview
        if not prev_interview:
            prev_interview = db.query(Interview).filter(
                Interview.user_id == user_id,
                Interview.id != interview_id,
                Interview.status == "completed",
                Interview.created_at < current_interview.created_at
            ).order_by(Interview.created_at.desc()).first()

        # Current evaluations
        current_evals = db.query(Evaluation).filter(Evaluation.interview_id == interview_id).all()
        current_strengths: List[Dict[str, Any]] = []
        current_weaknesses: List[str] = []
        current_skills_scores: Dict[str, List[float]] = {}

        for ev in current_evals:
            q = ev.question
            sc = _to_percentage(ev.overall_score)
            s_name = q.skill if q and q.skill else (q.category if q and q.category else current_topic)
            current_skills_scores.setdefault(s_name, []).append(sc)

            if ev.strengths:
                for s in _safe_json_list(ev.strengths):
                    current_strengths.append({"strength": s, "skill": s_name, "score": sc})
            if ev.improvements:
                current_weaknesses.extend(_safe_json_list(ev.improvements))
            if ev.missing_concepts:
                current_weaknesses.extend(_safe_json_list(ev.missing_concepts))
            if ev.incorrect_claims:
                current_weaknesses.extend(_safe_json_list(ev.incorrect_claims))

        # Handle baseline (first session)
        if not prev_interview:
            skills_needing_practice = [
                {"skill": s, "score": round(sum(scs) / len(scs), 1), "reason": "Scored under 70% in baseline session."}
                for s, scs in current_skills_scores.items()
                if (sum(scs) / len(scs)) < 70.0
            ]
            return SessionComparisonResponse(
                current_interview_id=current_interview.id,
                current_title=current_interview.title,
                current_score=current_score,
                current_date=current_date_str,
                current_topic=current_topic,
                previous_interview_id=None,
                previous_title=None,
                previous_score=None,
                previous_date=None,
                previous_topic=None,
                score_change=None,
                improvement_trend="baseline",
                trend_explanation=f"This is your baseline mock session for {current_topic}. Future interviews will be benchmarked against this result.",
                is_baseline_session=True,
                repeated_mistakes=[],
                newly_resolved_weaknesses=[],
                skills_needing_practice=skills_needing_practice,
                evidence_based_strengths=current_strengths[:4],
                next_recommended_actions=[
                    f"Review detailed question feedback and model answers for {current_topic}.",
                    "Take a second practice session on this topic to test concept retention and begin tracking progression."
                ]
            )

        # Previous interview data
        prev_score = round(float(prev_interview.total_score or 0.0), 1)
        prev_date_str = prev_interview.created_at.strftime("%b %d, %Y") if prev_interview.created_at else "Earlier"
        score_change = round((current_score or 0.0) - prev_score, 1)

        if score_change >= 5.0:
            trend = "improving"
            trend_expl = f"Strong upward progress! Your score increased by +{score_change}% compared to your session on {prev_date_str}."
        elif score_change <= -5.0:
            trend = "declining"
            trend_expl = f"Score dropped by {abs(score_change)}% compared to your session on {prev_date_str} ({prev_score}%)."
        else:
            trend = "consistent"
            trend_expl = f"Consistent performance ({score_change:+}%) compared to your session on {prev_date_str}."

        prev_evals = db.query(Evaluation).filter(Evaluation.interview_id == prev_interview.id).all()
        prev_weaknesses: List[str] = []
        prev_skills_scores: Dict[str, List[float]] = {}

        for ev in prev_evals:
            q = ev.question
            sc = _to_percentage(ev.overall_score)
            s_name = q.skill if q and q.skill else (q.category if q and q.category else prev_interview.topic or "Technical")
            prev_skills_scores.setdefault(s_name, []).append(sc)

            if ev.improvements:
                prev_weaknesses.extend(_safe_json_list(ev.improvements))
            if ev.missing_concepts:
                prev_weaknesses.extend(_safe_json_list(ev.missing_concepts))
            if ev.incorrect_claims:
                prev_weaknesses.extend(_safe_json_list(ev.incorrect_claims))

        # Detect Repeated Mistakes (present in previous session AND present in current session)
        repeated_mistakes: List[Dict[str, Any]] = []
        for pw in prev_weaknesses:
            pw_key = _normalize_concept_key(pw)
            for cw in current_weaknesses:
                cw_key = _normalize_concept_key(cw)
                if pw_key and cw_key and (pw_key in cw_key or cw_key in pw_key):
                    if not any(r["mistake"] == cw for r in repeated_mistakes):
                        repeated_mistakes.append({
                            "mistake": cw,
                            "previous_session_id": prev_interview.id,
                            "previous_session_title": prev_interview.title,
                            "status": "persistent_mistake",
                            "severity": "CRITICAL"
                        })

        # Detect Newly Resolved Weaknesses (weak in previous session, but current session scored >= 75%)
        newly_resolved: List[Dict[str, Any]] = []
        for s_name, prev_scs in prev_skills_scores.items():
            prev_avg = sum(prev_scs) / len(prev_scs)
            if prev_avg < 70.0 and s_name in current_skills_scores:
                curr_scs = current_skills_scores[s_name]
                curr_avg = sum(curr_scs) / len(curr_scs)
                if curr_avg >= 75.0:
                    newly_resolved.append({
                        "concept_or_skill": s_name,
                        "previous_score": round(prev_avg, 1),
                        "current_score": round(curr_avg, 1),
                        "improvement_delta": round(curr_avg - prev_avg, 1),
                        "status": "resolved"
                    })

        # Skills needing practice in current session
        skills_needing_practice = [
            {"skill": s, "score": round(sum(scs) / len(scs), 1), "reason": "Scored under 70% in this session."}
            for s, scs in current_skills_scores.items()
            if (sum(scs) / len(scs)) < 70.0
        ]

        # Recommendations based on comparison
        next_actions = []
        if repeated_mistakes:
            next_actions.append(f"Prioritize remediating: '{repeated_mistakes[0]['mistake'][:50]}' which repeated from your previous interview.")
        if newly_resolved:
            next_actions.append(f"Great work resolving '{newly_resolved[0]['concept_or_skill']}' (+{newly_resolved[0]['improvement_delta']}% improvement verified).")
        if skills_needing_practice:
            next_actions.append(f"Review core principles of '{skills_needing_practice[0]['skill']}' before your next mock.")
        else:
            next_actions.append("Keep practicing advanced difficulty questions to cement your interview readiness.")

        return SessionComparisonResponse(
            current_interview_id=current_interview.id,
            current_title=current_interview.title,
            current_score=current_score,
            current_date=current_date_str,
            current_topic=current_topic,
            previous_interview_id=prev_interview.id,
            previous_title=prev_interview.title,
            previous_score=prev_score,
            previous_date=prev_date_str,
            previous_topic=prev_interview.topic or "Technical",
            score_change=score_change,
            improvement_trend=trend,
            trend_explanation=trend_expl,
            is_baseline_session=False,
            repeated_mistakes=repeated_mistakes[:5],
            newly_resolved_weaknesses=newly_resolved[:5],
            skills_needing_practice=skills_needing_practice[:5],
            evidence_based_strengths=current_strengths[:4],
            next_recommended_actions=next_actions
        )

    @classmethod
    def sync_roadmap_with_memory(
        cls,
        db: Session,
        user_id: str,
        roadmap: InterviewAnalysisRoadmap
    ) -> None:
        """
        Incorporates historical repeated weaknesses into the roadmap tasks and marks
        resolved concepts so tasks reflect the candidate's actual evolving mastery.
        """
        if not roadmap or not roadmap.roadmap_tasks:
            return

        try:
            tasks = json.loads(roadmap.roadmap_tasks)
        except Exception:
            return

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return

        summary = cls.get_user_memory_summary(db, user)
        existing_task_topics = {_normalize_concept_key(t.get("topic", "")) for t in tasks}

        # 1. Inject recurring weaknesses as Phase 1 / Phase 2 tasks if not already present
        added_new = False
        active_weaknesses = [w for w in summary.recurring_weaknesses if w.status == "active_weakness"]

        for w in active_weaknesses[:3]:
            w_key = _normalize_concept_key(w.concept)
            if not any(w_key in t_key or t_key in w_key for t_key in existing_task_topics if t_key):
                new_task = {
                    "task_id": f"memory-task-{len(tasks) + 1}",
                    "phase_number": 1,
                    "day_or_sequence": len(tasks) + 1,
                    "priority": "CRITICAL",
                    "topic": f"Remediate: {w.concept[:60]}",
                    "subtopics": [w.category],
                    "learning_objectives": [f"Deep dive into {w.category} to eliminate recurring gap."],
                    "practical_exercise": f"Write and verify code targeting {w.concept[:40]}.",
                    "relevant_problems_or_questions": [q.question_text for q in w.supporting_questions[:2]],
                    "estimated_duration_hours": 2.0,
                    "expected_outcomes": f"Zero recurrence of misconception in future {w.category} interviews.",
                    "completion_criteria": "Pass diagnostic self-test with clean explanation.",
                    "status": "pending",
                    "completed_at": None
                }
                tasks.append(new_task)
                existing_task_topics.add(w_key)
                added_new = True

        # 2. Check if any previously pending tasks are now verified resolved
        resolved_concepts = {_normalize_concept_key(s.skill) for s in summary.improved_skills if s.status in ("improving", "mastered")}
        for t in tasks:
            t_key = _normalize_concept_key(t.get("topic", ""))
            if any(r_key in t_key for r_key in resolved_concepts if r_key) and t.get("status") == "pending":
                # Mark as resolved with timestamp
                t["status"] = "completed"
                t["completed_at"] = datetime.utcnow().isoformat()
                added_new = True

        if added_new:
            roadmap.roadmap_tasks = json.dumps(tasks)
            db.commit()
            db.refresh(roadmap)

    @classmethod
    def get_analytics_dashboard(
        cls,
        db: Session,
        user: User,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        session_a_id: Optional[str] = None,
        session_b_id: Optional[str] = None
    ) -> AnalyticsDashboardResponse:
        """
        Synthesizes deep, interactive analytics across user interviews:
        - Chronological Score Trajectory
        - Skill-wise Performance (Baseline vs Latest)
        - Weakness Frequency (Ranked by distinct session occurrences)
        - Score Distribution Bins (preserves genuine 0.0 scores)
        - Improvement Trend & Velocity
        - Grouped Rubric & Skill Session Comparison
        """
        profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
        target_role = profile.target_role if profile and profile.target_role else (user.target_role or "Software Developer")

        # Fetch all user interviews (strictly isolated)
        all_interviews = db.query(Interview).filter(
            Interview.user_id == user.id
        ).order_by(Interview.created_at.asc()).all()

        total_recorded = len(all_interviews)

        # Ensure scores are computed if missing
        from backend.services.interview_service import InterviewService
        for i in all_interviews:
            if i.status == "completed" and (i.total_score is None or i.total_score == 0.0):
                calc_sc = InterviewService.calculate_interview_final_score(db, i.id)
                if calc_sc > 0:
                    i.total_score = calc_sc

        # Date range filtering
        dt_from = None
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                try:
                    dt_from = datetime.strptime(date_from[:10], "%Y-%m-%d")
                except Exception:
                    dt_from = None

        dt_to = None
        if date_to:
            try:
                dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                try:
                    dt_to = datetime.strptime(date_to[:10], "%Y-%m-%d") + timedelta(days=1)
                except Exception:
                    dt_to = None

        # Filter for valid completed interviews with evaluations
        valid_interviews = []
        excluded_count = 0

        for i in all_interviews:
            if dt_from and i.created_at < dt_from:
                continue
            if dt_to and i.created_at > dt_to:
                continue

            # Exclude incomplete or un-evaluated interviews
            if i.status != "completed":
                excluded_count += 1
                continue

            eval_count = db.query(Evaluation).filter(Evaluation.interview_id == i.id).count()
            if eval_count == 0:
                excluded_count += 1
                continue

            # Preserves genuine 0.0, excludes only if total_score is None
            if i.total_score is None:
                calc_sc = InterviewService.calculate_interview_final_score(db, i.id)
                if calc_sc is not None:
                    i.total_score = calc_sc
                else:
                    excluded_count += 1
                    continue

            valid_interviews.append(i)

        # Available sessions list for dropdowns (reverse chronological)
        available_sessions = [
            {
                "id": i.id,
                "title": i.title,
                "date": i.created_at.strftime("%b %d, %Y") if i.created_at else "Recent",
                "score": round(float(i.total_score), 1),
                "topic": i.topic or "Technical",
                "difficulty": i.difficulty or "Medium"
            }
            for i in reversed(valid_interviews)
        ]

        if not valid_interviews:
            reason = f"{excluded_count} session(s) were excluded because they are incomplete or missing evaluations." if excluded_count > 0 else "No interview sessions found in the selected date range."
            return AnalyticsDashboardResponse(
                user_id=user.id,
                target_role=target_role,
                total_sessions_recorded=total_recorded,
                valid_evaluated_sessions=0,
                excluded_incomplete_sessions=excluded_count,
                exclusion_reason=reason,
                overall_average_score=0.0,
                highest_score=None,
                lowest_score=None,
                score_trajectory=[],
                skill_performance=[],
                weakness_frequency=[],
                score_distribution=[],
                improvement_trend=[],
                session_comparison=None,
                filter_date_from=date_from,
                filter_date_to=date_to,
                available_sessions=[]
            )

        valid_scores = [round(float(i.total_score), 1) for i in valid_interviews]
        overall_avg = round(sum(valid_scores) / len(valid_scores), 1)
        highest_score = max(valid_scores)
        lowest_score = min(valid_scores)

        # 1. Score Trajectory (Strictly chronological)
        trajectory_items: List[ScoreTrajectoryItem] = []
        prev_sc: Optional[float] = None
        for i in valid_interviews:
            sc = round(float(i.total_score), 1)
            delta = round(sc - prev_sc, 1) if prev_sc is not None else None
            trend = "baseline" if delta is None else ("up" if delta > 1.0 else ("down" if delta < -1.0 else "flat"))
            q_count = db.query(InterviewQuestion).filter(InterviewQuestion.interview_id == i.id).count()
            ev_count = db.query(Evaluation).filter(Evaluation.interview_id == i.id).count()

            trajectory_items.append(ScoreTrajectoryItem(
                session_id=i.id,
                session_title=i.title,
                target_role=i.target_role or target_role,
                topic=i.topic or "Technical",
                difficulty=i.difficulty or "Medium",
                date=i.created_at.strftime("%b %d, %Y") if i.created_at else "Recent",
                timestamp=i.created_at.isoformat() if i.created_at else "",
                score=sc,
                score_change=delta,
                trend_direction=trend,
                total_questions=q_count,
                evaluations_count=ev_count
            ))
            prev_sc = sc

        # 2. Evaluations gathering for skills and weaknesses
        valid_ids = [i.id for i in valid_interviews]
        evaluations = db.query(Evaluation).filter(
            Evaluation.interview_id.in_(valid_ids)
        ).order_by(Evaluation.created_at.asc()).all()

        skill_records: Dict[str, Dict[str, Any]] = {}
        concept_records: Dict[str, Dict[str, Any]] = {}

        for ev in evaluations:
            q = ev.question
            ans = ev.answer
            i = ev.interview
            if not q or not i:
                continue

            q_score = _to_percentage(ev.overall_score)
            s_name = _canonical_skill_name(q.skill if q.skill else (q.category if q.category else i.topic or "Technical"))
            cat_name = _canonical_skill_name(q.category if q.category else (i.topic or "Technical"))

            # Track skill
            if s_name not in skill_records:
                skill_records[s_name] = {
                    "category": cat_name,
                    "attempts": [],
                    "sessions": set()
                }
            skill_records[s_name]["attempts"].append(q_score)
            skill_records[s_name]["sessions"].add(i.id)

            # Track gaps & weaknesses without double-counting per session
            missing = _safe_json_list(ev.missing_concepts)
            incorrect = _safe_json_list(ev.incorrect_claims)
            improvements = _safe_json_list(ev.improvements)

            signals = set()
            for m in missing:
                if m: signals.add(m)
            for inc in incorrect:
                if inc: signals.add(inc)
            for imp in improvements:
                if imp: signals.add(imp)

            if q_score < 70.0 and not signals:
                signals.add(f"Deficiency in {s_name}")

            ans_excerpt = (ans.answer_text[:120] + "...") if ans and ans.answer_text else None
            date_str = (ev.created_at or i.created_at).strftime("%b %d, %Y") if (ev.created_at or i.created_at) else ""

            for sig in signals:
                c_key = _normalize_concept_key(sig)
                if not c_key or len(c_key) < 3:
                    continue

                if c_key not in concept_records:
                    concept_records[c_key] = {
                        "concept": sig,
                        "category": cat_name,
                        "session_ids": set(),
                        "sessions_info": [],
                        "question_count": 0,
                        "scores": [],
                        "sample_evidence": ans_excerpt
                    }

                rec = concept_records[c_key]
                rec["scores"].append(q_score)
                rec["question_count"] += 1
                if ans_excerpt and not rec["sample_evidence"]:
                    rec["sample_evidence"] = ans_excerpt

                if i.id not in rec["session_ids"]:
                    rec["session_ids"].add(i.id)
                    rec["sessions_info"].append(SupportingSessionInfo(
                        interview_id=i.id,
                        title=i.title,
                        date=date_str,
                        score=round(float(i.total_score or q_score), 1),
                        topic=i.topic,
                        difficulty=i.difficulty
                    ))

        # 3. Skill-wise Performance (Baseline vs Latest)
        skill_perf_items: List[SkillPerformanceItem] = []
        for s_name, data in skill_records.items():
            att = data["attempts"]
            count = len(att)
            sess_count = len(data["sessions"])

            if count < 2:
                skill_perf_items.append(SkillPerformanceItem(
                    skill=s_name,
                    category=data["category"],
                    baseline_score=round(att[0], 1),
                    latest_score=round(att[0], 1),
                    score_delta=0.0,
                    evaluation_count=count,
                    session_count=sess_count,
                    status="insufficient_evidence",
                    has_sufficient_evidence=False
                ))
            else:
                mid = count // 2
                baseline = round(sum(att[:mid]) / mid, 1)
                latest = round(sum(att[mid:]) / (count - mid), 1)
                delta = round(latest - baseline, 1)

                if delta >= 5.0:
                    status = "mastered" if latest >= 85.0 else "improving"
                elif delta <= -5.0:
                    status = "declining"
                else:
                    status = "stable"

                skill_perf_items.append(SkillPerformanceItem(
                    skill=s_name,
                    category=data["category"],
                    baseline_score=baseline,
                    latest_score=latest,
                    score_delta=delta,
                    evaluation_count=count,
                    session_count=sess_count,
                    status=status,
                    has_sufficient_evidence=True
                ))

        # Sort skills by evaluation count descending
        skill_perf_items.sort(key=lambda s: (s.has_sufficient_evidence, s.evaluation_count, s.latest_score), reverse=True)

        # 4. Weakness Frequency (Ranked by distinct session occurrences)
        weakness_items: List[WeaknessFrequencyItem] = []
        for c_key, rec in concept_records.items():
            distinct_sessions = len(rec["session_ids"])
            avg_sc = round(sum(rec["scores"]) / len(rec["scores"]), 1) if rec["scores"] else 0.0
            latest_sc = round(rec["scores"][-1], 1) if rec["scores"] else 0.0

            if latest_sc >= 80.0:
                status = "resolved"
            elif latest_sc >= 70.0:
                status = "improving"
            else:
                status = "active_weakness"

            weakness_items.append(WeaknessFrequencyItem(
                concept=rec["concept"],
                category=rec["category"],
                session_occurrences=distinct_sessions,
                total_question_occurrences=rec["question_count"],
                average_score=avg_sc,
                latest_score=latest_sc,
                status=status,
                supporting_sessions=rec["sessions_info"],
                sample_evidence=rec["sample_evidence"]
            ))

        # Rank weaknesses by session occurrences descending, then lowest score
        weakness_items.sort(key=lambda w: (w.session_occurrences, -w.average_score), reverse=True)

        # 5. Score Distribution Bins
        total_valid = len(valid_interviews)
        bins_def = [
            ("Below 50%", 0.0, 49.99),
            ("50% - 69%", 50.0, 69.99),
            ("70% - 84%", 70.0, 84.99),
            ("85% - 100%", 85.0, 100.0)
        ]
        score_dist: List[ScoreDistributionBin] = []
        for label, min_s, max_s in bins_def:
            matched_ids = [i.id for i in valid_interviews if min_s <= float(i.total_score) <= max_s]
            cnt = len(matched_ids)
            pct = round((cnt / total_valid) * 100, 1) if total_valid > 0 else 0.0
            score_dist.append(ScoreDistributionBin(
                bin_label=label,
                min_score=min_s,
                max_score=max_s,
                count=cnt,
                percentage=pct,
                session_ids=matched_ids
            ))

        # 6. Improvement Trend & Cumulative Velocity
        improvement_items: List[ImprovementTrendItem] = []
        running_sum = 0.0
        first_sc = valid_scores[0]
        for idx, i in enumerate(valid_interviews):
            sc = valid_scores[idx]
            running_sum += sc
            cum_avg = round(running_sum / (idx + 1), 1)
            verified_gain = round(sc - first_sc, 1) if idx > 0 else None
            ev_status = "baseline" if idx == 0 else ("insufficient_evidence" if idx < 2 else "sufficient")

            improvement_items.append(ImprovementTrendItem(
                date=i.created_at.strftime("%b %d, %Y") if i.created_at else "Recent",
                session_id=i.id,
                session_title=i.title,
                score=sc,
                cumulative_avg=cum_avg,
                verified_gain_delta=verified_gain,
                evidence_status=ev_status
            ))

        # 7. Grouped Session Comparison
        grouped_comp = None
        target_a_id = session_a_id or (valid_interviews[-1].id if valid_interviews else None)
        target_b_id = session_b_id or (valid_interviews[-2].id if len(valid_interviews) >= 2 else None)

        if target_a_id:
            sess_a = next((i for i in valid_interviews if str(i.id) == str(target_a_id)), valid_interviews[-1])
            sess_b = next((i for i in valid_interviews if str(i.id) == str(target_b_id)), None) if target_b_id and target_b_id != target_a_id else None

            # Evaluations for session A and B
            evals_a = db.query(Evaluation).filter(Evaluation.interview_id == sess_a.id).all()
            evals_b = db.query(Evaluation).filter(Evaluation.interview_id == sess_b.id).all() if sess_b else []

            # Rubric comparison
            rubric_dims = [
                ("Technical Correctness", "technical_correctness", 35),
                ("Conceptual Completeness", "conceptual_completeness", 25),
                ("Response Relevance", "response_relevance", 15),
                ("Structural Clarity", "structural_clarity", 15),
                ("Depth of Understanding", "depth_of_understanding", 10),
            ]
            rubric_items: List[SessionComparisonRubricItem] = []

            for label, field_name, wt in rubric_dims:
                sc_a_vals = [_to_percentage(getattr(e, field_name, 0.0)) for e in evals_a]
                avg_a = round(sum(sc_a_vals) / len(sc_a_vals), 1) if sc_a_vals else None

                avg_b = None
                delta = None
                if evals_b:
                    sc_b_vals = [_to_percentage(getattr(e, field_name, 0.0)) for e in evals_b]
                    avg_b = round(sum(sc_b_vals) / len(sc_b_vals), 1) if sc_b_vals else None
                    if avg_a is not None and avg_b is not None:
                        delta = round(avg_a - avg_b, 1)

                rubric_items.append(SessionComparisonRubricItem(
                    dimension=label,
                    weight_pct=wt,
                    session_a_score=avg_a,
                    session_b_score=avg_b,
                    score_delta=delta
                ))

            # Shared skill comparison
            skills_a: Dict[str, List[float]] = {}
            for e in evals_a:
                q = e.question
                sn = _canonical_skill_name(q.skill if q and q.skill else (q.category if q and q.category else sess_a.topic or "Technical"))
                skills_a.setdefault(sn, []).append(_to_percentage(e.overall_score))

            skills_b: Dict[str, List[float]] = {}
            for e in evals_b:
                q = e.question
                sn = _canonical_skill_name(q.skill if q and q.skill else (q.category if q and q.category else sess_b.topic or "Technical"))
                skills_b.setdefault(sn, []).append(_to_percentage(e.overall_score))

            all_skill_keys = sorted(set(skills_a.keys()) | set(skills_b.keys()))
            skill_comp_list = []
            for sk in all_skill_keys:
                a_sc = round(sum(skills_a[sk]) / len(skills_a[sk]), 1) if sk in skills_a else None
                b_sc = round(sum(skills_b[sk]) / len(skills_b[sk]), 1) if sk in skills_b else None
                sk_delta = round(a_sc - b_sc, 1) if a_sc is not None and b_sc is not None else None
                skill_comp_list.append({
                    "skill": sk,
                    "session_a_score": a_sc,
                    "session_b_score": b_sc,
                    "score_delta": sk_delta
                })

            # Check repeated mistakes and resolved weaknesses between A and B
            repeated_m = []
            resolved_w = []
            if sess_b:
                comp_res = cls.compare_session_to_previous(db, user.id, sess_a.id)
                repeated_m = comp_res.repeated_mistakes
                resolved_w = comp_res.newly_resolved_weaknesses

            ov_delta = round(float(sess_a.total_score) - float(sess_b.total_score), 1) if sess_b and sess_a.total_score is not None and sess_b.total_score is not None else None

            grouped_comp = GroupedSessionComparison(
                session_a_id=sess_a.id,
                session_a_title=sess_a.title,
                session_a_date=sess_a.created_at.strftime("%b %d, %Y") if sess_a.created_at else "Recent",
                session_a_score=round(float(sess_a.total_score), 1) if sess_a.total_score is not None else None,
                session_b_id=sess_b.id if sess_b else None,
                session_b_title=sess_b.title if sess_b else None,
                session_b_date=sess_b.created_at.strftime("%b %d, %Y") if sess_b and sess_b.created_at else None,
                session_b_score=round(float(sess_b.total_score), 1) if sess_b and sess_b.total_score is not None else None,
                overall_delta=ov_delta,
                rubric_comparison=rubric_items,
                skill_comparison=skill_comp_list,
                repeated_mistakes=repeated_m,
                newly_resolved_weaknesses=resolved_w
            )

        exclusion_msg = f"{excluded_count} session(s) were excluded because they are in progress or missing completed evaluations." if excluded_count > 0 else None

        return AnalyticsDashboardResponse(
            user_id=user.id,
            target_role=target_role,
            total_sessions_recorded=total_recorded,
            valid_evaluated_sessions=len(valid_interviews),
            excluded_incomplete_sessions=excluded_count,
            exclusion_reason=exclusion_msg,
            overall_average_score=overall_avg,
            highest_score=highest_score,
            lowest_score=lowest_score,
            score_trajectory=trajectory_items,
            skill_performance=skill_perf_items,
            weakness_frequency=weakness_items,
            score_distribution=score_dist,
            improvement_trend=improvement_items,
            session_comparison=grouped_comp,
            filter_date_from=date_from,
            filter_date_to=date_to,
            available_sessions=available_sessions
        )
