/* Personalized Preparation Roadmap Controller — Production Quality */
let currentInterviewId = null;
let currentRoadmap = null;
let activePhaseFilter = "all";
let activeStatusFilter = "all";
const expandedTaskIds = new Set();

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

  await initializeRoadmapPage();
  setupEventListeners();
});

async function initializeRoadmapPage() {
  try {
    const interviews = await API.get("/api/interviews");
    const selectEl = document.getElementById("roadmap-session-select");

    if (selectEl && Array.isArray(interviews) && interviews.length > 0) {
      selectEl.innerHTML = interviews.map(i => {
        const isSel = currentInterviewId ? (i.id === currentInterviewId) : false;
        const qCount = i.completed_questions || (i.questions ? i.questions.length : 0);
        const scoreStr = i.total_score != null ? `Score: ${Math.round(i.total_score)}%` : (i.status === 'completed' ? 'Completed' : 'In Progress');
        return `<option value="${i.id}" ${isSel ? 'selected' : ''}>${escapeHtml(i.target_role || i.title || 'Technical Interview')} (${i.difficulty || 'Medium'}) • ${scoreStr} [${qCount} Qs]</option>`;
      }).join("");

      // Pick selected or first completed with questions
      if (!currentInterviewId) {
        const completed = interviews.find(i => i.status === "completed" && (i.completed_questions || 0) > 0);
        currentInterviewId = completed ? completed.id : interviews[0].id;
        selectEl.value = currentInterviewId;
      }
    }

    if (currentInterviewId) {
      await loadRoadmapData(currentInterviewId);
    } else {
      showEmptyState("No interview sessions found. Please complete an adaptive mock interview first.");
    }
  } catch (err) {
    console.error("Roadmap init failed:", err);
    showToast(`Failed to load interviews: ${err.message}`, "error");
    showEmptyState(err.message);
  }
}

async function loadRoadmapData(interviewId) {
  const loadingEl = document.getElementById("roadmap-loading");
  const contentEl = document.getElementById("roadmap-content");
  const emptyEl = document.getElementById("roadmap-empty");

  if (loadingEl) loadingEl.style.display = "block";
  if (contentEl) contentEl.style.display = "none";
  if (emptyEl) emptyEl.style.display = "none";

  try {
    const data = await API.get(`/api/analysis/${interviewId}`);
    currentRoadmap = data;
    renderRoadmap(data);

    if (loadingEl) loadingEl.style.display = "none";
    if (contentEl) contentEl.style.display = "block";
    if (emptyEl) emptyEl.style.display = "none";

    // Update URL query param cleanly
    const newUrl = `${window.location.pathname}?id=${encodeURIComponent(interviewId)}`;
    window.history.replaceState({ path: newUrl }, '', newUrl);

    // Update Analysis Links
    updateAnalysisLinks(interviewId);

  } catch (err) {
    console.error("Roadmap fetch failed:", err);
    if (loadingEl) loadingEl.style.display = "none";
    if (contentEl) contentEl.style.display = "none";
    showEmptyState(`Unable to load preparation roadmap: ${err.message || 'No evaluation data found for this session.'}`);
  }
}

function renderRoadmap(data) {
  if (!data) return;

  // Title & Role
  const roleBadge = document.getElementById("roadmap-target-role-badge");
  if (roleBadge) roleBadge.textContent = `${data.target_role || 'Software Engineer'} (${data.target_difficulty || 'Medium'})`;

  // Readiness badge
  const rBadge = document.getElementById("roadmap-readiness-badge");
  if (rBadge) {
    const sc = data.readiness_score || 0;
    rBadge.textContent = `${data.readiness_level || 'Calibrated'} (${Math.round(sc)}%)`;
    if (sc >= 75) rBadge.className = "badge badge-success";
    else if (sc >= 50) rBadge.className = "badge badge-warning";
    else rBadge.className = "badge badge-danger";
  }

  // Task metrics calculation
  const allTasks = data.roadmap_tasks || [];
  const totalCount = allTasks.length;
  const completedTasks = allTasks.filter(t => t.status === "completed");
  const completedCount = completedTasks.length;
  const pendingCount = totalCount - completedCount;
  const criticalRemaining = allTasks.filter(t => (t.priority || '').toUpperCase() === "CRITICAL" && t.status !== "completed").length;

  const pct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  let totalHours = 0;
  let remainingHours = 0;
  allTasks.forEach(t => {
    const dur = parseFloat(t.estimated_duration_hours || t.estimated_hours || 1.5);
    totalHours += dur;
    if (t.status !== "completed") {
      remainingHours += dur;
    }
  });

  const pctEl = document.getElementById("roadmap-progress-pct");
  if (pctEl) pctEl.textContent = `${pct}%`;

  const compEl = document.getElementById("roadmap-tasks-completed-count");
  if (compEl) compEl.textContent = completedCount;

  const totEl = document.getElementById("roadmap-tasks-total-count");
  if (totEl) totEl.textContent = totalCount;

  const barFill = document.getElementById("roadmap-progress-bar-fill");
  if (barFill) barFill.style.width = `${pct}%`;

  const hoursEl = document.getElementById("roadmap-total-hours");
  if (hoursEl) hoursEl.textContent = `${Math.round(totalHours * 10) / 10} hrs`;

  const remHoursEl = document.getElementById("roadmap-remaining-hours");
  if (remHoursEl) remHoursEl.textContent = `${Math.round(remainingHours * 10) / 10} hrs`;

  const critEl = document.getElementById("roadmap-critical-count");
  if (critEl) critEl.textContent = criticalRemaining;

  // Status Filter Counts
  const allCountEl = document.getElementById("status-count-all");
  if (allCountEl) allCountEl.textContent = totalCount;

  const pendCountEl = document.getElementById("status-count-pending");
  if (pendCountEl) pendCountEl.textContent = pendingCount;

  const doneCountEl = document.getElementById("status-count-completed");
  if (doneCountEl) doneCountEl.textContent = completedCount;

  // Preferences form values
  const dateInput = document.getElementById("pref-target-date");
  if (dateInput && data.target_interview_date) {
    dateInput.value = data.target_interview_date.split("T")[0];
  }

  const hoursSelect = document.getElementById("pref-daily-hours");
  if (hoursSelect && data.daily_study_hours) {
    hoursSelect.value = data.daily_study_hours.toString();
  }

  // Render 4-Phase Container
  renderPhases(data);
}

function renderPhases(data) {
  const container = document.getElementById("phases-container");
  if (!container) return;

  const phases = data.roadmap_phases && data.roadmap_phases.length > 0 ? data.roadmap_phases : [
    { phase_number: 1, title: "Phase 1: Core Fundamentals & Concept Clarification", description: "Remediate missing concepts and misconceptions identified in interview answers.", duration_weeks: 1, milestone: "Mastery of foundational theory and standard terminology." },
    { phase_number: 2, title: "Phase 2: Technical Deep Dive & System Architecture", description: "Deepen understanding of edge cases, complexity trade-offs, and design patterns.", duration_weeks: 1.5, milestone: "Architectural fluency and scalability principles." },
    { phase_number: 3, title: "Phase 3: Applied Problem Solving & Coding Drills", description: "Hands-on execution of target algorithms and practical implementation questions.", duration_weeks: 1, milestone: "Zero-defect algorithm and data structure implementations." },
    { phase_number: 4, title: "Phase 4: Full Simulation & Executive Communication", description: "Polishing articulate delivery, STAR framing, and simulated loop mock interviews.", duration_weeks: 0.5, milestone: "Executive presence and high-conviction communication." }
  ];

  const tasks = data.roadmap_tasks || [];

  container.innerHTML = phases.map(phase => {
    const isPhaseVisible = (activePhaseFilter === "all" || parseInt(activePhaseFilter) === phase.phase_number);
    if (!isPhaseVisible) return "";

    const allPhaseTasks = tasks.filter(t => t.phase_number === phase.phase_number);
    const phaseTasks = allPhaseTasks.filter(t => {
      if (activeStatusFilter === "pending" && t.status === "completed") return false;
      if (activeStatusFilter === "completed" && t.status !== "completed") return false;
      return true;
    });

    const phaseCompleted = allPhaseTasks.filter(t => t.status === "completed").length;
    const phasePct = allPhaseTasks.length > 0 ? Math.round((phaseCompleted / allPhaseTasks.length) * 100) : 0;

    return `
      <div class="card" style="padding:0; overflow:hidden; border:1px solid #E2E8F0; margin-bottom:18px;">
        <!-- Phase Header -->
        <div style="background:#F8FAFC; padding:18px 24px; border-bottom:1px solid #E2E8F0; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
          <div>
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">
              <span style="font-size:0.75rem; background:#2563EB; color:#FFF; font-weight:800; padding:3px 10px; border-radius:6px; letter-spacing:0.5px;">
                PHASE ${phase.phase_number}
              </span>
              <h3 style="font-size:1.15rem; font-weight:800; color:#0F172A; margin:0;">
                ${escapeHtml(phase.title || `Phase ${phase.phase_number}`)}
              </h3>
            </div>
            <p class="text-muted" style="font-size:0.85rem; margin:0; line-height:1.4;">
              ${escapeHtml(phase.description || '')}
            </p>
            ${phase.milestone ? `
              <div style="font-size:0.8rem; color:#475569; margin-top:4px;">
                <strong style="color:#0F172A;">Milestone:</strong> ${escapeHtml(phase.milestone)}
              </div>
            ` : ''}
          </div>
          <div style="display:flex; align-items:center; gap:12px;">
            <div style="font-size:0.85rem; font-weight:700; color:#475569;">
              ${phaseCompleted}/${allPhaseTasks.length} Done (${phasePct}%)
            </div>
            <div class="progress-bar-bg" style="width:110px; height:8px; background:#E2E8F0; border-radius:999px; overflow:hidden;">
              <div class="progress-bar-fill" style="width:${phasePct}%; background-color:#10B981; height:100%; transition:width 0.3s ease;"></div>
            </div>
          </div>
        </div>

        <!-- Tasks List -->
        <div style="padding:20px 24px; display:flex; flex-direction:column; gap:14px;">
          ${phaseTasks.length === 0 ? `
            <div style="text-align:center; padding:20px; color:#94A3B8; font-size:0.9rem;">
              ${allPhaseTasks.length === 0 ? 'No tasks mapped to this phase.' : `No tasks matching the "${activeStatusFilter}" filter in this phase.`}
            </div>
          ` : phaseTasks.map(t => renderTaskItem(t, data.id)).join("")}
        </div>
      </div>
    `;
  }).join("");
}

function renderTaskItem(task, analysisId) {
  const taskId = task.task_id || task.id || `task-${task.phase_number}-${task.day_or_sequence}`;
  const isDone = task.status === "completed";
  const isExpanded = expandedTaskIds.has(taskId);

  // Priority Styling
  let prioClass = "task-prio-medium";
  const prio = (task.priority || "MEDIUM").toUpperCase();
  if (prio === "CRITICAL") prioClass = "task-prio-critical";
  else if (prio === "HIGH") prioClass = "task-prio-high";

  // Topic Headline (Strictly avoid "Preparation Task")
  const headline = task.topic || task.title || `Remediation Phase ${task.phase_number} Drill`;

  // Look for correlated skill gap in deep analysis
  let matchingGap = null;
  if (currentRoadmap && Array.isArray(currentRoadmap.skill_gaps)) {
    matchingGap = currentRoadmap.skill_gaps.find(g => {
      if (!g.topic) return false;
      const tTopic = (task.topic || '').toLowerCase();
      const gTopic = (g.topic || '').toLowerCase();
      return tTopic.includes(gTopic) || gTopic.includes(tTopic);
    });
  }

  const subtopics = Array.isArray(task.subtopics) ? task.subtopics : [];
  const learningObjectives = Array.isArray(task.learning_objectives) ? task.learning_objectives : [];
  const practiceProblems = Array.isArray(task.relevant_problems_or_questions) ? task.relevant_problems_or_questions : [];
  const duration = task.estimated_duration_hours || task.estimated_hours || 1.5;

  return `
    <div class="roadmap-task-card ${isDone ? 'task-completed' : ''}" id="card-${taskId}">
      <div style="display:flex; align-items:flex-start; gap:14px;">
        <!-- Checkbox with dynamic toggle -->
        <div style="margin-top:2px;">
          <input 
            type="checkbox" 
            ${isDone ? 'checked' : ''} 
            onchange="handleToggleTaskStatus('${analysisId}', '${taskId}', this.checked)"
            id="task-chk-${taskId}"
            style="width:20px; height:20px; cursor:pointer; accent-color:#10B981;"
          />
        </div>

        <!-- Task Content Body -->
        <div style="flex:1;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px; margin-bottom:6px;">
            <label for="task-chk-${taskId}" style="font-weight:700; font-size:1.02rem; color:${isDone ? '#64748B' : '#0F172A'}; cursor:pointer; text-decoration:${isDone ? 'line-through' : 'none'};">
              ${escapeHtml(headline)}
            </label>
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
              <span class="${prioClass}" style="font-size:0.75rem; font-weight:700; padding:2px 8px; border-radius:4px;">
                ${prio}
              </span>
              <span style="font-size:0.75rem; background:#F1F5F9; color:#475569; font-weight:600; padding:2px 8px; border-radius:4px;">
                Phase ${task.phase_number} • Day ${task.day_or_sequence || 1}
              </span>
              <span style="font-size:0.75rem; background:#F8FAFC; color:#334155; border:1px solid #E2E8F0; font-weight:600; padding:2px 8px; border-radius:4px;">
                ⏱️ ${duration} hrs
              </span>
              ${isDone ? `
                <span style="font-size:0.75rem; background:#D1FAE5; color:#065F46; font-weight:700; padding:2px 8px; border-radius:4px;">
                  ✓ Completed
                </span>
              ` : ''}
            </div>
          </div>

          <!-- Subtopics -->
          ${subtopics.length > 0 ? `
            <div style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px;">
              ${subtopics.map(st => `<span class="task-tag">${escapeHtml(st)}</span>`).join("")}
            </div>
          ` : ''}

          <!-- Correlated Evidence Gap Callout -->
          ${matchingGap ? `
            <div class="evidence-badge" title="Derived directly from candidate interview evaluation">
              <span>🎯 Evidence Gap:</span>
              <span>${escapeHtml(matchingGap.why_it_matters || matchingGap.remediation_action || matchingGap.topic)}</span>
            </div>
          ` : ''}

          <!-- Expandable Details -->
          ${isExpanded ? `
            <div style="margin-top:12px; padding-top:12px; border-top:1px solid #E2E8F0; display:flex; flex-direction:column; gap:10px;">
              
              <!-- Learning Objectives -->
              ${learningObjectives.length > 0 ? `
                <div>
                  <strong style="font-size:0.8rem; text-transform:uppercase; color:#2563EB; display:block; margin-bottom:4px; letter-spacing:0.5px;">
                    Learning Objectives
                  </strong>
                  <ul style="margin:0; padding-left:18px; font-size:0.88rem; color:#334155; line-height:1.5;">
                    ${learningObjectives.map(obj => `<li>${escapeHtml(obj)}</li>`).join("")}
                  </ul>
                </div>
              ` : ''}

              <!-- Practical Hands-on Exercise -->
              ${task.practical_exercise ? `
                <div class="exercise-box">
                  <strong style="font-size:0.8rem; text-transform:uppercase; color:#1E3A8A; display:block; margin-bottom:4px; letter-spacing:0.5px;">
                    🛠️ Practical Hands-on Exercise
                  </strong>
                  <p style="margin:0; font-size:0.88rem; color:#1E293B; line-height:1.5;">
                    ${escapeHtml(task.practical_exercise)}
                  </p>
                </div>
              ` : ''}

              <!-- Targeted Practice Questions / Problems -->
              ${practiceProblems.length > 0 ? `
                <div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:6px; padding:10px 14px;">
                  <strong style="font-size:0.8rem; text-transform:uppercase; color:#166534; display:block; margin-bottom:4px; letter-spacing:0.5px;">
                    📝 Targeted Practice Questions
                  </strong>
                  <ul style="margin:0; padding-left:18px; font-size:0.85rem; color:#14532D; line-height:1.4;">
                    ${practiceProblems.map(q => `<li>${escapeHtml(q)}</li>`).join("")}
                  </ul>
                  <div style="margin-top:8px;">
                    <a href="interview-config.html?topic=${encodeURIComponent(task.topic || '')}" class="btn btn-secondary" style="padding:3px 10px; font-size:0.75rem; text-decoration:none;">
                      Launch Practice Session on "${escapeHtml(task.topic || 'Topic')}" →
                    </a>
                  </div>
                </div>
              ` : ''}

              <!-- Expected Outcomes & Completion Criteria -->
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:4px;">
                ${task.expected_outcomes ? `
                  <div style="background:#F8FAFC; border:1px solid #E2E8F0; padding:8px 12px; border-radius:6px;">
                    <strong style="font-size:0.75rem; text-transform:uppercase; color:#64748B; display:block; margin-bottom:2px;">
                      Expected Outcome
                    </strong>
                    <span style="font-size:0.82rem; color:#334155;">${escapeHtml(task.expected_outcomes)}</span>
                  </div>
                ` : ''}
                ${task.completion_criteria ? `
                  <div style="background:#F8FAFC; border:1px solid #E2E8F0; padding:8px 12px; border-radius:6px;">
                    <strong style="font-size:0.75rem; text-transform:uppercase; color:#64748B; display:block; margin-bottom:2px;">
                      Measurable Completion Criteria
                    </strong>
                    <span style="font-size:0.82rem; color:#334155;">${escapeHtml(task.completion_criteria)}</span>
                  </div>
                ` : ''}
              </div>

            </div>
          ` : ''}

          <!-- Details Toggle Button -->
          <div>
            <button class="details-toggle-btn" onclick="toggleTaskDetails('${taskId}')">
              ${isExpanded ? '▲ Hide details & exercises' : '▼ Show learning objectives, exercises & criteria'}
            </button>
          </div>

        </div>
      </div>
    </div>
  `;
}

function toggleTaskDetails(taskId) {
  if (expandedTaskIds.has(taskId)) {
    expandedTaskIds.delete(taskId);
  } else {
    expandedTaskIds.add(taskId);
  }
  if (currentRoadmap) {
    renderPhases(currentRoadmap);
  }
}

async function handleToggleTaskStatus(analysisId, taskId, isChecked) {
  const newStatus = isChecked ? "completed" : "pending";

  // Optimistic update in memory
  if (currentRoadmap && Array.isArray(currentRoadmap.roadmap_tasks)) {
    currentRoadmap.roadmap_tasks = currentRoadmap.roadmap_tasks.map(t => {
      const matchId = t.task_id || t.id;
      if (matchId === taskId) {
        return {
          ...t,
          status: newStatus,
          completed_at: newStatus === "completed" ? new Date().toISOString() : null
        };
      }
      return t;
    });
    // Immediately refresh stats
    renderRoadmap(currentRoadmap);
  }

  try {
    const updated = await API.patch(`/api/analysis/${analysisId}/task/${taskId}`, {
      status: newStatus
    });

    currentRoadmap = updated;
    renderRoadmap(updated);
    showToast(
      isChecked 
        ? `Task completed! Readiness recalibrated to ${Math.round(updated.readiness_score || 0)}%.` 
        : `Task marked as pending.`, 
      "info"
    );

  } catch (err) {
    console.error("Task status update failed:", err);
    showToast(`Task update failed: ${err.message}`, "error");
    if (currentInterviewId) {
      loadRoadmapData(currentInterviewId);
    }
  }
}

async function handleUpdatePreferences() {
  if (!currentRoadmap || !currentRoadmap.id) return;

  const dateInput = document.getElementById("pref-target-date");
  const hoursSelect = document.getElementById("pref-daily-hours");
  const btn = document.getElementById("btn-save-schedule");

  const targetDate = dateInput ? dateInput.value : null;
  const dailyHours = hoursSelect ? parseFloat(hoursSelect.value) : 2.0;

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> Saving...`;
  }

  try {
    showToast("Recalibrating schedule and task duration models...", "info");
    const updated = await API.patch(`/api/analysis/${currentRoadmap.id}/preferences`, {
      target_interview_date: targetDate || null,
      daily_study_hours: dailyHours
    });

    currentRoadmap = updated;
    renderRoadmap(updated);
    showToast("Schedule and preparation timeline recalibrated successfully!", "success");

  } catch (err) {
    console.error("Schedule update failed:", err);
    showToast(`Schedule update failed: ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `💾 Recalibrate Schedule & Durations`;
    }
  }
}

function filterRoadmapPhase(phaseNum) {
  activePhaseFilter = phaseNum;

  document.querySelectorAll(".phase-tab-btn").forEach(btn => {
    btn.classList.remove("btn-primary", "active");
    btn.classList.add("btn-secondary");
  });

  const activeBtn = document.getElementById(phaseNum === "all" ? "tab-phase-all" : `tab-phase-${phaseNum}`);
  if (activeBtn) {
    activeBtn.classList.remove("btn-secondary");
    activeBtn.classList.add("btn-primary", "active");
  }

  if (currentRoadmap) {
    renderPhases(currentRoadmap);
  }
}

function filterTaskStatus(status) {
  activeStatusFilter = status;

  document.querySelectorAll(".status-tab-btn").forEach(btn => {
    btn.classList.remove("active");
  });

  const activeBtn = document.getElementById(`tab-status-${status}`);
  if (activeBtn) {
    activeBtn.classList.add("active");
  }

  if (currentRoadmap) {
    renderPhases(currentRoadmap);
  }
}

function updateAnalysisLinks(interviewId) {
  const qParam = `?id=${encodeURIComponent(interviewId)}`;
  const topbarLink = document.getElementById("topbar-analysis-link");
  if (topbarLink) topbarLink.href = `analysis.html${qParam}`;

  const switchBtn = document.getElementById("btn-switch-analysis");
  if (switchBtn) switchBtn.href = `analysis.html${qParam}`;

  const bottomBtn = document.getElementById("btn-bottom-analysis");
  if (bottomBtn) bottomBtn.href = `analysis.html${qParam}`;
}

function setupEventListeners() {
  const selectEl = document.getElementById("roadmap-session-select");
  if (selectEl) {
    selectEl.addEventListener("change", (e) => {
      const newId = e.target.value;
      if (newId) {
        currentInterviewId = newId;
        loadRoadmapData(newId);
      }
    });
  }

  // Bind PDF Download buttons across topbar, banner, and bottom navigation
  const downloadBtns = [
    document.getElementById("btn-download-pdf"),
    document.getElementById("btn-banner-download-pdf"),
    document.getElementById("btn-bottom-download-pdf")
  ].filter(Boolean);

  downloadBtns.forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      downloadRoadmapPDF();
    });
  });
}

async function downloadRoadmapPDF() {
  const downloadBtns = [
    document.getElementById("btn-download-pdf"),
    document.getElementById("btn-banner-download-pdf"),
    document.getElementById("btn-bottom-download-pdf")
  ].filter(Boolean);

  // If in empty state with no roadmap, prompt the user
  const emptyEl = document.getElementById("roadmap-empty");
  if (emptyEl && emptyEl.style.display !== "none" && !currentInterviewId) {
    showToast("No interview roadmap exists. Please complete a mock interview first.", "warning");
    return;
  }

  const targetId = currentInterviewId || "latest";

  // Retain original inner HTML and set loading states
  const originalContents = downloadBtns.map(btn => btn.innerHTML);
  downloadBtns.forEach(btn => {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> <span>Generating PDF...</span>`;
  });

  try {
    showToast("Compiling personalized roadmap analysis PDF...", "info");

    const token = API.getToken();
    const endpoint = (targetId && targetId !== "latest")
      ? `/api/analysis/${encodeURIComponent(targetId)}/export/pdf`
      : `/api/analysis/latest/export/pdf`;

    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      method: "GET",
      headers: {
        ...(token ? { "Authorization": `Bearer ${token}` } : {})
      }
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      if (response.status === 404) {
        throw new Error(errData.detail || "No preparation roadmap found. Please complete an interview first.");
      }
      throw new Error(errData.detail || errData.message || `PDF export failed (HTTP ${response.status})`);
    }

    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const downloadLink = document.createElement("a");
    downloadLink.href = blobUrl;
    downloadLink.download = "InterviewAI_Roadmap_Analysis.pdf";
    document.body.appendChild(downloadLink);
    downloadLink.click();
    downloadLink.remove();
    window.URL.revokeObjectURL(blobUrl);

    showToast("InterviewAI Roadmap PDF downloaded successfully!", "success");
  } catch (err) {
    console.error("PDF download failed:", err);
    showToast(err.message || "Failed to download roadmap PDF.", "error");
  } finally {
    downloadBtns.forEach((btn, idx) => {
      btn.disabled = false;
      btn.innerHTML = originalContents[idx];
    });
  }
}

function showEmptyState(msg) {
  const loadingEl = document.getElementById("roadmap-loading");
  const contentEl = document.getElementById("roadmap-content");
  const emptyEl = document.getElementById("roadmap-empty");
  const msgEl = document.getElementById("roadmap-empty-msg");

  if (loadingEl) loadingEl.style.display = "none";
  if (contentEl) contentEl.style.display = "none";
  if (emptyEl) {
    emptyEl.style.display = "block";
    if (msgEl && msg) {
      msgEl.textContent = msg;
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
