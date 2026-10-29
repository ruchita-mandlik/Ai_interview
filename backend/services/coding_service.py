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
    CustomRunRequest,
    CustomRunResultSchema,
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
        """Provides curated standard DSA coding problems by difficulty if GenAI API hits rate limits."""
        diff = (difficulty or "Medium").capitalize()
        lang_key = (language or "python").lower()
        if lang_key in ["py", "python3"]:
            lang_key = "python"
        elif lang_key in ["js", "node", "nodejs"]:
            lang_key = "javascript"
        elif lang_key in ["java", "jvm"]:
            lang_key = "java"
        elif lang_key in ["cpp", "c++", "cplusplus"]:
            lang_key = "cpp"

        problems = {
            "python": {
                "Easy": {
                    "title": "Reverse a String",
                    "description": "Given a string `s`, return the string reversed.\n\nExpected Time Complexity: O(N)\nExpected Space Complexity: O(N)",
                    "input_format": "Line 1: String `s`",
                    "output_format": "String representing reversed `s`",
                    "constraints": "0 <= s.length <= 10^5",
                    "starter_code": "def solution(s):\n    # Write your solution here\n    pass\n",
                    "hints": [
                        "Consider using two pointers swapping characters from the ends inward.",
                        "In Python, string slicing `s[::-1]` or converting to a list can reverse characters in O(N)."
                    ],
                    "sample_test_cases": [
                        {"input": "\"hello\"", "expected_output": "\"olleh\"", "explanation": "The reverse of 'hello' is 'olleh'."},
                        {"input": "\"interview\"", "expected_output": "\"weivretni\"", "explanation": "The reverse of 'interview' is 'weivretni'."}
                    ],
                    "hidden_test_cases": [
                        {"input": "\"a\"", "expected_output": "\"a\""},
                        {"input": "\"racecar\"", "expected_output": "\"racecar\""}
                    ],
                    "skill": topic or "Strings & DSA",
                    "difficulty": "Easy"
                },
                "Medium": {
                    "title": "Two Sum Target Index",
                    "description": "Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.\n\nExpected Time Complexity: O(N)\nExpected Space Complexity: O(N)",
                    "input_format": "Line 1: JSON array of integers `nums`\nLine 2: Target integer",
                    "output_format": "JSON array containing two indices [index1, index2]",
                    "constraints": "2 <= nums.length <= 10^4\n-10^9 <= nums[i] <= 10^9\n-10^9 <= target <= 10^9",
                    "starter_code": "def solution(nums, target):\n    # Write your solution here\n    pass\n",
                    "hints": [
                        "A brute force approach checks all pairs in O(N^2). Can you do it in O(N) by storing previously seen elements?",
                        "Use a Hash Map mapping `target - num` to its index to achieve instant lookups."
                    ],
                    "sample_test_cases": [
                        {"input": "[2, 7, 11, 15]\n9", "expected_output": "[0, 1]", "explanation": "nums[0] + nums[1] == 9, so return [0, 1]."},
                        {"input": "[3, 2, 4]\n6", "expected_output": "[1, 2]", "explanation": "nums[1] + nums[2] == 6."}
                    ],
                    "hidden_test_cases": [
                        {"input": "[3, 3]\n6", "expected_output": "[0, 1]"},
                        {"input": "[1, 5, 8, 3]\n8", "expected_output": "[1, 3]"}
                    ],
                    "skill": topic or "Arrays & Hash Table",
                    "difficulty": "Medium"
                },
                "Hard": {
                    "title": "Maximum Subarray Sum",
                    "description": "Given an integer array `nums`, find the contiguous subarray (containing at least one number) which has the largest sum and return its sum.\n\nExpected Time Complexity: O(N)\nExpected Space Complexity: O(1)",
                    "input_format": "JSON array of integers `nums`",
                    "output_format": "Integer representing the maximum subarray sum",
                    "constraints": "1 <= nums.length <= 10^5\n-10^4 <= nums[i] <= 10^4",
                    "starter_code": "def solution(nums):\n    # Write your solution here\n    pass\n",
                    "hints": [
                        "Think about Kadane's Algorithm: at each position, decide whether to extend the current running subarray or start a new one.",
                        "Track `current_sum = max(num, current_sum + num)` and `max_sum = max(max_sum, current_sum)`."
                    ],
                    "sample_test_cases": [
                        {"input": "[-2, 1, -3, 4, -1, 2, 1, -5, 4]", "expected_output": "6", "explanation": "[4, -1, 2, 1] has the largest sum = 6."},
                        {"input": "[1]", "expected_output": "1", "explanation": "Single element array."}
                    ],
                    "hidden_test_cases": [
                        {"input": "[5, 4, -1, 7, 8]", "expected_output": "23"},
                        {"input": "[-1, -2, -3]", "expected_output": "-1"}
                    ],
                    "skill": topic or "Dynamic Programming / DSA",
                    "difficulty": "Hard"
                }
            },
            "javascript": {
                "Easy": {
                    "title": "Check Palindrome String",
                    "description": "Given a string `s`, return `true` if it is a palindrome, or `false` otherwise.\n\nExpected Time Complexity: O(N)\nExpected Space Complexity: O(1)",
                    "input_format": "Line 1: string s",
                    "output_format": "Boolean true or false",
                    "constraints": "0 <= s.length <= 10^5",
                    "starter_code": "function solution(s) {\n    // Write your solution here\n    return false;\n}\n",
                    "hints": [
                        "A palindrome reads identically forwards and backwards.",
                        "Use two pointers, one at start and one at end, moving inwards."
                    ],
                    "sample_test_cases": [
                        {"input": "\"racecar\"", "expected_output": "true", "explanation": "'racecar' reads the same forwards and backwards."},
                        {"input": "\"hello\"", "expected_output": "false", "explanation": "'hello' is not a palindrome."}
                    ],
                    "hidden_test_cases": [
                        {"input": "\"a\"", "expected_output": "true"},
                        {"input": "\"ab\"", "expected_output": "false"}
                    ],
                    "skill": topic or "Strings & DSA",
                    "difficulty": "Easy"
                },
                "Medium": {
                    "title": "Two Sum Target Index",
                    "description": "Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.\n\nExpected Time Complexity: O(N)\nExpected Space Complexity: O(N)",
                    "input_format": "Line 1: JSON array of integers `nums`\nLine 2: Target integer",
                    "output_format": "JSON array containing two indices [index1, index2]",
                    "constraints": "2 <= nums.length <= 10^5",
                    "starter_code": "function solution(nums, target) {\n    // Write your solution here\n    return [];\n}\n",
                    "hints": [
                        "Use a JavaScript Map to record seen elements and their indices.",
                        "For each number, check if `target - nums[i]` exists in the Map."
                    ],
                    "sample_test_cases": [
                        {"input": "[2, 7, 11, 15]\n9", "expected_output": "[0, 1]", "explanation": "2 + 7 = 9"},
                        {"input": "[3, 2, 4]\n6", "expected_output": "[1, 2]", "explanation": "2 + 4 = 6"}
                    ],
                    "hidden_test_cases": [
                        {"input": "[3, 3]\n6", "expected_output": "[0, 1]"},
                        {"input": "[1, 5, 8, 3]\n8", "expected_output": "[1, 3]"}
                    ],
                    "skill": topic or "Algorithms & DSA",
                    "difficulty": "Medium"
                },
                "Hard": {
                    "title": "Maximum Subarray Sum",
                    "description": "Given an integer array `nums`, find the contiguous subarray (containing at least one number) which has the largest sum and return its sum.\n\nExpected Time Complexity: O(N)\nExpected Space Complexity: O(1)",
                    "input_format": "Line 1: JSON array of integers nums",
                    "output_format": "Integer sum",
                    "constraints": "1 <= nums.length <= 10^5",
                    "starter_code": "function solution(nums) {\n    // Write your solution here\n    return 0;\n}\n",
                    "hints": [
                        "Use Kadane's algorithm to compute maximum subarray ending at index i.",
                        "Maintain maxEndingHere = Math.max(nums[i], maxEndingHere + nums[i])."
                    ],
                    "sample_test_cases": [
                        {"input": "[-2, 1, -3, 4, -1, 2, 1, -5, 4]", "expected_output": "6", "explanation": "[4, -1, 2, 1] gives 6."},
                        {"input": "[1]", "expected_output": "1", "explanation": "Single item."}
                    ],
                    "hidden_test_cases": [
                        {"input": "[5, 4, -1, 7, 8]", "expected_output": "23"}
                    ],
                    "skill": topic or "Dynamic Programming",
                    "difficulty": "Hard"
                }
            },
            "java": {
                "Easy": {
                    "title": "Reverse a String",
                    "description": "Given a string `s`, return the string reversed.\n\nExpected Time Complexity: O(N)\nExpected Space Complexity: O(N)",
                    "input_format": "Line 1: string s",
                    "output_format": "Reversed string",
                    "constraints": "0 <= s.length() <= 10^5",
                    "starter_code": "import java.util.*;\n\npublic class Solution {\n    public String solution(String s) {\n        // Write your solution here\n        return new StringBuilder(s).reverse().toString();\n    }\n}\n",
                    "hints": [
                        "StringBuilder provides an efficient in-place reversal in O(N).",
                        "Alternatively, iterate backwards from length - 1 down to 0."
                    ],
                    "sample_test_cases": [
                        {"input": "\"hello\"", "expected_output": "\"olleh\"", "explanation": "Reverse of 'hello' is 'olleh'."},
                        {"input": "\"java\"", "expected_output": "\"avaj\"", "explanation": "Reverse of 'java' is 'avaj'."}
                    ],
                    "hidden_test_cases": [
                        {"input": "\"a\"", "expected_output": "\"a\""},
                        {"input": "\"radar\"", "expected_output": "\"radar\""}
                    ],
                    "skill": topic or "Strings & Java",
                    "difficulty": "Easy"
                },
                "Medium": {
                    "title": "Two Sum Target Index",
                    "description": "Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.\n\nExpected Time Complexity: O(N)\nExpected Space Complexity: O(N)",
                    "input_format": "Line 1: JSON array of integers nums\nLine 2: target integer",
                    "output_format": "Array containing two indices [index1, index2]",
                    "constraints": "2 <= nums.length <= 10^5",
                    "starter_code": "import java.util.*;\n\npublic class Solution {\n    public int[] solution(int[] nums, int target) {\n        // Write your solution here\n        return new int[]{};\n    }\n}\n",
                    "hints": [
                        "Use HashMap<Integer, Integer> to map array values to their indices.",
                        "Check if `map.containsKey(target - nums[i])`."
                    ],
                    "sample_test_cases": [
                        {"input": "[2, 7, 11, 15]\n9", "expected_output": "[0, 1]", "explanation": "2 + 7 = 9"},
                        {"input": "[3, 2, 4]\n6", "expected_output": "[1, 2]", "explanation": "2 + 4 = 6"}
                    ],
                    "hidden_test_cases": [
                        {"input": "[3, 3]\n6", "expected_output": "[0, 1]"},
                        {"input": "[1, 5, 8, 3]\n8", "expected_output": "[1, 3]"}
                    ],
                    "skill": topic or "Arrays & Java Collections",
                    "difficulty": "Medium"
                },
                "Hard": {
                    "title": "Maximum Subarray Sum",
                    "description": "Given an integer array `nums`, find the contiguous subarray (containing at least one number) which has the largest sum and return its sum.\n\nExpected Time Complexity: O(N)\nExpected Space Complexity: O(1)",
                    "input_format": "Line 1: JSON array of integers nums",
                    "output_format": "Integer maximum sum",
                    "constraints": "1 <= nums.length <= 10^5",
                    "starter_code": "import java.util.*;\n\npublic class Solution {\n    public int solution(int[] nums) {\n        // Write your solution here\n        return 0;\n    }\n}\n",
                    "hints": [
                        "Apply Kadane's algorithm tracking maxSoFar and currentMax.",
                        "Initialize maxSoFar with nums[0]."
                    ],
                    "sample_test_cases": [
                        {"input": "[-2, 1, -3, 4, -1, 2, 1, -5, 4]", "expected_output": "6", "explanation": "[4, -1, 2, 1] gives 6."},
                        {"input": "[1]", "expected_output": "1", "explanation": "Single item."}
                    ],
                    "hidden_test_cases": [
                        {"input": "[5, 4, -1, 7, 8]", "expected_output": "23"}
                    ],
                    "skill": topic or "Dynamic Programming",
                    "difficulty": "Hard"
                }
            },
            "cpp": {
                "Easy": {
                    "title": "Reverse a String",
                    "description": "Given a string `s`, return the string reversed.\n\nExpected Time Complexity: O(N)\nExpected Space Complexity: O(N)",
                    "input_format": "Standard Input: string s",
                    "output_format": "Standard Output: reversed string",
                    "constraints": "0 <= s.length() <= 10^5",
                    "starter_code": "#include <iostream>\n#include <string>\n#include <algorithm>\nusing namespace std;\n\nint main() {\n    string s;\n    if (cin >> s) {\n        reverse(s.begin(), s.end());\n        cout << s << endl;\n    }\n    return 0;\n}\n",
                    "hints": [
                        "std::reverse from <algorithm> reverses strings in-place in O(N) time.",
                        "Read string from std::cin and write to std::cout."
                    ],
                    "sample_test_cases": [
                        {"input": "\"hello\"", "expected_output": "\"olleh\"", "explanation": "Reversed is olleh"},
                        {"input": "\"cpp\"", "expected_output": "\"ppc\"", "explanation": "Reversed is ppc"}
                    ],
                    "hidden_test_cases": [
                        {"input": "\"a\"", "expected_output": "\"a\""}
                    ],
                    "skill": topic or "C++ Basics",
                    "difficulty": "Easy"
                },
                "Medium": {
                    "title": "Two Sum Target Index",
                    "description": "Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.\n\nExpected Time Complexity: O(N)\nExpected Space Complexity: O(N)",
                    "input_format": "JSON array of integers on Line 1, target on Line 2",
                    "output_format": "[index1, index2]",
                    "constraints": "2 <= nums.length <= 10^5",
                    "starter_code": "#include <iostream>\n#include <vector>\n#include <unordered_map>\nusing namespace std;\n\n// Write solution here\nint main() {\n    return 0;\n}\n",
                    "hints": [
                        "Use std::unordered_map<int, int> to map numbers to their index.",
                        "Check if `map.find(target - num) != map.end()`."
                    ],
                    "sample_test_cases": [
                        {"input": "[2, 7, 11, 15]\n9", "expected_output": "[0, 1]", "explanation": "2 + 7 = 9"}
                    ],
                    "hidden_test_cases": [
                        {"input": "[3, 2, 4]\n6", "expected_output": "[1, 2]"}
                    ],
                    "skill": topic or "Hash Tables & C++ STL",
                    "difficulty": "Medium"
                },
                "Hard": {
                    "title": "Maximum Subarray Sum",
                    "description": "Given an integer array `nums`, find the contiguous subarray (containing at least one number) which has the largest sum and return its sum.",
                    "input_format": "JSON array of integers",
                    "output_format": "Integer max sum",
                    "constraints": "1 <= nums.length <= 10^5",
                    "starter_code": "#include <iostream>\n#include <vector>\n#include <algorithm>\nusing namespace std;\n\nint main() {\n    return 0;\n}\n",
                    "hints": [
                        "Kadane's algorithm requires only two variables: current_max and max_so_far.",
                        "Time: O(N), Space: O(1)."
                    ],
                    "sample_test_cases": [
                        {"input": "[-2, 1, -3, 4, -1, 2, 1, -5, 4]", "expected_output": "6", "explanation": "[4, -1, 2, 1] gives 6."}
                    ],
                    "hidden_test_cases": [
                        {"input": "[5, 4, -1, 7, 8]", "expected_output": "23"}
                    ],
                    "skill": topic or "Dynamic Programming",
                    "difficulty": "Hard"
                }
            }
        }

        if lang_key not in problems:
            lang_key = "python"

        pool = problems[lang_key]
        return pool.get(diff, pool.get("Medium", pool[list(pool.keys())[0]]))

    @staticmethod
    async def create_coding_interview(
        db: Session,
        user: User,
        req: CodingInterviewCreateRequest
    ) -> CodingInterview:
        """Creates a Coding Interview session and generates an initial problem dynamically using GenAI."""
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

        prob_data = await CodingService._generate_problem_with_ai(
            target_role=req.target_role,
            experience_level=req.experience_level,
            topic=req.topic,
            difficulty=req.difficulty,
            language=req.language,
            question_number=1
        )

        hints_list = prob_data.get("hints", [])
        if not isinstance(hints_list, list):
            hints_list = [str(hints_list)]

        question = CodingQuestion(
            coding_interview_id=interview.id,
            question_number=1,
            title=prob_data.get("title", f"{req.topic} Coding Problem"),
            description=prob_data.get("description", "Write a program to solve the given technical requirement."),
            input_format=prob_data.get("input_format", "Standard Input / Function Arguments"),
            output_format=prob_data.get("output_format", "Standard Output / Return Value"),
            constraints=prob_data.get("constraints", "Standard time limit 3.0s"),
            starter_code=prob_data.get("starter_code", "# Write your code here\ndef solution():\n    pass"),
            hints=json.dumps(hints_list),
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
    async def _generate_problem_with_ai(
        target_role: str,
        experience_level: str,
        topic: str,
        difficulty: str,
        language: str,
        question_number: int = 1
    ) -> Dict[str, Any]:
        """Calls Gemini API dynamically to generate a standard DSA question with constraints, hints, and test cases."""
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "coding_problem_generation.txt")
        template = ""
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    template = f.read()
            except Exception:
                template = ""

        if template:
            try:
                prompt = template.format(
                    target_role=target_role,
                    experience_level=experience_level,
                    topic=topic,
                    difficulty=difficulty,
                    language=language
                )
            except Exception:
                prompt = CodingService._build_direct_prompt(target_role, experience_level, topic, difficulty, language)
        else:
            prompt = CodingService._build_direct_prompt(target_role, experience_level, topic, difficulty, language)

        prob_data = None
        try:
            raw_resp = await AIService._call_llm_api(prompt)
            cleaned = AIService._clean_json_string(raw_resp)
            prob_data = json.loads(cleaned)
        except Exception as e:
            logger.warning(f"GenAI coding problem generation error ({e}). Using curated fallback problem.")
            prob_data = CodingService._get_curated_fallback_problem(topic, difficulty, language)

        if not prob_data or not isinstance(prob_data, dict):
            prob_data = CodingService._get_curated_fallback_problem(topic, difficulty, language)

        return prob_data

    @staticmethod
    def _build_direct_prompt(target_role: str, experience_level: str, topic: str, difficulty: str, language: str) -> str:
        return (
            f"You are a Senior Technical Software Engineer and Coding Interviewer creating a standard Data Structures & Algorithms (DSA) problem.\n"
            f"TARGET ROLE: {target_role}\n"
            f"EXPERIENCE LEVEL: {experience_level}\n"
            f"TOPIC/SKILLS: {topic}\n"
            f"DIFFICULTY: {difficulty}\n"
            f"PROGRAMMING LANGUAGE: {language}\n"
            "INSTRUCTIONS:\n"
            "Generate 1 standard Data Structures & Algorithms (DSA) problem (e.g., 'Reverse a string', 'Find the second-largest element in an array', 'Check whether a string is a palindrome', 'Find two numbers that sum to a target', 'Valid Anagram', 'Maximum Subarray Sum').\n"
            "STRICT STYLE REQUIREMENT: DO NOT generate lengthy scenario-based questions, fictional company backstories, or verbose narrative setups. State the problem clearly and directly.\n"
            "Provide clear problem description with expected time and space complexity, input/output format, constraints, starter_code template in {language}, exactly 2 progressive hints, 2 sample test cases, 2 hidden test cases.\n"
            "Return ONLY valid JSON matching exact keys: title, description, input_format, output_format, constraints, starter_code, hints, sample_test_cases, hidden_test_cases, skill, difficulty."
        )

    @staticmethod
    def get_coding_interview(db: Session, interview_id: str, user_id: str) -> CodingInterview:
        interview = db.query(CodingInterview).filter(CodingInterview.id == interview_id).first()
        if not interview:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coding interview not found")
        if interview.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to coding interview")
        return interview

    @staticmethod
    def list_coding_interviews(db: Session, user_id: str) -> List[CodingInterview]:
        """Lists all coding interviews for the current user."""
        return db.query(CodingInterview).filter(CodingInterview.user_id == user_id).order_by(CodingInterview.created_at.desc()).all()

    @staticmethod
    async def generate_next_problem(db: Session, interview_id: str, user: User) -> CodingQuestion:
        """Generates the next sequential problem for this interview session."""
        interview = CodingService.get_coding_interview(db, interview_id, user.id)
        next_num = len(interview.questions) + 1

        prob_data = await CodingService._generate_problem_with_ai(
            target_role=interview.target_role,
            experience_level=interview.experience_level,
            topic=interview.topic,
            difficulty=interview.difficulty,
            language=interview.language,
            question_number=next_num
        )

        hints_list = prob_data.get("hints", [])
        if not isinstance(hints_list, list):
            hints_list = [str(hints_list)]

        question = CodingQuestion(
            coding_interview_id=interview.id,
            question_number=next_num,
            title=prob_data.get("title", f"{interview.topic} Problem #{next_num}"),
            description=prob_data.get("description", "Write a program to solve the given technical requirement."),
            input_format=prob_data.get("input_format", "Standard Input"),
            output_format=prob_data.get("output_format", "Standard Output"),
            constraints=prob_data.get("constraints", "Standard time limit 3.0s"),
            starter_code=prob_data.get("starter_code", "# Write your code here\ndef solution():\n    pass"),
            hints=json.dumps(hints_list),
            sample_test_cases=json.dumps(prob_data.get("sample_test_cases", [])),
            hidden_test_cases=json.dumps(prob_data.get("hidden_test_cases", [])),
            skill=prob_data.get("skill", interview.topic),
            difficulty=prob_data.get("difficulty", interview.difficulty)
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        return question

    @staticmethod
    def run_sample_tests(db: Session, req: CodeRunRequest, user: User) -> CodeRunResultSchema:
        """Runs candidate code against sample test cases (interactive 'Run Code') and optional custom input."""
        question = db.query(CodingQuestion).filter(CodingQuestion.id == req.question_id).first()
        if not question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coding question not found")

        sample_cases = json.loads(question.sample_test_cases or "[]")
        exec_results = CodeExecutor.execute_test_cases(req.code, req.language, sample_cases)

        tc_schemas = [TestCaseResultSchema(**res) for res in exec_results]
        passed_count = sum(1 for r in tc_schemas if r.passed)

        custom_res_schema = None
        if req.custom_input is not None and req.custom_input.strip() != "":
            raw_custom = CodeExecutor.execute_custom_input(req.code, req.language, req.custom_input)
            custom_res_schema = CustomRunResultSchema(**raw_custom)
        
        return CodeRunResultSchema(
            total_test_cases=len(tc_schemas),
            passed_test_cases=passed_count,
            all_passed=(passed_count == len(tc_schemas) and len(tc_schemas) > 0),
            results=tc_schemas,
            custom_result=custom_res_schema
        )

    @staticmethod
    def run_custom_input(req: CustomRunRequest) -> CustomRunResultSchema:
        """Executes candidate code with user-supplied custom input directly."""
        raw_res = CodeExecutor.execute_custom_input(req.code, req.language, req.custom_input)
        return CustomRunResultSchema(**raw_res)

    @staticmethod
    async def submit_coding_solution(
        db: Session,
        req: CodingSubmissionRequest,
        user: User
    ) -> CodingSubmission:
        """Executes full test suite (sample + hidden) and evaluates solution using real test evidence plus GenAI."""
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
            # Fallback evaluation based strictly on actual test execution
            code_quality = 85.0 if passed_count == total_count else (65.0 if passed_count > 0 else 40.0)
            edge_case = 90.0 if passed_count == total_count else (55.0 if passed_count > 0 else 30.0)
            overall_score = round((test_case_correctness_score * 0.50) + (code_quality * 0.25) + (edge_case * 0.25), 1)
            ai_eval = {
                "time_complexity": "O(N)",
                "space_complexity": "O(1)" if "set" not in req.code and "dict" not in req.code and "Map" not in req.code else "O(N)",
                "correctness_score": test_case_correctness_score,
                "code_quality_score": code_quality,
                "edge_case_score": edge_case,
                "overall_coding_score": overall_score,
                "strengths": [
                    "Structured implementation according to requirements.",
                    f"Passed {passed_count} of {total_count} execution test cases."
                ],
                "detected_mistakes": [] if passed_count == total_count else [
                    f"Failed {total_count - passed_count} test case(s). Check edge cases or input format."
                ],
                "optimization_suggestions": [
                    "Ensure boundary checks (e.g. empty inputs or extreme values) are handled."
                ],
                "code_review": f"Solution executed against {total_count} test cases with a pass rate of {round(pass_ratio * 100, 1)}%.",
                "model_solution": question.starter_code
            }

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
