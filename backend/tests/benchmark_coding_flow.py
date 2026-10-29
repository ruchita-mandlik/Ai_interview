import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.config.settings import settings
from backend.services.ai_service import AIService
from backend.services.coding_service import CodingService

async def profile_coding():
    print("=== PROFILING CODING FLOW ===")
    
    # 1. Coding Problem Generation
    prompt = (
        "You are a Senior Technical Software Engineer and Coding Interviewer creating a standard Data Structures & Algorithms (DSA) problem.\n"
        "TARGET ROLE: Full Stack Engineer\n"
        "EXPERIENCE LEVEL: Intermediate\n"
        "TOPIC/SKILLS: Arrays & Hash Table\n"
        "DIFFICULTY: Medium\n"
        "PROGRAMMING LANGUAGE: Python\n"
        "INSTRUCTIONS:\n"
        "Generate 1 standard Data Structures & Algorithms (DSA) problem.\n"
        "STRICT STYLE REQUIREMENT: DO NOT generate lengthy scenario-based questions, fictional company backstories, or verbose narrative setups. State the problem clearly and directly.\n"
        "Provide clear problem description with expected time and space complexity, input/output format, constraints, starter_code template in Python, 2 sample test cases, 2 hidden test cases.\n"
        "Return ONLY valid JSON matching exact keys: title, description, input_format, output_format, constraints, starter_code, sample_test_cases, hidden_test_cases, skill, difficulty."
    )
    t0 = time.time()
    raw = await AIService._call_llm_api(prompt)
    t_gen = time.time() - t0
    print(f"1. Coding Problem Generation: {t_gen:.2f}s | Output length: {len(raw)} chars")

    # 2. Coding Evaluation
    eval_prompt = (
        "You are a Principal Software Engineer evaluating a candidate solution to a DSA problem: Two Sum.\n"
        "Language: Python\n"
        "Code:\ndef solution(nums, target):\n    lookup = {}\n    for i, n in enumerate(nums):\n        if target - n in lookup:\n            return [lookup[target-n], i]\n        lookup[n] = i\n    return []\n\n"
        "Return ONLY a valid JSON object with keys: time_complexity, space_complexity, correctness_score, code_quality_score, edge_case_score, overall_coding_score, strengths, detected_mistakes, optimization_suggestions, code_review, model_solution.\n"
        "Guidelines: Keep code_review concise and evidence-based (2-3 sentences max)."
    )
    t0 = time.time()
    raw_eval = await AIService._call_llm_api(eval_prompt)
    t_eval = time.time() - t0
    print(f"2. Coding Submission Evaluation: {t_eval:.2f}s | Output length: {len(raw_eval)} chars")
    print(f"TOTAL CODING FLOW: {t_gen + t_eval:.2f}s")

if __name__ == "__main__":
    asyncio.run(profile_coding())
