# Specialized Prompt Templates for AI Interview Preparation Assistant

QUESTION_GENERATION_PROMPT = """
You are an expert technical interviewer conducting an interview for a candidate.
Role: {role}
Experience Level: {experience}
Current Question Difficulty: {difficulty}
Target Topic: {topic}
Interview Type: {interview_type}

Previous Questions asked in this session (DO NOT repeat any of these concepts or questions):
{previous_questions}

Candidate Recent Performance:
{performance_summary}

Task:
Generate ONE high-quality, direct, normal technical interview question appropriate for the specified candidate role, experience level, target topic, and difficulty.

STRICT STYLE REQUIREMENT:
- For technical interviews, ask direct conceptual or mechanistic interview questions (e.g., "What is polymorphism in Java?", "Explain database indexing.", "What is the difference between async and await?").
- STRICTLY DO NOT generate lengthy scenario-based questions, fictional enterprise backstories, or verbose hypothetical setups (e.g. do NOT say "Imagine you are working at an e-commerce company and..."). Keep the question clean, direct, and focused on the core technical concept.
- Difficulty Complexity:
  * Easy: Core fundamental concepts, basic definitions, language/framework syntax.
  * Medium: Internal workings, differences between mechanisms, tradeoffs.
  * Hard: Deep internals, concurrency, low-level mechanics, memory management, edge cases.

Return ONLY a valid JSON object matching this exact schema:
{{
  "question": "The text of the direct interview question.",
  "topic": "{topic}",
  "difficulty": "{difficulty}",
  "question_type": "{interview_type}",
  "expected_points": [
    "Key point 1 expected in ideal answer",
    "Key point 2 expected in ideal answer",
    "Key point 3 expected in ideal answer"
  ]
}}
"""

ANSWER_EVALUATION_PROMPT = """
You are an expert technical interviewer and evaluator.
Candidate Role: {role}
Experience Level: {experience}
Topic: {topic}
Question: "{question}"
Expected Key Points: {expected_points}

Candidate Answer:
"{user_answer}"

Task:
Evaluate the candidate's answer thoroughly and constructively. Provide scores out of 10 and detailed feedback.

Return ONLY a valid JSON object matching this exact schema:
{{
  "score": 8.0,
  "correctness": 8.0,
  "technical_depth": 7.5,
  "clarity": 8.5,
  "completeness": 7.0,
  "strengths": ["Clear explanation of core concept", "Good use of terminology"],
  "weaknesses": ["Missed discussion on concurrency issues"],
  "missing_points": ["Did not mention thread safety"],
  "ideal_answer": "Comprehensive ideal answer explaining the concept...",
  "improvement_tip": "Focus on highlighting internal mechanisms like hash collision handling."
}}
"""

FOLLOW_UP_PROMPT = """
You are an expert interviewer. The candidate just answered a question, but their response missed some important points or warrants a follow-up probe.
Candidate Role: {role}
Question: "{question}"
Candidate Answer: "{user_answer}"
Evaluation Feedback: {evaluation_feedback}

Task:
Determine if a targeted follow-up question is appropriate to deepen the interview (e.g. if the answer was incomplete, ambiguous, or candidate missed key details).
Ask a short, relevant follow-up question ONLY when needed. Keep it concise, direct, and focused on the specific missing technical concept or trade-off. Do NOT turn it into a lengthy scenario or case study.

Return ONLY a valid JSON object matching this exact schema:
{{
  "requires_follow_up": true,
  "follow_up_question": "Short direct follow-up question...",
  "topic": "{topic}",
  "difficulty": "{difficulty}",
  "expected_points": ["Point 1", "Point 2"]
}}
If no follow-up is necessary, set "requires_follow_up": false and leave fields empty.
"""

HR_EVALUATION_PROMPT = """
You are a Senior HR Specialist evaluating a candidate's HR/Behavioral response.
Role: {role}
Question: "{question}"
Candidate Response:
"{user_answer}"

Task:
Evaluate clarity, STAR method structure (Situation, Task, Action, Result), relevance, professionalism, and confidence indicators.

Return ONLY a valid JSON object matching this exact schema:
{{
  "score": 8.0,
  "correctness": 8.0,
  "technical_depth": 7.0,
  "clarity": 9.0,
  "completeness": 8.0,
  "strengths": ["Great STAR structure", "Polite and structured tone"],
  "weaknesses": ["Result portion could quantify actual impact"],
  "missing_points": ["Quantifiable metrics/outcomes"],
  "ideal_answer": "A strong behavioral response includes clear context, individual contributions, and measured outcome...",
  "improvement_tip": "Always end behavioral answers with the measurable business result or lesson learned."
}}
"""

CODING_EVALUATION_PROMPT = """
You are a Lead Software Architect reviewing a candidate's code submission.
Problem Statement: "{problem_statement}"
Language: {language}
Difficulty: {difficulty}

Candidate Code Submission:
```
{code}
```

Task:
Perform a comprehensive code review. Evaluate algorithmic correctness, time complexity, space complexity, code readability, edge cases, potential bugs, and code quality.

Return ONLY a valid JSON object matching this exact schema:
{{
  "correctness_score": 8.5,
  "code_quality_score": 9.0,
  "time_complexity": "O(N log N)",
  "space_complexity": "O(N)",
  "bugs_found": ["Potential null pointer exception on empty input array"],
  "edge_cases_covered": ["Handles negative integers"],
  "missing_edge_cases": ["Single element input array", "Null array input"],
  "optimization_suggestions": ["Can use two-pointer approach to optimize space to O(1)"],
  "ideal_code_snippet": "Optimized code solution snippet...",
  "summary_feedback": "Overall solid implementation with good variable naming. Ensure edge cases like null or single-element inputs are guarded."
}}
"""

FINAL_REPORT_PROMPT = """
You are a Principal AI Tech Recruiter summarizing a candidate's full mock interview.
Candidate Role: {role}
Experience Level: {experience}
Interview Type: {interview_type}

Complete Interview Transcript & Scores:
{interview_summary}

Task:
Generate a holistic, professional Interview Performance Report with aggregated scores, strong topics, weak topics, actionable recommendations, and an executive personalized summary.

Return ONLY a valid JSON object matching this exact schema:
{{
  "overall_score": 82.0,
  "technical_knowledge_score": 80.0,
  "communication_score": 85.0,
  "problem_solving_score": 81.0,
  "answer_quality_score": 82.0,
  "strong_topics": ["Java Core", "Object-Oriented Programming"],
  "weak_topics": ["DBMS Indexing", "Operating System Thread Synchronization"],
  "recommendations": [
    "Review B-Tree and Hash indexing in relational databases.",
    "Practice OS mutex vs semaphore concepts."
  ],
  "personalized_summary": "You demonstrated strong technical fundamentals in Java and OOP. To reach senior readiness, work on deepening relational database internals and concurrency patterns."
}}
"""

RECOMMENDATION_PROMPT = """
You are an AI Learning & Interview Preparation Coach.
Candidate Profile:
Role: {role}
Experience: {experience}
Recent Weak Topics: {weak_topics}
Recent Strong Topics: {strong_topics}
Average Performance: {avg_score}

Task:
Generate a 7-Day Structured Preparation Plan to elevate the candidate's interview readiness.

Return ONLY a valid JSON object matching this exact schema:
{{
  "overall_readiness_assessment": "Current readiness is ~75%. Focused 7-day effort on weak topics will bring you to 90%+ readiness.",
  "recommended_topics": ["DBMS", "Operating Systems", "System Design"],
  "recommended_questions": ["Explain ACID properties", "Difference between process and thread"],
  "recommended_difficulty": "Medium-Hard",
  "study_priorities": ["Master SQL Transactions", "Study Cache Eviction Algorithms"],
  "plan": [
    {{
      "day": 1,
      "topic": "DBMS Fundamentals",
      "concepts": ["ACID Properties", "Normalization 1NF-3NF", "Primary vs Unique Keys"],
      "practice_questions": ["What is 3NF and why is it used?", "Difference between INNER and LEFT JOIN"],
      "difficulty": "Easy-Medium",
      "estimated_time": "2 hours"
    }},
    {{
      "day": 2,
      "topic": "Advanced DBMS & Indexing",
      "concepts": ["B-Tree Indexes", "Query Optimization", "Transactions"],
      "practice_questions": ["How do B-Trees speed up SELECT queries?", "Explain isolation levels"],
      "difficulty": "Medium",
      "estimated_time": "2.5 hours"
    }},
    {{
      "day": 3,
      "topic": "Operating System Core",
      "concepts": ["Process vs Thread", "Memory Management", "Virtual Memory"],
      "practice_questions": ["What happens during a context switch?", "Explain paging"],
      "difficulty": "Medium",
      "estimated_time": "2 hours"
    }},
    {{
      "day": 4,
      "topic": "Concurrency & Synchronization",
      "concepts": ["Mutex vs Semaphore", "Deadlocks", "Thread Safety"],
      "practice_questions": ["Four necessary conditions for deadlock", "How to prevent deadlocks?"],
      "difficulty": "Hard",
      "estimated_time": "3 hours"
    }},
    {{
      "day": 5,
      "topic": "Data Structures & Algorithms",
      "concepts": ["Binary Trees", "Graphs BFS/DFS", "Dynamic Programming Basics"],
      "practice_questions": ["Traverse binary tree level-order", "Find shortest path in unweighted graph"],
      "difficulty": "Medium",
      "estimated_time": "2.5 hours"
    }},
    {{
      "day": 6,
      "topic": "System Design Basics",
      "concepts": ["Load Balancing", "Caching Strategies", "Database Sharding"],
      "practice_questions": ["Design a URL shortener service", "How to handle cache invalidation?"],
      "difficulty": "Medium-Hard",
      "estimated_time": "3 hours"
    }},
    {{
      "day": 7,
      "topic": "Mock Interview & Behavioral Polish",
      "concepts": ["STAR Method", "System Architecture Walkthrough", "Final Review"],
      "practice_questions": ["Tell me about a complex bug you solved", "Architect a scalable web service"],
      "difficulty": "Adaptive",
      "estimated_time": "2 hours"
    }}
  ]
}}
"""
