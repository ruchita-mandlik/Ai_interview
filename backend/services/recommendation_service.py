from datetime import datetime
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from backend.models.answer import Answer
from backend.models.evaluation import Evaluation
from backend.models.question import InterviewQuestion
from backend.models.coding_interview import CodingSubmission, CodingQuestion
from backend.models.candidate_profile import CandidateProfile
from backend.services.ai_service import AIService

class RecommendationService:
    @staticmethod
    def analyze_user_performance(db: Session, user_id: str) -> Tuple[List[str], List[str], float, int]:
        """
        Analyzes past interview and coding answers to identify candidate's strong and weak topics.
        """
        topic_scores: Dict[str, List[float]] = {}
        all_scores: List[float] = []

        # 1. Standard Interview answers & evaluations
        answers = (
            db.query(Answer)
            .filter(Answer.user_id == user_id)
            .all()
        )

        for ans in answers:
            ev = ans.evaluation
            q = ans.question
            if ev and q:
                # overall_score in Evaluation is 0-100 or 0-10
                score = ev.overall_score
                if score <= 10.0:
                    score = score * 10.0
                all_scores.append(score)
                topic = q.category or q.skill or "General"
                if topic not in topic_scores:
                    topic_scores[topic] = []
                topic_scores[topic].append(score)

        # 2. Coding Submissions & Questions
        coding_subs = (
            db.query(CodingSubmission)
            .filter(CodingSubmission.user_id == user_id)
            .all()
        )
        for sub in coding_subs:
            if sub.correctness_score is not None:
                score = sub.correctness_score
                if score <= 10.0:
                    score = score * 10.0
                all_scores.append(score)
                q_topic = "Algorithms"
                if sub.coding_question and sub.coding_question.topic:
                    q_topic = sub.coding_question.topic
                if q_topic not in topic_scores:
                    topic_scores[q_topic] = []
                topic_scores[q_topic].append(score)

        total_entries = len(answers) + len(coding_subs)

        if not all_scores:
            # Check candidate profile skills
            profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
            if profile and profile.skills:
                skills_list = [s.strip() for s in profile.skills.split(",") if s.strip()]
                if skills_list:
                    strong = skills_list[:2]
                    weak = ["System Design", "Scalability"]
                    return weak, strong, 75.0, 0
            return ["System Design", "Database Optimization"], ["Data Structures", "Algorithms"], 75.0, 0

        avg_score_100 = round(sum(all_scores) / len(all_scores), 1)

        # Sort topics by average score
        sorted_topics = []
        for t, scores in topic_scores.items():
            sorted_topics.append((t, sum(scores) / len(scores)))

        sorted_topics.sort(key=lambda x: x[1])  # ascending

        weak_topics = [t[0] for t in sorted_topics if t[1] < 70.0]
        if not weak_topics and sorted_topics:
            weak_topics = [sorted_topics[0][0]]
        if not weak_topics:
            weak_topics = ["System Design", "Database Indexing"]

        strong_topics = [t[0] for t in sorted_topics if t[1] >= 70.0]
        if not strong_topics and sorted_topics:
            strong_topics = [sorted_topics[-1][0]]
        if not strong_topics:
            strong_topics = ["Data Structures", "Algorithms"]

        return weak_topics, strong_topics, avg_score_100, total_entries

    @classmethod
    async def get_or_generate_plan(
        cls,
        db: Session,
        user_id: str,
        role: str = "Software Developer",
        experience: str = "Intermediate"
    ) -> Dict[str, Any]:
        """
        Generates or provides an AI-backed preparation roadmap.
        """
        weak_topics, strong_topics, avg_score, total_ans = cls.analyze_user_performance(db, user_id)

        ai_plan = await AIService.generate_preparation_plan(
            role=role,
            experience=experience,
            weak_topics=weak_topics,
            strong_topics=strong_topics,
            avg_score=avg_score / 10.0
        )

        return {
            "user_id": user_id,
            "recommended_topics": ai_plan.get("recommended_topics", weak_topics),
            "recommended_questions": ai_plan.get("recommended_questions", []),
            "recommended_difficulty": ai_plan.get("recommended_difficulty", "Medium"),
            "study_priorities": ai_plan.get("study_priorities", weak_topics),
            "plan": ai_plan.get("plan", []),
            "overall_readiness_assessment": ai_plan.get("overall_readiness_assessment", "Your readiness plan is ready."),
            "updated_at": datetime.utcnow().isoformat()
        }
