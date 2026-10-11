document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();

  const urlParams = new URLSearchParams(window.location.search);
  const interviewId = urlParams.get("id");

  if (!interviewId) {
    showToast("Invalid Coding Interview ID", "error");
    window.location.href = "coding-config.html";
    return;
  }

  let interviewData = null;
  let currentQuestion = null;

  const codeTextarea = document.getElementById("code-textarea");
  const langSelect = document.getElementById("editor-language");
  const runTestsBtn = document.getElementById("run-tests-btn");
  const drawerSubmitBtn = document.getElementById("drawer-submit-btn");
  const headerSubmitBtn = document.getElementById("header-submit-btn");
  const resetCodeBtn = document.getElementById("reset-code-btn");
  const drawerBody = document.getElementById("drawer-body");

  // Handle Tab key inside Code Textarea
  codeTextarea.addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const start = codeTextarea.selectionStart;
      const end = codeTextarea.selectionEnd;
      codeTextarea.value = codeTextarea.value.substring(0, start) + "    " + codeTextarea.value.substring(end);
      codeTextarea.selectionStart = codeTextarea.selectionEnd = start + 4;
    }
  });

  // Load Interview & Question Data
  async function loadInterview() {
    try {
      interviewData = await API.getCodingInterview(interviewId);
      if (!interviewData || !interviewData.questions || interviewData.questions.length === 0) {
        showToast("No questions found in this coding assessment.", "error");
        return;
      }

      currentQuestion = interviewData.questions[0];

      // Update UI elements
      document.getElementById("interview-title").textContent = interviewData.title;
      document.getElementById("problem-title").textContent = currentQuestion.title;
      document.getElementById("problem-topic").textContent = currentQuestion.skill || interviewData.topic;
      document.getElementById("problem-role").textContent = interviewData.target_role;

      const diffBadge = document.getElementById("problem-difficulty");
      diffBadge.textContent = currentQuestion.difficulty;
      diffBadge.className = `badge-difficulty badge-${currentQuestion.difficulty.toLowerCase()}`;

      document.getElementById("problem-description-text").textContent = currentQuestion.description;
      document.getElementById("problem-constraints").textContent = currentQuestion.constraints || "1 <= N <= 10^5";

      langSelect.value = interviewData.language || "python";

      // Populate Starter Code if code area is empty
      if (!codeTextarea.value || codeTextarea.value.trim() === "") {
        codeTextarea.value = currentQuestion.starter_code || "# Write code here\n";
      }

      // Render Sample Test Cases Cards
      renderSampleTestCases(currentQuestion.sample_test_cases || []);
    } catch (err) {
      showToast(err.message || "Failed to load coding interview", "error");
    }
  }

  function renderSampleTestCases(cases) {
    const container = document.getElementById("sample-test-cases-container");
    container.innerHTML = "";

    if (!cases || cases.length === 0) {
      container.innerHTML = "<div style='color: #64748B;'>No sample test cases specified.</div>";
      return;
    }

    cases.forEach((tc, idx) => {
      const card = document.createElement("div");
      card.className = "test-case-sample-card";
      card.innerHTML = `
        <div style="font-weight: 700; color: #38BDF8; margin-bottom: 6px;">Sample Case #${idx + 1}</div>
        <div class="sample-row"><span class="sample-label">Input:</span> ${escapeHtml(tc.input)}</div>
        <div class="sample-row"><span class="sample-label">Expected Output:</span> ${escapeHtml(tc.expected_output)}</div>
        ${tc.explanation ? `<div class="sample-row" style="color: #94A3B8;"><span class="sample-label">Explanation:</span> ${escapeHtml(tc.explanation)}</div>` : ''}
      `;
      container.appendChild(card);
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Reset Starter Code
  resetCodeBtn.addEventListener("click", () => {
    if (currentQuestion && currentQuestion.starter_code) {
      codeTextarea.value = currentQuestion.starter_code;
      showToast("Starter code reset", "info");
    }
  });

  // Run Sample Tests Action
  runTestsBtn.addEventListener("click", async () => {
    if (!currentQuestion) return;
    const code = codeTextarea.value.trim();
    if (!code) {
      showToast("Please write code before running tests.", "warning");
      return;
    }

    runTestsBtn.disabled = true;
    runTestsBtn.textContent = "⏳ Executing...";
    drawerBody.innerHTML = `<div style="color: #38BDF8; font-weight: 600;">Running sample test cases in safe sandbox...</div>`;

    try {
      const res = await API.runCodingTests({
        question_id: currentQuestion.id,
        language: langSelect.value,
        code: code
      });

      renderExecutionResults(res);
    } catch (err) {
      drawerBody.innerHTML = `<div style="color: #EF4444; font-weight: 700;">Execution Error: ${escapeHtml(err.message)}</div>`;
    } finally {
      runTestsBtn.disabled = false;
      runTestsBtn.textContent = "▶ Run Sample Tests";
    }
  });

  function renderExecutionResults(res) {
    const passedBadge = res.all_passed
      ? `<span class="test-result-badge test-passed">✓ PASSED (${res.passed_test_cases}/${res.total_test_cases})</span>`
      : `<span class="test-result-badge test-failed">✕ FAILED (${res.passed_test_cases}/${res.total_test_cases})</span>`;

    let html = `<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
      <div>${passedBadge}</div>
      <div style="font-size: 0.8rem; color: #94A3B8;">Sample Cases Evaluated</div>
    </div>`;

    res.results.forEach((tc) => {
      const statusBadge = tc.passed
        ? `<span style="color: #10B981; font-weight: 700;">✓ Pass</span>`
        : `<span style="color: #EF4444; font-weight: 700;">✕ Fail</span>`;

      html += `
        <div class="result-card-item" style="border-left: 3px solid ${tc.passed ? '#10B981' : '#EF4444'};">
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>Case #${tc.test_case_index} — ${statusBadge}</span>
            <span style="color: #64748B; font-size: 0.75rem;">${tc.execution_time_ms} ms</span>
          </div>
          <div><span style="color: #38BDF8;">Input:</span> ${escapeHtml(tc.input)}</div>
          <div><span style="color: #38BDF8;">Expected:</span> ${escapeHtml(tc.expected_output)}</div>
          <div><span style="color: #38BDF8;">Actual:</span> ${escapeHtml(tc.actual_output)}</div>
          ${tc.error ? `<div style="color: #EF4444; margin-top: 4px;"><span style="color: #F87171;">Error Log:</span> ${escapeHtml(tc.error)}</div>` : ''}
        </div>
      `;
    });

    drawerBody.innerHTML = html;
  }

  // Submit Final Code Action
  async function submitSolution() {
    if (!currentQuestion) return;
    const code = codeTextarea.value.trim();
    if (!code) {
      showToast("Please write your solution before submitting.", "warning");
      return;
    }

    drawerSubmitBtn.disabled = true;
    headerSubmitBtn.disabled = true;
    drawerSubmitBtn.textContent = "⏳ Evaluating...";
    headerSubmitBtn.textContent = "⏳ Evaluating...";
    drawerBody.innerHTML = `<div style="color: #38BDF8; font-weight: 700;">Running full test suite & Cloud GenAI Code Evaluation...</div>`;

    try {
      await API.submitCodingSolution({
        question_id: currentQuestion.id,
        language: langSelect.value,
        code: code
      });

      showToast("Submission Evaluated Successfully!", "success");
      setTimeout(() => {
        window.location.href = `coding-result.html?id=${interviewId}`;
      }, 800);
    } catch (err) {
      showToast(err.message || "Failed to submit code solution", "error");
      drawerSubmitBtn.disabled = false;
      headerSubmitBtn.disabled = false;
      drawerSubmitBtn.textContent = "🚀 Submit Final Code";
      headerSubmitBtn.textContent = "Submit Solution";
    }
  }

  drawerSubmitBtn.addEventListener("click", submitSolution);
  headerSubmitBtn.addEventListener("click", submitSolution);

  // Timer Setup (20 Minutes)
  let timeLeft = 20 * 60;
  const timerElem = document.getElementById("coding-timer");
  setInterval(() => {
    if (timeLeft <= 0) return;
    timeLeft--;
    const mins = Math.floor(timeLeft / 60);
    const secs = timeLeft % 60;
    timerElem.textContent = `⏱ ${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }, 1000);

  // Load initial interview
  loadInterview();
});
