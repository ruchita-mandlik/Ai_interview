import os
import shutil
import pytest
from fastapi.testclient import TestClient
from backend.services.code_executor import CodeExecutor
from backend.services.readiness_service import ReadinessService
from backend.database.database import get_db

def test_code_executor_python_real_execution():
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
    assert results[0]["execution_time_ms"] > 0


def test_code_executor_javascript_real_execution():
    node_bin = shutil.which("node")
    if not node_bin:
        pytest.skip("Node.js not installed on system")

    js_code = """
function solution(nums, target) {
    const map = new Map();
    for (let i = 0; i < nums.length; i++) {
        const diff = target - nums[i];
        if (map.has(diff)) return [map.get(diff), i];
        map.set(nums[i], i);
    }
    return [];
}
"""
    test_cases = [
        {"input": "[2, 7, 11, 15]\n9", "expected_output": "[0, 1]"},
        {"input": "[3, 2, 4]\n6", "expected_output": "[1, 2]"}
    ]
    results = CodeExecutor.execute_test_cases(js_code, "javascript", test_cases)
    assert len(results) == 2
    assert results[0]["passed"] is True
    assert results[1]["passed"] is True


def test_code_executor_java_real_execution():
    javac_bin = shutil.which("javac")
    java_bin = shutil.which("java")
    if not javac_bin or not java_bin:
        pytest.skip("Java JDK (javac/java) not installed on system")

    java_code = """
import java.util.*;

public class Solution {
    public int[] solution(int[] nums, int target) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int comp = target - nums[i];
            if (map.containsKey(comp)) {
                return new int[]{map.get(comp), i};
            }
            map.put(nums[i], i);
        }
        return new int[]{};
    }
}
"""
    test_cases = [
        {"input": "[2, 7, 11, 15]\n9", "expected_output": "[0, 1]"}
    ]
    results = CodeExecutor.execute_test_cases(java_code, "java", test_cases)
    assert len(results) == 1
    assert results[0]["passed"] is True
    assert results[0]["actual_output"] == "[0, 1]"


def test_code_executor_cpp_compiler_detection():
    cpp_bin = shutil.which("g++") or shutil.which("clang++")
    cpp_code = """
#include <iostream>
using namespace std;
int main() {
    cout << "CPP_OK" << endl;
    return 0;
}
"""
    test_cases = [{"input": "", "expected_output": "CPP_OK"}]
    results = CodeExecutor.execute_test_cases(cpp_code, "cpp", test_cases)
    assert len(results) == 1
    if not cpp_bin:
        assert results[0]["passed"] is False
        assert "not installed" in results[0]["error"].lower()
    else:
        assert results[0]["passed"] is True


def test_code_executor_custom_input():
    code = """
def solution(s):
    return s.upper()
"""
    res = CodeExecutor.execute_custom_input(code, "python", "interviewai")
    assert res["actual_output"] == "INTERVIEWAI"
    assert res["error"] is None


def test_code_executor_timeout_enforcement():
    infinite_loop_code = """
def solution():
    while True:
        pass
"""
    test_cases = [{"input": "", "expected_output": "done"}]
    results = CodeExecutor.execute_test_cases(infinite_loop_code, "python", test_cases)
    assert len(results) == 1
    assert results[0]["passed"] is False
    assert "Time Limit Exceeded" in results[0]["error"]


def get_auth_headers(client: TestClient, email="coder_master@example.com"):
    reg = client.post("/api/auth/register", json={
        "name": "Coder Master",
        "email": email,
        "password": "Password123!"
    })
    token = reg.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


def test_complete_coding_interview_workflow(client: TestClient):
    auth_headers = get_auth_headers(client, email="coding_e2e@example.com")

    # 1. Start Coding Interview
    payload = {
        "target_role": "Senior Backend Architect",
        "experience_level": "Advanced",
        "topic": "Arrays & Hash Table",
        "difficulty": "Medium",
        "language": "python"
    }
    response = client.post("/api/coding/start", json=payload, headers=auth_headers)
    assert response.status_code == 201
    interview = response.json()
    assert "id" in interview
    assert len(interview["questions"]) > 0
    q1 = interview["questions"][0]
    assert "hints" in q1
    assert isinstance(q1["hints"], list)

    interview_id = interview["id"]
    question_id = q1["id"]

    # 2. List Coding Interviews
    list_res = client.get("/api/coding/list", headers=auth_headers)
    assert list_res.status_code == 200
    interviews = list_res.json()
    assert any(i["id"] == interview_id for i in interviews)

    # 3. Run Sample Tests with Custom Input
    code_solution = """
def solution(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        diff = target - num
        if diff in seen:
            return [seen[diff], i]
        seen[num] = i
    return []
"""
    run_req = {
        "question_id": question_id,
        "language": "python",
        "code": code_solution,
        "custom_input": "[10, 20, 30]\n50"
    }
    run_res = client.post("/api/coding/run-tests", json=run_req, headers=auth_headers)
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["total_test_cases"] > 0
    assert run_data["custom_result"] is not None
    assert run_data["custom_result"]["actual_output"] == "[1, 2]"

    # 4. Direct Custom Input Endpoint
    custom_direct_res = client.post("/api/coding/run-custom", json={
        "code": code_solution,
        "language": "python",
        "custom_input": "[5, 10]\n15"
    }, headers=auth_headers)
    assert custom_direct_res.status_code == 200
    assert custom_direct_res.json()["actual_output"] == "[0, 1]"

    # 5. Submit Final Solution
    sub_res = client.post("/api/coding/submit", json={
        "question_id": question_id,
        "language": "python",
        "code": code_solution
    }, headers=auth_headers)
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["total_test_cases"] > 0
    assert sub_data["coding_score"] >= 0
    assert "time_complexity" in sub_data
    assert "space_complexity" in sub_data

    # 6. Fetch Results Endpoint
    res_get = client.get(f"/api/coding/{interview_id}/results", headers=auth_headers)
    assert res_get.status_code == 200
    assert res_get.json()["id"] == sub_data["id"]

    # 7. Generate Next Sequential Problem
    next_res = client.post(f"/api/coding/{interview_id}/next", headers=auth_headers)
    assert next_res.status_code == 200
    q2 = next_res.json()
    assert q2["question_number"] == 2
    assert "title" in q2
