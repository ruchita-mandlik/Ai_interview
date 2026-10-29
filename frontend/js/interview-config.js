/* Dynamic Interview Configuration Controller - ChatGPT-Grade AI Flow */

// Global helper functions for chips & question selectors (called from inline onclick)
function applyChip(fieldId, value) {
  const input = document.getElementById(fieldId);
  if (input) {
    input.value = value;
    input.focus();
    // Dispatch input event for any reactive listeners
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

function appendSkill(skillName) {
  const input = document.getElementById("skills_input");
  if (!input) return;
  const current = input.value.trim();
  if (!current) {
    input.value = skillName;
  } else {
    const list = current.split(",").map(s => s.trim().toLowerCase());
    if (!list.includes(skillName.toLowerCase())) {
      input.value = `${current}, ${skillName}`;
    }
  }
  input.focus();
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function updateQuestionCount(count) {
  const hiddenInput = document.getElementById("num_questions");
  if (hiddenInput) {
    hiddenInput.value = count;
  }

  [3, 5, 10].forEach(n => {
    const box = document.getElementById(`q-box-${n}`);
    if (box) {
      if (n === count) {
        box.style.borderColor = "#6366F1";
        box.style.background = "#EEF2FF";
        box.style.color = "#4338CA";
        box.style.fontWeight = "700";
      } else {
        box.style.borderColor = "#CBD5E1";
        box.style.background = "#F8FAFC";
        box.style.color = "#475569";
        box.style.fontWeight = "600";
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  // Check auth
  if (typeof requireAuth === "function") {
    requireAuth();
  }

  // Populate user profile info in sidebar
  try {
    const user = API.getUser();
    if (user) {
      const avatarEl = document.getElementById("sidebar-avatar");
      const nameEl = document.getElementById("sidebar-user-name");
      const roleEl = document.getElementById("sidebar-user-role");
      if (nameEl) nameEl.textContent = user.name || user.email || "Candidate";
      if (avatarEl) avatarEl.textContent = (user.name ? user.name[0] : "U").toUpperCase();
      if (roleEl && user.target_role) roleEl.textContent = user.target_role;
    }
  } catch (e) {
    console.debug("User info load skipped", e);
  }

  // Handle URL presets if any
  const urlParams = new URLSearchParams(window.location.search);
  const presetType = urlParams.get("type");
  const presetRole = urlParams.get("role");
  const presetDiff = urlParams.get("diff");

  if (presetType) {
    const typeInput = document.getElementById("interview_type");
    if (typeInput) typeInput.value = presetType;
  }
  if (presetRole) {
    const roleInput = document.getElementById("target_role");
    if (roleInput) roleInput.value = presetRole;
  }
  if (presetDiff) {
    const diffInput = document.getElementById("difficulty");
    if (diffInput) diffInput.value = presetDiff;
  }

  // Setup PDF Dropzone and file selection
  const fileInput = document.getElementById("resume_file_input");
  const dropzone = document.getElementById("pdf-dropzone");
  const fileNameDisplay = document.getElementById("pdf-file-name");

  if (fileInput && fileNameDisplay) {
    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files[0]) {
        const file = fileInput.files[0];
        if (!file.name.toLowerCase().endsWith(".pdf")) {
          showToast("Please upload a PDF file (.pdf)", "error");
          fileInput.value = "";
          fileNameDisplay.textContent = "Choose PDF or drag & drop";
          return;
        }
        fileNameDisplay.innerHTML = `✅ <strong>${file.name}</strong> (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
        if (dropzone) {
          dropzone.style.borderColor = "#10B981";
          dropzone.style.background = "#ECFDF5";
        }
      }
    });

    if (dropzone) {
      ["dragenter", "dragover"].forEach(evtName => {
        dropzone.addEventListener(evtName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          dropzone.classList.add("dragover");
        }, false);
      });

      ["dragleave", "drop"].forEach(evtName => {
        dropzone.addEventListener(evtName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          dropzone.classList.remove("dragover");
        }, false);
      });

      dropzone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        if (dt && dt.files && dt.files[0]) {
          fileInput.files = dt.files;
          fileInput.dispatchEvent(new Event("change"));
        }
      });
    }
  }

  // Form Submission
  const form = document.getElementById("dynamic-interview-form");
  const errorBanner = document.getElementById("config-error-banner");
  const launchBtn = document.getElementById("btn-launch-interview");

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      if (launchBtn && launchBtn.disabled) {
        return; // Prevent duplicate concurrent submissions
      }

      if (errorBanner) {
        errorBanner.style.display = "none";
        errorBanner.textContent = "";
      }

      const targetRole = (document.getElementById("target_role")?.value || "").trim();
      const experienceLevel = (document.getElementById("experience_level")?.value || "").trim();
      const skillsRaw = (document.getElementById("skills_input")?.value || "").trim();
      const jobDescription = (document.getElementById("job_description")?.value || "").trim();
      const interviewType = (document.getElementById("interview_type")?.value || "").trim();
      const difficulty = (document.getElementById("difficulty")?.value || "").trim();
      const numQuestions = parseInt(document.getElementById("num_questions")?.value || "5", 10);
      const resumeText = (document.getElementById("resume_text")?.value || "").trim();
      const additionalInstructions = (document.getElementById("additional_instructions")?.value || "").trim();

      if (!targetRole) {
        if (errorBanner) {
          errorBanner.textContent = "Please specify a Target Position or Job Role.";
          errorBanner.style.display = "block";
        }
        return;
      }

      // Parse skills into array
      const skillsList = skillsRaw
        ? skillsRaw.split(",").map(s => s.trim()).filter(Boolean)
        : [];

      // Disable button & show spinner
      if (launchBtn) {
        launchBtn.disabled = true;
        launchBtn.innerHTML = `
          <div style="display:inline-block; width:18px; height:18px; border:2px solid #fff; border-top-color:transparent; border-radius:50%; animation:spin 0.8s linear infinite;"></div>
          <span>Crafting Real-Time Questions with Gemini AI...</span>
        `;
      }

      let resumeAnalysisId = null;

      // Handle PDF resume upload if provided
      if (fileInput && fileInput.files && fileInput.files[0]) {
        try {
          if (launchBtn) {
            launchBtn.innerHTML = `
              <div style="display:inline-block; width:18px; height:18px; border:2px solid #fff; border-top-color:transparent; border-radius:50%; animation:spin 0.8s linear infinite;"></div>
              <span>Analyzing PDF Resume & Skill Gaps...</span>
            `;
          }
          const formData = new FormData();
          formData.append("file", fileInput.files[0]);
          formData.append("job_description", jobDescription || `Target Role: ${targetRole}`);
          formData.append("job_title", targetRole);

          const analysis = await API.postFormData("/api/resume-analysis/analyze", formData);
          if (analysis && analysis.id) {
            resumeAnalysisId = analysis.id;
          }
        } catch (uploadErr) {
          console.warn("Resume PDF analysis warning:", uploadErr);
          // If resume analysis fails, proceed with standard generation rather than blocking interview
        }
      }

      // Build payload for /api/interviews/start (Standard Mock Practice)
      const payload = {
        target_role: targetRole,
        role: targetRole,
        experience_level: experienceLevel || "Mid-to-Senior",
        topic: targetRole,
        topics: skillsList.length ? skillsList : [targetRole],
        skills: skillsList,
        job_description: jobDescription || null,
        interview_type: interviewType || "Technical Mock",
        difficulty: difficulty || "Medium",
        num_questions: numQuestions,
        total_questions: numQuestions,
        resume_text: resumeText || null,
        additional_instructions: additionalInstructions || null,
        resume_analysis_id: resumeAnalysisId,
        mode: "standard",
        is_adaptive: false
      };

      try {
        if (launchBtn) {
          launchBtn.innerHTML = `
            <div style="display:inline-block; width:18px; height:18px; border:2px solid #fff; border-top-color:transparent; border-radius:50%; animation:spin 0.8s linear infinite;"></div>
            <span>Generating Structured Mock Questions with Gemini...</span>
          `;
        }

        const interview = await API.post("/api/interviews/start", payload);

        if (!interview || !interview.id) {
          throw new Error("Interview creation failed. Missing interview ID from server.");
        }

        showToast("Standard Mock Interview Room Initialized!", "success");

        // Redirect to standard mock interview room
        setTimeout(() => {
          window.location.href = `interview.html?id=${interview.id}`;
        }, 500);

      } catch (err) {
        console.error("Failed to launch interview:", err);
        if (launchBtn) {
          launchBtn.disabled = false;
          launchBtn.innerHTML = `<span>🚀 Launch Standard Mock Interview Session →</span>`;
        }
        if (errorBanner) {
          errorBanner.innerHTML = `
            <strong>Unable to launch AI interview:</strong> ${err.message || "An unexpected error occurred."}<br>
            <span style="font-size:0.85rem; font-weight:400; color:#B91C1C;">
              If this is a Gemini API rate limit or quota issue, please verify credentials or retry in a few moments.
            </span>
          `;
          errorBanner.style.display = "block";
          errorBanner.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        showToast(err.message || "Interview launch failed", "error");
      }
    });
  }
});
