import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.models import User, CandidateProfile, Interview, Evaluation, InterviewQuestion, CodingInterview, CodingSubmission

class DashboardService:
    @staticmethod
    def get_dashboard_summary(db: Session, user: User) -> Dict[str, Any]:
        profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
        
        # User standard interviews
        all_interviews = db.query(Interview).filter(Interview.user_id == user.id).all()
        valid_interviews = [i for i in all_interviews if len(i.questions) > 0]
        completed_interviews = [i for i in valid_interviews if i.status == "completed" and i.total_score is not None]

        # User coding interviews
        all_coding = db.query(CodingInterview).filter(CodingInterview.user_id == user.id).all()
        completed_coding = [c for c in all_coding if c.status == "completed" and c.total_score is not None]

        interviews_count = len(completed_interviews) + len(completed_coding)
        
        all_scores = [i.total_score for i in completed_interviews] + [c.total_score for c in completed_coding]
        if all_scores:
            avg_score = round(sum(all_scores) / len(all_scores), 1)
        else:
            avg_score = 0.0

        coding_avg = round(sum(c.total_score for c in completed_coding) / len(completed_coding), 1) if completed_coding else 0.0

        # Synchronize with canonical ReadinessService
        from backend.services.readiness_service import ReadinessService
        readiness_snap = ReadinessService.get_latest_readiness(db, user)
        readiness_score = readiness_snap.overall_readiness_score

        # Skill breakdown based on evaluations & coding submissions
        evaluations = db.query(Evaluation).join(Interview).filter(Interview.user_id == user.id).all()
        coding_subs = db.query(CodingSubmission).filter(CodingSubmission.user_id == user.id).all()
        
        skills_map: Dict[str, List[float]] = {}
        for ev in evaluations:
            q = db.query(InterviewQuestion).filter(InterviewQuestion.id == ev.question_id).first()
            skill_name = (q.skill if q and q.skill else "General")
            if skill_name not in skills_map:
                skills_map[skill_name] = []
            skills_map[skill_name].append(ev.overall_score)

        for cs in coding_subs:
            skill_name = "Algorithms & Data Structures"
            if skill_name not in skills_map:
                skills_map[skill_name] = []
            skills_map[skill_name].append(cs.coding_score)

        if not skills_map and profile and profile.skills:
            for s in profile.skills.split(","):
                s_clean = s.strip()
                if s_clean:
                    skills_map[s_clean] = []

        skill_progress = []
        for skill_name, scores in skills_map.items():
            if scores:
                sc_avg = round(sum(scores) / len(scores), 1)
            else:
                sc_avg = 0.0
            skill_progress.append({
                "name": skill_name,
                "score": sc_avg
            })

        # Combined Recent activities (standard + coding)
        recent_interviews = sorted(valid_interviews, key=lambda x: x.created_at, reverse=True)[:5]
        recent_coding = sorted(all_coding, key=lambda x: x.created_at, reverse=True)[:5]

        combined = []
        for i in recent_interviews:
            combined.append({
                "id": i.id,
                "name": i.title,
                "date": i.created_at.strftime("%b %d, %Y") if i.created_at else "Recent",
                "type": i.interview_type,
                "topic": i.topic,
                "difficulty": i.difficulty,
                "score": f"{round(i.total_score, 1)}%" if i.total_score is not None and i.status == "completed" else "In Progress",
                "status": i.status,
                "is_coding": False,
                "created_at_dt": i.created_at
            })

        for c in recent_coding:
            combined.append({
                "id": c.id,
                "name": c.title,
                "date": c.created_at.strftime("%b %d, %Y") if c.created_at else "Recent",
                "type": "Coding",
                "topic": c.topic,
                "difficulty": c.difficulty,
                "score": f"{round(c.total_score, 1)}%" if c.total_score is not None and c.status == "completed" else "In Progress",
                "status": c.status,
                "is_coding": True,
                "created_at_dt": c.created_at
            })

        combined_sorted = sorted(combined, key=lambda x: x["created_at_dt"], reverse=True)[:5]
        for item in combined_sorted:
            del item["created_at_dt"]

        # Attach Interview Memory & Progress Intelligence
        memory_data = None
        try:
            from backend.services.interview_memory_service import InterviewMemoryService
            mem_summary = InterviewMemoryService.get_user_memory_summary(db, user)
            memory_data = mem_summary.model_dump()
        except Exception:
            memory_data = None

        return {
            "user": {
                "id": user.id,
                "name": profile.full_name if profile else user.name,
                "email": user.email,
                "target_role": profile.target_role if profile else "Software Developer",
                "experience_level": profile.experience_level if profile else "Intermediate"
            },
            "stats": {
                "interviews_practiced": interviews_count,
                "average_score": f"{avg_score}%",
                "coding_score": f"{coding_avg}%",
                "readiness_score": f"{readiness_score}%",
                "skills_in_progress": len(skill_progress)
            },
            "recent_activity": combined_sorted,
            "skill_progress": skill_progress,
            "memory_intelligence": memory_data
        }

    @staticmethod
    def get_performance_analytics(db: Session, user: User) -> Dict[str, Any]:
        all_interviews = db.query(Interview).filter(Interview.user_id == user.id).all()
        valid_interviews = [i for i in all_interviews if len(i.questions) > 0]
        completed = [i for i in valid_interviews if i.status == "completed" and i.total_score is not None]

        all_coding = db.query(CodingInterview).filter(CodingInterview.user_id == user.id).all()
        completed_coding = [c for c in all_coding if c.status == "completed" and c.total_score is not None]
        
        total_interviews = len(completed) + len(completed_coding)
        all_scores = [i.total_score for i in completed] + [c.total_score for c in completed_coding]
        best_score = max(all_scores, default=0.0)
        avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0
        
        evaluations = db.query(Evaluation).join(Interview).filter(Interview.user_id == user.id).all()
        coding_subs = db.query(CodingSubmission).filter(CodingSubmission.user_id == user.id).all()
        questions_answered = len(evaluations) + len(coding_subs)

        if evaluations:
            tc_avg = round(sum(e.technical_correctness for e in evaluations) / len(evaluations), 1)
            cc_avg = round(sum(e.conceptual_completeness for e in evaluations) / len(evaluations), 1)
            rr_avg = round(sum(e.response_relevance for e in evaluations) / len(evaluations), 1)
            sc_avg = round(sum(e.structural_clarity for e in evaluations) / len(evaluations), 1)
            du_avg = round(sum(e.depth_of_understanding for e in evaluations) / len(evaluations), 1)
        else:
            tc_avg = cc_avg = rr_avg = sc_avg = du_avg = 0.0

        skills_map: Dict[str, List[float]] = {}
        for ev in evaluations:
            q = db.query(InterviewQuestion).filter(InterviewQuestion.id == ev.question_id).first()
            skill_name = (q.skill if q and q.skill else "General")
            if skill_name not in skills_map:
                skills_map[skill_name] = []
            skills_map[skill_name].append(ev.overall_score)

        for cs in coding_subs:
            skill_name = "Algorithms & Data Structures"
            if skill_name not in skills_map:
                skills_map[skill_name] = []
            skills_map[skill_name].append(cs.coding_score)

        skill_analytics = []
        for skill_name, scores in skills_map.items():
            s_avg = round(sum(scores) / len(scores), 1) if scores else 0.0
            skill_analytics.append({
                "skill": skill_name,
                "score": s_avg,
                "count": len(scores)
            })

        chronological = sorted(
            [{"date": i.created_at, "title": i.title, "score": i.total_score} for i in completed] +
            [{"date": c.created_at, "title": c.title, "score": c.total_score} for c in completed_coding],
            key=lambda x: x["date"]
        )

        history_trend = [
            {
                "date": item["date"].strftime("%Y-%m-%d"),
                "title": item["title"],
                "score": item["score"]
            }
            for item in chronological
        ]

        return {
            "stats": {
                "average_score": f"{avg_score}%",
                "best_score": f"{best_score}%",
                "total_interviews": total_interviews,
                "questions_answered": questions_answered
            },
            "dimension_scores": {
                "technical_correctness": tc_avg,
                "conceptual_completeness": cc_avg,
                "response_relevance": rr_avg,
                "structural_clarity": sc_avg,
                "depth_of_understanding": du_avg
            },
            "skill_analytics": skill_analytics,
            "trend": history_trend
        }
