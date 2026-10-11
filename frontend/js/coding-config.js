document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();
  
  const user = API.getUser();
  if (user) {
    document.getElementById("nav-user-name").textContent = user.name || "Candidate";
    document.getElementById("user-avatar").textContent = (user.name || "C")[0].toUpperCase();
  }

  document.getElementById("logout-btn")?.addEventListener("click", () => {
    API.removeToken();
    window.location.href = "login.html";
  });

  const form = document.getElementById("coding-config-form");
  const startBtn = document.getElementById("start-btn");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const target_role = document.getElementById("target_role").value.trim();
    const topic = document.getElementById("topic").value;
    const experience_level = document.getElementById("experience_level").value;
    const difficulty = document.getElementById("difficulty").value;
    const language = document.getElementById("language").value;

    startBtn.disabled = true;
    startBtn.innerHTML = "⏳ Generating AI Problem...";

    try {
      const interview = await API.startCodingInterview({
        target_role,
        topic,
        experience_level,
        difficulty,
        language
      });

      showToast("Coding Problem Generated! Redirecting...", "success");
      setTimeout(() => {
        window.location.href = `coding-interview.html?id=${interview.id}`;
      }, 800);
    } catch (err) {
      showToast(err.message || "Failed to start coding interview", "error");
      startBtn.disabled = false;
      startBtn.innerHTML = "🚀 Start AI Coding Interview";
    }
  });
});
