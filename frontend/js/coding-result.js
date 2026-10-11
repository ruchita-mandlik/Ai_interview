document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();

  const urlParams = new URLSearchParams(window.location.search);
  const interviewId = urlParams.get("id");

  if (!interviewId) {
    showToast("Missing Coding Interview ID", "error");
    window.location.href = "dashboard.html";
    return;
  }

  try {
    const res = await API.getCodingResults(interviewId);
    renderCodingResults(res);
  } catch (err) {
    showToast(err.message || "Failed to load coding evaluation results", "error");
  }

  function renderCodingResults(data) {
    document.getElementById("overall-score-circle").textContent = `${Math.round(data.coding_score)}%`;
    document.getElementById("test-cases-val").textContent = `${data.test_cases_passed}/${data.total_test_cases}`;
    
    const pct = data.total_test_cases > 0 ? Math.round((data.test_cases_passed / data.total_test_cases) * 100) : 0;
    document.getElementById("pass-rate-text").textContent = `${pct}% Test Case Pass Rate`;

    document.getElementById("time-comp-val").textContent = data.time_complexity || "O(N)";
    document.getElementById("space-comp-val").textContent = data.space_complexity || "O(1)";
    document.getElementById("quality-score-val").textContent = `${Math.round(data.code_quality_score)}%`;

    // Detected Mistakes
    const mistakesList = document.getElementById("detected-mistakes-list");
    mistakesList.innerHTML = "";
    const mistakes = data.detected_mistakes || [];
    if (mistakes.length === 0) {
      mistakesList.innerHTML = "<li style='color: var(--success);'>✓ No critical logic flaws or syntax errors detected!</li>";
    } else {
      mistakes.forEach(m => {
        const li = document.createElement("li");
        li.textContent = m;
        mistakesList.appendChild(li);
      });
    }

    // Optimization Suggestions
    const optList = document.getElementById("optimization-list");
    optList.innerHTML = "";
    const suggestions = data.optimization_suggestions || [];
    if (suggestions.length === 0) {
      optList.innerHTML = "<li>Solution is well optimized for performance.</li>";
    } else {
      suggestions.forEach(s => {
        const li = document.createElement("li");
        li.textContent = s;
        optList.appendChild(li);
      });
    }

    // AI Code Review Narrative
    document.getElementById("ai-code-review-text").textContent = data.code_review || "Great attempt. Your code solution addresses the key algorithmic requirements.";

    // Ideal Model Solution
    document.getElementById("model-solution-code").textContent = data.model_solution || "// Ideal model solution placeholder";
  }
});
