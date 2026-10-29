import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import asyncio
import time
from backend.services.ai_service import AIService

async def benchmark_flow():
    print("=== PROFILING CURRENT FLOW ===")
    
    # 1. Question Generation
    t0 = time.time()
    q = await AIService.generate_interview_questions('Java Developer', 'Intermediate', 'Java Core', 'Technical', 'Medium', 1)
    t_qgen = time.time() - t0
    q_txt = q[0]["question"][:60]
    print(f"1. Question Generation: {t_qgen:.2f}s | Q: {q_txt}...")

    # 2. Answer Evaluation
    t0 = time.time()
    ev = await AIService.evaluate_candidate_answer(
        q[0]['question'],
        'Polymorphism in Java allows objects to take multiple forms through method overriding (runtime) and method overloading (compile-time).',
        'Java Core',
        'Java Developer',
        'Medium'
    )
    t_eval = time.time() - t0
    print(f"2. Answer Evaluation: {t_eval:.2f}s | Score: {ev.overall_score}%")

    # 3. Adaptive Question
    t0 = time.time()
    ad = await AIService.generate_next_adaptive_question(
        'Java Developer',
        'Intermediate',
        'Java Core',
        'Technical',
        q[0]['question'],
        'Polymorphism in Java allows objects to take multiple forms...',
        ev.overall_score,
        'Medium',
        2
    )
    t_adapt = time.time() - t0
    ad_txt = ad["question"][:60]
    print(f"3. Adaptive Next Question: {t_adapt:.2f}s | Next Q: {ad_txt}...")

    print(f"TOTAL SUBMISSION LATENCY (Evaluation + Next Question): {t_eval + t_adapt:.2f}s")

if __name__ == "__main__":
    asyncio.run(benchmark_flow())
