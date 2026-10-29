/* Dashboard Controller */
document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();
  await loadDashboardData();
});

async function loadDashboardData() {
  try {
    const data = await API.get("/api/dashboard");
    
    // Update user info
    const userNameEl = document.getElementById("welcome-user-name");
    if (userNameEl) userNameEl.textContent = data.user.name || "Candidate";
    
    const sidebarUserName = document.getElementById("sidebar-user-name");
    if (sidebarUserName) sidebarUserName.textContent = data.user.name || "Candidate";
    
    const sidebarUserRole = document.getElementById("sidebar-user-role");
    if (sidebarUserRole) sidebarUserRole.textContent = data.user.target_role || "Software Developer";

    const userAvatarEl = document.getElementById("user-avatar-initial");
    if (userAvatarEl && data.user.name) {
      userAvatarEl.textContent = data.user.name.charAt(0).toUpperCase();
    }

    // Update Stats Cards
    const statPracticed = document.getElementById("stat-practiced");
    if (statPracticed) statPracticed.textContent = data.stats.interviews_practiced;

    const statAvgScore = document.getElementById("stat-avg-score");
    if (statAvgScore) statAvgScore.textContent = data.stats.average_score;

    const statSkills = document.getElementById("stat-skills");
    if (statSkills) statSkills.textContent = data.stats.skills_in_progress;

    // Render Recent Activity Table
    const activityTbody = document.getElementById("recent-activity-tbody");
    if (activityTbody) {
      if (!data.recent_activity || data.recent_activity.length === 0) {
        activityTbody.innerHTML = `
          <tr>
            <td colspan="4" style="text-align: center; color: var(--text-muted); padding: 30px;">
              No interview activity yet. Start your first mock interview above!
            </td>
          </tr>`;
      } else {
        activityTbody.innerHTML = data.recent_activity.map(act => `
          <tr>
            <td>
              <strong>${act.name}</strong>
              <div style="font-size:0.8rem; color:var(--text-muted);">${act.topic} • ${act.difficulty}</div>
            </td>
            <td>${act.date}</td>
            <td>
              <span class="badge ${act.status === 'completed' ? 'badge-success' : 'badge-warning'}">
                ${act.status === 'completed' ? 'Completed' : 'In Progress'}
              </span>
            </td>
            <td><strong>${act.score}</strong></td>
            <td>
              <div style="display:flex; gap:6px; flex-wrap:wrap;">
                <a href="${act.status === 'completed' ? `result.html?id=${act.id}` : `interview.html?id=${act.id}`}" class="btn btn-secondary" style="padding:4px 10px; font-size:0.8rem;">
                  ${act.status === 'completed' ? 'Results' : 'Resume'}
                </a>
                ${act.status === 'completed' ? `
                  <a href="analysis.html?id=${act.id}" class="btn btn-primary" style="padding:4px 10px; font-size:0.8rem; background:#4F46E5; text-decoration:none;">
                    🔍 AI Analysis
                  </a>
                  <a href="roadmap.html?id=${act.id}" class="btn btn-secondary" style="padding:4px 10px; font-size:0.8rem; text-decoration:none;">
                    📅 Roadmap
                  </a>
                ` : `
                  <a href="interview.html?id=${act.id}" class="btn btn-primary" style="padding:4px 10px; font-size:0.8rem; background:#2563EB; text-decoration:none;">
                    ⚡ Resume Mock
                  </a>
                `}
              </div>
            </td>
          </tr>
        `).join("");
      }
    }

    // Render Skill Progress Bars
    const skillContainer = document.getElementById("skill-progress-container");
    if (skillContainer) {
      if (!data.skill_progress || data.skill_progress.length === 0) {
        skillContainer.innerHTML = `<p class="text-muted" style="font-size:0.9rem;">Complete mock interviews to track your skill scores.</p>`;
      } else {
        skillContainer.innerHTML = data.skill_progress.map(sk => `
          <div class="skill-item">
            <div class="skill-header">
              <span>${sk.name}</span>
              <span>${sk.score}%</span>
            </div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" style="width: ${Math.min(100, Math.max(5, sk.score))}%;"></div>
            </div>
          </div>
        `).join("");
      }
    }

    // Load Evidence-Based AI Readiness Intelligence
    await loadReadinessIntelligence();

  } catch (err) {
    showToast(`Failed to load dashboard: ${err.message}`, "error");
  }
}

async function loadReadinessIntelligence() {
  // Always attach recalculate button listener early so it is active in all states
  const recalcBtn = document.getElementById("btn-recalculate-readiness");
  if (recalcBtn && !recalcBtn.hasAttribute("data-bound")) {
    recalcBtn.setAttribute("data-bound", "true");
    recalcBtn.addEventListener("click", handleRecalculateReadiness);
  }

  try {
    const rData = await API.get("/api/readiness");
    if (!rData) return;

    const isInsufficient = rData.data_sufficiency === "INSUFFICIENT";
    const scoreVal = Math.round(rData.overall_readiness_score ?? rData.readiness_score ?? 0);
    const stageName = rData.readiness_stage || rData.readiness_level || (isInsufficient ? "Early Preparation" : "Calibrated");

    // Level Badge
    const lvlBadge = document.getElementById("readiness-level-badge");
    if (lvlBadge) {
      if (isInsufficient) {
        lvlBadge.textContent = "Awaiting Sessions";
        lvlBadge.className = "badge";
        lvlBadge.style.background = "#F1F5F9";
        lvlBadge.style.color = "#475569";
        lvlBadge.style.border = "1px solid #CBD5E1";
      } else {
        lvlBadge.textContent = stageName;
        lvlBadge.style.background = "";
        lvlBadge.style.color = "";
        lvlBadge.style.border = "";
        if (stageName.toLowerCase().includes("ready") || stageName.toLowerCase().includes("calibrated")) {
          lvlBadge.className = "badge badge-success";
        } else if (stageName.toLowerCase().includes("borderline") || stageName.toLowerCase().includes("target") || stageName.toLowerCase().includes("developing")) {
          lvlBadge.className = "badge badge-warning";
        } else {
          lvlBadge.className = "badge badge-primary";
        }
      }
    }

    // Sufficiency Badge
    const suffBadge = document.getElementById("data-sufficiency-badge");
    if (suffBadge) {
      const suff = (rData.data_sufficiency || (isInsufficient ? 'INSUFFICIENT' : 'MODERATE')).replace('_', ' ');
      suffBadge.textContent = `${suff} TELEMETRY`;
      if (isInsufficient) {
        suffBadge.style.background = "#FEF3C7";
        suffBadge.style.color = "#92400E";
      } else if (suff.includes("HIGH") || suff.includes("VERY")) {
        suffBadge.style.background = "#ECFDF5";
        suffBadge.style.color = "#065F46";
      } else {
        suffBadge.style.background = "#EEF2FF";
        suffBadge.style.color = "#4338CA";
      }
    }

    // Explanation Text
    const expEl = document.getElementById("readiness-explanation");
    if (expEl) {
      expEl.textContent = rData.data_sufficiency_explanation || rData.readiness_explanation || rData.overall_assessment || "Readiness index calibrated against your target role benchmarks.";
    }

    // Gauge Value
    const gaugeEl = document.getElementById("readiness-gauge-val");
    if (gaugeEl) {
      if (isInsufficient && scoreVal === 0) {
        gaugeEl.textContent = "0%";
        gaugeEl.style.color = "#64748B";
      } else {
        gaugeEl.textContent = `${scoreVal}%`;
        if (scoreVal >= 75) gaugeEl.style.color = "#10B981";
        else if (scoreVal >= 50) gaugeEl.style.color = "#2563EB";
        else gaugeEl.style.color = "#F59E0B";
      }
    }

    const subEl = document.getElementById("readiness-gauge-sub");
    if (subEl) {
      subEl.textContent = `Target: ${rData.target_role || 'Software Engineer'}`;
    }

    // Evidence Metadata
    const metaEl = document.getElementById("readiness-evidence-meta");
    if (metaEl) {
      const eb = rData.evidence_breakdown || {};
      const ansCount = eb.total_answers_analyzed ?? eb.evaluated_answers_count ?? 0;
      const sesCount = eb.completed_interviews ?? eb.completed_interviews_count ?? 0;
      metaEl.textContent = `${ansCount} answers • ${sesCount} sessions`;
    }

    // Render Dimensions Bars
    const dimContainer = document.getElementById("readiness-dimensions-container");
    if (dimContainer) {
      if (Array.isArray(rData.dimensions) && rData.dimensions.length > 0) {
        dimContainer.innerHTML = rData.dimensions.map(d => {
          const dScore = Math.round(d.score || 0);
          let barColor = "#2563EB";
          if (dScore >= 80) barColor = "#10B981";
          else if (dScore > 0 && dScore < 50) barColor = "#EF4444";
          else if (dScore === 0) barColor = "#94A3B8";

          const statusBadge = d.status ? `<span style="font-size:0.7rem; color:#64748B; font-weight:normal; margin-left:6px;">(${escapeHtml(d.status)})</span>` : '';

          return `
            <div>
              <div style="display:flex; justify-content:space-between; font-size:0.8rem; font-weight:600; margin-bottom:4px;">
                <span>${escapeHtml(d.name)}${statusBadge}</span>
                <span style="color:${dScore > 0 ? barColor : '#64748B'}; font-weight:700;">${dScore}%</span>
              </div>
              <div class="progress-bar-bg" style="height:6px;">
                <div class="progress-bar-fill" style="width:${Math.max(dScore > 0 ? 5 : 0, Math.min(100, dScore))}%; background-color:${barColor};"></div>
              </div>
            </div>
          `;
        }).join("");
      } else {
        dimContainer.innerHTML = `<div class="text-muted" style="font-size:0.85rem; padding:8px 0;">Complete mock interviews to calibrate dimension telemetry.</div>`;
      }
    }

    // Render Next Best Action
    const nbaTitle = document.getElementById("readiness-next-action-title");
    const nbaDesc = document.getElementById("readiness-next-action-desc");
    const nbaBtn = document.getElementById("readiness-next-action-btn");
    if (rData.next_best_action) {
      const nba = rData.next_best_action;
      if (nbaTitle) nbaTitle.textContent = nba.title || "Targeted Practice Session";
      if (nbaDesc) nbaDesc.textContent = nba.rationale || nba.evidence_basis || "Focus on highest-yield questions.";
      if (nbaBtn) {
        if (nba.deep_link_tab === "roadmap" || nba.deep_link_tab === "plan") {
          nbaBtn.href = "roadmap.html";
          nbaBtn.textContent = "Open Roadmap →";
        } else if (nba.deep_link_tab === "analysis") {
          nbaBtn.href = "analysis.html";
          nbaBtn.textContent = "View Analysis →";
        } else {
          nbaBtn.href = "interview-config.html";
          nbaBtn.textContent = "Start Practice →";
        }
      }
    }

    // Render Persistent Focus Areas
    const wTagsContainer = document.getElementById("readiness-weakness-tags");
    if (wTagsContainer) {
      const weaknesses = Array.isArray(rData.persistent_weaknesses) ? rData.persistent_weaknesses : [];
      if (weaknesses.length === 0) {
        wTagsContainer.innerHTML = `<span style="font-size:0.75rem; color:#64748B;">${isInsufficient ? 'Complete first mock interview to detect focus areas' : 'No critical weaknesses identified'}</span>`;
      } else {
        wTagsContainer.innerHTML = weaknesses.slice(0, 4).map(w => `
          <span style="font-size:0.75rem; background:#FEE2E2; color:#B91C1C; font-weight:600; padding:2px 8px; border-radius:4px; border:1px solid #FECACA;">
            ${escapeHtml(w.weakness_name || w.name || w)}
          </span>
        `).join("");
      }
    }

  } catch (rErr) {
    console.error("Readiness intelligence load failed:", rErr);

    const lvlBadge = document.getElementById("readiness-level-badge");
    if (lvlBadge) {
      lvlBadge.textContent = "Telemetry Offline";
      lvlBadge.className = "badge badge-warning";
    }

    const suffBadge = document.getElementById("data-sufficiency-badge");
    if (suffBadge) {
      suffBadge.textContent = "CONNECTION ERROR";
      suffBadge.style.background = "#FEE2E2";
      suffBadge.style.color = "#991B1B";
    }

    const expEl = document.getElementById("readiness-explanation");
    if (expEl) {
      expEl.innerHTML = `<span style="color:#DC2626;">Unable to retrieve readiness telemetry: ${escapeHtml(rErr.message || "Server connection error")}.</span> <button id="btn-inline-retry" class="btn btn-secondary" style="padding:2px 8px; font-size:0.75rem; margin-left:8px; cursor:pointer;">Retry</button>`;
      const inlineRetry = document.getElementById("btn-inline-retry");
      if (inlineRetry) inlineRetry.onclick = () => loadReadinessIntelligence();
    }

    const dimContainer = document.getElementById("readiness-dimensions-container");
    if (dimContainer) {
      dimContainer.innerHTML = `
        <div style="padding:12px; background:#FEF2F2; border:1px solid #FCA5A5; border-radius:8px; text-align:center;">
          <p style="font-size:0.82rem; color:#991B1B; margin-bottom:8px;">Telemetry could not be loaded.</p>
          <button id="btn-dim-retry" class="btn btn-secondary" style="padding:4px 12px; font-size:0.8rem; cursor:pointer;">Retry Telemetry</button>
        </div>
      `;
      const dimRetry = document.getElementById("btn-dim-retry");
      if (dimRetry) dimRetry.onclick = () => loadReadinessIntelligence();
    }
  }
}

async function handleRecalculateReadiness() {
  const btn = document.getElementById("btn-recalculate-readiness");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> Recalculating...`;
  }
  try {
    showToast("Recalculating readiness intelligence with latest session data...", "info");
    await API.post("/api/readiness/recalculate");
    await loadDashboardData();
    showToast("Readiness scores updated successfully!", "success");
  } catch (err) {
    showToast(`Recalculate failed: ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>🔄</span> Recalculate`;
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

function startPractice(type) {
  window.location.href = `interview-config.html?type=${encodeURIComponent(type)}`;
}

