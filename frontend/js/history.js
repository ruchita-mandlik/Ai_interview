/* Interview History Controller */
document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();
  await loadHistory();
});

async function loadHistory() {
  try {
    const list = await API.get("/api/history");
    const container = document.getElementById("history-list-tbody");
    if (!container) return;

    if (!list || list.length === 0) {
      container.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; padding: 40px; color: var(--text-muted);">
            No interview history found. Go to Dashboard and start your first mock practice!
          </td>
        </tr>`;
      return;
    }

    container.innerHTML = list.map(item => {
      const isAdaptive = Boolean(item.is_adaptive || item.interview_type?.includes("Adaptive"));
      const resumeUrl = isAdaptive ? `adaptive-interview.html?id=${item.id}` : `interview.html?id=${item.id}`;
      const typeBadge = isAdaptive 
        ? `<span class="badge" style="background:#EDE9FE; color:#6D28D9; font-weight:700;">🧠 Adaptive AI</span>`
        : `<span class="badge" style="background:#E0F2FE; color:#0369A1; font-weight:700;">🚀 Standard Mock</span>`;

      return `
      <tr>
        <td>
          <strong>${item.target_role}</strong>
          <div style="font-size:0.8rem; color:var(--text-muted);">${item.topic}</div>
        </td>
        <td>
          ${typeBadge}
          <div style="font-size:0.75rem; color:#64748B; margin-top:3px;">${item.interview_type || 'Technical'}</div>
        </td>
        <td><span class="badge badge-gray">${item.difficulty}</span></td>
        <td>${item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Recent'}</td>
        <td><span class="badge ${item.status === 'completed' ? 'badge-success' : 'badge-warning'}">${item.status === 'completed' ? 'Completed' : 'In Progress'}</span></td>
        <td><strong>${item.status === 'completed' ? Math.round(item.total_score || 0) + '%' : '-'}</strong></td>
        <td>
          <div style="display:flex; gap:6px; flex-wrap:wrap;">
            <a href="${item.status === 'completed' ? `result.html?id=${item.id}` : resumeUrl}" class="btn btn-secondary" style="padding:4px 10px; font-size:0.8rem;">
              ${item.status === 'completed' ? 'Results' : 'Resume'}
            </a>
            ${item.status === 'completed' ? `
              <a href="analysis.html?id=${item.id}" class="btn btn-primary" style="padding:4px 10px; font-size:0.8rem; background:#4F46E5; text-decoration:none;">
                🔍 Analysis
              </a>
              <a href="roadmap.html?id=${item.id}" class="btn btn-secondary" style="padding:4px 10px; font-size:0.8rem; text-decoration:none;">
                📅 Roadmap
              </a>
            ` : ''}
          </div>
        </td>
      </tr>
    `}).join("");

  } catch (err) {
    showToast(`Failed to load interview history: ${err.message}`, "error");
  }
}
