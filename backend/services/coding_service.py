import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.models import User, CodingInterview, CodingQuestion, CodingSubmission
from backend.schemas.coding_interview import (
    CodingInterviewCreateRequest,
    CodeRunRequest,
    CodingSubmissionRequest,
    CodeRunResultSchema,
    TestCaseResultSchema,
    CodingInterviewResponse
)
from backend.services.ai_service import AIService
from backend.services.code_executor import CodeExecutor

logger = logging.getLogger("uvicorn.error")

class CodingService:
    @staticmethod
    def _get_curated_fallback_problem(topic: str, difficulty: str, language: str) -> Dict[str, Any]:
        """Provides curated role-relevant coding problems if GenAI API hits rate limits."""
        problems = {
            "python": [
                {
                    "title": "Two Sum Target Index",
                    "description": "Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.",
                    "input_format": "Line 1: JSON array of integers `nums`\nLine 2: Target integer",
                    "output_format": "JSON array containing two indices [index1, index2]",
                    "constraints": "2 <= nums.length <= 10^4\n-10^9 <= nums[i] <= 10^9\n-10^9 <= target <= 10^9",
                    "starter_code": "def two_sum(nums, target):\n    # Write your solution here\n    pass\n",
                    "sample_test_cases": [
                        {"input": "[2, 7, 11, 15]\n9", "expected_output": "[0, 1]", "explanation": "nums[0] + nums[1] == 9, so return [0, 1]."},
                        {"input": "[3, 2, 4]\n6", "expected_output": "[1, 2]", "explanation": "nums[1] + nums[2] == 6."}
                    ],
                    "hidden_test_cases": [
                        {"input": "[3, 3]\n6", "expected_output": "[0, 1]"},
                        {"input": "[1, 5, 8, 3]\n8", "expected_output": "[1, 3]"}
                    ],
                    "skill": topic or "Data Structures",
                    "difficulty": difficulty
                },
                {
                    "title": "Maximum Subarray Sum",
                    "description": "Given an integer array `nums`, find the contiguous subarray (containing at least one number) which has the largest sum and return its sum.",
                    "input_format": "JSON array of integers `nums`",
                    "output_format": "Integer representing the maximum subarray sum",
                    "constraints": "1 <= nums.length <= 10^5\n-10^4 <= nums[i] <= 10^4",
                    "starter_code": "def max_sub_array(nums):\n    # Write your solution here\n    pass\n",
                    "sample_test_cases": [
                        {"input": "[-2, 1, -3, 4, -1, 2, 1, -5, 4]", "expected_output": "6", "explanation": "[4, -1, 2, 1] has the largest sum = 6."},
                        {"input": "[1]", "expected_output": "1", "explanation": "Single element array."}
                    ],
                    "hidden_test_cases": [
                        {"input": "[5, 4, -1, 7, 8]", "expected_output": "23"},
                        {"input": "[-1, -2, -3]", "expected_output": "-1"}
                    ],
                    "skill": topic or "Algorithms",
                    "difficulty": difficulty
                }
            ],
            "javascript": [
                {
                    "title": "Valid Anagram Checker",
                    "description": "Given two strings `s` and `t`, return `true` if `t` is an anagram of `s`, and `false` otherwise.",
                    "input_format": "Line 1: string s\nLine 2: string t",
                    "output_format": "Boolean true or false",
                    "constraints": "1 <= s.length, t.length <= 5 * 10^4",
                    "starter_code": "function solution(s, t) {\n    // Write your solution here\n    return false;\n}\n",
                    "sample_test_cases": [
                        {"input": "\"anagram\"\n\"nagaram\"", "expected_output": "true", "explanation": "Same character frequencies."},
                        {"input": "\"rat\"\n\"car\"", "expected_output": "false", "explanation": "Different characters."}
                    ],
                    "hidden_test_cases": [
                        {"input": "\"listen\"\n\"silent\"", "expected_output": "true"}
                    ],
                    "skill": topic or "Strings",
                    "difficulty": difficulty
                }
            ]
        }

        lang_key = (language or "python").lower()
        if lang_key not in problems:
            lang_key = "python"

        pool = problems[lang_key]
        return pool[0]

    @staticmethod
    async def create_coding_interview(
        db: Session,
        user: User,
        req: CodingInterviewCreateRequest
    ) -> CodingInterview:
        """Creates a Coding Interview session and generates an initial problem using GenAI."""
        title = f"{req.target_role} Coding Assessment ({req.topic})"
        
        interview = CodingInterview(
            user_id=user.id,
            title=title,
            target_role=req.target_role,
            experience_level=req.experience_level,
            topic=req.topic,
            difficulty=req.difficulty,
            language=req.language.lower(),
            status="in_progress",
            total_score=0.0
        )
        db.add(interview)
        db.flush()

        # Prompt GenAI API to generate coding problem
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "coding_problem_generation.txt")
        template = ""
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                template = f.read()

        if template:
            try:
                prompt = template.format(
                    target_role=req.target_role,
                    experience_level=req.experience_level,
                    topic=req.topic,
                    difficulty=req.difficulty,
                    language=req.language
                )
            except Exception:
                prompt = f"Generate 1 coding problem in {req.language} for {req.target_role} on topic {req.topic} ({req.difficulty})."
        else:
            prompt = f"Generate 1 coding problem in {req.language} for {req.target_role} on topic {req.topic} ({req.difficulty})."

        prob_data = None
        try:
            raw_resp = await AIService._call_llm_api(prompt)
            cleaned = AIService._clean_json_string(raw_resp)
            prob_data = json.loads(cleaned)
        except Exception as e:
            logger.warning(f"GenAI coding problem generation error ({e}). Using curated fallback problem.")
            prob_data = CodingService._get_curated_fallback_problem(req.topic, req.difficulty, req.language)

        if not prob_data or not isinstance(prob_data, dict):
            prob_data = CodingService._get_curated_fallback_problem(req.topic, req.difficulty, req.language)

        question = CodingQuestion(
            coding_interview_id=interview.id,
            question_number=1,
            title=prob_data.get("title", f"{req.topic} Coding Problem"),
            description=prob_data.get("description", "Write a program to solve the given technical requirement."),
            input_format=prob_data.get("input_format", "Standard Input / Function Arguments"),
            output_format=prob_data.get("output_format", "Standard Output / Return Value"),
            constraints=prob_data.get("constraints", "Standard time limit 3.0s"),
            starter_code=prob_data.get("starter_code", "# Write your code here\ndef solution():\n    pass"),
            sample_test_cases=json.dumps(prob_data.get("sample_test_cases", [])),
            hidden_test_cases=json.dumps(prob_data.get("hidden_test_cases", [])),
            skill=prob_data.get("skill", req.topic),
            difficulty=prob_data.get("difficulty", req.difficulty)
        )
        db.add(question)
        db.commit()
        db.refresh(interview)
        return interview

    @staticmethod
    def get_coding_interview(db: Session, interview_id: str, user_id: str) -> CodingInterview:
        interview = db.query(CodingInterview).filter(CodingInterview.id == interview_id).first()
        if not interview:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coding interview not found")
        if interview.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to coding interview")
        return interview

    @staticmethod
    def run_sample_tests(db: Session, req: CodeRunRequest, user: User) -> CodeRunResultSchema:
        """Runs candidate code against sample test cases (interactive 'Run Code')."""
        question = db.query(CodingQuestion).filter(CodingQuestion.id == req.question_id).first()
        if not question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coding question not found")

        sample_cases = json.loads(question.sample_test_cases or "[]")
        exec_results = CodeExecutor.execute_test_cases(req.code, req.language, sample_cases)

        tc_schemas = [TestCaseResultSchema(**res) for res in exec_results]
        passed_count = sum(1 for r in tc_schemas if r.passed)
        
        return CodeRunResultSchema(
            total_test_cases=len(tc_schemas),
            passed_test_cases=passed_count,
            all_passed=(passed_count == len(tc_schemas) and len(tc_schemas) > 0),
            results=tc_schemas
        )

    @staticmethod
    async def submit_coding_solution(
        db: Session,
        req: CodingSubmissionRequest,
        user: User
    ) -> CodingSubmission:
        """Executes full test suite (sample + hidden) and evaluates solution using GenAI."""
        question = db.query(CodingQuestion).filter(CodingQuestion.id == req.question_id).first()
        if not question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coding question not found")

        interview = CodingService.get_coding_interview(db, question.coding_interview_id, user.id)

        sample_cases = json.loads(question.sample_test_cases or "[]")
        hidden_cases = json.loads(question.hidden_test_cases or "[]")
        all_cases = sample_cases + hidden_cases

        # Run safe code executor against all test cases
        exec_results = CodeExecutor.execute_test_cases(req.code, req.language, all_cases)
        passed_count = sum(1 for r in exec_results if r["passed"])
        total_count = len(exec_results)

        pass_ratio = (passed_count / total_count) if total_count > 0 else 0.0
        test_case_correctness_score = round(pass_ratio * 100, 1)

        # AI Evaluation prompt
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "coding_submission_evaluation.txt")
        template = ""
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                template = f.read()

        exec_summary = f"{passed_count}/{total_count} test cases passed."
        if template:
            try:
                prompt = template.format(
                    problem_title=question.title,
                    problem_description=question.description,
                    language=req.language,
                    submitted_code=req.code,
                    passed_test_cases=passed_count,
                    total_test_cases=total_count,
                    execution_summary=exec_summary
                )
            except Exception:
                prompt = f"Evaluate code submission for {question.title}. Passed: {passed_count}/{total_count}.\nCode:\n{req.code}"
        else:
            prompt = f"Evaluate code submission for {question.title}. Passed: {passed_count}/{total_count}.\nCode:\n{req.code}"

        ai_eval = None
        try:
            raw_resp = await AIService._call_llm_api(prompt)
            cleaned = AIService._clean_json_string(raw_resp)
            ai_eval = json.loads(cleaned)
        except Exception as e:
            logger.warning(f"GenAI submission evaluation error ({e}). Using rule-based scoring.")

        if not ai_eval or not isinstance(ai_eval, dict):
            # Fallback evaluation
            code_quality = 80.0 if passed_count == total_count else 60.0
            edge_case = 85.0 if passed_count == total_count else 50.0
            overall_score = round((test_case_correctness_score * 0.6) + (code_quality * 0.2) + (edge_case * 0.2), 1)
            ai_eval = {
                "time_complexity": "O(N)",
                "space_complexity": "O(1)" if "set" not in req.code and "dict" not in req.code else "O(N)",
                "correctness_score": test_case_correctness_score,
                "code_quality_score": code_quality,
                "edge_case_score": edge_case,
                "overall_coding_score": overall_score,
                "strengths": ["Submitted functional code logic.", f"Passed {passed_count} test cases."],
                "detected_mistakes": [] if passed_count == total_count else ["Failed some test cases or edge cases."],
                "optimization_suggestions": ["Ensure boundary conditions and large input sets are handled cleanly."],
                "code_review": f"The solution passed {passed_count} out of {total_count} test cases. Focus on addressing edge cases and optimal complexity.",
                "model_solution": question.starter_code
            }

        # Calculate final combined weighted score
        final_coding_score = round(
            (test_case_correctness_score * 0.50) +
            (float(ai_eval.get("code_quality_score", 80)) * 0.25) +
            (float(ai_eval.get("edge_case_score", 80)) * 0.25),
            1
        )

        existing_sub = db.query(CodingSubmission).filter(
            CodingSubmission.question_id == question.id,
            CodingSubmission.user_id == user.id
        ).first()

        if existing_sub:
            sub = existing_sub
            sub.language = req.language
            sub.submitted_code = req.code
            sub.test_cases_passed = passed_count
            sub.total_test_cases = total_count
            sub.test_case_results = json.dumps(exec_results)
            sub.coding_score = final_coding_score
            sub.time_complexity = ai_eval.get("time_complexity", "O(N)")
            sub.space_complexity = ai_eval.get("space_complexity", "O(1)")
            sub.correctness_score = test_case_correctness_score
            sub.code_quality_score = float(ai_eval.get("code_quality_score", 80))
            sub.edge_case_score = float(ai_eval.get("edge_case_score", 80))
            sub.strengths = json.dumps(ai_eval.get("strengths", []))
            sub.detected_mistakes = json.dumps(ai_eval.get("detected_mistakes", []))
            sub.optimization_suggestions = json.dumps(ai_eval.get("optimization_suggestions", []))
            sub.code_review = ai_eval.get("code_review", "")
            sub.model_solution = ai_eval.get("model_solution", "")
            sub.submitted_at = datetime.utcnow()
        else:
            sub = CodingSubmission(
                coding_interview_id=interview.id,
                question_id=question.id,
                user_id=user.id,
                language=req.language,
                submitted_code=req.code,
                test_cases_passed=passed_count,
                total_test_cases=total_count,
                test_case_results=json.dumps(exec_results),
                coding_score=final_coding_score,
                time_complexity=ai_eval.get("time_complexity", "O(N)"),
                space_complexity=ai_eval.get("space_complexity", "O(1)"),
                correctness_score=test_case_correctness_score,
                code_quality_score=float(ai_eval.get("code_quality_score", 80)),
                edge_case_score=float(ai_eval.get("edge_case_score", 80)),
                strengths=json.dumps(ai_eval.get("strengths", [])),
                detected_mistakes=json.dumps(ai_eval.get("detected_mistakes", [])),
                optimization_suggestions=json.dumps(ai_eval.get("optimization_suggestions", [])),
                code_review=ai_eval.get("code_review", ""),
                model_solution=ai_eval.get("model_solution", "")
            )
            db.add(sub)

        # Update interview score and status
        interview.total_score = final_coding_score
        interview.status = "completed"
        db.commit()
        db.refresh(sub)
        return sub
