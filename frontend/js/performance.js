/* Performance Analytics Controller */
document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();
  await loadPerformanceData();
});

async function loadPerformanceData() {
  try {
    const data = await API.get("/api/performance");

    // Stats
    const avgEl = document.getElementById("perf-avg-score");
    if (avgEl) avgEl.textContent = data.stats.average_score;

    const bestEl = document.getElementById("perf-best-score");
    if (bestEl) bestEl.textContent = data.stats.best_score;

    const totalEl = document.getElementById("perf-total-interviews");
    if (totalEl) totalEl.textContent = data.stats.total_interviews;

    const qEl = document.getElementById("perf-questions-answered");
    if (qEl) qEl.textContent = data.stats.questions_answered;

    // Dimension breakdown
    const dims = data.dimension_scores || {};
    setPerfBar("pbar-tc", "pval-tc", dims.technical_correctness || 0);
    setPerfBar("pbar-cc", "pval-cc", dims.conceptual_completeness || 0);
    setPerfBar("pbar-rr", "pval-rr", dims.response_relevance || 0);
    setPerfBar("pbar-sc", "pval-sc", dims.structural_clarity || 0);
    setPerfBar("pbar-du", "pval-du", dims.depth_of_understanding || 0);

    // Skill breakdown list
    const skillListContainer = document.getElementById("perf-skills-container");
    if (skillListContainer) {
      if (!data.skill_analytics || data.skill_analytics.length === 0) {
        skillListContainer.innerHTML = `<p class="text-muted">No skill metrics generated yet. Practice more interviews!</p>`;
      } else {
        skillListContainer.innerHTML = data.skill_analytics.map(item => `
          <div class="skill-item">
            <div class="skill-header">
              <span><strong>${item.skill}</strong> (${item.count} questions evaluated)</span>
              <span>${Math.round(item.score)}%</span>
            </div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" style="width:${Math.min(100, Math.max(5, item.score))}%;"></div>
            </div>
          </div>
        `).join("");
      }
    }

  } catch (err) {
    showToast(`Failed to load performance analytics: ${err.message}`, "error");
  }
}

function setPerfBar(barId, valId, percent) {
  const bar = document.getElementById(barId);
  const val = document.getElementById(valId);
  const rounded = Math.round(percent);
  if (bar) bar.style.width = `${Math.min(100, Math.max(0, rounded))}%`;
  if (val) val.textContent = `${rounded}%`;
}
