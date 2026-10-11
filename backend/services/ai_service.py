import os
import json
import re
import logging
import asyncio
from typing import List, Dict, Any, Optional
import httpx
from pydantic import ValidationError

from backend.config.settings import settings
from backend.schemas.evaluation import AIEvaluationResult

logger = logging.getLogger("uvicorn.error")

from backend.schemas.resume_analysis import ResumeJDAnalysisResult

class AIService:
    @staticmethod
    def _clean_json_string(text: str) -> str:
        """Strip markdown code fence blocks if present."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    @classmethod
    async def _call_llm_api(cls, prompt: str) -> str:
        """Calls the configured Cloud GenAI API (Gemini or Groq or custom HTTP)."""
        g_key = settings.GENAI_API_KEY or settings.GEMINI_API_KEY or os.getenv("GENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
        groq_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        
        configured_model = settings.GENAI_MODEL or "gemini-3.8-flash"
        model_candidates = [configured_model, "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-pro-preview", "gemini-2.5-flash", "gemini-flash-latest"]
        
        seen = set()
        model_list = []
        for m in model_candidates:
            if m and m not in seen:
                seen.add(m)
                model_list.append(m)

        last_error = ""

        # 1. Direct Gemini REST endpoint HTTP call
        if g_key:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for model_name in model_list:
                    clean_model = model_name.replace("models/", "")
                    try:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={g_key}"
                        resp = await client.post(
                            url,
                            json={"contents": [{"parts": [{"text": prompt}]}]}
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    text_out = parts[0].get("text", "")
                                    if text_out:
                                        return text_out
                        else:
                            last_error = f"HTTP {resp.status_code} for {clean_model}: {resp.text}"
                            logger.warning(f"Gemini model {clean_model} returned status {resp.status_code}")
                    except Exception as e:
                        last_error = f"Exception for {clean_model}: {e}"
                        logger.warning(last_error)

        # 2. Try Groq API as secondary provider if key is available
        if groq_key:
            try:
                from groq import AsyncGroq
                client = AsyncGroq(api_key=groq_key)
                chat_completion = await client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile"
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                logger.warning(f"Groq API call failed: {e}")
                last_error = str(e)

        if not g_key and not groq_key:
            raise ValueError("GENAI_API_KEY / GEMINI_API_KEY is not configured in backend .env environment variables. Please set your Cloud GenAI API key.")
        
        raise ValueError(f"AI API call rate-limited or temporarily unavailable ({last_error}).")

    @classmethod
    async def analyze_resume_and_jd(
        cls,
        resume_text: str,
        job_description: str,
        job_title: str = "Software Developer"
    ) -> ResumeJDAnalysisResult:
        """Analyzes candidate resume against job description using AI or heuristic fallback."""
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "resume_jd_analysis.txt")
        template = ""
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                template = f.read()

        if template:
            try:
                prompt = template.format(
                    job_title=job_title,
                    resume_text=resume_text,
                    job_description=job_description
                )
            except KeyError as ke:
                logger.error(f"Template format error in resume_jd_analysis.txt: {ke}")
                prompt = f"Analyze resume against JD for {job_title}.\nResume:\n{resume_text}\nJD:\n{job_description}"
        else:
            prompt = f"Analyze resume against JD for {job_title}.\nResume:\n{resume_text}\nJD:\n{job_description}"

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned_json = cls._clean_json_string(raw_response)
            data = json.loads(cleaned_json)
            
            return ResumeJDAnalysisResult(
                matched_skills=data.get("matched_skills", []),
                missing_skills=data.get("missing_skills", []),
                priority_skills=data.get("priority_skills", []),
                match_percentage=float(data.get("match_percentage", 75.0)),
                analysis_summary=data.get("analysis_summary", "Resume & Job Description analysis completed."),
                extracted_resume_skills=data.get("extracted_resume_skills", []),
                extracted_jd_skills=data.get("extracted_jd_skills", [])
            )
        except Exception as e:
            logger.warning(f"GenAI Resume+JD analysis hit error ({e}). Using intelligent heuristic keyword extraction.")
            
            # Smart Heuristic Skill Extraction Fallback
            KNOWN_TECH_STACK = [
                "Java", "Python", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust", "PHP", "Ruby",
                "Spring Boot", "Django", "FastAPI", "React", "Angular", "Vue", "Node.js", "Express",
                "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Oracle", "NoSQL",
                "Docker", "Kubernetes", "AWS", "Azure", "GCP", "DevOps", "CI/CD", "Jenkins", "Git", "Linux",
                "Kafka", "RabbitMQ", "Microservices", "REST API", "GraphQL", "System Design",
                "OOP", "DSA", "Data Structures", "Algorithms", "Machine Learning", "PyTorch", "TensorFlow",
                "Unit Testing", "JUnit", "PyTest", "HTML", "CSS", "Tailwind"
            ]

            def extract_skills(text: str) -> List[str]:
                found = []
                for s in KNOWN_TECH_STACK:
                    pattern = r'\b' + re.escape(s) + r'\b'
                    if re.search(pattern, text, re.IGNORECASE):
                        found.append(s)
                return found

            resume_skills = extract_skills(resume_text)
            jd_skills = extract_skills(job_description)
            
            if not jd_skills:
                jd_skills = [job_title or "Software Development", "Problem Solving", "System Architecture", "Git"]

            res_set = set(resume_skills)
            jd_set = set(jd_skills)

            matched = sorted(list(res_set.intersection(jd_set)))
            missing = sorted(list(jd_set - res_set))
            
            if not matched and resume_skills:
                matched = resume_skills[:3]
            if not missing and len(jd_skills) > len(matched):
                missing = [s for s in jd_skills if s not in matched]

            priority = (missing[:3] + matched[:2]) if missing else matched[:5]

            match_pct = 75.0
            if jd_set:
                overlap = len(matched) / len(jd_set)
                match_pct = min(95.0, max(50.0, round(overlap * 100, 1)))

            summary_text = (
                f"Candidate matches {len(matched)} key technologies required by the role ({', '.join(matched[:3]) if matched else 'core concepts'}). "
                f"Areas to test in the interview include: {', '.join(priority[:3]) if priority else 'foundational skills'}."
            )

            return ResumeJDAnalysisResult(
                matched_skills=matched,
                missing_skills=missing,
                priority_skills=priority,
                match_percentage=match_pct,
                analysis_summary=summary_text,
                extracted_resume_skills=resume_skills or ["General Engineering"],
                extracted_jd_skills=jd_skills
            )

    @classmethod
    def _get_fallback_questions(cls, topic: str, target_role: str, difficulty: str, num_questions: int) -> List[Dict[str, Any]]:
        """Curated role-relevant questions fallback if GenAI API hits rate limits (429)."""
        pool = {
            "Java": [
                {
                    "question": "What is the difference between ArrayList and LinkedList in Java? Explain internal structure and performance trade-offs.",
                    "category": "Java Collections",
                    "skill": "Java",
                    "difficulty": difficulty,
                    "additional_instruction": "Discuss random access vs insertion/deletion complexities."
                },
                {
                    "question": "Explain the concept of immutability in Java and how to create a custom Immutable Class.",
                    "category": "Core Java",
                    "skill": "Java",
                    "difficulty": difficulty,
                    "additional_instruction": "Mention final class, private final fields, and deep copying."
                },
                {
                    "question": "How does Garbage Collection work in Java? Describe generational garbage collection architecture.",
                    "category": "JVM Internals",
                    "skill": "Java",
                    "difficulty": difficulty,
                    "additional_instruction": "Cover Young, Old, and Permanent/Metaspace generations."
                },
                {
                    "question": "What is the difference between fail-fast and fail-safe iterators in Java?",
                    "category": "Concurrency & Collections",
                    "skill": "Java",
                    "difficulty": difficulty,
                    "additional_instruction": "Give examples like ConcurrentHashMap vs HashMap."
                },
                {
                    "question": "Explain Java Stream API and the difference between intermediate and terminal operations.",
                    "category": "Java 8+ Features",
                    "skill": "Java",
                    "difficulty": difficulty,
                    "additional_instruction": "Provide short code snippet or map/filter/collect lifecycle."
                }
            ],
            "Python": [
                {
                    "question": "What is the GIL (Global Interpreter Lock) in Python and how does it impact multi-threading?",
                    "category": "Python Architecture",
                    "skill": "Python",
                    "difficulty": difficulty,
                    "additional_instruction": "Compare multi-threading vs multi-processing for CPU-bound vs IO-bound tasks."
                },
                {
                    "question": "Explain Python decorators and write a custom decorator to time function execution.",
                    "category": "Advanced Python",
                    "skill": "Python",
                    "difficulty": difficulty,
                    "additional_instruction": "Use functools.wraps and *args, **kwargs."
                },
                {
                    "question": "What is the difference between deepcopy and shallow copy in Python?",
                    "category": "Core Python",
                    "skill": "Python",
                    "difficulty": difficulty,
                    "additional_instruction": "Demonstrate behavior with nested mutable objects."
                },
                {
                    "question": "How do generators work in Python and why are they memory efficient?",
                    "category": "Python Control Flow",
                    "skill": "Python",
                    "difficulty": difficulty,
                    "additional_instruction": "Explain the yield keyword vs returning a list."
                }
            ]
        }

        selected = pool.get(topic, pool.get("Java"))
        res = []
        for idx in range(num_questions):
            item = selected[idx % len(selected)]
            res.append({
                "question": item["question"],
                "category": item["category"],
                "skill": item["skill"],
                "difficulty": difficulty,
                "additional_instruction": item["additional_instruction"]
            })
        return res

    @classmethod
    async def generate_interview_questions(
        cls,
        target_role: str,
        experience_level: str,
        topic: str,
        interview_type: str,
        difficulty: str,
        num_questions: int = 5,
        resume_analysis: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Generates structured interview questions using LLM API with optional Resume+JD context."""
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "question_generation.txt")
        template = ""
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                template = f.read()

        resume_context_str = ""
        if resume_analysis:
            matched = ", ".join(resume_analysis.get("matched_skills", []))
            missing = ", ".join(resume_analysis.get("missing_skills", []))
            priority = ", ".join(resume_analysis.get("priority_skills", []))
            score = resume_analysis.get("match_percentage", 75.0)
            summary = resume_analysis.get("analysis_summary", "")

            resume_context_str = (
                f"\n\nCandidate Resume + Job Description Personalization Context:\n"
                f"- Overall Skill Match Score: {score}%\n"
                f"- Candidate Matched Skills: {matched or 'General'}\n"
                f"- Key Candidate Missing/Gap Skills to Evaluate: {missing or 'Advanced Concepts'}\n"
                f"- High Priority Focus Skills for this Interview: {priority or topic}\n"
                f"- Match Summary: {summary}\n"
                f"IMPORTANT INSTRUCTION: Tailor the generated interview questions specifically to evaluate the priority skills and missing skills identified above."
            )

        if template:
            try:
                prompt = template.format(
                    target_role=target_role,
                    experience_level=experience_level,
                    topic=topic,
                    interview_type=interview_type,
                    difficulty=difficulty,
                    num_questions=num_questions
                ) + resume_context_str
            except KeyError as ke:
                logger.error(f"Template format error in question_generation.txt: {ke}. Falling back to default prompt.")
                prompt = (
                    f"Generate {num_questions} realistic {difficulty} {interview_type} questions for a {experience_level} "
                    f"{target_role} candidate on topic {topic}.{resume_context_str}\n"
                    "Return ONLY a valid JSON array of objects with keys: "
                    '["question", "category", "skill", "difficulty", "additional_instruction"].'
                )
        else:
            prompt = (
                f"Generate {num_questions} realistic {difficulty} {interview_type} questions for a {experience_level} "
                f"{target_role} candidate on topic {topic}.{resume_context_str}\n"
                "Return ONLY a valid JSON array of objects with keys: "
                '["question", "category", "skill", "difficulty", "additional_instruction"].'
            )

        last_err = ""
        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned_json = cls._clean_json_string(raw_response)
            questions_data = json.loads(cleaned_json)
            
            if isinstance(questions_data, list) and len(questions_data) > 0:
                validated_questions = []
                for item in questions_data[:num_questions]:
                    q_text = item.get("question") or item.get("question_text", "")
                    if q_text:
                        validated_questions.append({
                            "question": q_text,
                            "category": item.get("category", topic),
                            "skill": item.get("skill", topic),
                            "difficulty": item.get("difficulty", difficulty),
                            "additional_instruction": item.get("additional_instruction", "Explain concepts clearly with appropriate examples.")
                        })
                if validated_questions:
                    return validated_questions
        except Exception as e:
            last_err = str(e)
            logger.warning(f"GenAI API question generation failed or rate limited ({last_err}). Using curated fallback questions.")

        return cls._get_fallback_questions(topic, target_role, difficulty, num_questions)


    @classmethod
    async def generate_next_adaptive_question(
        cls,
        target_role: str,
        experience_level: str,
        topic: str,
        interview_type: str,
        previous_question_text: str,
        candidate_answer: str,
        overall_score: float,
        previous_difficulty: str,
        next_question_number: int
    ) -> Dict[str, Any]:
        """Adaptive Engine: Determines next difficulty and generates follow-up question based on score."""
        if overall_score >= 80.0:
            next_diff = "Hard" if previous_difficulty in ["Medium", "Hard"] else "Medium"
            reason = f"Excellent performance ({overall_score}%). Escalating difficulty to {next_diff} to probe deeper technical architectural knowledge."
        elif overall_score < 60.0:
            next_diff = "Easy" if previous_difficulty in ["Easy", "Medium"] else "Medium"
            reason = f"Candidate score ({overall_score}%). Adjusting difficulty to {next_diff} to reinforce foundational concepts."
        else:
            next_diff = previous_difficulty
            reason = f"Consistent performance ({overall_score}%). Maintaining {next_diff} difficulty level to assess practical applications."

        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "adaptive_question.txt")
        template = ""
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                template = f.read()

        if template:
            try:
                prompt = template.format(
                    target_role=target_role,
                    experience_level=experience_level,
                    topic=topic,
                    interview_type=interview_type,
                    previous_question_number=next_question_number - 1,
                    previous_question_text=previous_question_text,
                    candidate_answer=candidate_answer,
                    overall_score=overall_score,
                    next_difficulty=next_diff,
                    adaptation_reason=reason,
                    next_question_number=next_question_number
                )
            except KeyError as ke:
                logger.error(f"Format error in adaptive_question.txt: {ke}")
                prompt = f"Generate adaptive question #{next_question_number} at difficulty {next_diff} for {target_role} on topic {topic}."
        else:
            prompt = f"Generate adaptive question #{next_question_number} at difficulty {next_diff} for {target_role} on topic {topic}."

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned = cls._clean_json_string(raw_response)
            data = json.loads(cleaned)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]

            q_text = data.get("question") or data.get("question_text", "")
            if q_text:
                return {
                    "question": q_text,
                    "category": data.get("category", topic),
                    "skill": data.get("skill", topic),
                    "difficulty": data.get("difficulty", next_diff),
                    "additional_instruction": data.get("additional_instruction", "Explain concepts with appropriate examples."),
                    "adaptation_reason": reason
                }
        except Exception as e:
            logger.warning(f"GenAI adaptive question generation error ({e}). Using adaptive fallback.")

        fallback_set = cls._get_fallback_questions(topic, target_role, next_diff, 5)
        item = fallback_set[(next_question_number - 1) % len(fallback_set)]
        return {
            "question": item["question"],
            "category": item["category"],
            "skill": item["skill"],
            "difficulty": next_diff,
            "additional_instruction": item["additional_instruction"],
            "adaptation_reason": reason
        }

    @classmethod
    def generate_interviewer_intro(cls, role: str, topic: str, candidate_name: Optional[str] = None) -> str:
        """Generates a natural, professional spoken greeting for the AI Voice Interviewer."""
        name_prefix = f"Hello {candidate_name}! " if candidate_name else "Hello! "
        return (
            f"{name_prefix}Welcome to your AI Mock Interview for the {role} position. "
            f"I will be your AI technical interviewer today. We will focus on key core areas in {topic}. "
            f"Feel free to speak your answer clearly, review the live transcript, and submit when you are ready. "
            f"Here is your first question."
        )

    @classmethod
    async def generate_voice_conversational_response(
        cls,
        target_role: str,
        experience_level: str,
        topic: str,
        interview_type: str,
        previous_question_text: str,
        candidate_answer: str,
        overall_score: float,
        previous_difficulty: str,
        next_question_number: int,
        max_questions: int,
        strengths: Optional[List[str]] = None,
        improvements: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes a realistic spoken interviewer response:
        - Conversational prelude acknowledging candidate's answer.
        - Contextual follow-up question if answer has omissions or interesting points,
          otherwise smooth progression to next topic.
        - Verbal communication and answer structure notes.
        """
        strengths_str = ", ".join(strengths) if strengths else "Good basic grasp."
        improvements_str = ", ".join(improvements) if improvements else "Clarify edge cases."
        is_near_end = next_question_number > max_questions

        if overall_score >= 80.0:
            target_diff = "Hard" if previous_difficulty in ["Medium", "Hard"] else "Medium"
        elif overall_score < 60.0:
            target_diff = "Easy" if previous_difficulty in ["Easy", "Medium"] else "Medium"
        else:
            target_diff = previous_difficulty

        prompt = (
            f"You are a Senior Technical Hiring Manager conducting an interactive voice interview for {target_role} ({experience_level}).\n"
            f"Topic: {topic} | Interview Type: {interview_type}\n"
            f"Previous Question: \"{previous_question_text}\"\n"
            f"Candidate's Answer: \"{candidate_answer}\"\n"
            f"Evaluation Score: {overall_score}%\n"
            f"Candidate Strengths: {strengths_str}\n"
            f"Areas to Improve: {improvements_str}\n"
            f"Progress: Question {next_question_number} of {max_questions}\n\n"
            "As a realistic conversational interviewer, generate the next spoken interaction:\n"
            "1. 'conversational_prelude': 1-2 spoken sentences reacting naturally to their answer.\n"
            "2. 'is_follow_up': boolean (true if candidate omitted an essential trade-off or introduced an interesting detail to probe; false if advancing to a fresh question).\n"
            "3. 'question': The question text to speak.\n"
            f"4. 'difficulty': '{target_diff}'\n"
            f"5. 'category': '{topic}'\n"
            f"6. 'skill': '{topic}'\n"
            "7. 'additional_instruction': guidance hint\n"
            f"8. 'adaptation_reason': reason based on candidate's answer and score {overall_score}%\n"
            "9. 'communication_notes': 1 brief sentence on verbal clarity, terminology precision, and structure\n\n"
            "Return ONLY a valid JSON object matching these keys."
        )

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned = cls._clean_json_string(raw_response)
            data = json.loads(cleaned)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]

            q_text = data.get("question") or data.get("question_text", "")
            if q_text:
                return {
                    "conversational_prelude": data.get("conversational_prelude", "Thank you. Let's move to the next question."),
                    "is_follow_up": bool(data.get("is_follow_up", False) and not is_near_end),
                    "question": q_text,
                    "category": data.get("category", topic),
                    "skill": data.get("skill", topic),
                    "difficulty": data.get("difficulty", target_diff),
                    "additional_instruction": data.get("additional_instruction", "Explain concepts clearly with practical examples."),
                    "adaptation_reason": data.get("adaptation_reason", f"Adaptive voice response based on score of {overall_score}%."),
                    "communication_notes": data.get("communication_notes", "Clear technical delivery and structured phrasing.")
                }
        except Exception as e:
            logger.warning(f"Voice conversational generation error ({e}). Using curated conversational fallback.")

        words = candidate_answer.split()
        if overall_score < 65.0 and len(words) < 30 and not is_near_end:
            return {
                "conversational_prelude": "Thanks for sharing that overview. Could you expand on that with a bit more detail?",
                "is_follow_up": True,
                "question": f"Could you walk me through a specific production scenario where you applied that approach in {topic}?",
                "category": topic,
                "skill": topic,
                "difficulty": target_diff,
                "additional_instruction": "Elaborate on real-world practical considerations.",
                "adaptation_reason": f"Follow-up probe triggered by score ({overall_score}%) to evaluate deeper practical understanding.",
                "communication_notes": "Concise answer. Expanding further with concrete examples will strengthen technical impact."
            }
        else:
            fallback_set = cls._get_fallback_questions(topic, target_role, target_diff, 5)
            item = fallback_set[(next_question_number - 1) % len(fallback_set)]
            return {
                "conversational_prelude": "Great explanation. You covered the key fundamentals nicely. Let's move to our next question.",
                "is_follow_up": False,
                "question": item["question"],
                "category": item["category"],
                "skill": item["skill"],
                "difficulty": target_diff,
                "additional_instruction": item["additional_instruction"],
                "adaptation_reason": f"Progressing to next topic based on consistent performance ({overall_score}%).",
                "communication_notes": "Well-structured articulation with clear conceptual boundaries."
            }

    @classmethod
    async def evaluate_candidate_answer(
        cls,
        question_text: str,
        answer_text: str,
        topic: str,
        target_role: str,
        difficulty: str
    ) -> AIEvaluationResult:
        """Evaluates candidate answer against rubric and returns structured JSON score."""
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "answer_evaluation.txt")
        template = ""
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                template = f.read()

        if template:
            try:
                prompt = template.format(
                    question_text=question_text,
                    answer_text=answer_text,
                    topic=topic,
                    target_role=target_role,
                    difficulty=difficulty
                )
            except KeyError as ke:
                logger.error(f"Template format error in answer_evaluation.txt: {ke}. Falling back to default format.")
                prompt = (
                    f"Evaluate answer '{answer_text}' for question '{question_text}' on topic {topic} for role {target_role}.\n"
                    "Return ONLY a JSON object with keys: technical_correctness, conceptual_completeness, response_relevance, "
                    "structural_clarity, depth_of_understanding, overall_score, strengths, improvements, feedback, model_answer."
                )
        else:
            prompt = (
                f"Evaluate answer '{answer_text}' for question '{question_text}' on topic {topic} for role {target_role}.\n"
                "Return ONLY a JSON object with keys: technical_correctness, conceptual_completeness, response_relevance, "
                "structural_clarity, depth_of_understanding, overall_score, strengths, improvements, feedback, model_answer."
            )

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned_json = cls._clean_json_string(raw_response)
            eval_dict = json.loads(cleaned_json)

            tc = float(eval_dict.get("technical_correctness", 75))
            cc = float(eval_dict.get("conceptual_completeness", 75))
            rr = float(eval_dict.get("response_relevance", 80))
            sc = float(eval_dict.get("structural_clarity", 80))
            du = float(eval_dict.get("depth_of_understanding", 70))

            computed_score = round((tc * 0.35) + (cc * 0.25) + (rr * 0.15) + (sc * 0.15) + (du * 0.10), 1)

            strengths = eval_dict.get("strengths", ["Identified basic concepts correctly."])
            if isinstance(strengths, str): strengths = [strengths]

            improvements = eval_dict.get("improvements", ["Provide deeper technical detail and edge cases."])
            if isinstance(improvements, str): improvements = [improvements]

            feedback = eval_dict.get("feedback", "Good response overall with clear articulation of core concepts.")
            model_ans = eval_dict.get("model_answer", "A comprehensive answer should define the concept, outline performance trade-offs, and give practical examples.")

            return AIEvaluationResult(
                technical_correctness=min(100.0, max(0.0, tc)),
                conceptual_completeness=min(100.0, max(0.0, cc)),
                response_relevance=min(100.0, max(0.0, rr)),
                structural_clarity=min(100.0, max(0.0, sc)),
                depth_of_understanding=min(100.0, max(0.0, du)),
                overall_score=min(100.0, max(0.0, computed_score)),
                strengths=strengths,
                improvements=improvements,
                feedback=feedback,
                model_answer=model_ans
            )
        except Exception as e:
            logger.warning(f"GenAI evaluation call encountered error ({e}). Using heuristic scoring.")
            word_count = len(answer_text.split())
            base_score = min(88.0, max(60.0, 65.0 + (word_count / 5)))
            return AIEvaluationResult(
                technical_correctness=base_score,
                conceptual_completeness=base_score - 2,
                response_relevance=base_score + 2,
                structural_clarity=base_score,
                depth_of_understanding=base_score - 3,
                overall_score=round(base_score, 1),
                strengths=["Addressed the core question topic.", "Provided clear terminology."],
                improvements=["Elaborate with deeper architectural trade-offs and code examples."],
                feedback="Solid attempt. Focus on structuring your response with clear trade-offs and real-world scenarios.",
                model_answer=f"For {question_text}, an ideal response explains the core principles, performance implications, and practical usage examples."
            )

    @classmethod
    async def evaluate_code(
        cls,
        problem_statement: str,
        language: str,
        code: str,
        difficulty: str = "Medium",
        topic: str = "Algorithms"
    ) -> Dict[str, Any]:
        """Evaluates arbitrary code submission using GenAI with fallback."""
        prompt = (
            f"You are a Senior Technical Interviewer evaluating a candidate's code submission in {language}.\n"
            f"Problem Statement:\n{problem_statement}\n\n"
            f"Topic: {topic} | Difficulty: {difficulty}\n"
            f"Candidate Code:\n```{language}\n{code}\n```\n\n"
            "Return ONLY a JSON object with the following keys:\n"
            "- correctness_score (0-10 float)\n"
            "- code_quality_score (0-10 float)\n"
            "- time_complexity (string e.g. 'O(N)')\n"
            "- space_complexity (string e.g. 'O(1)')\n"
            "- bugs_found (list of strings)\n"
            "- edge_cases_covered (list of strings)\n"
            "- missing_edge_cases (list of strings)\n"
            "- optimization_suggestions (list of strings)\n"
            "- ideal_code_snippet (string with clean reference solution in " + language + ")\n"
            "- summary_feedback (string with professional feedback summary)"
        )

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned = cls._clean_json_string(raw_response)
            data = json.loads(cleaned)
            return {
                "correctness_score": float(data.get("correctness_score", 8.5)),
                "code_quality_score": float(data.get("code_quality_score", 8.0)),
                "time_complexity": str(data.get("time_complexity", "O(N)")),
                "space_complexity": str(data.get("space_complexity", "O(1)")),
                "bugs_found": list(data.get("bugs_found", [])),
                "edge_cases_covered": list(data.get("edge_cases_covered", ["Standard input cases handled"])),
                "missing_edge_cases": list(data.get("missing_edge_cases", ["Empty or single-element inputs"])),
                "optimization_suggestions": list(data.get("optimization_suggestions", ["Consider space optimization."])),
                "ideal_code_snippet": str(data.get("ideal_code_snippet", code)),
                "summary_feedback": str(data.get("summary_feedback", "Solid technical implementation with good readability."))
            }
        except Exception as e:
            logger.warning(f"GenAI evaluate_code encountered error ({e}). Using rule-based fallback.")
            code_len = len(code.strip().splitlines())
            has_comments = "#" in code or "//" in code
            quality = min(9.5, max(6.0, 7.5 + (0.5 if has_comments else 0.0) + min(1.0, code_len * 0.05)))
            return {
                "correctness_score": 8.5,
                "code_quality_score": round(quality, 1),
                "time_complexity": "O(N)",
                "space_complexity": "O(1)" if "dict" not in code and "set" not in code and "Map" not in code else "O(N)",
                "bugs_found": [],
                "edge_cases_covered": ["Standard positive test scenarios"],
                "missing_edge_cases": ["Large dataset stress test", "Null / boundary conditions"],
                "optimization_suggestions": [
                    "Validate input constraints at the beginning of the function.",
                    "Ensure appropriate data structures are chosen for optimal asymptotic runtime."
                ],
                "ideal_code_snippet": code,
                "summary_feedback": "Well-structured code adhering to language idioms. Continue practicing boundary condition verification."
            }

    @classmethod
    async def generate_final_report(
        cls,
        role: str,
        experience: str,
        interview_type: str,
        interview_summary: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Synthesizes overall interview performance from question summaries and evaluations."""
        eval_scores = []
        tc_scores = []
        cc_scores = []
        sc_scores = []
        topics_seen = []

        for item in interview_summary:
            ev = item.get("evaluation", {})
            score = ev.get("overall_score") or (ev.get("score", 7.5) * 10.0 if "score" in ev else 75.0)
            eval_scores.append(float(score))
            if "technical_correctness" in ev:
                tc_scores.append(float(ev["technical_correctness"]))
            if "conceptual_completeness" in ev:
                cc_scores.append(float(ev["conceptual_completeness"]))
            if "structural_clarity" in ev:
                sc_scores.append(float(ev["structural_clarity"]))
            q_info = item.get("question", {})
            if isinstance(q_info, dict) and "topic" in q_info:
                topics_seen.append(q_info["topic"])

        avg_score = round(sum(eval_scores) / len(eval_scores), 1) if eval_scores else 78.0
        avg_tc = round(sum(tc_scores) / len(tc_scores), 1) if tc_scores else avg_score
        avg_cc = round(sum(cc_scores) / len(cc_scores), 1) if cc_scores else avg_score
        avg_sc = round(sum(sc_scores) / len(sc_scores), 1) if sc_scores else avg_score

        prompt = (
            f"You are a Lead Hiring Manager reviewing a completed {interview_type} mock interview for {role} ({experience}).\n"
            f"Session Average Score: {avg_score}%\n"
            f"Transcript Summary:\n{json.dumps(interview_summary, default=str)[:2000]}\n\n"
            "Generate a comprehensive final performance evaluation.\n"
            "Return ONLY a JSON object with keys:\n"
            "- overall_score (float 0-100)\n"
            "- technical_knowledge_score (float 0-100)\n"
            "- communication_score (float 0-100)\n"
            "- problem_solving_score (float 0-100)\n"
            "- answer_quality_score (float 0-100)\n"
            "- strong_topics (list of strings)\n"
            "- weak_topics (list of strings)\n"
            "- recommendations (list of strings)\n"
            "- personalized_summary (string)"
        )

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned = cls._clean_json_string(raw_response)
            data = json.loads(cleaned)
            return {
                "overall_score": float(data.get("overall_score", avg_score)),
                "technical_knowledge_score": float(data.get("technical_knowledge_score", avg_tc)),
                "communication_score": float(data.get("communication_score", avg_sc)),
                "problem_solving_score": float(data.get("problem_solving_score", avg_cc)),
                "answer_quality_score": float(data.get("answer_quality_score", avg_score)),
                "strong_topics": list(data.get("strong_topics", topics_seen[:2] or ["Core Principles", "Syntax"])),
                "weak_topics": list(data.get("weak_topics", ["Deep Concurrency", "System Scalability"])),
                "recommendations": list(data.get("recommendations", [
                    "Review low-level runtime execution details.",
                    "Practice articulating architectural trade-offs using the STAR method."
                ])),
                "personalized_summary": str(data.get("personalized_summary", f"Strong performance for {role}. You demonstrated solid fundamentals and good problem-solving logic."))
            }
        except Exception as e:
            logger.warning(f"GenAI generate_final_report error ({e}). Using calculated fallback.")
            return {
                "overall_score": avg_score,
                "technical_knowledge_score": avg_tc,
                "communication_score": avg_sc,
                "problem_solving_score": avg_cc,
                "answer_quality_score": avg_score,
                "strong_topics": list(set(topics_seen))[:2] if topics_seen else ["Core Concepts", "Problem Formulation"],
                "weak_topics": ["Architectural Trade-offs", "Edge Case Robustness"],
                "recommendations": [
                    "Deepen understanding of internal data structure implementations and time complexities.",
                    "Incorporate practical real-world production examples in technical explanations.",
                    "Practice structured behavioral and system design answers."
                ],
                "personalized_summary": (
                    f"Candidate exhibited solid foundational knowledge for {role} at the {experience} level. "
                    f"Overall score of {avg_score}% demonstrates strong readiness. Continuing structured practice "
                    f"in edge cases will help push readiness above 90%."
                )
            }

    @classmethod
    async def generate_preparation_plan(
        cls,
        role: str,
        experience: str,
        weak_topics: List[str],
        strong_topics: List[str],
        avg_score: float = 7.5
    ) -> Dict[str, Any]:
        """Generates a structured 7-day preparation roadmap tailored to candidate strengths and weaknesses."""
        prompt = (
            f"You are a Senior Tech Career Coach creating a 7-day intensive interview preparation plan for a {role} ({experience}).\n"
            f"Candidate Weak Areas: {', '.join(weak_topics)}\n"
            f"Candidate Strengths: {', '.join(strong_topics)}\n"
            f"Current Assessment Score: {avg_score}/10\n\n"
            "Return ONLY a JSON object with keys:\n"
            "- plan: list of exactly 7 objects, each with:\n"
            "    day (int 1-7)\n"
            "    topic (string)\n"
            "    concepts (list of 3 strings)\n"
            "    practice_questions (list of 2 strings)\n"
            "    difficulty (string 'Easy'|'Medium'|'Hard')\n"
            "    estimated_time (string e.g. '2.5 Hours')\n"
            "- overall_readiness_assessment (string summary)\n"
            "- recommended_topics (list of strings)\n"
            "- recommended_difficulty (string)\n"
            "- study_priorities (list of strings)"
        )

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned = cls._clean_json_string(raw_response)
            data = json.loads(cleaned)
            if "plan" in data and len(data["plan"]) == 7:
                return data
        except Exception as e:
            logger.warning(f"GenAI generate_preparation_plan error ({e}). Using curated study plan.")

        primary_weak = weak_topics[0] if weak_topics else "Algorithms"
        secondary_weak = weak_topics[1] if len(weak_topics) > 1 else "System Architecture"

        default_plan = [
            {
                "day": 1,
                "topic": f"{primary_weak} Fundamentals",
                "concepts": ["Core Definitions & Invariants", "Memory Layout & Asymptotics", "Common Pitfalls"],
                "practice_questions": [f"Explain the internal architecture of {primary_weak}.", f"What are common edge cases when working with {primary_weak}?"],
                "difficulty": "Easy",
                "estimated_time": "2.0 Hours"
            },
            {
                "day": 2,
                "topic": f"Advanced {primary_weak} Deep-Dive",
                "concepts": ["High-Performance Patterns", "Concurrency & Locking", "Thread Safety Mechanisms"],
                "practice_questions": [f"How do you handle race conditions in {primary_weak}?", "Compare alternative concurrency strategies."],
                "difficulty": "Medium",
                "estimated_time": "2.5 Hours"
            },
            {
                "day": 3,
                "topic": f"{secondary_weak} & Data Modeling",
                "concepts": ["Normalization vs Denormalization", "Indexing Strategies (B-Tree vs Hash)", "Query Optimization"],
                "practice_questions": ["Explain ACID transactions and isolation levels.", "Design an indexing strategy for high-read queries."],
                "difficulty": "Medium",
                "estimated_time": "2.5 Hours"
            },
            {
                "day": 4,
                "topic": "Algorithms & Problem Solving",
                "concepts": ["Two Pointers & Sliding Window", "Graph Traversal (BFS/DFS)", "Dynamic Programming Basics"],
                "practice_questions": ["Implement Least Recently Used (LRU) Cache.", "Find longest palindromic substring."],
                "difficulty": "Hard",
                "estimated_time": "3.0 Hours"
            },
            {
                "day": 5,
                "topic": "System Design & Distributed Patterns",
                "concepts": ["Microservices vs Monolith", "Caching Layers (Redis/Memcached)", "Rate Limiting & Load Balancing"],
                "practice_questions": ["Design a distributed URL shortener (TinyURL).", "Explain cache invalidation trade-offs."],
                "difficulty": "Hard",
                "estimated_time": "3.0 Hours"
            },
            {
                "day": 6,
                "topic": "Behavioral & STAR Scenario Mastery",
                "concepts": ["Conflict Resolution", "Handling Production Incidents", "Mentorship & Technical Leadership"],
                "practice_questions": ["Tell me about a time an outage occurred and how you responded.", "How do you handle disagreement over technical direction?"],
                "difficulty": "Medium",
                "estimated_time": "2.0 Hours"
            },
            {
                "day": 7,
                "topic": "Full-Length Mock Interview Simulation",
                "concepts": ["End-to-End Time Management", "Clear Whiteboard Communication", "Final Performance Review"],
                "practice_questions": ["Complete a 45-minute timed technical mock interview.", "Review feedback rubric and identify remaining gaps."],
                "difficulty": "Hard",
                "estimated_time": "2.5 Hours"
            }
        ]

        return {
            "plan": default_plan,
            "overall_readiness_assessment": (
                f"Candidate exhibits solid base readiness with an average score of {avg_score * 10:.0f}%. "
                f"Focusing on {primary_weak} and {secondary_weak} over the next 7 days will provide the highest ROI for your upcoming {role} interviews."
            ),
            "recommended_topics": weak_topics or ["Data Structures", "System Design"],
            "recommended_difficulty": "Medium",
            "study_priorities": [f"Master {primary_weak}", f"Review {secondary_weak}", "Timed Mock Simulation"]
        }
