import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.models import User, Interview, InterviewQuestion, Answer, Evaluation, CandidateProfile, ResumeJDAnalysis
from backend.schemas.interview import InterviewCreateRequest, QuestionSchema
from backend.schemas.evaluation import AIEvaluationResult
from backend.services.ai_service import AIService

logger = logging.getLogger("uvicorn.error")

class InterviewService:
    @staticmethod
    def calculate_interview_final_score(db: Session, interview_id: str) -> float:
        """
        Calculates and persists the aggregate final percentage score for an interview.
        Deduplicates evaluations by question_id (taking the most recent evaluation).
        Validates that individual scores are within [0.0, 100.0].
        Excludes skipped and unanswered questions without penalizing answered questions.
        If no answered questions exist, sets total_score to 0.0.
        """
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            logger.warning(f"Interview {interview_id} not found during score calculation.")
            return 0.0

        all_evals = db.query(Evaluation).filter(
            Evaluation.interview_id == interview_id
        ).order_by(Evaluation.created_at.asc()).all()

        if not all_evals:
            logger.info(f"Interview {interview_id} has no evaluations; final score set to 0.0%.")
            interview.total_score = 0.0
            return 0.0

        # Deduplicate evaluations by question_id (latest evaluation wins)
        evals_by_question: Dict[str, Evaluation] = {}
        for ev in all_evals:
            if ev.question_id:
                evals_by_question[ev.question_id] = ev

        valid_scores: List[float] = []
        for q_id, ev in evals_by_question.items():
            score = None
            if ev.overall_score is not None:
                try:
                    score = float(ev.overall_score)
                except (ValueError, TypeError):
                    score = None

            if score is None:
                # Recalculate from rubric dimensions if available
                try:
                    tc = float(ev.technical_correctness or 0.0)
                    cc = float(ev.conceptual_completeness or 0.0)
                    rr = float(ev.response_relevance or 0.0)
                    sc = float(ev.structural_clarity or 0.0)
                    du = float(ev.depth_of_understanding or 0.0)
                    score = round(tc * 0.35 + cc * 0.25 + rr * 0.15 + sc * 0.15 + du * 0.10, 1)
                except (ValueError, TypeError):
                    score = None

            if score is not None:
                clamped_score = min(100.0, max(0.0, score))
                valid_scores.append(clamped_score)
            else:
                logger.warning(f"Evaluation {ev.id} for question {q_id} has unresolvable score; omitted from aggregation.")

        if not valid_scores:
            logger.info(f"Interview {interview_id} has evaluations but no valid scores; total score set to 0.0%.")
            final_score = 0.0
        else:
            final_score = round(sum(valid_scores) / len(valid_scores), 1)

        interview.total_score = final_score
        logger.info(
            f"Successfully computed final score for interview {interview_id}: {final_score}% "
            f"across {len(valid_scores)} evaluated questions (total questions: {interview.num_questions})."
        )
        return final_score

    @staticmethod
    async def create_interview(db: Session, user: User, req: InterviewCreateRequest) -> Interview:
        target_role = req.get_role() if hasattr(req, "get_role") else (req.role or req.target_role or "Software Developer")
        topic = req.get_topic() if hasattr(req, "get_topic") else (req.topic or "General")
        num_questions = req.get_num_questions() if hasattr(req, "get_num_questions") else (req.num_questions or 5)
        interview_type = req.interview_type or "Technical"
        experience_level = req.experience_level or "Intermediate"
        difficulty = req.difficulty or "Medium"
        mode = req.get_mode() if hasattr(req, "get_mode") else getattr(req, "mode", "text")
        voice_name = getattr(req, "voice_name", "default") or "default"

        is_adaptive = True
        if hasattr(req, "is_adaptive") and req.is_adaptive is not None:
            is_adaptive = bool(req.is_adaptive)
        elif getattr(req, "mode", "") == "standard" or getattr(req, "interview_mode", "") == "standard":
            is_adaptive = False
        elif interview_type in ["Standard Mock", "Standard Practice", "Mock Interview", "Standard"]:
            is_adaptive = False
        elif interview_type in ["Adaptive AI", "Adaptive", "Adaptive Interview"]:
            is_adaptive = True

        title = f"{target_role} ({topic}) - {interview_type}"
        if mode == "voice":
            title = f"🎙️ {target_role} ({topic}) - Voice Interview"
        elif is_adaptive:
            title = f"🧠 {target_role} ({topic}) - Adaptive AI Interview"
        else:
            title = f"🚀 {target_role} ({topic}) - Standard Mock Practice"
        
        resume_analysis_dict = None
        if req.resume_analysis_id:
            analysis = db.query(ResumeJDAnalysis).filter(
                ResumeJDAnalysis.id == req.resume_analysis_id,
                ResumeJDAnalysis.user_id == user.id
            ).first()
            if analysis:
                try:
                    resume_analysis_dict = {
                        "matched_skills": json.loads(analysis.matched_skills or "[]"),
                        "missing_skills": json.loads(analysis.missing_skills or "[]"),
                        "priority_skills": json.loads(analysis.priority_skills or "[]"),
                        "match_percentage": analysis.match_percentage,
                        "analysis_summary": analysis.analysis_summary
                    }
                except Exception:
                    pass

        skills_str = ""
        if hasattr(req, "get_skills_list") and req.get_skills_list():
            skills_str = ", ".join(req.get_skills_list())
        elif isinstance(req.skills, list):
            skills_str = ", ".join(req.skills)
        elif isinstance(req.skills, str):
            skills_str = req.skills

        interview = Interview(
            user_id=user.id,
            title=title,
            interview_type=interview_type,
            target_role=target_role,
            experience_level=experience_level,
            topic=topic,
            difficulty=difficulty,
            num_questions=num_questions,
            job_description=req.job_description,
            resume_text=req.resume_text,
            skills=skills_str,
            additional_instructions=req.additional_instructions,
            resume_analysis_id=req.resume_analysis_id,
            status="in_progress",
            duration_minutes=num_questions * 4,
            mode=mode,
            voice_name=voice_name,
            is_adaptive=is_adaptive
        )
        db.add(interview)
        db.flush()

        try:
            if not is_adaptive:
                # Standard Mock Interview: Generate all requested questions upfront (e.g. 5 questions)
                ai_questions = await AIService.generate_interview_questions(
                    target_role=target_role,
                    experience_level=experience_level,
                    topic=topic,
                    interview_type=interview_type,
                    difficulty=difficulty,
                    num_questions=num_questions,
                    resume_analysis=resume_analysis_dict,
                    job_description=req.job_description,
                    resume_text=req.resume_text,
                    skills=req.get_skills_list() if hasattr(req, "get_skills_list") else (req.skills if isinstance(req.skills, list) else None),
                    additional_instructions=req.additional_instructions
                )

                if not ai_questions:
                    raise ValueError("No questions generated by AI service.")

                for idx, q_item in enumerate(ai_questions, start=1):
                    reason_text = f"Standard mock question #{idx} for {target_role} ({topic})."
                    question = InterviewQuestion(
                        interview_id=interview.id,
                        question_number=idx,
                        question_text=q_item["question"],
                        category=q_item.get("category", topic),
                        skill=q_item.get("skill", topic),
                        difficulty=q_item.get("difficulty", difficulty),
                        additional_instruction=q_item.get("additional_instruction"),
                        adaptation_reason=reason_text,
                        adaptive_action=None,
                        assessment_objective=f"Evaluate proficiency in {q_item.get('skill', topic)}.",
                        is_follow_up=False,
                        parent_question_id=None
                    )
                    db.add(question)
            else:
                # Adaptive Interview: Generate initial baseline question
                ai_questions = await AIService.generate_interview_questions(
                    target_role=target_role,
                    experience_level=experience_level,
                    topic=topic,
                    interview_type=interview_type,
                    difficulty=difficulty,
                    num_questions=1,
                    resume_analysis=resume_analysis_dict,
                    job_description=req.job_description,
                    resume_text=req.resume_text,
                    skills=req.get_skills_list() if hasattr(req, "get_skills_list") else (req.skills if isinstance(req.skills, list) else None),
                    additional_instructions=req.additional_instructions
                )

                if not ai_questions:
                    raise ValueError("No initial question generated by AI service.")

                q_item = ai_questions[0]
                reason_text = f"Initial {difficulty} question for {target_role} ({topic})."
                if resume_analysis_dict:
                    reason_text = f"Personalized initial question based on Resume & JD Skill Match ({resume_analysis_dict.get('match_percentage', 75)}% match)."

                question = InterviewQuestion(
                    interview_id=interview.id,
                    question_number=1,
                    question_text=q_item["question"],
                    category=q_item.get("category", topic),
                    skill=q_item.get("skill", topic),
                    difficulty=q_item.get("difficulty", difficulty),
                    additional_instruction=q_item.get("additional_instruction"),
                    adaptation_reason=reason_text,
                    adaptive_action="NEXT_TOPIC",
                    assessment_objective=f"Initial evaluation of {q_item.get('skill', topic)}.",
                    is_follow_up=False,
                    parent_question_id=None
                )
                db.add(question)
            
            db.commit()
            db.refresh(interview)
            return interview
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def get_interview(db: Session, interview_id: str, user_id: str) -> Interview:
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
        if interview.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to interview")
        return interview

    @staticmethod
    def _build_answer_response(
        interview: Interview,
        question: InterviewQuestion,
        answer: Answer,
        evaluation: Evaluation,
        next_q: Optional[InterviewQuestion],
        is_last: bool,
        user_id: str,
        conversational_prelude: Optional[str] = None
    ) -> Dict[str, Any]:
        score_10 = round(evaluation.overall_score / 10.0, 1)

        try:
            strengths = json.loads(evaluation.strengths) if isinstance(evaluation.strengths, str) and evaluation.strengths.startswith("[") else ([evaluation.strengths] if evaluation.strengths else [])
        except Exception:
            strengths = [evaluation.strengths] if evaluation.strengths else []

        try:
            improvements = json.loads(evaluation.improvements) if isinstance(evaluation.improvements, str) and evaluation.improvements.startswith("[") else ([evaluation.improvements] if evaluation.improvements else [])
        except Exception:
            improvements = [evaluation.improvements] if evaluation.improvements else []

        try:
            missing_concepts = json.loads(evaluation.missing_concepts) if isinstance(evaluation.missing_concepts, str) and evaluation.missing_concepts.startswith("[") else ([evaluation.missing_concepts] if evaluation.missing_concepts else [])
        except Exception:
            missing_concepts = [evaluation.missing_concepts] if evaluation.missing_concepts else []

        try:
            incorrect_claims = json.loads(evaluation.incorrect_claims) if isinstance(evaluation.incorrect_claims, str) and evaluation.incorrect_claims.startswith("[") else ([evaluation.incorrect_claims] if evaluation.incorrect_claims else [])
        except Exception:
            incorrect_claims = [evaluation.incorrect_claims] if evaluation.incorrect_claims else []

        try:
            knowledge_gaps_list = json.loads(interview.knowledge_gaps) if isinstance(interview.knowledge_gaps, str) and interview.knowledge_gaps.startswith("[") else ([interview.knowledge_gaps] if interview.knowledge_gaps else [])
        except Exception:
            knowledge_gaps_list = []

        nested_evaluation = {
            "id": evaluation.id,
            "answer_id": answer.id,
            "score": evaluation.overall_score,
            "score_out_of_10": score_10,
            "correctness": evaluation.technical_correctness,
            "technical_depth": evaluation.depth_of_understanding,
            "clarity": evaluation.structural_clarity,
            "completeness": evaluation.conceptual_completeness,
            "strengths": strengths,
            "weaknesses": improvements,
            "missing_points": improvements,
            "missing_concepts": missing_concepts,
            "incorrect_claims": incorrect_claims,
            "actionable_feedback": evaluation.actionable_feedback,
            "ideal_answer": evaluation.model_answer or "",
            "improved_sample_answer": evaluation.model_answer or "",
            "improvement_tip": improvements[0] if improvements else "",
            "evaluation_type": evaluation.evaluation_type or "technical",
            "communication_notes": getattr(evaluation, "communication_notes", None) or "Clear articulation of principles.",
            "evaluated_at": evaluation.created_at.isoformat() if evaluation.created_at else datetime.utcnow().isoformat()
        }

        next_question_dict = None
        follow_up_question_dict = None
        adaptive_action = getattr(next_q, "adaptive_action", None) or ("NEXT_TOPIC" if not is_last else "NEXT_TOPIC")
        decision_rationale = getattr(next_q, "adaptation_reason", None) or (f"Performance on Question #{question.question_number} ({evaluation.overall_score}%)." if not is_last else "All interview questions completed.")
        assessment_objective = getattr(next_q, "assessment_objective", None)

        actual_prelude = (
            conversational_prelude
            or getattr(next_q, "spoken_intro", None)
            or ("Thank you for your response. Let's proceed to the next question." if not is_last else "Thank you. That concludes all interview questions.")
        )

        if next_q and not is_last:
            is_fu = bool(getattr(next_q, "is_follow_up", False))
            spoken_intro = actual_prelude or getattr(next_q, "adaptation_reason", None) or ("Here is a targeted follow-up question." if is_fu else "Let's move to our next question.")
            next_question_dict = {
                "id": next_q.id,
                "interview_id": next_q.interview_id,
                "question_number": next_q.question_number,
                "question_text": next_q.question_text,
                "question": next_q.question_text,
                "category": next_q.category,
                "topic": next_q.category or next_q.skill or interview.topic,
                "skill": next_q.skill,
                "difficulty": next_q.difficulty,
                "question_type": "Technical",
                "expected_points": [next_q.adaptation_reason] if next_q.adaptation_reason else [],
                "additional_instruction": next_q.additional_instruction,
                "adaptation_reason": next_q.adaptation_reason,
                "adaptive_action": next_q.adaptive_action or "NEXT_TOPIC",
                "assessment_objective": next_q.assessment_objective,
                "is_follow_up": is_fu,
                "parent_question_id": getattr(next_q, "parent_question_id", None),
                "spoken_intro": spoken_intro,
                "created_at": next_q.created_at.isoformat() if next_q.created_at else ""
            }
            if is_fu:
                follow_up_question_dict = next_question_dict

        adaptive_decision = {
            "action": adaptive_action,
            "updated_difficulty": getattr(next_q, "difficulty", getattr(interview, "current_difficulty", interview.difficulty)),
            "decision_rationale": decision_rationale,
            "next_question": next_q.question_text if next_q and not is_last else None,
            "assessment_objective": assessment_objective if next_q and not is_last else None,
            "category": getattr(next_q, "category", interview.topic),
            "skill": getattr(next_q, "skill", interview.topic),
            "additional_instruction": getattr(next_q, "additional_instruction", None),
            "identified_knowledge_gaps": knowledge_gaps_list,
            "conversational_prelude": actual_prelude,
            "is_terminal": is_last
        }

        return {
            # Flat attributes for legacy HTML and tests:
            "answer_id": answer.id,
            "evaluation_id": evaluation.id,
            "overall_score": evaluation.overall_score,
            "total_score": interview.total_score,
            "final_score": interview.total_score,
            "status": interview.status,
            "score_out_of_10": score_10,
            "technical_correctness": evaluation.technical_correctness,
            "conceptual_completeness": evaluation.conceptual_completeness,
            "response_relevance": evaluation.response_relevance,
            "structural_clarity": evaluation.structural_clarity,
            "depth_of_understanding": evaluation.depth_of_understanding,
            "strengths": strengths,
            "improvements": improvements,
            "missing_concepts": missing_concepts,
            "incorrect_claims": incorrect_claims,
            "actionable_feedback": evaluation.actionable_feedback,
            "feedback": evaluation.feedback,
            "model_answer": evaluation.model_answer,
            "improved_sample_answer": evaluation.model_answer or "",
            "evaluation_type": evaluation.evaluation_type or "technical",
            "is_last_question": is_last,
            "is_adaptive": bool(getattr(interview, "is_adaptive", True)),
            "next_question": next_question_dict,
            "conversational_prelude": adaptive_decision["conversational_prelude"],

            # Structured Adaptive Intelligence contract attributes:
            "adaptive_action": adaptive_action,
            "decision_rationale": decision_rationale,
            "assessment_objective": assessment_objective,
            "current_difficulty": getattr(interview, "current_difficulty", interview.difficulty) or interview.difficulty,
            "knowledge_gaps": knowledge_gaps_list,
            "adaptive_decision": adaptive_decision,

            # React SPA attributes:
            "id": answer.id,
            "interview_id": interview.id,
            "question_id": question.id,
            "user_id": user_id,
            "answer": answer.answer_text,
            "transcript_raw": answer.transcript_raw,
            "is_voice_submission": answer.is_voice_submission,
            "audio_duration_seconds": answer.audio_duration_seconds,
            "submitted_at": answer.submitted_at.isoformat() if answer.submitted_at else datetime.utcnow().isoformat(),
            "evaluation": nested_evaluation,
            "interview_completed": is_last,
            "follow_up_question": follow_up_question_dict
        }

    @staticmethod
    async def submit_answer(
        db: Session,
        interview_id: str,
        question_id: str,
        user: User,
        answer_text: str,
        transcript_raw: Optional[str] = None,
        is_voice_submission: bool = False,
        audio_duration_seconds: Optional[float] = None
    ) -> Dict[str, Any]:
        interview = InterviewService.get_interview(db, interview_id, user.id)
        
        question = db.query(InterviewQuestion).filter(
            InterviewQuestion.id == question_id,
            InterviewQuestion.interview_id == interview_id
        ).first()
        
        if not question:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question does not belong to this interview")

        existing_answer = db.query(Answer).filter(
            Answer.interview_id == interview_id,
            Answer.question_id == question_id,
            Answer.user_id == user.id
        ).first()

        existing_eval = None
        if existing_answer:
            existing_eval = db.query(Evaluation).filter(Evaluation.answer_id == existing_answer.id).first()

        # Check for existing next question (idempotency support)
        next_q_num = question.question_number + 1
        existing_next_q = db.query(InterviewQuestion).filter(
            InterviewQuestion.interview_id == interview_id,
            InterviewQuestion.question_number == next_q_num
        ).first()
        if not existing_next_q:
            existing_next_q = db.query(InterviewQuestion).filter(
                InterviewQuestion.interview_id == interview_id,
                InterviewQuestion.parent_question_id == question.id
            ).first()

        is_last = (question.question_number >= interview.num_questions)

        # Idempotency fast-path: return cached response if already evaluated with same answer
        if existing_answer and existing_eval and (existing_next_q or is_last):
            if existing_answer.answer_text.strip() == answer_text.strip():
                if is_last:
                    InterviewService.calculate_interview_final_score(db, interview_id)
                    interview.status = "completed"
                    db.commit()
                    db.refresh(interview)
                return InterviewService._build_answer_response(
                    interview=interview,
                    question=question,
                    answer=existing_answer,
                    evaluation=existing_eval,
                    next_q=existing_next_q,
                    is_last=is_last,
                    user_id=user.id
                )

        if existing_answer:
            existing_answer.answer_text = answer_text
            existing_answer.transcript_raw = transcript_raw or answer_text
            existing_answer.is_voice_submission = is_voice_submission
            existing_answer.audio_duration_seconds = audio_duration_seconds
            existing_answer.submitted_at = datetime.utcnow()
            answer = existing_answer
        else:
            answer = Answer(
                interview_id=interview_id,
                question_id=question_id,
                user_id=user.id,
                answer_text=answer_text,
                transcript_raw=transcript_raw or answer_text,
                is_voice_submission=is_voice_submission,
                audio_duration_seconds=audio_duration_seconds
            )
            db.add(answer)
            
        db.flush()

        # AI Rubric Evaluation
        ai_eval = await AIService.evaluate_candidate_answer(
            question_text=question.question_text,
            answer_text=answer_text,
            topic=interview.topic,
            target_role=interview.target_role,
            difficulty=question.difficulty,
            interview_type=interview.interview_type,
            job_description=interview.job_description,
            additional_instructions=interview.additional_instructions
        )

        if not ai_eval:
            logger.error(f"AI evaluation service returned null or empty result for interview {interview_id}, question {question_id}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI evaluation service returned an empty evaluation response."
            )

        if isinstance(ai_eval, dict):
            raw_ov = ai_eval.get("overall_score") if ai_eval.get("overall_score") is not None else ai_eval.get("score")
            raw_tc = ai_eval.get("technical_correctness")
            raw_cc = ai_eval.get("conceptual_completeness")
            raw_rr = ai_eval.get("response_relevance")
            raw_sc = ai_eval.get("structural_clarity")
            raw_du = ai_eval.get("depth_of_understanding")

            tc = max(0.0, min(100.0, float(raw_tc if raw_tc is not None else (raw_ov if raw_ov is not None else 70.0))))
            cc = max(0.0, min(100.0, float(raw_cc if raw_cc is not None else (raw_ov if raw_ov is not None else 70.0))))
            rr = max(0.0, min(100.0, float(raw_rr if raw_rr is not None else (raw_ov if raw_ov is not None else 75.0))))
            sc = max(0.0, min(100.0, float(raw_sc if raw_sc is not None else (raw_ov if raw_ov is not None else 75.0))))
            du = max(0.0, min(100.0, float(raw_du if raw_du is not None else (raw_ov if raw_ov is not None else 65.0))))

            if raw_ov is not None:
                overall_score = max(0.0, min(100.0, float(raw_ov)))
            else:
                overall_score = round((tc * 0.35) + (cc * 0.25) + (rr * 0.15) + (sc * 0.15) + (du * 0.10), 1)

            strengths = ai_eval.get("strengths") or ["Demonstrated engagement with technical topic."]
            improvements = ai_eval.get("improvements") or ai_eval.get("weaknesses") or ["Explore deeper trade-offs and edge-case handling."]
            missing_concepts = ai_eval.get("missing_concepts") or improvements
            incorrect_claims = ai_eval.get("incorrect_claims") or []
            feedback = ai_eval.get("feedback") or ai_eval.get("actionable_feedback") or "Feedback on candidate response."
            model_answer = ai_eval.get("model_answer") or ai_eval.get("ideal_answer") or "Standard benchmark answer."

            ai_eval = AIEvaluationResult(
                technical_correctness=tc,
                conceptual_completeness=cc,
                response_relevance=rr,
                structural_clarity=sc,
                depth_of_understanding=du,
                overall_score=overall_score,
                strengths=strengths,
                improvements=improvements,
                missing_concepts=missing_concepts,
                incorrect_claims=incorrect_claims,
                feedback=feedback,
                actionable_feedback=ai_eval.get("actionable_feedback") or feedback,
                model_answer=model_answer,
                improved_sample_answer=ai_eval.get("improved_sample_answer") or model_answer,
                evaluation_type=ai_eval.get("evaluation_type", "technical"),
                communication_notes=ai_eval.get("communication_notes")
            )
        else:
            tc = max(0.0, min(100.0, float(getattr(ai_eval, "technical_correctness", 0.0) or 0.0)))
            cc = max(0.0, min(100.0, float(getattr(ai_eval, "conceptual_completeness", 0.0) or 0.0)))
            rr = max(0.0, min(100.0, float(getattr(ai_eval, "response_relevance", 0.0) or 0.0)))
            sc = max(0.0, min(100.0, float(getattr(ai_eval, "structural_clarity", 0.0) or 0.0)))
            du = max(0.0, min(100.0, float(getattr(ai_eval, "depth_of_understanding", 0.0) or 0.0)))
            raw_ov = getattr(ai_eval, "overall_score", None)
            if raw_ov is not None and float(raw_ov) > 0.0:
                overall_score = max(0.0, min(100.0, float(raw_ov)))
            else:
                overall_score = round((tc * 0.35) + (cc * 0.25) + (rr * 0.15) + (sc * 0.15) + (du * 0.10), 1)

            ai_eval.technical_correctness = tc
            ai_eval.conceptual_completeness = cc
            ai_eval.response_relevance = rr
            ai_eval.structural_clarity = sc
            ai_eval.depth_of_understanding = du
            ai_eval.overall_score = overall_score

        logger.info(
            f"Question #{question.question_number} (ID: {question_id}) in Interview {interview_id} evaluated: "
            f"overall={ai_eval.overall_score}% (tc={ai_eval.technical_correctness}, cc={ai_eval.conceptual_completeness}, "
            f"rr={ai_eval.response_relevance}, sc={ai_eval.structural_clarity}, du={ai_eval.depth_of_understanding})"
        )

        communication_notes = None

        # Save or update Evaluation
        if existing_eval:
            existing_eval.technical_correctness = ai_eval.technical_correctness
            existing_eval.conceptual_completeness = ai_eval.conceptual_completeness
            existing_eval.response_relevance = ai_eval.response_relevance
            existing_eval.structural_clarity = ai_eval.structural_clarity
            existing_eval.depth_of_understanding = ai_eval.depth_of_understanding
            existing_eval.overall_score = ai_eval.overall_score
            existing_eval.strengths = json.dumps(ai_eval.strengths)
            existing_eval.improvements = json.dumps(ai_eval.improvements)
            existing_eval.missing_concepts = json.dumps(ai_eval.missing_concepts)
            existing_eval.incorrect_claims = json.dumps(ai_eval.incorrect_claims)
            existing_eval.feedback = ai_eval.feedback
            existing_eval.actionable_feedback = ai_eval.actionable_feedback
            existing_eval.model_answer = ai_eval.model_answer
            existing_eval.evaluation_type = ai_eval.evaluation_type
            evaluation = existing_eval
        else:
            evaluation = Evaluation(
                answer_id=answer.id,
                interview_id=interview_id,
                question_id=question_id,
                technical_correctness=ai_eval.technical_correctness,
                conceptual_completeness=ai_eval.conceptual_completeness,
                response_relevance=ai_eval.response_relevance,
                structural_clarity=ai_eval.structural_clarity,
                depth_of_understanding=ai_eval.depth_of_understanding,
                overall_score=ai_eval.overall_score,
                strengths=json.dumps(ai_eval.strengths),
                improvements=json.dumps(ai_eval.improvements),
                missing_concepts=json.dumps(ai_eval.missing_concepts),
                incorrect_claims=json.dumps(ai_eval.incorrect_claims),
                feedback=ai_eval.feedback,
                actionable_feedback=ai_eval.actionable_feedback,
                model_answer=ai_eval.model_answer,
                evaluation_type=ai_eval.evaluation_type
            )
            db.add(evaluation)

        db.flush()

        # Build nested evaluation dictionary
        score_10 = ai_eval.score_out_of_10 or round(evaluation.overall_score / 10.0, 1)
        nested_evaluation = {
            "id": evaluation.id,
            "answer_id": answer.id,
            "score": evaluation.overall_score,
            "score_out_of_10": score_10,
            "correctness": evaluation.technical_correctness,
            "technical_depth": evaluation.depth_of_understanding,
            "clarity": evaluation.structural_clarity,
            "completeness": evaluation.conceptual_completeness,
            "strengths": ai_eval.strengths,
            "weaknesses": ai_eval.improvements,
            "missing_points": ai_eval.improvements,
            "missing_concepts": ai_eval.missing_concepts,
            "incorrect_claims": ai_eval.incorrect_claims,
            "actionable_feedback": ai_eval.actionable_feedback,
            "ideal_answer": evaluation.model_answer or "",
            "improved_sample_answer": ai_eval.improved_sample_answer or evaluation.model_answer or "",
            "improvement_tip": ai_eval.improvements[0] if ai_eval.improvements else "",
            "evaluation_type": ai_eval.evaluation_type or "technical",
            "communication_notes": communication_notes or getattr(evaluation, "communication_notes", None) or "Clear articulation of principles.",
            "evaluated_at": evaluation.created_at.isoformat() if evaluation.created_at else datetime.utcnow().isoformat()
        }

        # Context Gathering for Adaptive Progression
        conversational_prelude = None
        raw_gaps = getattr(interview, "knowledge_gaps", None)
        accumulated_gaps: List[str] = []
        if raw_gaps:
            if isinstance(raw_gaps, str) and raw_gaps.startswith("["):
                try:
                    accumulated_gaps = json.loads(raw_gaps)
                except Exception:
                    accumulated_gaps = [raw_gaps]
            elif isinstance(raw_gaps, list):
                accumulated_gaps = list(raw_gaps)

        all_answers = db.query(Answer).filter(Answer.interview_id == interview_id).all()
        all_evals = db.query(Evaluation).filter(Evaluation.interview_id == interview_id).all()
        eval_map = {e.question_id: e for e in all_evals}
        ans_map = {a.question_id: a for a in all_answers}

        recent_history = []
        for q in interview.questions:
            a = ans_map.get(q.id)
            ev = eval_map.get(q.id)
            if a:
                recent_history.append({
                    "question_text": q.question_text,
                    "answer_text": a.answer_text,
                    "score": ev.overall_score if ev else 0.0
                })

        consecutive_strong = 0
        consecutive_weak = 0
        for h in reversed(recent_history):
            if h["score"] >= 80.0:
                consecutive_strong += 1
            else:
                break
        for h in reversed(recent_history):
            if h["score"] < 60.0:
                consecutive_weak += 1
            else:
                break

        is_adaptive = getattr(interview, "is_adaptive", True)
        if is_adaptive is None:
            is_adaptive = True

        # Conversational / Adaptive Engine: Generate follow-up or next question
        if not is_last:
            if not is_adaptive:
                # Standard Mock Interview: Pure linear advancement without adaptive dynamic re-generation
                if not existing_next_q:
                    next_q_num = question.question_number + 1
                    existing_next_q = db.query(InterviewQuestion).filter(
                        InterviewQuestion.interview_id == interview_id,
                        InterviewQuestion.question_number == next_q_num
                    ).first()
            elif not existing_next_q:
                skills_list = [s.strip() for s in (interview.skills or "").split(",") if s.strip()]
                all_prev = [q.question_text for q in interview.questions]

                if interview.mode == "voice" or is_voice_submission:
                    voice_res = await AIService.generate_voice_conversational_response(
                        target_role=interview.target_role,
                        experience_level=interview.experience_level,
                        topic=interview.topic,
                        interview_type=interview.interview_type,
                        previous_question_text=question.question_text,
                        candidate_answer=answer_text,
                        overall_score=evaluation.overall_score,
                        previous_difficulty=question.difficulty,
                        next_question_number=next_q_num,
                        max_questions=interview.num_questions,
                        strengths=ai_eval.strengths,
                        improvements=ai_eval.improvements,
                        knowledge_gaps=accumulated_gaps
                    )
                    communication_notes = voice_res.get("communication_notes")
                    if communication_notes:
                        evaluation.communication_notes = communication_notes
                        nested_evaluation["communication_notes"] = communication_notes
                        db.commit()

                    adaptive_action = voice_res.get("adaptive_action") or voice_res.get("action") or "NEXT_TOPIC"
                    assessment_objective = voice_res.get("assessment_objective") or f"Assess verbal articulation of {voice_res.get('skill', interview.topic)}."
                    is_fu = bool(voice_res.get("is_follow_up", False) or adaptive_action in ("FOLLOW_UP", "CLARIFY"))
                    new_diff = voice_res.get("updated_difficulty") or voice_res.get("difficulty") or question.difficulty
                    adaptation_reason = voice_res.get("decision_rationale") or voice_res.get("adaptation_reason")
                    q_text = voice_res.get("next_question") or voice_res.get("question") or "Please elaborate on your response."

                    # Update knowledge gaps
                    new_gaps = voice_res.get("identified_knowledge_gaps") or voice_res.get("new_knowledge_gaps", [])
                    for g in new_gaps:
                        if g and g not in accumulated_gaps:
                            accumulated_gaps.append(g)
                    interview.knowledge_gaps = json.dumps(accumulated_gaps)
                    interview.current_difficulty = new_diff

                    new_q = InterviewQuestion(
                        interview_id=interview_id,
                        question_number=next_q_num,
                        question_text=q_text,
                        category=voice_res.get("category", interview.topic),
                        skill=voice_res.get("skill", interview.topic),
                        difficulty=new_diff,
                        additional_instruction=voice_res.get("additional_instruction"),
                        adaptation_reason=adaptation_reason,
                        adaptive_action=adaptive_action,
                        assessment_objective=assessment_objective,
                        is_follow_up=is_fu,
                        parent_question_id=question.id if is_fu else None
                    )
                    conversational_prelude = voice_res.get("conversational_prelude")
                    new_q.spoken_intro = conversational_prelude
                else:
                    adaptive_res = await AIService.generate_next_adaptive_question(
                        target_role=interview.target_role,
                        experience_level=interview.experience_level,
                        topic=interview.topic,
                        interview_type=interview.interview_type,
                        previous_question_text=question.question_text,
                        candidate_answer=answer_text,
                        overall_score=evaluation.overall_score,
                        previous_difficulty=question.difficulty,
                        next_question_number=next_q_num,
                        all_previous_questions=all_prev,
                        job_description=interview.job_description,
                        skills=skills_list,
                        additional_instructions=interview.additional_instructions,
                        evaluation_result=nested_evaluation,
                        knowledge_gaps=accumulated_gaps,
                        recent_history=recent_history,
                        remaining_questions=interview.num_questions - question.question_number,
                        resume_text=interview.resume_text,
                        consecutive_strong_count=consecutive_strong,
                        consecutive_weak_count=consecutive_weak
                    )

                    adaptive_action = adaptive_res.get("adaptive_action") or adaptive_res.get("action") or "NEXT_TOPIC"
                    assessment_objective = adaptive_res.get("assessment_objective") or f"Assess mastery in {adaptive_res.get('skill', interview.topic)}."
                    is_fu = bool(adaptive_res.get("is_follow_up", False) or adaptive_action in ("FOLLOW_UP", "CLARIFY"))
                    new_diff = adaptive_res.get("updated_difficulty") or adaptive_res.get("difficulty") or question.difficulty
                    adaptation_reason = adaptive_res.get("decision_rationale") or adaptive_res.get("adaptation_reason")
                    q_text = adaptive_res.get("next_question") or adaptive_res.get("question") or "Please elaborate on your technical solution."
                    conversational_prelude = adaptive_res.get("conversational_prelude")

                    # Update knowledge gaps
                    new_gaps = adaptive_res.get("identified_knowledge_gaps") or adaptive_res.get("new_knowledge_gaps", [])
                    for g in new_gaps:
                        if g and g not in accumulated_gaps:
                            accumulated_gaps.append(g)
                    interview.knowledge_gaps = json.dumps(accumulated_gaps)
                    interview.current_difficulty = new_diff

                    new_q = InterviewQuestion(
                        interview_id=interview_id,
                        question_number=next_q_num,
                        question_text=q_text,
                        category=adaptive_res.get("category", interview.topic),
                        skill=adaptive_res.get("skill", interview.topic),
                        difficulty=new_diff,
                        additional_instruction=adaptive_res.get("additional_instruction"),
                        adaptation_reason=adaptation_reason,
                        adaptive_action=adaptive_action,
                        assessment_objective=assessment_objective,
                        is_follow_up=is_fu,
                        parent_question_id=question.id if is_fu else None
                    )
                    new_q.spoken_intro = conversational_prelude

                db.add(new_q)
                db.commit()
                db.refresh(new_q)
                db.refresh(interview)
                existing_next_q = new_q
        else:
            # Final question completed: compute total score and complete interview
            final_score = InterviewService.calculate_interview_final_score(db, interview_id)
            interview.status = "completed"
            db.commit()
            db.refresh(interview)
            logger.info(f"Interview {interview_id} completed via final answer submission. Final score: {final_score}%")

        return InterviewService._build_answer_response(
            interview=interview,
            question=question,
            answer=answer,
            evaluation=evaluation,
            next_q=existing_next_q,
            is_last=is_last,
            user_id=user.id,
            conversational_prelude=conversational_prelude
        )

    @staticmethod
    async def skip_question(
        db: Session,
        interview_id: str,
        user_id: str,
        question_id: Optional[str] = None
    ) -> Dict[str, Any]:
        interview = InterviewService.get_interview(db, interview_id, user_id)
        
        questions = db.query(InterviewQuestion).filter(
            InterviewQuestion.interview_id == interview_id
        ).order_by(InterviewQuestion.question_number.asc()).all()

        if not questions:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interview contains no questions to skip.")

        # Identify target question to skip
        target_q = None
        if question_id:
            target_q = next((q for q in questions if q.id == question_id), None)

        if not target_q:
            # Find the active unanswered and unskipped question
            answered_q_ids = {
                ans.question_id for ans in db.query(Answer.question_id).filter(Answer.interview_id == interview_id).all()
            }
            unanswered = [q for q in questions if q.id not in answered_q_ids and not getattr(q, "is_skipped", False)]
            target_q = unanswered[0] if unanswered else questions[-1]

        # Mark question as skipped in database
        target_q.is_skipped = True
        db.commit()
        db.refresh(target_q)

        # Check if the skipped question is the last question in the interview
        is_last = (target_q.question_number >= interview.num_questions)

        if is_last:
            # Transition to interview completion
            final_score = InterviewService.calculate_interview_final_score(db, interview_id)
            interview.status = "completed"
            db.commit()
            db.refresh(interview)
            logger.info(f"Interview {interview_id} completed via skip_question. Final score: {final_score}%")

            return {
                "status": "completed",
                "interview_completed": True,
                "total_score": interview.total_score,
                "final_score": interview.total_score,
                "skipped_question_id": target_q.id,
                "next_question": None,
                "id": None,
                "question": None,
                "question_text": None,
                "message": "All interview questions completed."
            }

        next_q_num = target_q.question_number + 1

        # Check if a question for next_q_num was already created (e.g. duplicate click)
        existing_next_q = db.query(InterviewQuestion).filter(
            InterviewQuestion.interview_id == interview_id,
            InterviewQuestion.question_number == next_q_num
        ).first()

        is_adaptive = getattr(interview, "is_adaptive", True)
        if is_adaptive is None:
            is_adaptive = True

        if existing_next_q:
            new_q = existing_next_q
        elif not is_adaptive:
            interview.status = "completed"
            db.commit()
            return {
                "status": "completed",
                "interview_completed": True,
                "skipped_question_id": target_q.id,
                "next_question": None,
                "id": None,
                "question": None,
                "question_text": None,
                "message": "All interview questions completed."
            }
        else:
            all_prev = [q.question_text for q in questions]
            skills_list = [s.strip() for s in (interview.skills or "").split(",") if s.strip()]

            adaptive_res = await AIService.generate_next_adaptive_question(
                target_role=interview.target_role,
                experience_level=interview.experience_level,
                topic=interview.topic,
                interview_type=interview.interview_type,
                previous_question_text=target_q.question_text,
                candidate_answer="Candidate passed / skipped this question.",
                overall_score=70.0,
                previous_difficulty=target_q.difficulty or "Medium",
                next_question_number=next_q_num,
                all_previous_questions=all_prev,
                job_description=interview.job_description,
                skills=skills_list,
                additional_instructions=interview.additional_instructions
            )

            q_text = adaptive_res.get("next_question") or adaptive_res.get("question") or "Next interview question."
            new_diff = adaptive_res.get("updated_difficulty") or adaptive_res.get("difficulty") or target_q.difficulty or "Medium"
            reason = adaptive_res.get("decision_rationale") or adaptive_res.get("adaptation_reason", "Candidate passed previous question; shifting focus to next topic area.")

            new_q = InterviewQuestion(
                interview_id=interview_id,
                question_number=next_q_num,
                question_text=q_text,
                category=adaptive_res.get("category", target_q.category or "General"),
                skill=adaptive_res.get("skill", target_q.skill or "Core Knowledge"),
                difficulty=new_diff,
                additional_instruction=adaptive_res.get("additional_instruction"),
                adaptation_reason=reason,
                adaptive_action="NEXT_TOPIC",
                assessment_objective=adaptive_res.get("assessment_objective", "Evaluate practical concepts in adjacent topic after candidate skip."),
                is_follow_up=False,
                is_skipped=False,
                parent_question_id=None
            )
            db.add(new_q)
            db.commit()
            db.refresh(new_q)

        next_question_dict = {
            "id": new_q.id,
            "interview_id": new_q.interview_id,
            "question_number": new_q.question_number,
            "question_text": new_q.question_text,
            "question": new_q.question_text,
            "category": new_q.category,
            "topic": new_q.category or new_q.skill or interview.topic,
            "skill": new_q.skill,
            "difficulty": new_q.difficulty,
            "question_type": "Technical",
            "expected_points": [new_q.adaptation_reason] if new_q.adaptation_reason else [],
            "additional_instruction": new_q.additional_instruction,
            "adaptation_reason": new_q.adaptation_reason,
            "adaptive_action": getattr(new_q, "adaptive_action", "NEXT_TOPIC") or "NEXT_TOPIC",
            "assessment_objective": getattr(new_q, "assessment_objective", None),
            "is_follow_up": False,
            "is_skipped": False,
            "spoken_intro": "Understood, let's move forward to our next question.",
            "created_at": new_q.created_at.isoformat() if new_q.created_at else ""
        }

        return {
            "status": "in_progress",
            "interview_completed": False,
            "skipped_question_id": target_q.id,
            "next_question": next_question_dict,
            **next_question_dict
        }

    @staticmethod
    def complete_interview(db: Session, interview_id: str, user_id: str) -> Dict[str, Any]:
        interview = InterviewService.get_interview(db, interview_id, user_id)
        
        final_score = InterviewService.calculate_interview_final_score(db, interview_id)
        interview.status = "completed"
        db.commit()
        db.refresh(interview)

        answered_count = db.query(Answer).filter(Answer.interview_id == interview_id).count()
        evaluations_count = db.query(Evaluation).filter(Evaluation.interview_id == interview_id).count()
        logger.info(f"Interview {interview_id} manually completed. Final score: {final_score}% across {evaluations_count} evaluations.")

        return {
            "interview_id": interview.id,
            "status": interview.status,
            "total_score": interview.total_score,
            "final_score": interview.total_score,
            "questions_count": len(interview.questions),
            "answered_count": answered_count,
            "evaluations_count": evaluations_count
        }

    @staticmethod
    async def ask_clarification(
        db: Session,
        interview_id: str,
        question_id: str,
        user: User,
        user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Provides an interviewer hint or clarification for a question during a live session."""
        interview = InterviewService.get_interview(db, interview_id, user.id)
        question = db.query(InterviewQuestion).filter(
            InterviewQuestion.id == question_id,
            InterviewQuestion.interview_id == interview_id
        ).first()
        if not question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in this interview.")

        clarification_res = await AIService.generate_clarification_or_hint(
            target_role=interview.target_role,
            experience_level=interview.experience_level,
            question_text=question.question_text,
            topic=question.category or question.skill or interview.topic,
            user_query=user_query,
            difficulty=question.difficulty
        )

        return {
            "interview_id": interview_id,
            "question_id": question_id,
            "question_number": question.question_number,
            "clarification": clarification_res.get("clarification"),
            "hint": clarification_res.get("hint"),
            "focus_areas": clarification_res.get("focus_areas", [])
        }

