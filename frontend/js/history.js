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

    container.innerHTML = list.map(item => `
      <tr>
        <td><strong>${item.target_role}</strong><div style="font-size:0.8rem; color:var(--text-muted);">${item.topic}</div></td>
        <td>${item.interview_type}</td>
        <td><span class="badge badge-gray">${item.difficulty}</span></td>
        <td>${item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Recent'}</td>
        <td><span class="badge ${item.status === 'completed' ? 'badge-success' : 'badge-warning'}">${item.status === 'completed' ? 'Completed' : 'In Progress'}</span></td>
        <td><strong>${item.status === 'completed' ? Math.round(item.total_score || 0) + '%' : '-'}</strong></td>
        <td>
          <a href="${item.status === 'completed' ? `result.html?id=${item.id}` : `interview.html?id=${item.id}`}" class="btn btn-secondary" style="padding:4px 12px; font-size:0.8rem;">
            ${item.status === 'completed' ? 'View Report' : 'Resume'}
          </a>
        </td>
      </tr>
    `).join("");

  } catch (err) {
    showToast(`Failed to load interview history: ${err.message}`, "error");
  }
}
