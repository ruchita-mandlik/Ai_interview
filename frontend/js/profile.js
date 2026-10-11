/* Candidate Profile Controller */
document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();
  await loadProfile();
  setupProfileForm();
});

async function loadProfile() {
  try {
    const profile = await API.get("/api/profile");

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el && val !== undefined && val !== null) el.value = val;
    };

    setVal("full_name", profile.full_name);
    setVal("email", profile.email);
    setVal("education", profile.education || "Bachelor's Degree");
    setVal("skills", profile.skills || "Java, OOP, DSA, SQL");
    setVal("experience_level", profile.experience_level || "Intermediate");
    setVal("target_role", profile.target_role || "Java Developer");
    setVal("years_of_experience", profile.years_of_experience || 2);
    setVal("preferred_interview_type", profile.preferred_interview_type || "Technical");
    setVal("technical_interests", profile.technical_interests || "Backend, Cloud, Databases");

  } catch (err) {
    showToast(`Failed to load profile: ${err.message}`, "error");
  }
}

function setupProfileForm() {
  const form = document.getElementById("profile-form");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = form.querySelector("button[type='submit']");
      btn.disabled = true;
      btn.innerHTML = `<span class="loading-spinner"></span> Saving Changes...`;

      const payload = {
        full_name: document.getElementById("full_name").value.trim(),
        email: document.getElementById("email").value.trim(),
        education: document.getElementById("education").value,
        skills: document.getElementById("skills").value.trim(),
        experience_level: document.getElementById("experience_level").value,
        target_role: document.getElementById("target_role").value,
        years_of_experience: parseInt(document.getElementById("years_of_experience").value, 10),
        preferred_interview_type: document.getElementById("preferred_interview_type").value,
        technical_interests: document.getElementById("technical_interests").value.trim()
      };

      try {
        const updated = await API.put("/api/profile/update", payload);
        btn.disabled = false;
        btn.innerHTML = "Save Changes";
        showToast("Profile updated successfully!", "success");

        // Update stored user object name
        const user = API.getUser() || {};
        user.name = updated.full_name;
        API.setUser(user);
      } catch (err) {
        btn.disabled = false;
        btn.innerHTML = "Save Changes";
        showToast(`Failed to save profile: ${err.message}`, "error");
      }
    });
  }
}
