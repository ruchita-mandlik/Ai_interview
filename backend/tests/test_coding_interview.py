import pytest
from fastapi.testclient import TestClient
from backend.services.code_executor import CodeExecutor

def test_code_executor_passing_python():
    code = """
def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        diff = target - num
        if diff in seen:
            return [seen[diff], i]
        seen[num] = i
    return []
"""
    test_cases = [
        {"input": "[2, 7, 11, 15]\n9", "expected_output": "[0, 1]"},
        {"input": "[3, 2, 4]\n6", "expected_output": "[1, 2]"}
    ]
    results = CodeExecutor.execute_test_cases(code, "python", test_cases)
    assert len(results) == 2
    assert results[0]["passed"] is True
    assert results[1]["passed"] is True


def test_code_executor_failing_python():
    code = """
def solution(nums, target):
    return [0, 0]
"""
    test_cases = [
        {"input": "[2, 7, 11, 15]\n9", "expected_output": "[0, 1]"}
    ]
    results = CodeExecutor.execute_test_cases(code, "python", test_cases)
    assert len(results) == 1
    assert results[0]["passed"] is False


def test_code_executor_syntax_error_python():
    code = "def broken_func(: invalid syntax"
    test_cases = [
        {"input": "123", "expected_output": "123"}
    ]
    results = CodeExecutor.execute_test_cases(code, "python", test_cases)
    assert len(results) == 1
    assert results[0]["passed"] is False
    assert results[0]["error"] is not None


def get_auth_headers(client: TestClient):
    reg = client.post("/api/auth/register", json={
        "name": "Coder User",
        "email": "coder@example.com",
        "password": "Password123!"
    })
    token = reg.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


def test_create_coding_interview_api(client: TestClient):
    auth_headers = get_auth_headers(client)
    payload = {
        "target_role": "Python Engineer",
        "experience_level": "Intermediate",
        "topic": "Data Structures",
        "difficulty": "Medium",
        "language": "python"
    }
    response = client.post("/api/coding/start", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["target_role"] == "Python Engineer"
    assert len(data["questions"]) > 0
    assert "starter_code" in data["questions"][0]


def test_run_tests_and_submit_coding_api(client: TestClient):
    auth_headers = get_auth_headers(client)
    
    # 1. Start interview
    start_payload = {
        "target_role": "Backend Engineer",
        "experience_level": "Intermediate",
        "topic": "Algorithms",
        "difficulty": "Medium",
        "language": "python"
    }
    start_res = client.post("/api/coding/start", json=start_payload, headers=auth_headers)
    assert start_res.status_code == 201
    interview_data = start_res.json()
    interview_id = interview_data["id"]
    question_id = interview_data["questions"][0]["id"]

    # 2. Run sample tests
    code_solution = """
def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        diff = target - num
        if diff in seen:
            return [seen[diff], i]
        seen[num] = i
    return []
"""
    run_payload = {
        "question_id": question_id,
        "language": "python",
        "code": code_solution
    }
    run_res = client.post("/api/coding/run-tests", json=run_payload, headers=auth_headers)
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert "total_test_cases" in run_data

    # 3. Submit solution
    submit_payload = {
        "question_id": question_id,
        "language": "python",
        "code": code_solution
    }
    submit_res = client.post("/api/coding/submit", json=submit_payload, headers=auth_headers)
    assert submit_res.status_code == 200
    sub_data = submit_res.json()
    assert "coding_score" in sub_data
    assert "time_complexity" in sub_data
    assert "space_complexity" in sub_data

    # 4. Fetch results
    results_res = client.get(f"/api/coding/{interview_id}/results", headers=auth_headers)
    assert results_res.status_code == 200
    res_data = results_res.json()
    assert res_data["id"] == sub_data["id"]
