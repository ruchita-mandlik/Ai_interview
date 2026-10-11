/* Interview Result Controller */
document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();

  const urlParams = new URLSearchParams(window.location.search);
  const interviewId = urlParams.get("id");

  if (!interviewId) {
    showToast("No interview ID provided", "error");
    window.location.href = "dashboard.html";
    return;
  }

  await loadInterviewResult(interviewId);
});

async function loadInterviewResult(interviewId) {
  try {
    const data = await API.get(`/api/evaluation/interview/${interviewId}`);

    // Update Overall Score
    const scoreValEl = document.getElementById("overall-score-val");
    if (scoreValEl) scoreValEl.textContent = `${Math.round(data.total_score || 0)}%`;

    const titleEl = document.getElementById("result-title");
    if (titleEl) titleEl.textContent = data.title || "Interview Completed!";

    // Calculate aggregated dimension scores across all evaluated questions
    let tcSum = 0, ccSum = 0, rrSum = 0, scSum = 0, duSum = 0;
    let strengthsAll = [];
    let improvementsAll = [];
    let feedbackAll = [];
    let modelAnswersAll = [];

    const evs = data.evaluations || [];
    const count = evs.length || 1;

    evs.forEach(ev => {
      tcSum += ev.technical_correctness || 0;
      ccSum += ev.conceptual_completeness || 0;
      rrSum += ev.response_relevance || 0;
      scSum += ev.structural_clarity || 0;
      duSum += ev.depth_of_understanding || 0;

      if (ev.strengths) strengthsAll.push(...ev.strengths);
      if (ev.improvements) improvementsAll.push(...ev.improvements);
      if (ev.feedback) feedbackAll.push(ev.feedback);
      if (ev.model_answer) modelAnswersAll.push(`Q${ev.question_number}: ${ev.model_answer}`);
    });

    const tcAvg = Math.round(tcSum / count);
    const ccAvg = Math.round(ccSum / count);
    const rrAvg = Math.round(rrSum / count);
    const scAvg = Math.round(scSum / count);
    const duAvg = Math.round(duSum / count);

    // Update dimension progress bars
    setBar("bar-tc", "val-tc", tcAvg);
    setBar("bar-cc", "val-cc", ccAvg);
    setBar("bar-rr", "val-rr", rrAvg);
    setBar("bar-sc", "val-sc", scAvg);
    setBar("bar-du", "val-du", duAvg);

    // Render Strengths List
    const strengthsEl = document.getElementById("strengths-list");
    if (strengthsEl) {
      const uniqueStrengths = [...new Set(strengthsAll)];
      strengthsEl.innerHTML = (uniqueStrengths.length > 0 ? uniqueStrengths : ["Demonstrated solid understanding of core concepts."])
        .map(s => `<li>${s}</li>`).join("");
    }

    // Render Improvements List
    const improvementsEl = document.getElementById("improvements-list");
    if (improvementsEl) {
      const uniqueImp = [...new Set(improvementsAll)];
      improvementsEl.innerHTML = (uniqueImp.length > 0 ? uniqueImp : ["Practice explaining complex trade-offs and edge cases."])
        .map(i => `<li>${i}</li>`).join("");
    }

    // Render Feedback Commentary
    const feedbackEl = document.getElementById("feedback-text");
    if (feedbackEl) {
      feedbackEl.textContent = feedbackAll.join(" ") || "Great effort! Review the detailed model answers below to refine your responses.";
    }

    // Render Model Answers
    const modelAnsEl = document.getElementById("model-answers-container");
    if (modelAnsEl) {
      modelAnsEl.innerHTML = evs.map(ev => `
        <div class="model-answer-box" style="margin-bottom:16px;">
          <h4 style="color:var(--primary-dark); margin-bottom:6px;">Q${ev.question_number}: ${ev.question_text}</h4>
          <p style="color:var(--text-muted); font-size:0.85rem; margin-bottom:8px;"><strong>Your Answer:</strong> ${ev.candidate_answer || 'No response provided'}</p>
          <div style="background:#FFFFFF; padding:12px; border-radius:8px; border-left:3px solid var(--primary);">
            <strong>Ideal Model Answer:</strong> ${ev.model_answer}
          </div>
        </div>
      `).join("");
    }

  } catch (err) {
    showToast(`Failed to load results: ${err.message}`, "error");
  }
}

function setBar(barId, valId, percent) {
  const bar = document.getElementById(barId);
  const val = document.getElementById(valId);
  if (bar) bar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
  if (val) val.textContent = `${percent}%`;
}
