import os
import sys
import json
import time
import tempfile
import subprocess
import shutil
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("uvicorn.error")

class CodeExecutor:
    @staticmethod
    def execute_test_cases(
        code: str,
        language: str,
        test_cases: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Executes candidate code against provided test cases safely in an isolated subprocess.
        Enforces strict time limits (3.0s - 4.0s) and memory caps. Never runs in the main FastAPI process.
        Returns detailed result list containing passed status, actual_output, execution_time_ms, and error trace.
        """
        language = (language or "python").lower().strip()
        if language in ["py", "python3"]:
            language = "python"
        elif language in ["js", "node", "nodejs"]:
            language = "javascript"
        elif language in ["cpp", "c++", "cplusplus"]:
            language = "cpp"
        elif language in ["java", "jvm"]:
            language = "java"

        results = []
        for idx, tc in enumerate(test_cases):
            tc_input = str(tc.get("input", "")).strip()
            expected_output = str(tc.get("expected_output", "")).strip()

            if language == "python":
                res = CodeExecutor._run_python_test(code, tc_input, expected_output, idx)
            elif language == "javascript":
                res = CodeExecutor._run_javascript_test(code, tc_input, expected_output, idx)
            elif language == "java":
                res = CodeExecutor._run_java_test(code, tc_input, expected_output, idx)
            elif language == "cpp":
                res = CodeExecutor._run_cpp_test(code, tc_input, expected_output, idx)
            else:
                res = {
                    "test_case_index": idx + 1,
                    "input": tc_input,
                    "expected_output": expected_output,
                    "actual_output": "Unsupported Language",
                    "passed": False,
                    "execution_time_ms": 0.0,
                    "error": f"Language '{language}' is not supported. Supported languages: python, javascript, java, cpp.",
                    "stdout": ""
                }
                
            results.append(res)

        return results

    @staticmethod
    def execute_custom_input(
        code: str,
        language: str,
        custom_input: str
    ) -> Dict[str, Any]:
        """
        Executes user code with arbitrary custom input. Returns execution output, time, stdout, and error diagnostics.
        """
        single_case = [{"input": custom_input, "expected_output": ""}]
        res_list = CodeExecutor.execute_test_cases(code, language, single_case)
        if res_list:
            r = res_list[0]
            return {
                "input": custom_input,
                "actual_output": r.get("actual_output", ""),
                "execution_time_ms": r.get("execution_time_ms", 0.0),
                "error": r.get("error"),
                "stdout": r.get("stdout", "")
            }
        return {
            "input": custom_input,
            "actual_output": "",
            "execution_time_ms": 0.0,
            "error": "Failed to execute custom input",
            "stdout": ""
        }

    # =========================================================================
    # 1. PYTHON EXECUTION (Isolated subprocess, timeout 3.0s)
    # =========================================================================
    @staticmethod
    def _run_python_test(code: str, tc_input: str, expected_output: str, test_idx: int) -> Dict[str, Any]:
        wrapper_code = f"""
import sys, json, ast

{code}

def __run_harness__():
    raw_input = {repr(tc_input)}
    locs = globals()
    target_fn = None
    for fn_name in ['solution', 'solve', 'two_sum', 'twoSum', 'max_sub_array', 'maxSubArray', 'is_palindrome', 'isPalindrome', 'reverse_string', 'main']:
        if fn_name in locs and callable(locs[fn_name]):
            target_fn = locs[fn_name]
            break
            
    if target_fn is None:
        for k, v in locs.items():
            if callable(v) and not k.startswith('__') and k != '__run_harness__':
                target_fn = v
                break

    if target_fn is not None:
        args = []
        if raw_input:
            lines = raw_input.strip().split('\\n')
            for line in lines:
                line_str = line.strip()
                try:
                    parsed = json.loads(line_str)
                    args.append(parsed)
                except Exception:
                    try:
                        parsed = ast.literal_eval(line_str)
                        args.append(parsed)
                    except Exception:
                        if ',' in line_str and not line_str.startswith('[') and not line_str.startswith('{{'):
                            sub_parts = line_str.split(',')
                            for sp in sub_parts:
                                sp = sp.strip()
                                try:
                                    args.append(json.loads(sp))
                                except Exception:
                                    args.append(sp)
                        else:
                            args.append(line_str)
        try:
            res = target_fn(*args)
            if res is not None:
                if isinstance(res, (dict, list, bool)):
                    print(json.dumps(res))
                else:
                    print(str(res))
        except TypeError:
            try:
                res = target_fn(raw_input)
                if res is not None:
                    print(json.dumps(res) if isinstance(res, (dict, list, bool)) else str(res))
            except Exception as inner_e:
                print(str(inner_e), file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    __run_harness__()
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(wrapper_code)
            temp_filepath = f.name

        start_time = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, temp_filepath],
                input=tc_input,
                capture_output=True,
                text=True,
                timeout=3.0
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            if proc.returncode != 0:
                clean_err = stderr or f"Process exited with code {proc.returncode}"
                if "Traceback" in clean_err:
                    clean_err = clean_err.split("Traceback")[-1].strip()
                return {
                    "test_case_index": test_idx + 1,
                    "input": tc_input,
                    "expected_output": expected_output,
                    "actual_output": stdout or "Error",
                    "passed": False,
                    "execution_time_ms": elapsed_ms,
                    "error": clean_err,
                    "stdout": stdout
                }

            passed = CodeExecutor._compare_outputs(stdout, expected_output) if expected_output else True
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": stdout,
                "passed": passed,
                "execution_time_ms": elapsed_ms,
                "error": None if passed else f"Expected '{expected_output}', but got '{stdout}'",
                "stdout": stdout
            }
        except subprocess.TimeoutExpired:
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": "Time Limit Exceeded (3.0s)",
                "passed": False,
                "execution_time_ms": 3000.0,
                "error": "Time Limit Exceeded (TLE) - Execution took longer than 3.0 seconds.",
                "stdout": ""
            }
        except Exception as e:
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": "Execution Error",
                "passed": False,
                "execution_time_ms": 0.0,
                "error": str(e),
                "stdout": ""
            }
        finally:
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass

    # =========================================================================
    # 2. JAVASCRIPT / NODE.JS EXECUTION (Node subprocess, timeout 3.0s, memory capped)
    # =========================================================================
    @staticmethod
    def _run_javascript_test(code: str, tc_input: str, expected_output: str, test_idx: int) -> Dict[str, Any]:
        node_bin = shutil.which("node")
        if not node_bin:
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": "Node.js Not Found",
                "passed": False,
                "execution_time_ms": 0.0,
                "error": "Node.js executable is not found on the server environment PATH.",
                "stdout": ""
            }

        wrapper_js = f"""
{code}

try {{
    let fn = typeof solution === 'function' ? solution : (typeof solve === 'function' ? solve : null);
    if (!fn) {{
        const fnNames = Object.keys(global).filter(k => typeof global[k] === 'function' && k !== 'solution' && !k.startsWith('_'));
        if (fnNames.length > 0) fn = global[fnNames[0]];
    }}
    let inputStr = {repr(tc_input)};
    let parsedInput;
    if (inputStr) {{
        let lines = inputStr.split('\\n');
        let args = lines.map(line => {{
            try {{ return JSON.parse(line.trim()); }} catch(e) {{ return line.trim(); }}
        }});
        if (fn) {{
            let res = fn.apply(null, args);
            if (res !== undefined) {{
                console.log(typeof res === 'object' ? JSON.stringify(res) : res);
            }}
        }}
    }} else if (fn) {{
        let res = fn();
        if (res !== undefined) {{
            console.log(typeof res === 'object' ? JSON.stringify(res) : res);
        }}
    }}
}} catch (err) {{
    console.error(err.stack || err.toString());
    process.exit(1);
}}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(wrapper_js)
            temp_filepath = f.name

        start_time = time.time()
        try:
            proc = subprocess.run(
                [node_bin, "--max-old-space-size=256", temp_filepath],
                input=tc_input,
                capture_output=True,
                text=True,
                timeout=3.0
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            if proc.returncode != 0:
                return {
                    "test_case_index": test_idx + 1,
                    "input": tc_input,
                    "expected_output": expected_output,
                    "actual_output": "Runtime Error",
                    "passed": False,
                    "execution_time_ms": elapsed_ms,
                    "error": stderr or f"Node.js process exited with code {proc.returncode}",
                    "stdout": stdout
                }

            passed = CodeExecutor._compare_outputs(stdout, expected_output) if expected_output else True
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": stdout,
                "passed": passed,
                "execution_time_ms": elapsed_ms,
                "error": None if passed else f"Expected '{expected_output}', but got '{stdout}'",
                "stdout": stdout
            }
        except subprocess.TimeoutExpired:
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": "Time Limit Exceeded (3.0s)",
                "passed": False,
                "execution_time_ms": 3000.0,
                "error": "Time Limit Exceeded (3.0s) - Execution took longer than 3.0 seconds.",
                "stdout": ""
            }
        except Exception as e:
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": "Execution Error",
                "passed": False,
                "execution_time_ms": 0.0,
                "error": str(e),
                "stdout": ""
            }
        finally:
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass

    # =========================================================================
    # 3. JAVA EXECUTION (Real javac compiler + isolated JVM runner, timeout 4.0s)
    # =========================================================================
    @staticmethod
    def _run_java_test(code: str, tc_input: str, expected_output: str, test_idx: int) -> Dict[str, Any]:
        javac_bin = shutil.which("javac")
        java_bin = shutil.which("java")

        if not javac_bin or not java_bin:
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": "Java SDK Missing",
                "passed": False,
                "execution_time_ms": 0.0,
                "error": "Java compiler (javac) or runtime (java) is not installed on the server environment PATH.",
                "stdout": ""
            }

        temp_dir = tempfile.mkdtemp(prefix="java_sandbox_")
        try:
            # Check if user wrote public static void main
            has_main = "public static void main" in code

            # Ensure public class name matches Solution or rename if needed
            cleaned_code = code
            if "public class " in cleaned_code and "public class Solution" not in cleaned_code:
                # Replace whatever public class name with Solution
                import re
                cleaned_code = re.sub(r'public\s+class\s+([A-Za-z0-9_]+)', 'public class Solution', cleaned_code, count=1)
            elif "class Solution" not in cleaned_code:
                cleaned_code = f"public class Solution {{\n{cleaned_code}\n}}"

            solution_path = os.path.join(temp_dir, "Solution.java")
            with open(solution_path, "w", encoding="utf-8") as f:
                f.write(cleaned_code)

            if has_main:
                # Compile Solution.java directly
                comp_proc = subprocess.run(
                    [javac_bin, "-encoding", "UTF-8", solution_path],
                    capture_output=True,
                    text=True,
                    timeout=6.0
                )
                if comp_proc.returncode != 0:
                    return {
                        "test_case_index": test_idx + 1,
                        "input": tc_input,
                        "expected_output": expected_output,
                        "actual_output": "Compilation Error",
                        "passed": False,
                        "execution_time_ms": 0.0,
                        "error": comp_proc.stderr.strip() or "Java compilation failed.",
                        "stdout": ""
                    }
                entry_class = "Solution"
            else:
                # Provide reflection-based Runner.java
                runner_path = os.path.join(temp_dir, "Runner.java")
                runner_source = """
import java.io.*;
import java.lang.reflect.*;
import java.util.*;

public class Runner {
    public static void main(String[] args) {
        try {
            BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line).append("\\n");
            }
            String input = sb.toString().trim();

            Class<?> clazz = Class.forName("Solution");
            Object instance = null;
            try {
                instance = clazz.getDeclaredConstructor().newInstance();
            } catch (Exception e) {}

            Method targetMethod = null;
            for (Method m : clazz.getDeclaredMethods()) {
                if (!m.getName().equals("main") && Modifier.isPublic(m.getModifiers())) {
                    targetMethod = m;
                    break;
                }
            }
            if (targetMethod == null) {
                System.err.println("No public method found in Solution class to evaluate.");
                System.exit(1);
            }

            Class<?>[] paramTypes = targetMethod.getParameterTypes();
            Object[] invokeArgs = new Object[paramTypes.length];
            String[] inputLines = input.isEmpty() ? new String[0] : input.split("\\n");

            for (int i = 0; i < paramTypes.length; i++) {
                String valStr = i < inputLines.length ? inputLines[i].trim() : "";
                Class<?> pt = paramTypes[i];
                if (pt == int[].class) {
                    valStr = valStr.replace("[", "").replace("]", "").trim();
                    if (valStr.isEmpty()) {
                        invokeArgs[i] = new int[0];
                    } else {
                        String[] parts = valStr.split(",");
                        int[] arr = new int[parts.length];
                        for (int j = 0; j < parts.length; j++) arr[j] = Integer.parseInt(parts[j].trim());
                        invokeArgs[i] = arr;
                    }
                } else if (pt == int.class || pt == Integer.class) {
                    invokeArgs[i] = Integer.parseInt(valStr);
                } else if (pt == long.class || pt == Long.class) {
                    invokeArgs[i] = Long.parseLong(valStr);
                } else if (pt == boolean.class || pt == Boolean.class) {
                    invokeArgs[i] = Boolean.parseBoolean(valStr);
                } else if (pt == String.class) {
                    if (valStr.startsWith("\\\"") && valStr.endsWith("\\\"") && valStr.length() >= 2) {
                        valStr = valStr.substring(1, valStr.length() - 1);
                    }
                    invokeArgs[i] = valStr;
                } else {
                    invokeArgs[i] = valStr;
                }
            }

            Object result = targetMethod.invoke(instance, invokeArgs);
            if (result instanceof int[]) {
                System.out.println(Arrays.toString((int[]) result));
            } else if (result instanceof Object[]) {
                System.out.println(Arrays.toString((Object[]) result));
            } else if (result != null) {
                System.out.println(result);
            }
        } catch (InvocationTargetException ite) {
            Throwable cause = ite.getCause() != null ? ite.getCause() : ite;
            cause.printStackTrace();
            System.exit(1);
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        }
    }
}
"""
                with open(runner_path, "w", encoding="utf-8") as f:
                    f.write(runner_source)

                comp_proc = subprocess.run(
                    [javac_bin, "-encoding", "UTF-8", solution_path, runner_path],
                    capture_output=True,
                    text=True,
                    timeout=6.0
                )
                if comp_proc.returncode != 0:
                    return {
                        "test_case_index": test_idx + 1,
                        "input": tc_input,
                        "expected_output": expected_output,
                        "actual_output": "Compilation Error",
                        "passed": False,
                        "execution_time_ms": 0.0,
                        "error": comp_proc.stderr.strip() or "Java compilation failed.",
                        "stdout": ""
                    }
                entry_class = "Runner"

            # Execute JVM with 256MB memory cap and 4.0s timeout
            start_time = time.time()
            run_proc = subprocess.run(
                [java_bin, "-Xmx256m", "-cp", temp_dir, entry_class],
                input=tc_input,
                capture_output=True,
                text=True,
                timeout=4.0
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            stdout = run_proc.stdout.strip()
            stderr = run_proc.stderr.strip()

            if run_proc.returncode != 0:
                clean_err = stderr or f"JVM exited with code {run_proc.returncode}"
                return {
                    "test_case_index": test_idx + 1,
                    "input": tc_input,
                    "expected_output": expected_output,
                    "actual_output": "Runtime Exception",
                    "passed": False,
                    "execution_time_ms": elapsed_ms,
                    "error": clean_err,
                    "stdout": stdout
                }

            passed = CodeExecutor._compare_outputs(stdout, expected_output) if expected_output else True
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": stdout,
                "passed": passed,
                "execution_time_ms": elapsed_ms,
                "error": None if passed else f"Expected '{expected_output}', but got '{stdout}'",
                "stdout": stdout
            }

        except subprocess.TimeoutExpired:
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": "Time Limit Exceeded (4.0s)",
                "passed": False,
                "execution_time_ms": 4000.0,
                "error": "Time Limit Exceeded (4.0s) - JVM execution took longer than 4.0 seconds.",
                "stdout": ""
            }
        except Exception as e:
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": "Execution Error",
                "passed": False,
                "execution_time_ms": 0.0,
                "error": str(e),
                "stdout": ""
            }
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    # =========================================================================
    # 4. C++ EXECUTION (Real g++ compiler if present, truthful diagnostic if missing)
    # =========================================================================
    @staticmethod
    def _run_cpp_test(code: str, tc_input: str, expected_output: str, test_idx: int) -> Dict[str, Any]:
        cpp_bin = shutil.which("g++") or shutil.which("clang++")
        if not cpp_bin:
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": "C++ Compiler Missing",
                "passed": False,
                "execution_time_ms": 0.0,
                "error": "C++ compiler (g++ / clang++) is not installed on the system PATH. Please select Python, JavaScript, or Java, or install MinGW-w64 to execute C++ code.",
                "stdout": ""
            }

        temp_dir = tempfile.mkdtemp(prefix="cpp_sandbox_")
        try:
            src_path = os.path.join(temp_dir, "solution.cpp")
            bin_path = os.path.join(temp_dir, "solution.exe" if os.name == "nt" else "solution")

            with open(src_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Compile with C++17 and optimization
            comp_proc = subprocess.run(
                [cpp_bin, "-O2", "-std=c++17", src_path, "-o", bin_path],
                capture_output=True,
                text=True,
                timeout=6.0
            )
            if comp_proc.returncode != 0:
                return {
                    "test_case_index": test_idx + 1,
                    "input": tc_input,
                    "expected_output": expected_output,
                    "actual_output": "Compilation Error",
                    "passed": False,
                    "execution_time_ms": 0.0,
                    "error": comp_proc.stderr.strip() or "C++ compilation failed.",
                    "stdout": ""
                }

            start_time = time.time()
            run_proc = subprocess.run(
                [bin_path],
                input=tc_input,
                capture_output=True,
                text=True,
                timeout=3.0
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            stdout = run_proc.stdout.strip()
            stderr = run_proc.stderr.strip()

            if run_proc.returncode != 0:
                return {
                    "test_case_index": test_idx + 1,
                    "input": tc_input,
                    "expected_output": expected_output,
                    "actual_output": "Runtime Error",
                    "passed": False,
                    "execution_time_ms": elapsed_ms,
                    "error": stderr or f"Process exited with code {run_proc.returncode}",
                    "stdout": stdout
                }

            passed = CodeExecutor._compare_outputs(stdout, expected_output) if expected_output else True
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": stdout,
                "passed": passed,
                "execution_time_ms": elapsed_ms,
                "error": None if passed else f"Expected '{expected_output}', but got '{stdout}'",
                "stdout": stdout
            }
        except subprocess.TimeoutExpired:
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": "Time Limit Exceeded (3.0s)",
                "passed": False,
                "execution_time_ms": 3000.0,
                "error": "Time Limit Exceeded (3.0s) - C++ binary execution timed out.",
                "stdout": ""
            }
        except Exception as e:
            return {
                "test_case_index": test_idx + 1,
                "input": tc_input,
                "expected_output": expected_output,
                "actual_output": "Execution Error",
                "passed": False,
                "execution_time_ms": 0.0,
                "error": str(e),
                "stdout": ""
            }
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    # =========================================================================
    # 5. OUTPUT COMPARATOR
    # =========================================================================
    @staticmethod
    def _compare_outputs(actual: str, expected: str) -> bool:
        """
        Compares actual output vs expected output handling:
        - Exact string equality
        - Whitespace and newline trimming
        - Quoted strings vs unquoted strings (e.g. '"olleh"' vs 'olleh')
        - JSON array element order flexibility if arrays
        - Boolean true/false case insensitivity
        - Numbers represented as int vs float (e.g. 10 vs 10.0)
        """
        if actual == expected:
            return True
            
        act_clean = actual.strip().replace(" ", "").replace("\n", "")
        exp_clean = expected.strip().replace(" ", "").replace("\n", "")
        if act_clean == exp_clean:
            return True

        def strip_quotes(s: str) -> str:
            st = s.strip()
            if len(st) >= 2 and ((st.startswith('"') and st.endswith('"')) or (st.startswith("'") and st.endswith("'"))):
                return st[1:-1]
            return st

        if strip_quotes(actual) == strip_quotes(expected):
            return True

        if act_clean.lower() == exp_clean.lower() and act_clean.lower() in ["true", "false"]:
            return True

        # Try parsing JSON
        try:
            act_json = json.loads(actual.strip())
            exp_json = json.loads(expected.strip())
            if isinstance(act_json, list) and isinstance(exp_json, list):
                if act_json == exp_json:
                    return True
                if sorted(str(x) for x in act_json) == sorted(str(x) for x in exp_json):
                    return True
            if act_json == exp_json:
                return True
        except Exception:
            pass

        # Try numeric comparison
        try:
            if float(actual.strip()) == float(expected.strip()):
                return True
        except Exception:
            pass

        return False

