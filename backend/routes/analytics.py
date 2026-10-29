import json
from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User, Interview, InterviewQuestion, Answer, Evaluation, CodingInterview, CodingSubmission
from backend.utils.security import get_current_user
from backend.schemas.analytics import (
    OverviewAnalyticsResponse,
    PerformanceTrendPoint,
    TopicPerformance,
    DifficultyPerformance,
    TypePerformance
)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/overview", response_model=OverviewAnalyticsResponse)
def get_overview_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Fetch user data from database
    interviews = db.query(Interview).filter(Interview.user_id == current_user.id).order_by(Interview.created_at.asc()).all()
    answers = db.query(Answer).filter(Answer.user_id == current_user.id).all()
    evaluations = db.query(Evaluation).join(Answer, Evaluation.answer_id == Answer.id).filter(Answer.user_id == current_user.id).all()
    coding_interviews = db.query(CodingInterview).filter(CodingInterview.user_id == current_user.id).all()
    coding_subs = db.query(CodingSubmission).filter(CodingSubmission.user_id == current_user.id).all()

    completed_interviews = [i for i in interviews if i.status == "completed"]
    completed_coding = [ci for ci in coding_interviews if ci.status == "completed"]
    interviews_completed_count = len(completed_interviews) + len(completed_coding)
    questions_answered_count = len(answers) + len(coding_subs)

    # Collect scores across sessions
    all_scores: List[float] = []
    for i in completed_interviews:
        if i.total_score and i.total_score > 0:
            all_scores.append(float(i.total_score))
    for ev in evaluations:
        if ev.overall_score and ev.overall_score > 0:
            all_scores.append(float(ev.overall_score))
    for cs in coding_subs:
        if cs.coding_score and cs.coding_score > 0:
            all_scores.append(float(cs.coding_score))

    avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0
    best_score = round(max(all_scores), 1) if all_scores else 0.0

    # Categorize by topic, difficulty, and interview type
    topic_scores: Dict[str, List[float]] = {}
    diff_scores: Dict[str, List[float]] = {}
    type_scores: Dict[str, List[float]] = {}

    for ev in evaluations:
        q = ev.question
        if q:
            t = q.category or q.skill or "General Technical"
            d = q.difficulty or "Medium"
            s = float(ev.overall_score)
            topic_scores.setdefault(t, []).append(s)
            diff_scores.setdefault(d, []).append(s)
            
            interview_type = ev.interview.interview_type if ev.interview else "Technical"
            type_scores.setdefault(interview_type, []).append(s)

    for cs in coding_subs:
        q = cs.question
        if q:
            t = q.skill or "Coding & Algorithms"
            d = q.difficulty or "Medium"
            s = float(cs.coding_score)
            topic_scores.setdefault(t, []).append(s)
            diff_scores.setdefault(d, []).append(s)
            type_scores.setdefault("Coding", []).append(s)

    topic_perf_list = [
        TopicPerformance(
            topic=t,
            score=round(sum(scs) / len(scs), 1),
            total_questions=len(scs)
        )
        for t, scs in topic_scores.items()
    ]
    topic_perf_list.sort(key=lambda x: x.score, reverse=True)

    strongest_topic = topic_perf_list[0].topic if topic_perf_list else "None yet"
    weakest_topic = topic_perf_list[-1].topic if topic_perf_list else "None yet"
    weak_topics = [tp.topic for tp in topic_perf_list if tp.score < 75.0]

    diff_perf_list = [
        DifficultyPerformance(
            difficulty=d,
            score=round(sum(scs) / len(scs), 1),
            total_questions=len(scs)
        )
        for d, scs in diff_scores.items()
    ]

    type_perf_list = [
        TypePerformance(
            interview_type=it,
            score=round(sum(scs) / len(scs), 1),
            count=len(scs)
        )
        for it, scs in type_scores.items()
    ]

    # Performance Trend (Last 7 sessions)
    trend_points: List[PerformanceTrendPoint] = []
    all_sessions = []
    for i in completed_interviews:
        date_str = i.created_at.strftime("%Y-%m-%d") if i.created_at else "Session"
        all_sessions.append((date_str, float(i.total_score or 0.0), i.interview_type or "Technical"))
    for ci in completed_coding:
        date_str = ci.created_at.strftime("%Y-%m-%d") if ci.created_at else "Session"
        all_sessions.append((date_str, float(ci.total_score or 0.0), "Coding"))

    for idx, (dt, sc, itype) in enumerate(all_sessions[-7:]):
        trend_points.append(PerformanceTrendPoint(
            date=dt if dt != "Session" else f"Session {idx+1}",
            score=round(sc, 1),
            interview_type=itype
        ))

    # Improvement index
    if len(trend_points) >= 2:
        recent_improvement = round(trend_points[-1].score - trend_points[0].score, 1)
    else:
        recent_improvement = 0.0

    # Synchronize readiness score with ReadinessService for unified platform intelligence
    from backend.services.readiness_service import ReadinessService
    readiness_snap = ReadinessService.get_latest_readiness(db, current_user)
    readiness_score = readiness_snap.overall_readiness_score
    readiness_explanation = readiness_snap.data_sufficiency_explanation


    return OverviewAnalyticsResponse(
        interviews_completed=interviews_completed_count,
        average_score=avg_score,
        best_score=best_score,
        questions_answered=questions_answered_count,
        readiness_score=readiness_score,
        readiness_explanation=readiness_explanation,
        strongest_topic=strongest_topic,
        weakest_topic=weakest_topic,
        recent_improvement=recent_improvement,
        weak_topics=weak_topics,
        performance_trend=trend_points,
        topic_performance=topic_perf_list,
        difficulty_performance=diff_perf_list,
        type_performance=type_perf_list
    )
