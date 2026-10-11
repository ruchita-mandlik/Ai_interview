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
              <a href="${act.status === 'completed' ? `result.html?id=${act.id}` : `interview.html?id=${act.id}`}" class="btn btn-secondary" style="padding:4px 12px; font-size:0.8rem;">
                ${act.status === 'completed' ? 'View Results' : 'Resume'}
              </a>
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

  } catch (err) {
    showToast(`Failed to load dashboard: ${err.message}`, "error");
  }
}

function startPractice(type) {
  window.location.href = `interview-config.html?type=${encodeURIComponent(type)}`;
}
