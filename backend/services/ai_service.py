import os
import json
import re
import time
import logging
import asyncio
import hashlib
from typing import List, Dict, Any, Optional
import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError

from backend.config.settings import settings
from backend.schemas.evaluation import (
    AIEvaluationResult,
    AdaptiveAction,
    AdaptiveDecision,
    _normalize_to_str,
    _normalize_to_str_list
)
from backend.schemas.resume_analysis import ResumeJDAnalysisResult

logger = logging.getLogger("uvicorn.error")

class AIService:
    @staticmethod
    def _clean_json_string(text: str) -> str:
        """Extract and clean valid JSON string from markdown code fence blocks or text."""
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    _in_flight_tasks: Dict[str, asyncio.Task] = {}
    _in_flight_lock: Optional[asyncio.Lock] = None
    _shared_client: Optional[httpx.AsyncClient] = None
    _model_cooldowns: Dict[str, float] = {}
    _model_daily_quota_info: Dict[str, Dict[str, Any]] = {}
    _last_successful_model: Optional[str] = None

    @classmethod
    def _get_http_client(cls) -> httpx.AsyncClient:
        """Returns shared AsyncClient with HTTP connection pooling to avoid TLS handshake per request."""
        if cls._shared_client is None or cls._shared_client.is_closed:
            cls._shared_client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=25.0, write=5.0, pool=30.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=40, keepalive_expiry=60.0)
            )
        return cls._shared_client

    @classmethod
    def reset_model_state(cls) -> None:
        """Resets cached model health and cooldowns (used by test suites)."""
        cls._model_cooldowns.clear()
        cls._last_successful_model = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        if cls._in_flight_lock is None:
            cls._in_flight_lock = asyncio.Lock()
        return cls._in_flight_lock

    @classmethod
    def _parse_gemini_error(
        cls,
        resp_status: int,
        data: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Parses Google Gemini REST API error response for daily quota vs transient rate limits."""
        if headers is None:
            headers = {}
        err_obj = data.get("error", {}) if isinstance(data, dict) else {}
        err_msg = err_obj.get("message", "")
        details = err_obj.get("details", []) if isinstance(err_obj, dict) else []

        retry_delay_sec: Optional[float] = None
        is_daily_quota = False
        quota_limit = None
        quota_metric = None
        quota_id = None

        retry_after_hdr = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after_hdr:
            try:
                retry_delay_sec = float(retry_after_hdr)
            except (ValueError, TypeError):
                pass

        for d in details:
            if not isinstance(d, dict):
                continue
            detail_type = d.get("@type", "")
            if "RetryInfo" in detail_type:
                raw_delay = d.get("retryDelay", "")
                if isinstance(raw_delay, str) and raw_delay.endswith("s"):
                    try:
                        retry_delay_sec = float(raw_delay[:-1])
                    except ValueError:
                        pass
            elif "QuotaFailure" in detail_type:
                violations = d.get("violations", [])
                for v in violations:
                    if isinstance(v, dict):
                        quota_id = v.get("quotaId", "")
                        quota_metric = v.get("quotaMetric", "")
                        quota_limit = v.get("quotaValue", "")
                        if "PerDay" in quota_id or "free_tier_requests" in quota_metric:
                            is_daily_quota = True

        lower_msg = err_msg.lower()
        if "generate_content_free_tier_requests" in lower_msg or "perday" in lower_msg or "daily" in lower_msg:
            is_daily_quota = True

        if retry_delay_sec is not None and retry_delay_sec > 60:
            is_daily_quota = True

        if retry_delay_sec is not None:
            if retry_delay_sec >= 3600:
                friendly_str = f"{retry_delay_sec / 3600:.1f} hours"
            elif retry_delay_sec >= 60:
                friendly_str = f"{retry_delay_sec / 60:.1f} minutes"
            else:
                friendly_str = f"{int(retry_delay_sec)} seconds"
        else:
            m = re.search(r"retry in\s+([0-9\.]+[hmsd]+(?:\s*[0-9\.]+[hmsd]+)*)", err_msg, re.IGNORECASE)
            if m:
                friendly_str = m.group(1)
            else:
                friendly_str = "the next daily reset cycle"

        return {
            "is_daily_quota": is_daily_quota,
            "retry_delay_seconds": retry_delay_sec,
            "quota_limit": quota_limit,
            "quota_metric": quota_metric,
            "quota_id": quota_id,
            "friendly_retry_str": friendly_str,
            "error_message": err_msg
        }

    @classmethod
    async def _call_llm_api(cls, prompt: str) -> str:
        """Calls the configured GenAI API with deduplication, transient exponential backoff, and robust quota handling."""
        prompt_hash = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()
        current_task = asyncio.current_task()

        if current_task is not None:
            async with cls._get_lock():
                existing_task = cls._in_flight_tasks.get(prompt_hash)
                if existing_task is None or existing_task.done():
                    cls._in_flight_tasks[prompt_hash] = current_task
                    existing_task = None

            if existing_task is not None and existing_task != current_task:
                logger.info(f"Duplicate in-flight AI prompt detected (hash: {prompt_hash[:8]}). Awaiting existing execution.")
                return await asyncio.shield(existing_task)

        try:
            # Single positional prompt argument ensures full compatibility with test mocks
            return await cls._execute_llm_call(prompt)
        finally:
            if current_task is not None:
                async with cls._get_lock():
                    if cls._in_flight_tasks.get(prompt_hash) == current_task:
                        cls._in_flight_tasks.pop(prompt_hash, None)

    @classmethod
    async def _execute_llm_call(
        cls,
        prompt: str,
        max_output_tokens: Optional[int] = None,
        response_mime_type: Optional[str] = "application/json"
    ) -> str:
        """Executes LLM call with persistent connection reuse, model circuit breaker, bounded tokens, and failover."""
        # Dynamically infer optimal bounded maxOutputTokens based on task to minimize latency:
        if max_output_tokens is None:
            if "DEEP INTERVIEW ANALYSIS" in prompt or "SEQUENCED PREPARATION ROADMAP" in prompt or "TARGET ROLE & CONTEXT:" in prompt:
                max_output_tokens = 8192
            elif "Evaluate the candidate's response" in prompt or "Evaluate code submission" in prompt:
                max_output_tokens = 700
            elif "Generate 1 standard Data Structures" in prompt or "coding problem" in prompt:
                max_output_tokens = 1000
            elif "Generate the next adaptive interview question" in prompt or "interactive voice interview" in prompt:
                max_output_tokens = 500
            elif "interview questions directly tailored" in prompt or "question_generation" in prompt:
                max_output_tokens = 700
            elif "interviewer clarification or hint" in prompt:
                max_output_tokens = 400
            else:
                max_output_tokens = 1024

        g_key = (settings.GENAI_API_KEY or settings.GEMINI_API_KEY or os.getenv("GENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
        groq_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        
        if not g_key and not groq_key and not openai_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cloud GenAI API key is not configured. Please set GEMINI_API_KEY in backend/.env."
            )

        # In unit tests with mock keys, reset cache and cooldowns to guarantee clean test isolation
        if g_key.startswith("test_"):
            cls._model_cooldowns.clear()
            cls._model_daily_quota_info.clear()
            cls._last_successful_model = None

        configured_model = (settings.GENAI_MODEL or "gemini-3.5-flash-lite").replace("models/", "").strip()
        # Confirmed active free-tier models on Google GenAI in speed/priority order:
        fallback_free_models = [
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3.8-flash",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite-preview"
        ]

        now = time.time()
        # Clear expired cooldowns
        expired = [m for m, cd_until in cls._model_cooldowns.items() if now >= cd_until]
        for m in expired:
            cls._model_cooldowns.pop(m, None)
            cls._model_daily_quota_info.pop(m, None)

        ordered_candidates = []
        # Configured model is prioritized first (honors user config and test overrides):
        if configured_model and configured_model not in cls._model_cooldowns:
            ordered_candidates.append(configured_model)
        # If last successful model is known and not on cooldown, prioritize next:
        if cls._last_successful_model and cls._last_successful_model not in cls._model_cooldowns and cls._last_successful_model not in ordered_candidates:
            ordered_candidates.append(cls._last_successful_model)
        # Then other candidate models in priority order:
        for m in fallback_free_models:
            if m not in ordered_candidates and m not in cls._model_cooldowns:
                ordered_candidates.append(m)
        # If all candidates are currently in cooldown, include them anyway so quota details can be raised
        if not ordered_candidates:
            ordered_candidates = [configured_model] + [m for m in fallback_free_models if m != configured_model]

        seen = set()
        model_list = []
        for m in ordered_candidates:
            clean = m.replace("models/", "").strip()
            if clean and clean not in seen:
                seen.add(clean)
                model_list.append(clean)

        last_error = ""
        is_auth_error = False
        daily_quota_errors: Dict[str, Dict[str, Any]] = {}

        # 1. Direct Gemini REST endpoint HTTP call with connection reuse, circuit breaker, & quota handling
        if g_key:
            try:
                client = cls._get_http_client()
                for clean_model in model_list:
                    # Circuit breaker check: skip model immediately if currently in cooldown
                    if clean_model in cls._model_cooldowns:
                        cd_remaining = int(cls._model_cooldowns[clean_model] - now)
                        logger.debug(f"Skipping model '{clean_model}' (cooling down for {cd_remaining}s).")
                        continue

                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={g_key}"
                    
                    payload: Dict[str, Any] = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.2,
                            "topP": 0.8,
                            "maxOutputTokens": max_output_tokens
                        }
                    }
                    if response_mime_type:
                        payload["generationConfig"]["responseMimeType"] = response_mime_type

                    max_retries = 3

                    for attempt in range(max_retries):
                        try:
                            resp = await client.post(url, json=payload)
                            
                            if resp.status_code == 200:
                                data = resp.json()
                                candidates = data.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    if parts:
                                        text_out = parts[0].get("text", "")
                                        if text_out:
                                            cls._last_successful_model = clean_model
                                            cls._model_cooldowns.pop(clean_model, None)
                                            if clean_model != model_list[0]:
                                                logger.info(
                                                    f"Successfully generated dynamic response using active free-tier fallback model '{clean_model}'."
                                                )
                                            return text_out

                            elif resp.status_code == 429:
                                resp_data = {}
                                try:
                                    parsed = resp.json()
                                    if isinstance(parsed, dict):
                                        resp_data = parsed
                                except Exception:
                                    pass
                                if not resp_data and hasattr(resp, "text") and isinstance(resp.text, str):
                                    try:
                                        parsed = json.loads(resp.text)
                                        if isinstance(parsed, dict):
                                            resp_data = parsed
                                    except Exception:
                                        resp_data = {"error": {"message": resp.text}}

                                headers_dict = {}
                                if hasattr(resp, "headers") and isinstance(resp.headers, (dict, httpx.Headers)):
                                    headers_dict = dict(resp.headers)

                                error_info = cls._parse_gemini_error(resp.status_code, resp_data, headers_dict)

                                if error_info["is_daily_quota"]:
                                    cooldown_dur = error_info.get("retry_delay_seconds") or 3600.0
                                    cls._model_cooldowns[clean_model] = time.time() + cooldown_dur
                                    cls._model_daily_quota_info[clean_model] = error_info
                                    daily_quota_errors[clean_model] = error_info
                                    last_error = (
                                        f"Gemini model '{clean_model}' daily free-tier quota exhausted "
                                        f"(limit: {error_info.get('quota_limit', '20')} requests/day; reset in {error_info['friendly_retry_str']})."
                                    )
                                    logger.warning(
                                        f"{last_error} Cooldown active. Trying next available model without waiting."
                                    )
                                    break
                                else:
                                    delay_sec = error_info.get("retry_delay_seconds")
                                    backoff = min(10.0, max(1.0, delay_sec or (1.0 * (2 ** attempt))))
                                    logger.warning(
                                        f"Gemini transient rate limit on {clean_model} (attempt {attempt + 1}/{max_retries}). "
                                        f"Backing off for {backoff:.1f}s before retry..."
                                    )
                                    if attempt < max_retries - 1:
                                        await asyncio.sleep(backoff)
                                        continue
                                    else:
                                        last_error = f"Transient rate limit persisted on {clean_model} after {max_retries} attempts."
                                        break

                            elif resp.status_code in (500, 502, 503, 504):
                                backoff = min(6.0, 1.0 * (2 ** attempt))
                                logger.warning(
                                    f"Gemini server error HTTP {resp.status_code} on {clean_model} (attempt {attempt + 1}/{max_retries}). "
                                    f"Retrying in {backoff:.1f}s..."
                                )
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(backoff)
                                    continue
                                else:
                                    last_error = f"Gemini HTTP {resp.status_code} on {clean_model}: {resp.text[:200]}"
                                    break

                            elif resp.status_code == 403:
                                is_auth_error = True
                                last_error = f"Gemini API authentication failed (HTTP 403: Invalid key or permission denied) on {clean_model}"
                                logger.warning(last_error)
                                break

                            elif resp.status_code == 404:
                                cls._model_cooldowns[clean_model] = time.time() + 86400.0
                                last_error = f"Model {clean_model} not found or deprecated (HTTP 404)"
                                logger.debug(last_error)
                                break

                            elif resp.status_code == 400 and "responseMimeType" in payload.get("generationConfig", {}):
                                logger.warning(f"HTTP 400 on {clean_model}. Retrying without responseMimeType...")
                                payload["generationConfig"].pop("responseMimeType", None)
                                continue

                            else:
                                last_error = f"HTTP {resp.status_code} on {clean_model}: {resp.text[:200]}"
                                break

                        except httpx.TimeoutException:
                            logger.warning(f"Timeout requesting model {clean_model} on attempt {attempt + 1}/{max_retries}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(1.0)
                                continue
                            else:
                                last_error = f"Timeout (25s) requesting model {clean_model}"
                                break
                        except Exception as req_err:
                            last_error = f"Request error on {clean_model}: {req_err}"
                            break

                    if is_auth_error:
                        break

            except Exception as client_err:
                last_error = str(client_err)

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

        # 3. Try OpenAI API as tertiary provider if key is available
        if openai_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {openai_key}"},
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [{"role": "user", "content": prompt}]
                        }
                    )
                    if resp.status_code == 200:
                        return resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"OpenAI API call failed: {e}")
                last_error = str(e)

        if is_auth_error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gemini API authentication failed (HTTP 403: Invalid API key or permission denied). Please check your GEMINI_API_KEY in backend/.env."
            )

        if "Timeout" in last_error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service request timed out after 35 seconds. Please check network connectivity and retry."
            )

        if not daily_quota_errors and not last_error and cls._model_daily_quota_info:
            daily_quota_errors.update(cls._model_daily_quota_info)

        if daily_quota_errors:
            primary_info = daily_quota_errors.get(model_list[0]) or list(daily_quota_errors.values())[0]
            limit_val = primary_info.get("quota_limit", "20")
            reset_time = primary_info.get("friendly_retry_str", "several hours")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Gemini API daily free-tier quota exhausted ({limit_val} requests/day per model limit reached). "
                    f"Daily free-tier quota resets in approximately {reset_time}. "
                    f"To continue immediately, provide an alternate Gemini API key with available quota in backend/.env."
                )
            )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service temporarily unavailable ({last_error}). Please check configuration and retry."
        )

    @classmethod
    async def analyze_resume_and_jd(
        cls,
        resume_text: str,
        job_description: str,
        job_title: str = "Software Developer"
    ) -> ResumeJDAnalysisResult:
        """Analyzes candidate resume against job description using AI."""
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
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"GenAI Resume+JD analysis failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to analyze resume and job description: {str(e)}"
            )

    @classmethod
    async def generate_interview_questions(
        cls,
        target_role: str,
        experience_level: str,
        topic: str,
        interview_type: str,
        difficulty: str,
        num_questions: int = 5,
        resume_analysis: Optional[Dict[str, Any]] = None,
        job_description: Optional[str] = None,
        resume_text: Optional[str] = None,
        skills: Optional[List[str]] = None,
        additional_instructions: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generates structured interview questions dynamically using LLM API with rich candidate context."""
        skills_str = ", ".join(skills) if skills else topic
        jd_context_str = f"\nJob Description Requirements:\n{job_description[:800]}\n" if job_description else ""
        add_instr_str = f"\nUser Additional Instructions:\n{additional_instructions}\n" if additional_instructions else ""
        
        resume_context_str = ""
        if resume_analysis:
            matched = ", ".join(resume_analysis.get("matched_skills", []))
            missing = ", ".join(resume_analysis.get("missing_skills", []))
            priority = ", ".join(resume_analysis.get("priority_skills", []))
            score = resume_analysis.get("match_percentage", 75.0)
            summary = resume_analysis.get("analysis_summary", "")

            resume_context_str = (
                f"\nCandidate Resume + Job Description Match Context:\n"
                f"- Overall Skill Match Score: {score}%\n"
                f"- Matched Skills: {matched or 'General'}\n"
                f"- Missing / Growth Skills to Probe: {missing or 'Advanced Concepts'}\n"
                f"- High Priority Focus Skills: {priority or skills_str}\n"
                f"- Match Summary: {summary}\n"
            )
        elif resume_text:
            resume_context_str = f"\nCandidate Profile / Resume Summary:\n{resume_text[:600]}\n"

        # Check if question_generation.txt template exists for customization
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "question_generation.txt")
        template = ""
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    template = f.read()
            except Exception:
                template = ""

        if template:
            try:
                base_prompt = template.format(
                    num_questions=num_questions,
                    target_role=target_role,
                    experience_level=experience_level,
                    topic=skills_str,
                    interview_type=interview_type,
                    difficulty=difficulty
                )
                prompt = (
                    f"{base_prompt}\n"
                    f"{jd_context_str}{resume_context_str}{add_instr_str}\n"
                    "Remember: Return ONLY a valid JSON array of objects with keys: 'question', 'category', 'skill', 'difficulty', 'additional_instruction'. No markdown code fences or conversational text outside JSON."
                )
            except Exception:
                template = ""

        if not template:
            prompt = (
                f"You are an expert technical interviewer conducting a {difficulty} {interview_type} interview for a {experience_level} {target_role}.\n"
                f"Focus Skills/Topics: {skills_str}\n"
                f"{jd_context_str}{resume_context_str}{add_instr_str}\n"
                f"Task: Generate exactly {num_questions} direct, normal technical interview questions directly tailored to this candidate.\n"
                "STRICT STYLE REQUIREMENT: Questions MUST be direct, concise, standard interview questions (e.g., 'What is polymorphism in Java?', 'Explain database indexing.', 'What is the difference between async and await?').\n"
                "DO NOT generate lengthy scenario-based questions, fictional enterprise backstories, or verbose hypothetical setups (e.g. do NOT say 'Imagine you are working at an e-commerce platform and...'). Keep the question text clean, direct, and focused on the core technical concept or mechanism.\n"
                f"Difficulty Complexity ({difficulty}):\n"
                "- Easy: Core definitions, basic syntax, fundamental principles.\n"
                "- Medium: Operational mechanisms, differences between concepts, tradeoffs.\n"
                "- Hard: Deep internals, concurrency, memory management, low-level mechanics, edge cases.\n"
                "Return ONLY a valid JSON array of objects. Each object MUST have keys: 'question', 'category', 'skill', 'difficulty', 'additional_instruction'.\n"
                "No conversational filler or markdown code blocks outside JSON."
            )

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
                            "additional_instruction": item.get("additional_instruction", "Explain concepts clearly with concrete technical examples.")
                        })
                if validated_questions:
                    return validated_questions
            raise ValueError("AI response did not contain a valid list of questions.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"GenAI question generation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to dynamically generate interview questions: {str(e)}"
            )

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
        next_question_number: int,
        all_previous_questions: Optional[List[str]] = None,
        job_description: Optional[str] = None,
        skills: Optional[List[str]] = None,
        additional_instructions: Optional[str] = None,
        evaluation_result: Optional[Dict[str, Any]] = None,
        knowledge_gaps: Optional[List[str]] = None,
        recent_history: Optional[List[Dict[str, Any]]] = None,
        remaining_questions: Optional[int] = None,
        resume_text: Optional[str] = None,
        consecutive_strong_count: int = 0,
        consecutive_weak_count: int = 0
    ) -> Dict[str, Any]:
        """
        Adaptive Engine: Dynamically evaluates the candidate's actual answer content, conceptual omissions,
        misconceptions, accumulated knowledge gaps, and streak history to determine the next action:
        - Strong answer: INCREASE_DIFFICULTY (architecture, scaling, trade-offs)
        - Partially correct: FOLLOW_UP (probe missing concepts / edge cases)
        - Weak answer: SIMPLIFY (core foundational principles)
        - Ambiguous answer: CLARIFY (diagnostic probe before grading unfairly)
        - Incorrect answer: FOLLOW_UP or SIMPLIFY (diagnose misconception)
        - Repeated weakness: Explicitly track recurring knowledge gaps
        - Balanced progression: NEXT_TOPIC
        """
        # Baseline fallback heuristics
        if overall_score >= 80.0:
            next_diff = "Hard" if previous_difficulty in ["Medium", "Hard"] else "Medium"
            reason = f"Candidate demonstrated strong technical depth ({overall_score}%). Escalating difficulty to {next_diff} to evaluate advanced architectural reasoning and optimization trade-offs."
            inferred_action = AdaptiveAction.INCREASE_DIFFICULTY
        elif overall_score < 60.0:
            next_diff = "Easy" if previous_difficulty in ["Easy", "Medium"] else "Medium"
            reason = f"Candidate scored {overall_score}%. Adjusting difficulty to {next_diff} to reinforce and evaluate foundational understanding."
            inferred_action = AdaptiveAction.SIMPLIFY
        else:
            next_diff = previous_difficulty
            reason = f"Candidate answered with solid baseline understanding ({overall_score}%). Continuing at {next_diff} difficulty to probe practical execution nuances."
            inferred_action = AdaptiveAction.NEXT_TOPIC

        # Context formatting
        strengths_list = (evaluation_result.get("strengths") or []) if evaluation_result else []
        improvements_list = (evaluation_result.get("weaknesses") or evaluation_result.get("improvements") or []) if evaluation_result else []
        missing_concepts = (evaluation_result.get("missing_concepts") or []) if evaluation_result else []
        incorrect_claims = (evaluation_result.get("incorrect_claims") or []) if evaluation_result else []
        accumulated_gaps = knowledge_gaps or []

        prev_list_str = ""
        if all_previous_questions:
            prev_list_str = "Previously Asked Questions in Session (DO NOT REPEAT ANY OF THESE):\n" + "\n".join(f"- {q}" for q in all_previous_questions) + "\n"

        history_summary = ""
        if recent_history:
            history_summary = "Prior Questions & Answers History:\n" + "\n".join(
                f"Q: {h.get('question_text') or h.get('question', '')}\nA: {str(h.get('answer_text') or h.get('answer', ''))[:160]}... [Score: {h.get('score', 0)}%]"
                for h in recent_history[-3:]
            ) + "\n"

        gaps_str = ""
        if accumulated_gaps:
            gaps_str = f"Accumulated Knowledge Gaps Across Session: {', '.join(accumulated_gaps)}\n"

        jd_str = f"Target Job Description:\n{job_description}\n" if job_description else ""
        resume_str = f"Candidate Resume Highlights:\n{resume_text}\n" if resume_text else ""
        skills_str = f"Target Technical Skills: {', '.join(skills)}\n" if skills else ""
        instructions_str = f"Interviewer Directives: {additional_instructions}\n" if additional_instructions else ""

        streak_str = ""
        if consecutive_strong_count >= 2:
            streak_str = f"Candidate Momentum: {consecutive_strong_count} consecutive strong answers. Escalate technical depth towards Senior/Staff-level architectural trade-offs.\n"
        elif consecutive_weak_count >= 2:
            streak_str = f"Candidate Pattern: Struggled across {consecutive_weak_count} consecutive questions. Simplify focus to verify foundational building blocks.\n"

        prompt = (
            "Generate the next adaptive interview question based on the candidate's actual answer and context.\n"
            f"You are a Principal AI Technical Interviewer and Hiring Bar Raiser conducting an adaptive {interview_type} interview for {target_role} ({experience_level}).\n"
            f"Focus Area: {topic}\n"
            f"{skills_str}{jd_str}{resume_str}{instructions_str}\n"
            "--- SESSION PROGRESS ---\n"
            f"Next Question Number: {next_question_number}\n"
            f"Previous Difficulty: {previous_difficulty}\n"
            f"Target Next Difficulty: {next_diff}\n"
            f"{streak_str}"
            f"{gaps_str}"
            f"{prev_list_str}"
            f"{history_summary}\n"
            "--- PREVIOUS QUESTION & CANDIDATE RESPONSE ---\n"
            f"Previous Question: \"{previous_question_text}\"\n"
            f"Candidate Answer: \"{candidate_answer}\"\n"
            f"Rubric Score: {overall_score}%\n"
            f"Candidate Strengths: {', '.join(strengths_list) if strengths_list else 'None specified'}\n"
            f"Missing Concepts / Omissions: {', '.join(missing_concepts) if missing_concepts else 'None'}\n"
            f"Incorrect Claims / Misconceptions: {', '.join(incorrect_claims) if incorrect_claims else 'None'}\n\n"
            "--- ADAPTIVE INTELLIGENCE INSTRUCTIONS ---\n"
            "Analyze the candidate's actual response content, depth of reasoning, problem-solving, and omissions to dynamically select the optimal next action:\n"
            "1. STRONG ANSWER (>=80%): Action 'INCREASE_DIFFICULTY' or 'CHALLENGE_REASONING'. Escalate difficulty to Medium/Hard. Challenge the candidate's reasoning, architectural choices, or trade-offs with probing questions (e.g. 'Why did you choose this over alternatives?', 'What happens if traffic increases 100x?', 'How would you handle deadlock or failover?').\n"
            "2. PARTIALLY CORRECT (60-79%): Action 'FOLLOW_UP'. Ask a targeted follow-up question (1-2 sentences) probing the specific missing concept, unaddressed edge case, or trade-off without giving away the answer.\n"
            "3. WEAK ANSWER (<60%): Action 'SIMPLIFY'. Reduce difficulty to Easy/Medium. Ask a direct question testing core fundamental principles to diagnose baseline comprehension.\n"
            "4. AMBIGUOUS / VAGUE / UNSUPPORTED REASONING: Action 'CLARIFY'. Ask a diagnostic verification question to test whether the candidate truly understands the mechanism or is hand-waving. Do NOT label an answer memorized or incorrect without evidence.\n"
            "5. REPEATED WEAKNESS: Action 'REVISIT_WEAKNESS'. If the answer touches on a previously accumulated knowledge gap, revisit and test that gap with a targeted practical scenario.\n"
            "6. TOPIC MASTERY VERIFIED: Action 'NEXT_TOPIC'. Smoothly transition to the next important topic area tailored to the role.\n\n"
            "--- QUESTION STYLE REQUIREMENTS ---\n"
            "- Ask meaningful, realistic technical questions and follow-ups.\n"
            "- Avoid repetitive questions, irrelevant topics, endless follow-ups, and arbitrary difficulty changes.\n"
            "- Questions should be clear, professional, and targeted to the role and seniority.\n\n"
            "Return ONLY a valid JSON object matching these exact keys:\n"
            "{\n"
            "  \"adaptive_action\": \"INCREASE_DIFFICULTY\" | \"CHALLENGE_REASONING\" | \"FOLLOW_UP\" | \"SIMPLIFY\" | \"CLARIFY\" | \"REVISIT_WEAKNESS\" | \"NEXT_TOPIC\",\n"
            "  \"difficulty\": \"Easy\" | \"Medium\" | \"Hard\",\n"
            "  \"decision_rationale\": \"Concise, professional explanation of why this question and difficulty was chosen\",\n"
            "  \"question\": \"Formulated next question or follow-up question text\",\n"
            "  \"assessment_objective\": \"Concise statement of what capability this question measures\",\n"
            "  \"category\": \"Category or domain\",\n"
            "  \"skill\": \"Skill name\",\n"
            "  \"additional_instruction\": \"Guidance for candidate response\",\n"
            "  \"new_knowledge_gaps\": [\"list of newly identified or reinforced knowledge gaps\"],\n"
            "  \"conversational_prelude\": \"Natural transitional sentence acknowledging prior response\"\n"
            "}"
        )

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned = cls._clean_json_string(raw_response)
            data = json.loads(cleaned)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]

            # Robust resolution of fields with graceful fallbacks
            q_text = data.get("question") or data.get("question_text", "")
            if not q_text:
                raise ValueError("AI response did not contain an adaptive question.")

            raw_action = data.get("adaptive_action") or data.get("action")
            if raw_action:
                act_str = str(raw_action).strip().upper()
                if "CHALLENG" in act_str:
                    resolved_action = AdaptiveAction.CHALLENGE_REASONING
                elif "REVISIT" in act_str or "WEAKNESS" in act_str:
                    resolved_action = AdaptiveAction.REVISIT_WEAKNESS
                elif "INCREASE" in act_str or "HARD" in act_str:
                    resolved_action = AdaptiveAction.INCREASE_DIFFICULTY
                elif "FOLLOW" in act_str or "PROBE" in act_str:
                    resolved_action = AdaptiveAction.FOLLOW_UP
                elif "SIMPLIF" in act_str or "EASY" in act_str or "REDUC" in act_str:
                    resolved_action = AdaptiveAction.SIMPLIFY
                elif "CLARIF" in act_str or "AMBIG" in act_str:
                    resolved_action = AdaptiveAction.CLARIFY
                else:
                    resolved_action = AdaptiveAction.NEXT_TOPIC
            else:
                # Infer action if mock or legacy response omitted it
                if data.get("is_follow_up"):
                    resolved_action = AdaptiveAction.FOLLOW_UP
                elif data.get("difficulty") == "Hard" and previous_difficulty != "Hard":
                    resolved_action = AdaptiveAction.INCREASE_DIFFICULTY
                elif data.get("difficulty") == "Easy" and previous_difficulty != "Easy":
                    resolved_action = AdaptiveAction.SIMPLIFY
                elif "escalat" in str(data.get("adaptation_reason", "")).lower():
                    resolved_action = AdaptiveAction.INCREASE_DIFFICULTY
                elif "follow" in str(data.get("adaptation_reason", "")).lower():
                    resolved_action = AdaptiveAction.FOLLOW_UP
                else:
                    resolved_action = inferred_action

            diff_val = data.get("difficulty") or data.get("updated_difficulty") or next_diff
            rationale_val = data.get("decision_rationale") or data.get("adaptation_reason") or reason
            objective_val = data.get("assessment_objective") or f"Assess candidate's technical mastery and design principles in {data.get('skill', topic)}."
            
            raw_gaps = data.get("new_knowledge_gaps") or data.get("identified_knowledge_gaps") or []
            if isinstance(raw_gaps, str):
                gaps_val = [raw_gaps.strip()] if raw_gaps.strip() else []
            elif isinstance(raw_gaps, list):
                gaps_val = [str(g).strip() for g in raw_gaps if str(g).strip()]
            else:
                gaps_val = []

            prelude_val = data.get("conversational_prelude") or "Thank you for your answer. Let's proceed to the next question."
            is_follow_up = bool(resolved_action in (AdaptiveAction.FOLLOW_UP, AdaptiveAction.CLARIFY, AdaptiveAction.CHALLENGE_REASONING) or data.get("is_follow_up", False))

            return {
                "question": q_text,
                "category": data.get("category", topic),
                "skill": data.get("skill", topic),
                "difficulty": diff_val,
                "additional_instruction": data.get("additional_instruction", "Explain concepts with appropriate examples."),
                "adaptation_reason": rationale_val,
                "decision_rationale": rationale_val,
                "adaptive_action": resolved_action.value,
                "assessment_objective": objective_val,
                "new_knowledge_gaps": gaps_val,
                "conversational_prelude": prelude_val,
                "is_follow_up": is_follow_up
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"GenAI adaptive question generation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to generate next adaptive question: {str(e)}"
            )

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
        improvements: Optional[List[str]] = None,
        knowledge_gaps: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes a realistic spoken interviewer response:
        - Conversational prelude acknowledging candidate's answer.
        - Contextual follow-up question or adaptive next topic.
        - Adaptive action determination and assessment objective.
        - Verbal communication and answer structure notes.
        """
        strengths_str = ", ".join(strengths) if strengths else "Good basic grasp."
        improvements_str = ", ".join(improvements) if improvements else "Clarify edge cases."
        is_near_end = next_question_number > max_questions

        if overall_score >= 80.0:
            target_diff = "Hard" if previous_difficulty in ["Medium", "Hard"] else "Medium"
            reason = f"Strong verbal explanation ({overall_score}%). Escalating to {target_diff} to test advanced architecture and optimization trade-offs."
            inferred_action = AdaptiveAction.INCREASE_DIFFICULTY
        elif overall_score < 60.0:
            target_diff = "Easy" if previous_difficulty in ["Easy", "Medium"] else "Medium"
            reason = f"Candidate scored {overall_score}%. Adjusting difficulty to {target_diff} to verify foundational principles."
            inferred_action = AdaptiveAction.SIMPLIFY
        else:
            target_diff = previous_difficulty
            reason = f"Steady response ({overall_score}%). Maintaining {target_diff} difficulty to explore practical execution."
            inferred_action = AdaptiveAction.NEXT_TOPIC

        gaps_str = f"Prior Knowledge Gaps: {', '.join(knowledge_gaps)}\n" if knowledge_gaps else ""

        prompt = (
            f"You are a Senior Technical Hiring Manager conducting an interactive voice interview for {target_role} ({experience_level}).\n"
            f"Topic: {topic} | Interview Type: {interview_type}\n"
            f"Previous Question: \"{previous_question_text}\"\n"
            f"Candidate's Spoken Answer: \"{candidate_answer}\"\n"
            f"Evaluation Score: {overall_score}%\n"
            f"Candidate Strengths: {strengths_str}\n"
            f"Areas to Improve / Missing: {improvements_str}\n"
            f"{gaps_str}"
            f"Progress: Question {next_question_number} of {max_questions}\n\n"
            "As a realistic conversational interviewer, generate the next spoken interaction:\n"
            "1. 'conversational_prelude': 1-2 spoken sentences reacting naturally to their answer.\n"
            "2. 'adaptive_action': 'INCREASE_DIFFICULTY' | 'FOLLOW_UP' | 'SIMPLIFY' | 'CLARIFY' | 'NEXT_TOPIC'\n"
            "3. 'is_follow_up': boolean (true if candidate omitted an essential trade-off or introduced a concept to probe; false if advancing to a fresh question).\n"
            "4. 'question': Direct, concise spoken technical interview question or short follow-up (e.g. 'What is the difference between synchronous and asynchronous operations?'). STRICTLY NO lengthy scenario stories or case studies.\n"
            f"5. 'difficulty': '{target_diff}'\n"
            f"6. 'category': '{topic}'\n"
            f"7. 'skill': '{topic}'\n"
            "8. 'assessment_objective': What technical concept this spoken question evaluates.\n"
            "9. 'additional_instruction': guidance hint\n"
            f"10. 'adaptation_reason': reason based on candidate's answer and score {overall_score}%\n"
            "11. 'communication_notes': 1 brief sentence on verbal clarity, terminology precision, and structure\n"
            "12. 'new_knowledge_gaps': [\"list of newly identified knowledge gaps\"]\n\n"
            "Return ONLY a valid JSON object matching these keys."
        )

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned = cls._clean_json_string(raw_response)
            data = json.loads(cleaned)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]

            q_text = data.get("question") or data.get("question_text", "")
            if not q_text:
                raise ValueError("AI response did not contain valid voice conversational content.")

            raw_action = data.get("adaptive_action") or data.get("action")
            if raw_action:
                act_str = str(raw_action).strip().upper()
                if "INCREASE" in act_str:
                    resolved_action = AdaptiveAction.INCREASE_DIFFICULTY
                elif "FOLLOW" in act_str or "PROBE" in act_str:
                    resolved_action = AdaptiveAction.FOLLOW_UP
                elif "SIMPLIF" in act_str or "EASY" in act_str:
                    resolved_action = AdaptiveAction.SIMPLIFY
                elif "CLARIF" in act_str:
                    resolved_action = AdaptiveAction.CLARIFY
                else:
                    resolved_action = AdaptiveAction.NEXT_TOPIC
            else:
                if data.get("is_follow_up"):
                    resolved_action = AdaptiveAction.FOLLOW_UP
                elif data.get("difficulty") == "Hard" and previous_difficulty != "Hard":
                    resolved_action = AdaptiveAction.INCREASE_DIFFICULTY
                elif data.get("difficulty") == "Easy" and previous_difficulty != "Easy":
                    resolved_action = AdaptiveAction.SIMPLIFY
                else:
                    resolved_action = inferred_action

            is_follow_up = bool((resolved_action in (AdaptiveAction.FOLLOW_UP, AdaptiveAction.CLARIFY) or data.get("is_follow_up", False)) and not is_near_end)
            diff_val = data.get("difficulty") or target_diff
            rationale_val = data.get("adaptation_reason") or reason
            objective_val = data.get("assessment_objective") or f"Assess spoken explanation of {data.get('skill', topic)}."

            raw_gaps = data.get("new_knowledge_gaps") or []
            gaps_val = [str(g).strip() for g in raw_gaps if str(g).strip()] if isinstance(raw_gaps, list) else []

            return {
                "conversational_prelude": data.get("conversational_prelude", "Thank you. Let's move to the next question."),
                "is_follow_up": is_follow_up,
                "question": q_text,
                "category": data.get("category", topic),
                "skill": data.get("skill", topic),
                "difficulty": diff_val,
                "additional_instruction": data.get("additional_instruction", "Explain concepts clearly with practical examples."),
                "adaptation_reason": rationale_val,
                "decision_rationale": rationale_val,
                "adaptive_action": resolved_action.value,
                "assessment_objective": objective_val,
                "communication_notes": data.get("communication_notes", "Clear technical delivery and structured phrasing."),
                "new_knowledge_gaps": gaps_val
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Voice conversational generation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to generate voice conversational response: {str(e)}"
            )

    @classmethod
    async def evaluate_candidate_answer(
        cls,
        question_text: str,
        answer_text: str,
        topic: str,
        target_role: str,
        difficulty: str,
        interview_type: str = "Technical",
        job_description: Optional[str] = None,
        additional_instructions: Optional[str] = None
    ) -> AIEvaluationResult:
        """
        Evaluates candidate answer against rubric dynamically using GenAI and returns structured JSON score
        with score_out_of_10, strengths, missing_concepts, incorrect_claims, improved_sample_answer, and actionable_feedback.
        """
        eval_type = "technical"
        itype_lower = interview_type.lower()
        if "coding" in itype_lower:
            eval_type = "coding"
            rubric_focus = "algorithmic correctness, time/space complexity, syntax precision, edge cases"
        elif "behavioral" in itype_lower:
            eval_type = "behavioral"
            rubric_focus = "STAR framework (Situation, Task, Action, Result), leadership, conflict resolution, tangible impact"
        elif "hr" in itype_lower:
            eval_type = "hr"
            rubric_focus = "communication, alignment with company values, career trajectory, team collaboration"
        else:
            eval_type = "technical"
            rubric_focus = "technical correctness, internal runtime mechanics, trade-offs, architecture"

        jd_str = f"\nTarget Job Description:\n{job_description[:500]}\n" if job_description else ""
        add_str = f"\nCandidate Interview Instructions:\n{additional_instructions}\n" if additional_instructions else ""

        prompt = (
            f"You are an expert hiring manager and interviewer evaluating a candidate's response to an interview question.\n\n"
            f"Question:\n\"{question_text}\"\n\n"
            f"Topic / Skill: {topic}\n"
            f"Target Role: {target_role}\n"
            f"Difficulty Level: {difficulty}\n"
            f"Interview Type: {interview_type} (Focus: {rubric_focus})\n"
            f"{jd_str}{add_str}\n"
            f"Candidate's Submitted Answer:\n\"{answer_text}\"\n\n"
            "Evaluate the candidate's response rigorously across the 5 dimensions:\n"
            "1. Technical Correctness (35% weight, 0-100)\n"
            "2. Conceptual Completeness (25% weight, 0-100)\n"
            "3. Response Relevance (15% weight, 0-100)\n"
            "4. Structural Clarity (15% weight, 0-100)\n"
            "5. Depth of Understanding (10% weight, 0-100)\n\n"
            "Return ONLY a valid JSON object with keys:\n"
            "- technical_correctness (float 0-100)\n"
            "- conceptual_completeness (float 0-100)\n"
            "- response_relevance (float 0-100)\n"
            "- structural_clarity (float 0-100)\n"
            "- depth_of_understanding (float 0-100)\n"
            "- overall_score (float 0-100)\n"
            "- score_out_of_10 (float 0-10)\n"
            "- strengths (list of strings: specific points the candidate covered accurately)\n"
            "- missing_concepts (list of strings: vital principles, trade-offs or edge cases omitted)\n"
            "- incorrect_claims (list of strings: flawed assertions or inaccurate facts; empty list if none)\n"
            "- actionable_feedback (string: targeted, practical next steps)\n"
            "- improved_sample_answer (string: concise model answer demonstrating mastery)\n"
            "- feedback (string: balanced summary feedback paragraph)\n"
            "- model_answer (string: concise model reference answer)\n"
            f"- evaluation_type (string: '{eval_type}')\n"
            "Guidelines: Keep feedback, actionable_feedback, and model_answer concise, evidence-based, and direct (2-3 sentences max) without redundant filler."
        )

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned_json = cls._clean_json_string(raw_response)
            eval_dict = json.loads(cleaned_json)

            def _safe_float(val: Any, default: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
                if val is None:
                    return default
                try:
                    if isinstance(val, str):
                        val = val.replace("%", "").strip()
                    f = float(val)
                    return min(max_val, max(min_val, f))
                except (ValueError, TypeError):
                    return default

            tc = _safe_float(eval_dict.get("technical_correctness"), 75.0)
            cc = _safe_float(eval_dict.get("conceptual_completeness"), 75.0)
            rr = _safe_float(eval_dict.get("response_relevance"), 80.0)
            sc = _safe_float(eval_dict.get("structural_clarity"), 80.0)
            du = _safe_float(eval_dict.get("depth_of_understanding"), 70.0)

            computed_score = round((tc * 0.35) + (cc * 0.25) + (rr * 0.15) + (sc * 0.15) + (du * 0.10), 1)
            raw_score_10 = eval_dict.get("score_out_of_10")
            score_10 = _safe_float(raw_score_10, round(computed_score / 10.0, 1), max_val=10.0)

            strengths = _normalize_to_str_list(
                eval_dict.get("strengths"),
                default=["Identified core concepts correctly."]
            )

            raw_missing = eval_dict.get("missing_concepts")
            if raw_missing is None:
                raw_missing = eval_dict.get("improvements")
            missing_concepts = _normalize_to_str_list(
                raw_missing,
                default=["Provide deeper technical detail and edge cases."]
            )

            incorrect_claims = _normalize_to_str_list(
                eval_dict.get("incorrect_claims"),
                default=[]
            )

            actionable_feedback = _normalize_to_str(
                eval_dict.get("actionable_feedback"),
                default="Structure your answer by leading with high-level trade-offs before diving into syntax."
            )

            improved_sample_answer = _normalize_to_str(
                eval_dict.get("improved_sample_answer") or eval_dict.get("model_answer"),
                default="A comprehensive answer should define the concept, outline performance trade-offs, and give practical examples."
            )

            feedback = _normalize_to_str(
                eval_dict.get("feedback"),
                default="Good response overall with clear articulation of core concepts."
            )

            model_ans = _normalize_to_str(
                eval_dict.get("model_answer"),
                default=improved_sample_answer
            )

            return AIEvaluationResult(
                technical_correctness=tc,
                conceptual_completeness=cc,
                response_relevance=rr,
                structural_clarity=sc,
                depth_of_understanding=du,
                overall_score=computed_score,
                score_out_of_10=score_10,
                strengths=strengths,
                improvements=missing_concepts,
                missing_concepts=missing_concepts,
                incorrect_claims=incorrect_claims,
                feedback=feedback,
                actionable_feedback=actionable_feedback,
                model_answer=model_ans,
                improved_sample_answer=improved_sample_answer,
                evaluation_type=eval_type
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"GenAI evaluation call failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to evaluate candidate answer: {str(e)}"
            )

    @classmethod
    async def generate_clarification_or_hint(
        cls,
        target_role: str,
        experience_level: str,
        question_text: str,
        topic: str,
        user_query: Optional[str] = None,
        difficulty: str = "Medium"
    ) -> Dict[str, Any]:
        """Generates an interviewer clarification or hint dynamically without revealing the complete solution."""
        prompt = (
            f"You are a Senior Technical Interviewer conducting a {difficulty} interview for a {target_role} ({experience_level}).\n"
            f"Interview Question: \"{question_text}\"\n"
            f"Topic: {topic}\n"
            f"Candidate Request: \"{user_query or 'Could you provide a hint or clarify what key aspects to focus on?'}\"\n\n"
            "Respond constructively as the interviewer:\n"
            "1. 'clarification': 1-2 friendly sentences clarifying the question scope, input constraints, or expected focus without giving away the full answer.\n"
            "2. 'hint': A subtle technical nudge or guiding thought (e.g., consider asymptotic trade-offs, edge cases, or concurrency).\n"
            "3. 'focus_areas': List of 2-3 specific technical concepts the candidate should address in their response.\n\n"
            "Return ONLY a valid JSON object with keys: 'clarification', 'hint', 'focus_areas'."
        )

        try:
            raw = await cls._call_llm_api(prompt)
            data = json.loads(cls._clean_json_string(raw))
            return {
                "clarification": data.get("clarification", "Focus on explaining the underlying mechanics and real-world trade-offs."),
                "hint": data.get("hint", f"Think about how {topic} handles memory management, edge cases, and runtime efficiency."),
                "focus_areas": list(data.get("focus_areas", [topic, "Architectural Trade-offs", "Edge Cases"]))
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Clarification generation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to generate clarification or hint: {str(e)}"
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
        """Evaluates arbitrary code submission dynamically using GenAI."""
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
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"GenAI evaluate_code error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to evaluate code submission: {str(e)}"
            )

    @classmethod
    async def generate_final_report(
        cls,
        role: str,
        experience: str,
        interview_type: str,
        interview_summary: List[Dict[str, Any]],
        job_description: Optional[str] = None,
        additional_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes overall interview performance from actual question summaries and candidate evaluations,
        producing a comprehensive diagnostic report via GenAI.
        """
        eval_scores = []
        tc_scores = []
        cc_scores = []
        sc_scores = []
        topics_seen = []
        all_strengths = []
        all_missing = []
        all_incorrect = []
        question_results = []

        for idx, item in enumerate(interview_summary):
            ev = item.get("evaluation", {})
            q_info = item.get("question", {})
            q_text = q_info.get("question") or q_info.get("question_text", f"Question #{idx + 1}")
            q_topic = q_info.get("topic") or q_info.get("category", role)
            q_diff = q_info.get("difficulty", "Medium")
            u_ans = item.get("answer", "")
            is_skipped = bool(item.get("is_skipped") or q_info.get("is_skipped") or ev.get("is_skipped", False))

            if is_skipped:
                question_results.append({
                    "question_number": idx + 1,
                    "question": q_text,
                    "topic": q_topic,
                    "difficulty": q_diff,
                    "user_answer": u_ans or "Question skipped by candidate.",
                    "score": 0.0,
                    "score_out_of_10": None,
                    "strengths": ["Question passed by candidate."],
                    "missing_concepts": [],
                    "incorrect_claims": [],
                    "feedback": "Question was skipped by candidate. Excluded from evaluation scoring.",
                    "model_answer": ev.get("model_answer") or "Reference benchmark solution available for review.",
                    "is_skipped": True,
                    "status": "skipped"
                })
                continue

            score = ev.get("overall_score") or (ev.get("score", 7.5) * 10.0 if "score" in ev else 75.0)
            score_float = float(score)
            eval_scores.append(score_float)

            if "technical_correctness" in ev:
                tc_scores.append(float(ev["technical_correctness"]))
            if "conceptual_completeness" in ev:
                cc_scores.append(float(ev["conceptual_completeness"]))
            if "structural_clarity" in ev:
                sc_scores.append(float(ev["structural_clarity"]))

            if q_topic:
                topics_seen.append(q_topic)

            st = ev.get("strengths", [])
            if isinstance(st, str):
                st = [st]
            all_strengths.extend(st)

            mi = ev.get("missing_concepts", ev.get("missing_points", ev.get("improvements", [])))
            if isinstance(mi, str):
                mi = [mi]
            all_missing.extend(mi)

            inc = ev.get("incorrect_claims", [])
            if isinstance(inc, str):
                inc = [inc]
            all_incorrect.extend(inc)

            question_results.append({
                "question_number": idx + 1,
                "question": q_text,
                "topic": q_topic,
                "difficulty": q_diff,
                "user_answer": u_ans,
                "score": score_float,
                "score_out_of_10": round(score_float / 10.0, 1),
                "strengths": st[:3] if st else ["Addressed question scope."],
                "missing_concepts": mi[:3] if mi else ["No critical omissions flagged."],
                "incorrect_claims": inc[:2],
                "feedback": ev.get("feedback") or ev.get("improvement_tip") or "Solid technical delivery.",
                "model_answer": ev.get("model_answer") or ev.get("ideal_answer") or "",
                "is_skipped": False,
                "status": "answered"
            })

        avg_score = round(sum(eval_scores) / len(eval_scores), 1) if eval_scores else 0.0
        score_10 = round(avg_score / 10.0, 1)
        avg_tc = round(sum(tc_scores) / len(tc_scores), 1) if tc_scores else avg_score
        avg_cc = round(sum(cc_scores) / len(cc_scores), 1) if cc_scores else avg_score
        avg_sc = round(sum(sc_scores) / len(sc_scores), 1) if sc_scores else avg_score

        # Baseline readiness description
        if not eval_scores:
            readiness_lvl = "Not Evaluated"
            readiness_desc = "All questions in this session were skipped. No scored responses available for evaluation."
        elif avg_score >= 85.0:
            readiness_lvl = "Ready"
            readiness_desc = (
                f"High Readiness ({avg_score}%). The candidate demonstrates strong production-level competence, "
                f"clear articulation of trade-offs, and sound architectural logic suitable for a {role} position."
            )
        elif avg_score >= 70.0:
            readiness_lvl = "Nearly Ready"
            readiness_desc = (
                f"Promising Readiness ({avg_score}%). Candidate has solid fundamental proficiency. "
                f"Addressing the identified missing concepts and edge cases will place them firmly in the top candidate tier."
            )
        elif avg_score >= 55.0:
            readiness_lvl = "Needs Preparation"
            readiness_desc = (
                f"Moderate Readiness ({avg_score}%). Shows foundational understanding but requires focused practice "
                f"on internal mechanics, runtime trade-offs, and structured response delivery for {role}."
            )
        else:
            readiness_lvl = "Foundational"
            readiness_desc = (
                f"Foundational Stage ({avg_score}%). Recommend comprehensive revision of core principles "
                f"and repeated simulated practice before live hiring interviews."
            )

        unique_topics = list(dict.fromkeys(topics_seen))
        strong_topics = unique_topics[:2] if len(unique_topics) >= 2 else (unique_topics or [role])
        weak_topics = list(dict.fromkeys(all_missing))[:3] if all_missing else ["Concurrency Edge Cases", "Distributed Scalability"]

        jd_context = f"\nTarget Job Description Requirements:\n{job_description[:500]}\n" if job_description else ""

        prompt = (
            f"You are a Lead Hiring Manager reviewing a completed {interview_type} mock interview for {role} ({experience}).\n"
            f"Session Average Score: {avg_score}%\n"
            f"{jd_context}"
            f"Session Transcript & Rubric Results:\n{json.dumps(question_results, default=str)[:2500]}\n\n"
            "Generate a comprehensive, actionable final evaluation report.\n"
            "Return ONLY a JSON object with keys:\n"
            "- overall_score (float 0-100)\n"
            "- technical_knowledge_score (float 0-100)\n"
            "- communication_score (float 0-100)\n"
            "- problem_solving_score (float 0-100)\n"
            "- answer_quality_score (float 0-100)\n"
            "- strong_topics (list of strings)\n"
            "- weak_topics (list of strings)\n"
            "- skill_gaps (list of strings)\n"
            "- recommendations (list of strings)\n"
            "- communication_observations (string)\n"
            "- readiness_estimate (string)\n"
            "- readiness_level (string: 'Ready' | 'Nearly Ready' | 'Needs Preparation' | 'Foundational')\n"
            "- personalized_summary (string)"
        )

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned = cls._clean_json_string(raw_response)
            data = json.loads(cleaned)
            return {
                "overall_score": float(data.get("overall_score", avg_score)),
                "score_out_of_10": round(float(data.get("overall_score", avg_score)) / 10.0, 1),
                "technical_knowledge_score": float(data.get("technical_knowledge_score", avg_tc)),
                "communication_score": float(data.get("communication_score", avg_sc)),
                "problem_solving_score": float(data.get("problem_solving_score", avg_cc)),
                "answer_quality_score": float(data.get("answer_quality_score", avg_score)),
                "strong_topics": list(data.get("strong_topics", strong_topics)),
                "weak_topics": list(data.get("weak_topics", weak_topics)),
                "skill_gaps": list(data.get("skill_gaps", weak_topics)),
                "recommendations": list(data.get("recommendations", [
                    "Review memory allocation and internal runtime mechanics.",
                    "Practice answering using the structured Invariant -> Mechanics -> Trade-off rubric."
                ])),
                "communication_observations": str(data.get("communication_observations", "Communicates technical thoughts with good clarity; focus on crisply articulating edge cases.")),
                "readiness_estimate": str(data.get("readiness_estimate", readiness_desc)),
                "readiness_level": str(data.get("readiness_level", readiness_lvl)),
                "personalized_summary": str(data.get("personalized_summary", f"Solid performance for {role}. Continuing targeted practice will cement your competitive edge.")),
                "question_results": question_results
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"GenAI generate_final_report error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to generate final interview report: {str(e)}"
            )

    @classmethod
    async def generate_preparation_plan(
        cls,
        role: str,
        experience: str,
        weak_topics: List[str],
        strong_topics: List[str],
        avg_score: float = 7.5
    ) -> Dict[str, Any]:
        """Generates a structured 7-day preparation roadmap tailored to candidate strengths and weaknesses using GenAI."""
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
            raise ValueError("Invalid preparation plan format returned from AI model.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"GenAI generate_preparation_plan error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to generate preparation plan: {str(e)}"
            )

    @classmethod
    async def deep_analyze_interview_session(
        cls,
        interview_context: Dict[str, Any],
        qa_history: List[Dict[str, Any]],
        coding_submissions: Optional[List[Dict[str, Any]]] = None,
        target_interview_date: Optional[str] = None,
        daily_study_hours: float = 2.0
    ) -> Dict[str, Any]:
        """Conducts a deep, evidence-based post-interview intelligence analysis and generates a personalized preparation roadmap."""
        qa_text_blocks = []
        for item in qa_history:
            q_num = item.get("question_number", 1)
            q_text = item.get("question_text", "")
            q_cat = item.get("category", "General")
            q_diff = item.get("difficulty", "Medium")
            is_skipped = item.get("is_skipped", False)
            ans = item.get("candidate_answer", "")
            ev = item.get("existing_eval") or {}
            
            block = (
                f"--- Question {q_num} [Category: {q_cat}, Difficulty: {q_diff}] ---\n"
                f"Question Text: {q_text}\n"
                f"Candidate Status: {'SKIPPED' if is_skipped else 'ANSWERED'}\n"
                f"Candidate Answer: \"{ans}\"\n"
            )
            if ev:
                block += (
                    f"Existing Scores: Correctness={ev.get('technical_correctness', 0)}/10, "
                    f"Completeness={ev.get('conceptual_completeness', 0)}/10, "
                    f"Depth={ev.get('depth_of_understanding', 0)}/10, Overall={ev.get('overall_score', 0)}/10\n"
                    f"Noted Strengths: {ev.get('strengths', [])}\n"
                    f"Missing Concepts: {ev.get('missing_concepts', [])}\n"
                    f"Incorrect Claims: {ev.get('incorrect_claims', [])}\n"
                )
            qa_text_blocks.append(block)

        coding_blocks = ""
        if coding_submissions:
            coding_blocks = "\n--- Candidate Coding Submissions ---\n"
            for c in coding_submissions:
                coding_blocks += (
                    f"Problem: {c.get('problem_title')} ({c.get('language')})\n"
                    f"Tests Passed: {c.get('test_cases_passed')}/{c.get('total_test_cases')}\n"
                    f"Code:\n{c.get('code', '')[:1000]}\n"
                )

        prompt = (
            "You are a Principal Technical Interview Auditor and Senior Staff Career Architect at Google and Microsoft.\n"
            "You are analyzing the complete question-and-answer history of a candidate's completed interview.\n\n"
            "TARGET ROLE & CONTEXT:\n"
            f"Target Role: {interview_context.get('target_role', 'Software Engineer')}\n"
            f"Experience Level: {interview_context.get('experience_level', 'Intermediate')}\n"
            f"Interview Topic: {interview_context.get('topic', 'Software Engineering')}\n"
            f"Interview Difficulty: {interview_context.get('difficulty', 'Medium')}\n"
            f"Job Description: {interview_context.get('job_description', 'N/A')}\n"
            f"Target Interview Date: {target_interview_date or 'Not specified (assume 3 weeks)'}\n"
            f"Candidate Daily Available Study Hours: {daily_study_hours} hrs/day\n\n"
            "COMPLETE INTERVIEW RECORD:\n"
            f"{chr(10).join(qa_text_blocks)}\n"
            f"{coding_blocks}\n\n"
            "MANDATORY REQUIREMENTS:\n"
            "1. DEEP INTERVIEW ANALYSIS: Evaluate every answered question for technical_correctness, conceptual_understanding, depth_and_clarity, reasoning_approach, completeness (all strictly on a 0.0 to 10.0 scale, e.g. 7.5). For code, evaluate logic, edge cases, complexity (Big-O), and correctness. Identify misconceptions, missing concepts, repeated mistakes, strong areas, and answers that were correct but poorly explained. Do NOT rely on the overall score alone.\n"
            "2. EVIDENCE-BASED SKILL GAPS: Connect EVERY identified weakness to the EXACT question number and verbatim quote/excerpt from the candidate's answer. Explain what was missing or incorrect, why it matters in engineering practice, what the correct understanding is, and confidence level (HIGH/MEDIUM/LOW). Distinguish CONFIRMED_WEAKNESS from UNCERTAIN_FINDING and UNTESTED_COMPETENCY. Provide 3-5 confirmed gaps. NEVER invent mistakes or cite evidence not present in candidate's answers.\n"
            "3. PERSONALIZED REMEDIATION PATH: For every major weakness, provide: what went wrong -> what to learn -> what to practice -> how to verify improvement.\n"
            "4. SEQUENCED PREPARATION ROADMAP: Generate 4 progressive phases:\n"
            "   Phase 1: Prerequisite & Core Concepts Remediation\n"
            "   Phase 2: Deep Technical & Architectural Systems\n"
            "   Phase 3: Practical Application & Targeted Problem Solving\n"
            "   Phase 4: Mock Interviews & Final Calibration Revision\n"
            "   Create 6-8 focused, high-impact tasks (1-2 per phase) with topics, subtopics, learning objectives, practical exercises, relevant problems/questions, realistic duration in hours, expected outcomes, and completion criteria. Prioritize weaknesses with greatest impact on interview readiness. Avoid assigning topics candidate has already mastered.\n"
            "5. DIAGNOSTIC REASSESSMENT QUESTIONS: 3-4 challenging questions specifically targeting the identified weaknesses with benchmark solutions.\n\n"
            "CRITICAL OUTPUT LENGTH & DENSITY RULES:\n"
            "- executive_summary: 2-3 concise sentences (<80 words).\n"
            "- For each item in question_analyses: candidate_answer_excerpt must be a single concise sentence (<25 words). Keep key_strengths, misconceptions, missing_concepts, poorly_explained_aspects to 1-2 brief bullets.\n"
            "- skill_gaps: Exactly 2 to 4 confirmed weaknesses. Keep what_was_missing_or_incorrect, why_it_matters, correct_understanding, and remediation_path fields to 1-2 direct sentences.\n"
            "- strengths: 2 to 3 items.\n"
            "- untested_competencies: 2 items.\n"
            "- roadmap_phases: exactly 4 phases.\n"
            "- roadmap_tasks: 4 to 6 high-impact tasks (1-2 per phase).\n"
            "- reassessment_questions: 3 questions with 2 key points each and a concise benchmark solution.\n\n"
            "Return ONLY a valid JSON object with EXACT schema:\n"
            "{\n"
            '  "readiness_score": 75.0,\n'
            '  "readiness_level": "Needs Targeted Preparation",\n'
            '  "executive_summary": "Comprehensive 2-paragraph evaluation...",\n'
            '  "question_analyses": [\n'
            "    {\n"
            '      "question_id": "...",\n'
            '      "question_number": 1,\n'
            '      "question_text": "...",\n'
            '      "candidate_answer_excerpt": "...",\n'
            '      "technical_correctness": 8.0,\n'
            '      "conceptual_understanding": 7.5,\n'
            '      "depth_and_clarity": 7.0,\n'
            '      "reasoning_approach": 7.5,\n'
            '      "completeness": 8.0,\n'
            '      "key_strengths": ["..."],\n'
            '      "misconceptions": ["..."],\n'
            '      "missing_concepts": ["..."],\n'
            '      "poorly_explained_aspects": ["..."],\n'
            '      "coding_evaluation": null\n'
            "    }\n"
            "  ],\n"
            '  "skill_gaps": [\n'
            "    {\n"
            '      "gap_id": "gap_1",\n'
            '      "competency": "...",\n'
            '      "category": "...",\n'
            '      "finding_type": "CONFIRMED_WEAKNESS",\n'
            '      "confidence_level": "HIGH",\n'
            '      "evidence_question_id": "...",\n'
            '      "evidence_question_number": 1,\n'
            '      "evidence_question_text": "...",\n'
            '      "candidate_answer_excerpt": "...",\n'
            '      "what_was_missing_or_incorrect": "...",\n'
            '      "why_it_matters": "...",\n'
            '      "correct_understanding": "...",\n'
            '      "priority": "CRITICAL",\n'
            '      "remediation_path": {\n'
            '        "what_went_wrong": "...",\n'
            '        "what_to_learn": "...",\n'
            '        "what_to_practice": "...",\n'
            '        "how_to_verify": "..."\n'
            "      }\n"
            "    }\n"
            "  ],\n"
            '  "strengths": [\n'
            "    {\n"
            '      "competency": "...",\n'
            '      "category": "...",\n'
            '      "evidence_question_number": 2,\n'
            '      "candidate_excerpt": "...",\n'
            '      "demonstrated_mastery": "..."\n'
            "    }\n"
            "  ],\n"
            '  "untested_competencies": [\n'
            "    {\n"
            '      "competency": "...",\n'
            '      "category": "...",\n'
            '      "importance_for_role": "...",\n'
            '      "recommended_next_step": "..."\n'
            "    }\n"
            "  ],\n"
            '  "roadmap_phases": [\n'
            "    {\n"
            '      "phase_number": 1,\n'
            '      "title": "Phase 1: Prerequisite & Core Concepts Remediation",\n'
            '      "duration_weeks": 1.0,\n'
            '      "focus_areas": ["..."],\n'
            '      "milestone": "..."\n'
            "    }\n"
            "  ],\n"
            '  "roadmap_tasks": [\n'
            "    {\n"
            '      "task_id": "task_1",\n'
            '      "phase_number": 1,\n'
            '      "day_or_sequence": 1,\n'
            '      "priority": "CRITICAL",\n'
            '      "topic": "...",\n'
            '      "subtopics": ["..."],\n'
            '      "learning_objectives": ["..."],\n'
            '      "practical_exercise": "...",\n'
            '      "relevant_problems_or_questions": ["..."],\n'
            '      "estimated_duration_hours": 2.0,\n'
            '      "expected_outcomes": "...",\n'
            '      "completion_criteria": "...",\n'
            '      "status": "pending"\n'
            "    }\n"
            "  ],\n"
            '  "reassessment_questions": [\n'
            "    {\n"
            '      "id": "reassess_1",\n'
            '      "targeted_gap_id": "gap_1",\n'
            '      "competency": "...",\n'
            '      "question_text": "...",\n'
            '      "expected_key_points": ["..."],\n'
            '      "benchmark_solution": "...",\n'
            '      "difficulty": "Medium"\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        try:
            raw_response = await cls._call_llm_api(prompt)
            cleaned = cls._clean_json_string(raw_response)
            data = json.loads(cleaned)
            return data
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"GenAI deep_analyze_interview_session error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to generate deep interview analysis: {str(e)}"
            )
