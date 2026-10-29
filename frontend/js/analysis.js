/* Deep AI Analysis Controller - Blue/White Theme */
let currentInterviewId = null;
let currentRoadmapData = null;

document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();

  // Populate sidebar user info
  const user = API.getUser();
  if (user) {
    const avatarEl = document.getElementById("sidebar-user-avatar");
    const nameEl = document.getElementById("sidebar-user-name");
    const roleEl = document.getElementById("sidebar-user-role");
    if (nameEl) nameEl.textContent = user.name || user.email || "Candidate";
    if (roleEl) roleEl.textContent = user.target_role || "Software Developer";
    if (avatarEl) avatarEl.textContent = (user.name ? user.name[0] : "U").toUpperCase();
  }

  const urlParams = new URLSearchParams(window.location.search);
  currentInterviewId = urlParams.get("id");

  await initializeAnalysisPage();
  setupEventListeners();
});

async function initializeAnalysisPage() {
  try {
    // 1. Fetch user's interviews for dropdown selector
    const interviews = await API.get("/api/interviews");
    const selectEl = document.getElementById("session-select");

    if (selectEl && Array.isArray(interviews) && interviews.length > 0) {
      selectEl.innerHTML = interviews.map(i => {
        const isSel = currentInterviewId ? (i.id === currentInterviewId) : false;
        const qCount = i.completed_questions || (i.questions ? i.questions.length : 0);
        return `<option value="${i.id}" ${isSel ? 'selected' : ''}>${escapeHtml(i.target_role || i.title || 'Technical Interview')} (${i.difficulty || 'Medium'}) - Score: ${Math.round(i.total_score || 0)}% [${qCount} Qs]</option>`;
      }).join("");

      // If no ID specified, select the first one (or first completed)
      if (!currentInterviewId) {
        const completed = interviews.find(i => i.status === "completed" && (i.completed_questions || 0) > 0);
        currentInterviewId = completed ? completed.id : interviews[0].id;
        selectEl.value = currentInterviewId;
      }
    }

    if (currentInterviewId) {
      await loadAnalysisData(currentInterviewId);
    } else {
      showEmptyState("No interview sessions found. Please complete a mock interview first.");
    }
  } catch (err) {
    console.error("Initialization failed:", err);
    showToast(`Failed to load interviews: ${err.message}`, "error");
    showEmptyState(err.message);
  }
}

async function loadAnalysisData(interviewId, forceRefresh = false) {
  const loadingEl = document.getElementById("analysis-loading");
  const contentEl = document.getElementById("analysis-content");

  if (loadingEl) loadingEl.style.display = "block";
  if (contentEl) contentEl.style.display = "none";

  try {
    let data;
    if (forceRefresh) {
      data = await API.post(`/api/analysis/${interviewId}/generate?force_refresh=true`);
    } else {
      data = await API.get(`/api/analysis/${interviewId}`);
    }

    currentRoadmapData = data;
    renderAnalysisData(data);

    if (loadingEl) loadingEl.style.display = "none";
    if (contentEl) contentEl.style.display = "block";

    // Update URL without reloading
    const newUrl = `${window.location.pathname}?id=${encodeURIComponent(interviewId)}`;
    window.history.replaceState({ path: newUrl }, '', newUrl);

    // Update Roadmap Links
    updateRoadmapLinks(interviewId);

  } catch (err) {
    console.error("Analysis load failed:", err);
    if (loadingEl) loadingEl.style.display = "none";
    showToast(`Analysis synthesis failed: ${err.message}`, "error");
    showEmptyState(`Unable to generate AI analysis: ${err.message}`);
  }
}

function renderAnalysisData(data) {
  // Title & Subtitle
  const titleEl = document.getElementById("analysis-session-title");
  if (titleEl) titleEl.textContent = `${data.target_role || 'Software Engineer'} Deep Analysis`;

  const dateBadge = document.getElementById("analysis-date-badge");
  if (dateBadge && data.created_at) {
    try {
      const dt = new Date(data.created_at);
      dateBadge.textContent = dt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch (_) {}
  }

  // Overall Score & Readiness
  const scoreVal = Math.round(data.readiness_score || 0);
  const scoreEl = document.getElementById("analysis-overall-score");
  if (scoreEl) scoreEl.textContent = `${scoreVal}%`;

  const lvlEl = document.getElementById("analysis-readiness-level");
  if (lvlEl) {
    lvlEl.textContent = data.readiness_level || "Calibrated";
    if (scoreVal >= 75) lvlEl.className = "badge badge-success";
    else if (scoreVal >= 55) lvlEl.className = "badge badge-warning";
    else lvlEl.className = "badge badge-danger";
  }

  // Executive Summary
  const execEl = document.getElementById("analysis-executive-summary");
  if (execEl) {
    execEl.textContent = data.executive_summary || "Candidate demonstrated functional competencies across evaluated technical domains.";
  }

  // Hiring Verdict
  const verdictEl = document.getElementById("analysis-hiring-verdict");
  if (verdictEl) {
    if (scoreVal >= 80) verdictEl.textContent = "Strong Hire recommendation based on deep conceptual grounding and architectural clarity.";
    else if (scoreVal >= 60) verdictEl.textContent = "Potential Hire with targeted remediation needed on key missing concepts.";
    else verdictEl.textContent = "Remediation Recommended before proceeding to on-site live technical interview loops.";
  }

  // Calculate 5-Dimension Averages from Question Analyses
  const qList = data.question_analyses || [];
  let tc = 0, cc = 0, rr = 0, sc = 0, du = 0;
  const count = qList.length || 1;

  qList.forEach(q => {
    tc += q.technical_correctness || 7.0;
    cc += q.conceptual_understanding || 7.0;
    rr += q.reasoning_approach || 7.0;
    sc += q.depth_and_clarity || 7.0;
    du += q.completeness || 7.0;
  });

  const tcPct = Math.min(100, Math.round((tc / count) * 10));
  const ccPct = Math.min(100, Math.round((cc / count) * 10));
  const rrPct = Math.min(100, Math.round((rr / count) * 10));
  const scPct = Math.min(100, Math.round((sc / count) * 10));
  const duPct = Math.min(100, Math.round((du / count) * 10));

  const rubricContainer = document.getElementById("rubric-bars-container");
  if (rubricContainer) {
    rubricContainer.innerHTML = `
      ${renderRubricBar("Technical Correctness", tcPct, "35% weight", "#2563EB")}
      ${renderRubricBar("Conceptual Completeness", ccPct, "25% weight", "#4F46E5")}
      ${renderRubricBar("Response Relevance", rrPct, "15% weight", "#10B981")}
      ${renderRubricBar("Structural Clarity", scPct, "15% weight", "#06B6D4")}
      ${renderRubricBar("Depth of Understanding", duPct, "10% weight", "#8B5CF6")}
    `;
  }

  // Strengths List
  const strengthsContainer = document.getElementById("strengths-list-container");
  if (strengthsContainer) {
    const strengths = data.strengths || [];
    if (strengths.length === 0) {
      strengthsContainer.innerHTML = `<p class="text-muted" style="font-size:0.9rem;">No verified strength evidence logged.</p>`;
    } else {
      strengthsContainer.innerHTML = strengths.map(s => `
        <div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:8px; padding:12px 14px;">
          <div style="font-weight:700; color:#166534; font-size:0.95rem; margin-bottom:4px; display:flex; justify-content:space-between;">
            <span>${escapeHtml(s.competency || 'Demonstrated Competency')}</span>
            <span style="font-size:0.75rem; background:#DCFCE7; color:#15803D; padding:2px 8px; border-radius:4px;">${escapeHtml(s.category || 'General')}</span>
          </div>
          <div style="font-size:0.85rem; color:#15803D; margin-bottom:6px;">${escapeHtml(s.demonstrated_mastery || '')}</div>
          ${s.candidate_excerpt ? `
            <div style="font-size:0.8rem; background:#FFFFFF; border-left:3px solid #22C55E; padding:6px 10px; color:#374151; font-style:italic;">
              "${escapeHtml(s.candidate_excerpt)}"
            </div>
          ` : ''}
        </div>
      `).join("");
    }
  }

  // Skill Gaps List
  const gapsContainer = document.getElementById("gaps-list-container");
  if (gapsContainer) {
    const gaps = data.skill_gaps || [];
    if (gaps.length === 0) {
      gapsContainer.innerHTML = `<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:16px; color:#10B981; font-weight:600;">✅ No critical skill gaps identified! You performed consistently well across all questions.</div>`;
    } else {
      gapsContainer.innerHTML = gaps.map(g => {
        let badgeColor = "#DC2626";
        let badgeBg = "#FEE2E2";
        if (g.severity === "HIGH") { badgeColor = "#EA580C"; badgeBg = "#FFEDD5"; }
        else if (g.severity === "MEDIUM" || g.severity === "MODERATE") { badgeColor = "#D97706"; badgeBg = "#FEF3C7"; }

        return `
          <div style="background:#FEF2F2; border:1px solid #FECACA; border-radius:8px; padding:12px 14px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <span style="font-weight:700; color:#991B1B; font-size:0.95rem;">${escapeHtml(g.topic || 'Skill Gap')}</span>
              <span style="font-size:0.75rem; background:${badgeBg}; color:${badgeColor}; font-weight:700; padding:2px 8px; border-radius:4px;">
                ${escapeHtml(g.severity || 'CRITICAL')}
              </span>
            </div>
            <div style="font-size:0.85rem; color:#7F1D1D; margin-bottom:6px;">
              <strong>Missing / Misconception:</strong> ${escapeHtml(g.misconception || g.description || 'Concept requires remediation.')}
            </div>
            ${g.evidence_quote ? `
              <div style="font-size:0.8rem; background:#FFFFFF; border-left:3px solid #EF4444; padding:6px 10px; color:#374151; font-style:italic; margin-bottom:6px;">
                Candidate quote: "${escapeHtml(g.evidence_quote)}"
              </div>
            ` : ''}
            <div style="font-size:0.8rem; color:#475569; background:rgba(255,255,255,0.7); padding:6px 10px; border-radius:4px;">
              <strong>Remediation Target:</strong> ${escapeHtml(g.remediation_task_title || 'Review topic in preparation roadmap.')}
            </div>
          </div>
        `;
      }).join("");
    }
  }

  // Question-by-Question Deep Analysis Feed
  const qFeed = document.getElementById("questions-analysis-feed");
  const qBadge = document.getElementById("question-count-badge");
  if (qBadge) qBadge.textContent = `${qList.length} Questions Evaluated`;

  if (qFeed) {
    if (qList.length === 0) {
      qFeed.innerHTML = `<p class="text-muted" style="padding:20px; text-align:center;">No question answers found for this session.</p>`;
    } else {
      qFeed.innerHTML = qList.map((qa, idx) => {
        const qScore = Math.min(100, Math.round(((qa.technical_correctness || 7.0) + (qa.conceptual_understanding || 7.0) + (qa.completeness || 7.0)) / 3.0 * 10));
        
        let pillClass = "badge-success";
        if (qScore < 55) pillClass = "badge-danger";
        else if (qScore < 75) pillClass = "badge-warning";

        return `
          <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; overflow:hidden; box-shadow:var(--shadow-sm);">
            <!-- Header bar -->
            <div style="background:#F8FAFC; padding:16px 20px; border-bottom:1px solid #E2E8F0; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
              <div style="display:flex; align-items:center; gap:10px;">
                <span style="font-size:0.8rem; background:#2563EB; color:#FFF; font-weight:800; padding:4px 10px; border-radius:6px;">
                  Question #${qa.question_number || (idx + 1)}
                </span>
                <span class="badge ${pillClass}" style="font-size:0.8rem;">Score: ${qScore}%</span>
              </div>
              <div style="font-size:0.8rem; color:#64748B;">
                Scored by Gemini 3.8 Flash Rubric
              </div>
            </div>

            <!-- Body -->
            <div style="padding:20px;">
              <!-- Question Text -->
              <div style="font-size:1.1rem; font-weight:700; color:#0F172A; margin-bottom:14px; line-height:1.5;">
                "${escapeHtml(qa.question_text || '')}"
              </div>

              <!-- Candidate Submitted Answer -->
              <div style="margin-bottom:16px;">
                <div style="font-size:0.8rem; font-weight:700; color:#64748B; text-transform:uppercase; margin-bottom:6px;">
                  Candidate's Submitted Answer
                </div>
                <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-left:4px solid #2563EB; border-radius:8px; padding:14px; font-size:0.95rem; color:#1E293B; line-height:1.6; white-space:pre-wrap;">
                  ${escapeHtml(qa.candidate_answer_excerpt || 'No answer recorded for this question.')}
                </div>
              </div>

              <!-- 2-column breakdown: Strengths vs Gaps -->
              <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:16px;">
                <div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:8px; padding:12px 14px;">
                  <div style="font-size:0.85rem; font-weight:700; color:#166534; margin-bottom:6px;">✅ Verified Strengths</div>
                  <ul style="margin:0; padding-left:18px; font-size:0.85rem; color:#15803D; line-height:1.5;">
                    ${(qa.key_strengths && qa.key_strengths.length > 0) ? qa.key_strengths.map(st => `<li>${escapeHtml(st)}</li>`).join("") : '<li>Core conceptual foundation present.</li>'}
                  </ul>
                </div>

                <div style="background:#FEF2F2; border:1px solid #FECACA; border-radius:8px; padding:12px 14px;">
                  <div style="font-size:0.85rem; font-weight:700; color:#991B1B; margin-bottom:6px;">⚠️ Missing Concepts & Gaps</div>
                  <ul style="margin:0; padding-left:18px; font-size:0.85rem; color:#991B1B; line-height:1.5;">
                    ${(qa.missing_concepts && qa.missing_concepts.length > 0) ? qa.missing_concepts.map(mc => `<li>${escapeHtml(mc)}</li>`).join("") : '<li>No critical conceptual omissions detected.</li>'}
                  </ul>
                </div>
              </div>

              <!-- Ideal Model Answer -->
              ${qa.benchmark_solution || qa.model_answer ? `
                <div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:8px; padding:14px; margin-top:12px;">
                  <div style="font-size:0.82rem; font-weight:700; color:#1E40AF; text-transform:uppercase; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                    <span>💡</span> Ideal Benchmark Model Answer
                  </div>
                  <div style="font-size:0.92rem; color:#1E3A8A; line-height:1.6;">
                    ${escapeHtml(qa.benchmark_solution || qa.model_answer || '')}
                  </div>
                </div>
              ` : ''}

            </div>
          </div>
        `;
      }).join("");
    }
  }

  // Reassessment Drills
  const reassessContainer = document.getElementById("reassessment-drills-container");
  const reassessList = data.reassessment_questions || [];
  if (reassessContainer) {
    if (reassessList.length === 0) {
      document.getElementById("reassessment-section").style.display = "none";
    } else {
      document.getElementById("reassessment-section").style.display = "block";
      reassessContainer.innerHTML = reassessList.map((rq, idx) => `
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:16px;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
            <div style="font-weight:700; color:#0F172A; font-size:0.95rem;">
              Drill #${idx + 1}: ${escapeHtml(rq.question_text || '')}
            </div>
            <span style="font-size:0.75rem; background:#F1F5F9; color:#475569; padding:2px 8px; border-radius:4px; font-weight:600;">
              ${escapeHtml(rq.competency || 'Competency')}
            </span>
          </div>
          <button onclick="toggleDrillAnswer('drill-ans-${idx}')" class="btn btn-secondary" style="padding:4px 10px; font-size:0.78rem; margin-top:6px;">
            👁️ Reveal Benchmark Solution
          </button>
          <div id="drill-ans-${idx}" style="display:none; margin-top:10px; background:#F8FAFC; border-left:3px solid #2563EB; padding:10px 14px; font-size:0.88rem; color:#1E293B; line-height:1.5;">
            ${escapeHtml(rq.benchmark_solution || '')}
          </div>
        </div>
      `).join("");
    }
  }
}

function renderRubricBar(name, score, weight, color) {
  return `
    <div>
      <div style="display:flex; justify-content:space-between; font-size:0.88rem; font-weight:600; margin-bottom:6px;">
        <span>${escapeHtml(name)} <span style="font-size:0.75rem; color:#64748B; font-weight:400;">(${escapeHtml(weight)})</span></span>
        <span style="color:${color}; font-weight:700;">${score}%</span>
      </div>
      <div class="progress-bar-bg" style="height:8px;">
        <div class="progress-bar-fill" style="width:${score}%; background-color:${color};"></div>
      </div>
    </div>
  `;
}

function updateRoadmapLinks(interviewId) {
  const qParam = `?id=${encodeURIComponent(interviewId)}`;
  const topbarLink = document.getElementById("topbar-roadmap-link");
  if (topbarLink) topbarLink.href = `roadmap.html${qParam}`;

  const jumpBtn = document.getElementById("btn-jump-roadmap");
  if (jumpBtn) jumpBtn.href = `roadmap.html${qParam}`;

  const bottomBtn = document.getElementById("btn-bottom-roadmap");
  if (bottomBtn) bottomBtn.href = `roadmap.html${qParam}`;
}

function setupEventListeners() {
  const selectEl = document.getElementById("session-select");
  if (selectEl) {
    selectEl.addEventListener("change", (e) => {
      const newId = e.target.value;
      if (newId) {
        currentInterviewId = newId;
        loadAnalysisData(newId, false);
      }
    });
  }

  const refreshBtn = document.getElementById("btn-force-refresh-analysis");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      if (currentInterviewId) {
        showToast("Triggering full live AI evidence analysis from Gemini...", "info");
        loadAnalysisData(currentInterviewId, true);
      }
    });
  }
}

function toggleDrillAnswer(id) {
  const el = document.getElementById(id);
  if (el) {
    el.style.display = el.style.display === "none" ? "block" : "none";
  }
}

function showEmptyState(msg) {
  const loadingEl = document.getElementById("analysis-loading");
  const contentEl = document.getElementById("analysis-content");
  if (loadingEl) loadingEl.style.display = "none";
  if (contentEl) {
    contentEl.style.display = "block";
    contentEl.innerHTML = `
      <div class="card" style="text-align:center; padding:60px 20px;">
        <div style="font-size:3rem; margin-bottom:16px;">📋</div>
        <h2 style="color:#0F172A; margin-bottom:8px;">No Interview Analysis Found</h2>
        <p class="text-muted" style="max-width:500px; margin:0 auto 24px;">
          ${escapeHtml(msg || "Start a mock interview to get comprehensive AI analysis.")}
        </p>
        <a href="interview-config.html" class="btn btn-primary" style="padding:12px 28px; text-decoration:none;">
          Start New Practice Interview →
        </a>
      </div>
    `;
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
