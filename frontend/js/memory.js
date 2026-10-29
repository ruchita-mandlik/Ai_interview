/* InterviewAI — Interview Memory & Progress Intelligence Dashboard Controller */

let currentFilter = "all";
let filterDateFrom = null;
let filterDateTo = null;
let selectedSessionA = null;
let selectedSessionB = null;

let analyticsData = null;
let summaryData = null;

// Chart.js references for clean re-rendering
let chartTrajectoryInstance = null;
let chartImprovementInstance = null;
let chartSkillPerfInstance = null;
let chartWeaknessFreqInstance = null;
let chartSessionCompInstance = null;
let chartScoreDistInstance = null;

document.addEventListener("DOMContentLoaded", () => {
  requireAuth();
  initUserProfile();
  loadAnalyticsDashboard();
});

// Initialize User Profile in Sidebar
function initUserProfile() {
  const user = API.getUser();
  if (user) {
    const avatar = document.getElementById("sidebar-user-avatar");
    if (avatar) avatar.textContent = (user.name || user.email || "U").charAt(0).toUpperCase();

    const nameEl = document.getElementById("sidebar-user-name");
    if (nameEl) nameEl.textContent = user.name || user.email.split("@")[0];

    const roleEl = document.getElementById("sidebar-user-role");
    if (roleEl) roleEl.textContent = user.target_role || "Software Developer";
  }
}

// Load and Render Analytics Dashboard
async function loadAnalyticsDashboard() {
  const loadingEl = document.getElementById("memory-loading");
  const emptyEl = document.getElementById("memory-empty");
  const contentEl = document.getElementById("memory-content");

  try {
    loadingEl.style.display = "block";
    emptyEl.style.display = "none";
    contentEl.style.display = "none";

    const params = {};
    if (filterDateFrom) params.date_from = filterDateFrom;
    if (filterDateTo) params.date_to = filterDateTo;
    if (selectedSessionA) params.session_a_id = selectedSessionA;
    if (selectedSessionB) params.session_b_id = selectedSessionB;

    const [analyticsRes, summaryRes] = await Promise.all([
      API.getAnalyticsDashboard(params).catch(err => {
        console.warn("Analytics dashboard error:", err);
        return null;
      }),
      API.getMemorySummary().catch(err => {
        console.warn("Memory summary error:", err);
        return null;
      })
    ]);

    loadingEl.style.display = "none";

    if (!analyticsRes || analyticsRes.valid_evaluated_sessions === 0) {
      emptyEl.style.display = "block";
      const emptyMsg = document.getElementById("empty-state-message");
      if (emptyMsg && analyticsRes && analyticsRes.exclusion_reason) {
        emptyMsg.textContent = analyticsRes.exclusion_reason;
      }
      return;
    }

    analyticsData = analyticsRes;
    summaryData = summaryRes;
    contentEl.style.display = "block";

    // Setup session dropdowns if not set
    if (!selectedSessionA && analyticsRes.session_comparison) {
      selectedSessionA = analyticsRes.session_comparison.session_a_id;
      selectedSessionB = analyticsRes.session_comparison.session_b_id;
    }

    renderHeaderAndMetrics(analyticsRes, summaryRes);
    renderExclusionNotice(analyticsRes);
    renderScoreTrajectoryChart(analyticsRes.score_trajectory || []);
    renderImprovementTrendChart(analyticsRes.improvement_trend || []);
    renderSkillPerformanceChart(analyticsRes.skill_performance || []);
    renderWeaknessFrequencyChart(analyticsRes.weakness_frequency || []);
    renderSessionComparison(analyticsRes);
    renderScoreDistributionChart(analyticsRes.score_distribution || []);
    renderNextBestAction(summaryRes, analyticsRes);
    renderSessionArchiveTable(analyticsRes.score_trajectory || []);

    // Bind refresh button
    const refreshBtn = document.getElementById("btn-refresh-memory");
    if (refreshBtn) {
      refreshBtn.onclick = async () => {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = `<span>⏳</span> <span>Syncing...</span>`;
        await loadAnalyticsDashboard();
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = `<span>🔄</span> <span>Sync Telemetry</span>`;
        showToast("Interview memory analytics synchronized!", "success");
      };
    }

  } catch (err) {
    console.error("Failed to load interview memory dashboard:", err);
    loadingEl.style.display = "none";
    emptyEl.style.display = "block";
    showToast("Error loading memory analytics: " + (err.message || "Unknown error"), "error");
  }
}

// Render Header & Top Summary KPI Metrics
function renderHeaderAndMetrics(analytics, summary) {
  const roleEl = document.getElementById("memory-target-role");
  if (roleEl && analytics.target_role) {
    roleEl.textContent = `Target Role: ${analytics.target_role}`;
  }

  // Header Banner Pill Stats
  const statSessions = document.getElementById("stat-sessions-count");
  if (statSessions) statSessions.textContent = analytics.valid_evaluated_sessions;

  const statAvg = document.getElementById("stat-avg-score");
  const avgVal = Number(analytics.overall_average_score ?? 0);
  if (statAvg) statAvg.textContent = `${!isNaN(avgVal) ? Math.round(avgVal) : 0}%`;

  const statImproved = document.getElementById("stat-improved-count");
  const improvedList = (analytics.skill_performance || []).filter(s => s.status === "improving" || s.status === "mastered");
  if (statImproved) statImproved.textContent = improvedList.length;

  const statWeakness = document.getElementById("stat-weakness-count");
  const activeWeaknesses = (analytics.weakness_frequency || []).filter(w => w.status === "active_weakness");
  if (statWeakness) statWeakness.textContent = activeWeaknesses.length;

  // Top Summary Metric Cards
  const kpiValidSessions = document.getElementById("kpi-valid-sessions");
  if (kpiValidSessions) kpiValidSessions.textContent = analytics.valid_evaluated_sessions;

  const totalQuestions = (analytics.score_trajectory || []).reduce((acc, cur) => acc + (cur.total_questions || 0), 0);
  const kpiQuestions = document.getElementById("kpi-questions-count");
  if (kpiQuestions) kpiQuestions.textContent = `${totalQuestions} questions evaluated`;

  const kpiAvg = document.getElementById("kpi-avg-score");
  if (kpiAvg) kpiAvg.textContent = `${!isNaN(avgVal) ? Math.round(avgVal) : 0}%`;

  const kpiRange = document.getElementById("kpi-score-range");
  if (kpiRange) {
    const hi = analytics.highest_score !== null ? `${Math.round(analytics.highest_score)}%` : "--";
    const lo = analytics.lowest_score !== null ? `${Math.round(analytics.lowest_score)}%` : "--";
    kpiRange.textContent = `High: ${hi} | Low: ${lo}`;
  }

  const kpiImproved = document.getElementById("kpi-improved-skills");
  if (kpiImproved) kpiImproved.textContent = improvedList.length;

  const kpiWeaknesses = document.getElementById("kpi-weaknesses");
  if (kpiWeaknesses) kpiWeaknesses.textContent = activeWeaknesses.length;

  // Trajectory KPI
  const kpiTrajectory = document.getElementById("kpi-trajectory");
  const kpiDelta = document.getElementById("kpi-overall-delta");
  if (analytics.score_trajectory && analytics.score_trajectory.length > 0) {
    const firstScore = analytics.score_trajectory[0].score;
    const latestScore = analytics.score_trajectory[analytics.score_trajectory.length - 1].score;
    const delta = Math.round((latestScore - firstScore) * 10) / 10;
    const sign = delta > 0 ? "+" : "";

    if (kpiTrajectory) {
      if (delta >= 5.0) {
        kpiTrajectory.textContent = "Improving";
        kpiTrajectory.style.color = "#16A34A";
      } else if (delta <= -5.0) {
        kpiTrajectory.textContent = "Declining";
        kpiTrajectory.style.color = "#DC2626";
      } else {
        kpiTrajectory.textContent = "Stable";
        kpiTrajectory.style.color = "#2563EB";
      }
    }
    if (kpiDelta) {
      kpiDelta.textContent = analytics.score_trajectory.length === 1 ? "Baseline established" : `Overall Gain: ${sign}${delta}%`;
    }
  }
}

// Render Exclusion Notice if Any
function renderExclusionNotice(analytics) {
  const container = document.getElementById("exclusion-badge-container");
  const badge = document.getElementById("exclusion-badge");
  if (analytics.excluded_incomplete_sessions > 0) {
    if (container) container.style.display = "block";
    if (badge) {
      badge.textContent = `ℹ️ ${analytics.excluded_incomplete_sessions} incomplete session(s) excluded`;
      badge.title = analytics.exclusion_reason || "Sessions in progress or lacking completed evaluations are excluded from telemetry.";
    }
  } else {
    if (container) container.style.display = "none";
  }
}

// 1. Score Trajectory Line Chart
function renderScoreTrajectoryChart(trajectory) {
  const canvas = document.getElementById("chart-score-trajectory");
  if (!canvas) return;

  if (chartTrajectoryInstance) {
    chartTrajectoryInstance.destroy();
  }

  const labels = trajectory.map(t => t.date);
  const dataScores = trajectory.map(t => t.score);

  chartTrajectoryInstance = new Chart(canvas, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Evaluation Score",
        data: dataScores,
        borderColor: "#2563EB",
        backgroundColor: "rgba(37, 99, 235, 0.08)",
        borderWidth: 3,
        tension: 0.35,
        fill: true,
        pointBackgroundColor: "#1D4ED8",
        pointBorderColor: "#FFFFFF",
        pointBorderWidth: 2,
        pointRadius: 6,
        pointHoverRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0F172A",
          titleFont: { size: 13, weight: "bold" },
          bodyFont: { size: 12 },
          padding: 12,
          callbacks: {
            title: (items) => {
              const idx = items[0].dataIndex;
              const item = trajectory[idx];
              return `${item.session_title} (${item.date})`;
            },
            label: (item) => {
              const idx = item.dataIndex;
              const sess = trajectory[idx];
              const deltaStr = sess.score_change !== null ? ` (Change: ${sess.score_change > 0 ? "+" : ""}${sess.score_change}%)` : " (Baseline)";
              return [
                `Score: ${sess.score}%${deltaStr}`,
                `Role: ${sess.target_role}`,
                `Topic: ${sess.topic} (${sess.difficulty})`,
                `Evaluations: ${sess.evaluations_count}`
              ];
            }
          }
        }
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { callback: v => v + "%", font: { size: 11 } },
          grid: { color: "#F1F5F9" }
        },
        x: {
          ticks: { font: { size: 11 } },
          grid: { display: false }
        }
      },
      onClick: (evt, activeEls) => {
        if (activeEls && activeEls.length > 0) {
          const idx = activeEls[0].index;
          const sess = trajectory[idx];
          inspectSessionEvidence(sess.session_id);
        }
      }
    }
  });
}

// 2. Improvement Trend & Moving Average Chart
function renderImprovementTrendChart(improvementItems) {
  const canvas = document.getElementById("chart-improvement-trend");
  if (!canvas) return;

  if (chartImprovementInstance) {
    chartImprovementInstance.destroy();
  }

  const labels = improvementItems.map(i => i.date);
  const sessionScores = improvementItems.map(i => i.score);
  const movingAverages = improvementItems.map(i => i.cumulative_avg);

  // Status pill update
  const pill = document.getElementById("improvement-status-pill");
  if (pill && improvementItems.length > 0) {
    const latest = improvementItems[improvementItems.length - 1];
    if (latest.evidence_status === "sufficient" && latest.verified_gain_delta !== null) {
      if (latest.verified_gain_delta >= 5.0) {
        pill.className = "delta-badge positive";
        pill.textContent = `▲ +${latest.verified_gain_delta}% Verified Gain`;
      } else if (latest.verified_gain_delta <= -5.0) {
        pill.className = "delta-badge negative";
        pill.textContent = `▼ ${latest.verified_gain_delta}% vs Baseline`;
      } else {
        pill.className = "delta-badge neutral";
        pill.textContent = "Stable Performance";
      }
    } else {
      pill.className = "delta-badge neutral";
      pill.textContent = "Baseline Progress";
    }
  }

  chartImprovementInstance = new Chart(canvas, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Session Score",
          data: sessionScores,
          borderColor: "#93C5FD",
          backgroundColor: "transparent",
          borderWidth: 2,
          borderDash: [5, 5],
          pointRadius: 4,
          pointBackgroundColor: "#3B82F6"
        },
        {
          label: "Cumulative Average Velocity",
          data: movingAverages,
          borderColor: "#7C3AED",
          backgroundColor: "rgba(124, 58, 237, 0.08)",
          borderWidth: 3,
          tension: 0.3,
          fill: true,
          pointRadius: 5,
          pointBackgroundColor: "#6D28D9"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          backgroundColor: "#0F172A",
          padding: 10,
          callbacks: {
            label: (item) => `${item.dataset.label}: ${item.raw}%`
          }
        }
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { callback: v => v + "%", font: { size: 11 } },
          grid: { color: "#F1F5F9" }
        },
        x: { ticks: { font: { size: 11 } }, grid: { display: false } }
      }
    }
  });
}

// 3. Skill-wise Performance (Baseline vs Latest) Grouped Bar Chart
function renderSkillPerformanceChart(skills) {
  const canvas = document.getElementById("chart-skill-performance");
  if (!canvas) return;

  if (chartSkillPerfInstance) {
    chartSkillPerfInstance.destroy();
  }

  // Display top 8 evaluated skills
  const displaySkills = skills.slice(0, 8);
  const labels = displaySkills.map(s => s.skill);
  const baselines = displaySkills.map(s => s.baseline_score);
  const latestScores = displaySkills.map(s => s.latest_score);

  chartSkillPerfInstance = new Chart(canvas, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Baseline Score",
          data: baselines,
          backgroundColor: "#93C5FD",
          borderRadius: 6
        },
        {
          label: "Latest Score",
          data: latestScores,
          backgroundColor: "#10B981",
          borderRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          backgroundColor: "#0F172A",
          padding: 10,
          callbacks: {
            label: (item) => {
              const sk = displaySkills[item.dataIndex];
              const deltaStr = sk.has_sufficient_evidence ? ` (Delta: ${sk.score_delta > 0 ? "+" : ""}${sk.score_delta}%)` : " (1 evaluation)";
              return `${item.dataset.label}: ${item.raw}%${deltaStr}`;
            }
          }
        }
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { callback: v => v + "%", font: { size: 11 } },
          grid: { color: "#F1F5F9" }
        },
        x: { ticks: { font: { size: 11 } }, grid: { display: false } }
      },
      onClick: (evt, activeEls) => {
        if (activeEls && activeEls.length > 0) {
          const idx = activeEls[0].index;
          const sk = displaySkills[idx];
          inspectSkillEvidence(sk);
        }
      }
    }
  });
}

// 4. Weakness Frequency Horizontal Bar Chart
function renderWeaknessFrequencyChart(weaknesses) {
  const canvas = document.getElementById("chart-weakness-frequency");
  if (!canvas) return;

  if (chartWeaknessFreqInstance) {
    chartWeaknessFreqInstance.destroy();
  }

  const displayWeaknesses = weaknesses.slice(0, 7);
  const labels = displayWeaknesses.map(w => w.concept.length > 28 ? w.concept.substring(0, 26) + "..." : w.concept);
  const counts = displayWeaknesses.map(w => w.session_occurrences);
  const bgColors = displayWeaknesses.map(w => w.status === "active_weakness" ? "#EF4444" : w.status === "improving" ? "#F59E0B" : "#10B981");

  chartWeaknessFreqInstance = new Chart(canvas, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "Distinct Session Occurrences",
        data: counts,
        backgroundColor: bgColors,
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0F172A",
          padding: 10,
          callbacks: {
            title: (items) => displayWeaknesses[items[0].dataIndex].concept,
            label: (item) => {
              const w = displayWeaknesses[item.dataIndex];
              return [
                `Distinct Sessions: ${w.session_occurrences}`,
                `Total Questions: ${w.total_question_occurrences}`,
                `Average Score on Topic: ${w.average_score}%`,
                `Status: ${w.status.replace("_", " ").toUpperCase()}`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { stepSize: 1, font: { size: 11 } },
          grid: { color: "#F1F5F9" }
        },
        y: { ticks: { font: { size: 11 } }, grid: { display: false } }
      },
      onClick: (evt, activeEls) => {
        if (activeEls && activeEls.length > 0) {
          const idx = activeEls[0].index;
          const w = displayWeaknesses[idx];
          inspectWeaknessEvidence(w);
        }
      }
    }
  });
}

// 5. Interactive Session Comparison (Rubric Dimensions & Badges)
function renderSessionComparison(analytics) {
  const comp = analytics.session_comparison;
  const selectA = document.getElementById("select-session-a");
  const selectB = document.getElementById("select-session-b");

  // Populate Dropdowns
  const sessions = analytics.available_sessions || [];
  if (selectA && selectB) {
    selectA.innerHTML = sessions.map(s => `<option value="${s.id}" ${s.id === comp?.session_a_id ? "selected" : ""}>${s.title} (${s.score}% - ${s.date})</option>`).join("");
    selectB.innerHTML = `<option value="">None (Baseline)</option>` + sessions.map(s => `<option value="${s.id}" ${s.id === comp?.session_b_id ? "selected" : ""}>${s.title} (${s.score}% - ${s.date})</option>`).join("");

    selectA.onchange = (e) => {
      selectedSessionA = e.target.value;
      loadAnalyticsDashboard();
    };
    selectB.onchange = (e) => {
      selectedSessionB = e.target.value || null;
      loadAnalyticsDashboard();
    };
  }

  // Render Grouped Bar Chart
  const canvas = document.getElementById("chart-session-comparison");
  if (!canvas) return;

  if (chartSessionCompInstance) {
    chartSessionCompInstance.destroy();
  }

  const rubric = comp?.rubric_comparison || [];
  const labels = rubric.map(r => r.dimension);
  const scoresA = rubric.map(r => r.session_a_score || 0);
  const scoresB = rubric.map(r => r.session_b_score || 0);

  chartSessionCompInstance = new Chart(canvas, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: comp?.session_a_title ? `${comp.session_a_title} (${comp.session_a_score}%)` : "Session A",
          data: scoresA,
          backgroundColor: "#2563EB",
          borderRadius: 6
        },
        {
          label: comp?.session_b_title ? `${comp.session_b_title} (${comp.session_b_score}%)` : "Session B",
          data: scoresB,
          backgroundColor: "#94A3B8",
          borderRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          backgroundColor: "#0F172A",
          padding: 10,
          callbacks: {
            label: (item) => `${item.dataset.label}: ${item.raw}%`
          }
        }
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { callback: v => v + "%", font: { size: 11 } },
          grid: { color: "#F1F5F9" }
        },
        x: { ticks: { font: { size: 10 } }, grid: { display: false } }
      }
    }
  });

  // Render Resolved & Repeated Mistake Badges (Fixes [object Object])
  const resolvedBadgesEl = document.getElementById("comp-resolved-badges");
  if (resolvedBadgesEl) {
    const resolvedList = comp?.newly_resolved_weaknesses || [];
    if (resolvedList.length > 0) {
      resolvedBadgesEl.innerHTML = resolvedList.map(item => {
        const text = typeof item === "object" && item !== null ? (item.concept_or_skill || item.concept || item.skill || JSON.stringify(item)) : String(item);
        const gain = item.improvement_delta ? ` (+${item.improvement_delta}%)` : "";
        return `<span class="badge" style="background:#DCFCE7; color:#15803D; margin:2px 4px 2px 0; font-size:0.75rem;">✓ ${escapeHtml(text)}${gain}</span>`;
      }).join("");
    } else {
      resolvedBadgesEl.innerHTML = `<span style="font-style:italic; font-size:0.8rem; color:#94A3B8;">None recorded in this session</span>`;
    }
  }

  const repeatedBadgesEl = document.getElementById("comp-repeated-badges");
  if (repeatedBadgesEl) {
    const repeatedList = comp?.repeated_mistakes || [];
    if (repeatedList.length > 0) {
      repeatedBadgesEl.innerHTML = repeatedList.map(item => {
        const text = typeof item === "object" && item !== null ? (item.mistake || item.concept || JSON.stringify(item)) : String(item);
        return `<span class="badge" style="background:#FEE2E2; color:#991B1B; margin:2px 4px 2px 0; font-size:0.75rem;">⚠️ ${escapeHtml(text)}</span>`;
      }).join("");
    } else {
      repeatedBadgesEl.innerHTML = `<span style="font-style:italic; font-size:0.8rem; color:#94A3B8;">Zero repeated mistakes between sessions</span>`;
    }
  }
}

// 6. Score Distribution Bins Chart
function renderScoreDistributionChart(distribution) {
  const canvas = document.getElementById("chart-score-distribution");
  if (!canvas) return;

  if (chartScoreDistInstance) {
    chartScoreDistInstance.destroy();
  }

  const labels = distribution.map(d => `${d.bin_label} (${d.count})`);
  const counts = distribution.map(d => d.count);
  const colors = ["#EF4444", "#F59E0B", "#3B82F6", "#10B981"];

  chartScoreDistInstance = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [{
        data: counts,
        backgroundColor: colors,
        borderWidth: 2,
        borderColor: "#FFFFFF"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "right", labels: { boxWidth: 14, font: { size: 11 } } },
        tooltip: {
          backgroundColor: "#0F172A",
          padding: 10,
          callbacks: {
            label: (item) => {
              const bin = distribution[item.dataIndex];
              return `${bin.count} session(s) (${bin.percentage}%)`;
            }
          }
        }
      }
    }
  });
}

// 7. Render Next Best Action
function renderNextBestAction(summary, analytics) {
  const actionText = document.getElementById("next-action-text");
  if (!actionText) return;

  if (summary && summary.next_best_action) {
    const act = summary.next_best_action;
    actionText.innerHTML = `<strong>${escapeHtml(act.title)}</strong> — ${escapeHtml(act.reason)}`;
  } else if (analytics.weakness_frequency && analytics.weakness_frequency.length > 0) {
    const topW = analytics.weakness_frequency[0];
    actionText.textContent = `Remediate ${topW.concept} (${topW.session_occurrences} session occurrences) to eliminate your most frequent interview gap.`;
  } else {
    actionText.textContent = "Maintain high interview velocity by practicing an advanced adaptive technical mock.";
  }
}

// 8. Evaluated Sessions Archive Table
function renderSessionArchiveTable(trajectory) {
  const tbody = document.getElementById("session-archive-tbody");
  const badge = document.getElementById("archive-count-badge");
  if (badge) badge.textContent = `${trajectory.length} Valid Sessions`;

  if (!tbody) return;

  if (trajectory.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:#64748B;">No sessions found.</td></tr>`;
    return;
  }

  // Reverse chronological for tabular display
  const reversed = [...trajectory].reverse();
  tbody.innerHTML = reversed.map((sess) => {
    const score = Math.round(sess.score);
    const deltaStr = sess.score_change !== null
      ? (sess.score_change > 0 ? `<span style="color:#16A34A; font-weight:700;">+${sess.score_change}%</span>` : (sess.score_change < 0 ? `<span style="color:#DC2626; font-weight:700;">${sess.score_change}%</span>` : `<span style="color:#64748B;">0%</span>`))
      : `<span style="color:#64748B;">Baseline</span>`;

    return `
      <tr>
        <td style="font-weight:600;">${sess.date}</td>
        <td><span class="badge" style="background:#EFF6FF; color:#1E40AF; font-weight:600;">${escapeHtml(sess.target_role)}</span></td>
        <td style="color:#475569;">${escapeHtml(sess.topic)} • ${escapeHtml(sess.difficulty)}</td>
        <td>
          <span style="font-weight:800; font-size:1rem; color:${score >= 70 ? "#16A34A" : score >= 50 ? "#2563EB" : "#DC2626"};">
            ${score}%
          </span>
        </td>
        <td>${deltaStr}</td>
        <td>
          <div style="display:flex; gap:6px; flex-wrap:wrap;">
            <button class="btn btn-secondary" style="padding:4px 8px; font-size:0.75rem; cursor:pointer;" onclick="inspectSessionEvidence('${sess.session_id}')" title="Inspect Evidence">
              🔍 Inspect
            </button>
            <a href="analysis.html?session_id=${sess.session_id}" class="btn btn-secondary" style="padding:4px 8px; font-size:0.75rem; text-decoration:none;" title="View Deep Analysis">
              Analysis
            </a>
            <a href="roadmap.html?session_id=${sess.session_id}" class="btn btn-secondary" style="padding:4px 8px; font-size:0.75rem; text-decoration:none;" title="View Roadmap">
              Roadmap
            </a>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

// Interactive Evidence Inspection Functions
async function inspectSessionEvidence(sessionId) {
  const modal = document.getElementById("evidence-modal-backdrop");
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");

  if (!modal || !title || !body) return;

  modal.style.display = "flex";
  title.innerHTML = `<span>🔍</span> <span>Session Evidence Inspector</span>`;
  body.innerHTML = `<div style="text-align:center; padding:30px;">Loading session evaluations...</div>`;

  try {
    const interview = await API.get(`/api/interviews/${sessionId}`);
    const questions = interview.questions || [];

    let qHtml = "";
    if (questions.length === 0) {
      qHtml = `<p class="text-muted">No evaluated questions recorded for this session.</p>`;
    } else {
      qHtml = questions.map((q, idx) => {
        const ev = q.evaluations && q.evaluations.length > 0 ? q.evaluations[0] : null;
        const qScore = ev ? Math.round(ev.overall_score > 10 ? ev.overall_score : ev.overall_score * 10) : "--";
        const missing = ev && ev.missing_concepts ? JSON.parse(ev.missing_concepts || "[]") : [];

        return `
          <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:12px 14px; margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
              <strong style="color:#0F172A;">Q${idx + 1}: ${escapeHtml(q.skill || q.category || "Question")}</strong>
              <span class="badge" style="background:#EFF6FF; color:#1E40AF; font-weight:700;">Score: ${qScore}%</span>
            </div>
            <p style="font-size:0.85rem; color:#334155; margin-bottom:6px;">${escapeHtml(q.question_text)}</p>
            ${missing.length > 0 ? `<div style="font-size:0.75rem; color:#DC2626;"><strong>Missing Concepts:</strong> ${missing.join(", ")}</div>` : ""}
          </div>
        `;
      }).join("");
    }

    body.innerHTML = `
      <div style="margin-bottom:16px;">
        <h4 style="margin:0 0 4px 0; font-size:1.1rem; color:#0F172A;">${escapeHtml(interview.title || "Interview Session")}</h4>
        <div style="font-size:0.82rem; color:#64748B;">Role: ${escapeHtml(interview.target_role || "Candidate")} | Topic: ${escapeHtml(interview.topic || "Technical")} (${escapeHtml(interview.difficulty || "Medium")})</div>
      </div>
      <div style="max-height:50vh; overflow-y:auto;">
        ${qHtml}
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<div style="color:#DC2626; padding:20px;">Failed to load session details: ${escapeHtml(err.message)}</div>`;
  }
}

function inspectWeaknessEvidence(weakness) {
  const modal = document.getElementById("evidence-modal-backdrop");
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");

  if (!modal || !title || !body) return;

  modal.style.display = "flex";
  title.innerHTML = `<span>⚠️</span> <span>Weakness Concept Evidence</span>`;

  const sessionsHtml = (weakness.supporting_sessions || []).map(s => `
    <li style="margin-bottom:6px;">
      <strong>${escapeHtml(s.title || "Session")}</strong> (${s.date}) — Scored ${Math.round(s.score || 0)}%
    </li>
  `).join("");

  body.innerHTML = `
    <div style="margin-bottom:16px;">
      <h4 style="margin:0 0 6px 0; color:#991B1B; font-size:1.1rem;">${escapeHtml(weakness.concept)}</h4>
      <div style="font-size:0.82rem; color:#64748B;">Category: ${escapeHtml(weakness.category)} | Distinct Session Occurrences: ${weakness.session_occurrences}</div>
    </div>
    <div style="background:#FFF1F2; border:1px solid #FFE4E6; border-radius:8px; padding:14px; margin-bottom:16px;">
      <div style="font-size:0.78rem; font-weight:700; color:#9F1239; text-transform:uppercase; margin-bottom:4px;">Sample Candidate Answer Evidence</div>
      <div style="font-size:0.85rem; color:#475569; font-style:italic;">"${escapeHtml(weakness.sample_evidence || "Identified across multiple question evaluations.")}"</div>
    </div>
    <div>
      <div style="font-size:0.8rem; font-weight:700; color:#475569; text-transform:uppercase; margin-bottom:6px;">Supporting Interview Sessions:</div>
      <ul style="padding-left:18px; font-size:0.85rem; color:#334155;">
        ${sessionsHtml || "<li>Multiple completed interviews</li>"}
      </ul>
    </div>
  `;
}

function inspectSkillEvidence(skill) {
  const modal = document.getElementById("evidence-modal-backdrop");
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");

  if (!modal || !title || !body) return;

  modal.style.display = "flex";
  title.innerHTML = `<span>🎯</span> <span>Skill Performance Evidence</span>`;

  body.innerHTML = `
    <div style="margin-bottom:16px;">
      <h4 style="margin:0 0 6px 0; color:#0F172A; font-size:1.15rem;">${escapeHtml(skill.skill)}</h4>
      <div style="font-size:0.82rem; color:#64748B;">Category: ${escapeHtml(skill.category)} | Total Evaluations: ${skill.evaluation_count} across ${skill.session_count} session(s)</div>
    </div>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-bottom:16px;">
      <div style="background:#EFF6FF; border:1px solid #DBEAFE; border-radius:8px; padding:12px; text-align:center;">
        <span style="font-size:0.75rem; color:#1E40AF; text-transform:uppercase; font-weight:700;">Baseline Score</span>
        <div style="font-size:1.5rem; font-weight:800; color:#1E3A8A;">${skill.baseline_score}%</div>
      </div>
      <div style="background:#F0FDF4; border:1px solid #DCFCE7; border-radius:8px; padding:12px; text-align:center;">
        <span style="font-size:0.75rem; color:#166534; text-transform:uppercase; font-weight:700;">Latest Score</span>
        <div style="font-size:1.5rem; font-weight:800; color:#14532D;">${skill.latest_score}%</div>
      </div>
    </div>
    <div style="font-size:0.88rem; color:#334155; line-height:1.5;">
      <strong>Statistical Reliability:</strong> ${skill.has_sufficient_evidence ? `Supported by ${skill.evaluation_count} real answer evaluations.` : "Single evaluation recorded so far. Take another mock interview testing this topic to establish verified longitudinal progress."}
    </div>
  `;
}

function closeEvidenceModal() {
  const modal = document.getElementById("evidence-modal-backdrop");
  if (modal) modal.style.display = "none";
}

// Date Filter Helpers
window.setTimeFilter = (filterType) => {
  currentFilter = filterType;
  document.querySelectorAll(".filter-pill-btn").forEach(btn => btn.classList.remove("active"));
  const activeBtn = document.getElementById(`filter-pill-${filterType}`);
  if (activeBtn) activeBtn.classList.add("active");

  const now = new Date();
  if (filterType === "30d") {
    const d = new Date();
    d.setDate(now.getDate() - 30);
    filterDateFrom = d.toISOString().split("T")[0];
    filterDateTo = null;
  } else if (filterType === "90d") {
    const d = new Date();
    d.setDate(now.getDate() - 90);
    filterDateFrom = d.toISOString().split("T")[0];
    filterDateTo = null;
  } else {
    filterDateFrom = null;
    filterDateTo = null;
  }

  const fromInput = document.getElementById("filter-date-from");
  const toInput = document.getElementById("filter-date-to");
  if (fromInput) fromInput.value = filterDateFrom || "";
  if (toInput) toInput.value = filterDateTo || "";

  loadAnalyticsDashboard();
};

window.applyCustomDateFilter = () => {
  const fromInput = document.getElementById("filter-date-from");
  const toInput = document.getElementById("filter-date-to");
  filterDateFrom = fromInput ? fromInput.value : null;
  filterDateTo = toInput ? toInput.value : null;

  document.querySelectorAll(".filter-pill-btn").forEach(btn => btn.classList.remove("active"));
  loadAnalyticsDashboard();
};

window.resetDateFilter = () => {
  setTimeFilter("all");
};

// HTML Utility
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
