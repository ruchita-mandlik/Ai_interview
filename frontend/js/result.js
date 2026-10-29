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

    const deepAnalysisBtn = document.getElementById("btn-view-deep-analysis") || document.getElementById("btn-deep-analysis");
    if (deepAnalysisBtn) {
      deepAnalysisBtn.href = `analysis.html?id=${encodeURIComponent(interviewId)}`;
    }

    const roadmapBtn = document.getElementById("btn-view-roadmap") || document.getElementById("btn-roadmap");
    if (roadmapBtn) {
      roadmapBtn.href = `roadmap.html?id=${encodeURIComponent(interviewId)}`;
    }

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
      const evaluatedHtml = evs.map(ev => `
        <div class="model-answer-box" style="margin-bottom:16px;">
          <h4 style="color:var(--primary-dark); margin-bottom:6px;">Q${ev.question_number}: ${escapeHtml(ev.question_text || '')} <span style="font-size:0.75rem; background:#E0E7FF; color:#4338CA; padding:2px 8px; border-radius:10px; margin-left:8px;">Score: ${Math.round(ev.overall_score || 0)}%</span></h4>
          <p style="color:var(--text-muted); font-size:0.85rem; margin-bottom:8px;"><strong>Your Answer:</strong> ${escapeHtml(ev.candidate_answer || 'No response provided')}</p>
          <div style="background:#FFFFFF; padding:12px; border-radius:8px; border-left:3px solid var(--primary);">
            <strong>Ideal Model Answer:</strong> ${escapeHtml(ev.model_answer || '')}
          </div>
        </div>
      `).join("");

      const skippedHtml = (data.skipped_questions || []).map(sq => `
        <div class="model-answer-box" style="margin-bottom:16px; border:1px dashed #9CA3AF;">
          <h4 style="color:#6B7280; margin-bottom:6px;">Q${sq.question_number}: ${escapeHtml(sq.question_text || '')} <span style="font-size:0.75rem; background:#F3F4F6; color:#6B7280; padding:2px 8px; border-radius:10px; margin-left:8px;">Skipped / Passed</span></h4>
          <p style="color:#9CA3AF; font-size:0.85rem; margin-bottom:8px;"><em>Candidate skipped this question. Excluded from overall score calculation.</em></p>
          <div style="background:#F9FAFB; padding:12px; border-radius:8px; border-left:3px solid #9CA3AF;">
            <strong>Adaptation Rationale:</strong> ${escapeHtml(sq.adaptation_reason || "Topic skipped; focus on reviewing core concepts.")}
          </div>
        </div>
      `).join("");

      modelAnsEl.innerHTML = (evaluatedHtml + skippedHtml) || "<p style='color:var(--text-muted);'>No questions were evaluated.</p>";
    }

    // Render Session-to-Session Comparison
    let comparison = data.session_comparison;
    if (!comparison) {
      try {
        comparison = await API.get(`/api/intelligence/session-comparison/${interviewId}`);
      } catch (e) {
        console.warn("Session comparison fetch fallback failed:", e);
      }
    }
    if (comparison) {
      renderSessionComparison(comparison, data.total_score);
    }

  } catch (err) {
    showToast(`Failed to load results: ${err.message}`, "error");
  }
}

function renderSessionComparison(comp, latestScore) {
  if (!comp) return;

  // Trend Badge
  const trendBadge = document.getElementById("comparison-trend-badge");
  if (trendBadge) {
    if (comp.is_baseline_session) {
      trendBadge.textContent = "Baseline Session";
      trendBadge.className = "badge badge-primary";
    } else if (comp.improvement_trend === "improving") {
      trendBadge.textContent = `Progressing (+${comp.score_change}%)`;
      trendBadge.className = "badge badge-success";
    } else if (comp.improvement_trend === "declining") {
      trendBadge.textContent = `Declining (${comp.score_change}%)`;
      trendBadge.className = "badge badge-warning";
    } else {
      trendBadge.textContent = "Consistent";
      trendBadge.className = "badge badge-primary";
    }
  }

  // Explanation
  const expEl = document.getElementById("comparison-explanation");
  if (expEl) expEl.textContent = comp.trend_explanation || "Progress comparison with previous sessions.";

  // Previous score
  const prevScoreEl = document.getElementById("comp-prev-score");
  const prevMetaEl = document.getElementById("comp-prev-meta");
  if (prevScoreEl) {
    prevScoreEl.textContent = comp.previous_score !== null && comp.previous_score !== undefined
      ? `${Math.round(comp.previous_score)}%`
      : "--";
  }
  if (prevMetaEl) {
    prevMetaEl.textContent = comp.previous_date ? `Session on ${comp.previous_date}` : "First Recorded Mock";
  }

  // Latest score
  const currScoreEl = document.getElementById("comp-curr-score");
  const currMetaEl = document.getElementById("comp-curr-meta");
  if (currScoreEl) {
    const scoreVal = comp.current_score !== null && comp.current_score !== undefined
      ? Math.round(comp.current_score)
      : Math.round(latestScore || 0);
    currScoreEl.textContent = `${scoreVal}%`;
  }
  if (currMetaEl) {
    currMetaEl.textContent = comp.current_date ? `Completed on ${comp.current_date}` : "Current Session";
  }

  // Delta score
  const deltaScoreEl = document.getElementById("comp-delta-score");
  const deltaMetaEl = document.getElementById("comp-delta-meta");
  if (deltaScoreEl) {
    if (comp.is_baseline_session || comp.score_change === null || comp.score_change === undefined) {
      deltaScoreEl.textContent = "Baseline";
      deltaScoreEl.style.color = "#2563EB";
      if (deltaMetaEl) deltaMetaEl.textContent = "Reference Established";
    } else {
      const delta = comp.score_change;
      if (delta > 0) {
        deltaScoreEl.textContent = `+${delta}%`;
        deltaScoreEl.style.color = "#10B981";
        if (deltaMetaEl) deltaMetaEl.textContent = "Upward Progress";
      } else if (delta < 0) {
        deltaScoreEl.textContent = `${delta}%`;
        deltaScoreEl.style.color = "#EF4444";
        if (deltaMetaEl) deltaMetaEl.textContent = "Score Drop";
      } else {
        deltaScoreEl.textContent = "0.0%";
        deltaScoreEl.style.color = "#64748B";
        if (deltaMetaEl) deltaMetaEl.textContent = "Unchanged";
      }
    }
  }

  // Repeated Mistakes
  const repEl = document.getElementById("comp-repeated-mistakes");
  if (repEl) {
    const reps = comp.repeated_mistakes || [];
    if (reps.length > 0) {
      repEl.innerHTML = reps.map(m => `
        <li style="margin-bottom: 6px;">
          <strong>${escapeHtml(m.mistake || m)}</strong>
          <span style="font-size:0.7rem; background:#FED7D7; color:#9B2C2C; padding:1px 6px; border-radius:4px; font-weight:700; margin-left:4px;">Repeated Gap</span>
        </li>
      `).join("");
    } else {
      repEl.innerHTML = `<li><em>${comp.is_baseline_session ? "Baseline session recorded. Mistakes will be tracked for recurring patterns." : "Zero recurring mistakes detected! Historical mistakes were not repeated."}</em></li>`;
    }
  }

  // Newly Resolved Weaknesses
  const resEl = document.getElementById("comp-resolved-weaknesses");
  if (resEl) {
    const res = comp.newly_resolved_weaknesses || [];
    if (res.length > 0) {
      resEl.innerHTML = res.map(w => `
        <li style="margin-bottom: 6px;">
          <strong>${escapeHtml(w.concept_or_skill)}</strong>
          <span style="font-size:0.75rem; background:#DCFCE7; color:#166534; padding:2px 6px; border-radius:4px; font-weight:700; margin-left:4px;">+${w.improvement_delta}% Verified</span>
        </li>
      `).join("");
    } else {
      resEl.innerHTML = `<li><em>${comp.is_baseline_session ? "Subsequent sessions will identify resolved skills once higher scores are achieved." : "Continue targeted practice to verify resolution of remaining gaps."}</em></li>`;
    }
  }

  // Recommended Next Actions
  const actEl = document.getElementById("comp-next-actions");
  if (actEl) {
    const acts = comp.next_recommended_actions || [];
    if (acts.length > 0) {
      actEl.innerHTML = acts.map(a => `<li style="margin-bottom: 4px;">${escapeHtml(a)}</li>`).join("");
    } else {
      actEl.innerHTML = `<li>Review the question model answers below to strengthen response structure.</li>`;
    }
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function setBar(barId, valId, percent) {
  const bar = document.getElementById(barId);
  const val = document.getElementById(valId);
  if (bar) bar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
  if (val) val.textContent = `${percent}%`;
}
