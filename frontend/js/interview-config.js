/* Interview Configuration Controller - Resume + JD Intelligence */

function switchConfigMode(mode) {
  const tabResume = document.getElementById("tab-btn-resume");
  const tabStandard = document.getElementById("tab-btn-standard");
  const containerResume = document.getElementById("mode-resume-container");
  const containerStandard = document.getElementById("mode-standard-container");

  if (mode === "resume") {
    tabResume.classList.add("active");
    tabStandard.classList.remove("active");
    containerResume.style.display = "block";
    containerStandard.style.display = "none";
  } else {
    tabStandard.classList.add("active");
    tabResume.classList.remove("active");
    containerStandard.style.display = "block";
    containerResume.style.display = "none";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  requireAuth();

  // Check URL query params for preset
  const urlParams = new URLSearchParams(window.location.search);
  const presetType = urlParams.get("type");
  const presetMode = urlParams.get("mode");

  if (presetType) {
    const typeSelect = document.getElementById("interview_type");
    if (typeSelect) typeSelect.value = presetType;
  }

  if (presetMode === "standard") {
    switchConfigMode("standard");
  } else {
    switchConfigMode("resume");
  }

  // PDF File Input Listener
  const fileInput = document.getElementById("resume_file_input");
  const fileNameDisplay = document.getElementById("pdf-file-name");
  const dropzone = document.getElementById("pdf-dropzone");

  if (fileInput && fileNameDisplay) {
    fileInput.addEventListener("change", (e) => {
      if (fileInput.files && fileInput.files[0]) {
        const file = fileInput.files[0];
        if (!file.name.toLowerCase().endswith(".pdf") && !file.name.toLowerCase().endsWith(".pdf")) {
          showToast("Please select a PDF file (.pdf)", "error");
          fileInput.value = "";
          fileNameDisplay.innerHTML = "Click to choose or drag & drop your PDF Resume";
          return;
        }
        fileNameDisplay.innerHTML = `✅ Selected: <strong>${file.name}</strong> (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
      }
    });

    // Drag & drop handlers
    if (dropzone) {
      ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          dropzone.classList.add('active');
        }, false);
      });
      ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          dropzone.classList.remove('active');
        }, false);
      });
      dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files[0]) {
          fileInput.files = files;
          fileInput.dispatchEvent(new Event('change'));
        }
      });
    }
  }

  // Resume + JD Analysis Form Submission
  const resumeForm = document.getElementById("resume-analysis-form");
  if (resumeForm) {
    resumeForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = document.getElementById("resume-form-error");
      const btn = document.getElementById("btn-analyze-resume");
      if (errEl) errEl.textContent = "";

      const file = fileInput.files[0];
      const jobDesc = document.getElementById("job_description_input").value.trim();
      const jobTitle = document.getElementById("resume_job_title").value.trim() || "Software Developer";

      if (!file) {
        if (errEl) errEl.textContent = "Please upload a PDF resume file.";
        return;
      }
      if (!jobDesc || jobDesc.length < 10) {
        if (errEl) errEl.textContent = "Please provide a valid Job Description.";
        return;
      }

      btn.disabled = true;
      btn.innerHTML = `<span class="loading-spinner"></span> Extracting Skills & Analyzing Match...`;

      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("job_description", jobDesc);
        formData.append("job_title", jobTitle);

        const analysis = await API.postFormData("/api/resume-analysis/analyze", formData);
        showToast("Resume & Job Description Analysis Completed!", "success");

        renderSkillMatchReport(analysis);
        btn.disabled = false;
        btn.innerHTML = "🔍 Re-analyze Resume & Job Description";

      } catch (err) {
        btn.disabled = false;
        btn.innerHTML = "🔍 Analyze Skill Match & Prepare Interview →";
        if (errEl) errEl.textContent = err.message;
        showToast(err.message, "error");
      }
    });
  }

  // Render Skill Match Intelligence Report
  function renderSkillMatchReport(analysis) {
    const reportCard = document.getElementById("skill-match-report");
    const pctVal = document.getElementById("match-pct-value");
    const summaryText = document.getElementById("match-summary-text");
    const activeAnalysisId = document.getElementById("active_analysis_id");

    const matchedContainer = document.getElementById("pill-matched-container");
    const missingContainer = document.getElementById("pill-missing-container");
    const priorityContainer = document.getElementById("pill-priority-container");

    if (!reportCard) return;

    activeAnalysisId.value = analysis.id;
    pctVal.textContent = `${Math.round(analysis.match_percentage)}%`;
    summaryText.textContent = analysis.analysis_summary || "Personalized match profile generated based on your resume and job requirements.";

    // Render Pills
    matchedContainer.innerHTML = (analysis.matched_skills || []).map(s => 
      `<span class="skill-pill skill-pill-matched">✓ ${s}</span>`
    ).join("") || `<span class="text-muted" style="font-size:0.8rem;">No exact overlaps</span>`;

    missingContainer.innerHTML = (analysis.missing_skills || []).map(s => 
      `<span class="skill-pill skill-pill-missing">⚠ ${s}</span>`
    ).join("") || `<span class="text-muted" style="font-size:0.8rem;">None (Full match)</span>`;

    priorityContainer.innerHTML = (analysis.priority_skills || []).map(s => 
      `<span class="skill-pill skill-pill-priority">🎯 ${s}</span>`
    ).join("") || `<span class="text-muted" style="font-size:0.8rem;">Core Role Skills</span>`;

    reportCard.style.display = "block";
    reportCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Start Personalized Interview Submission
  const startPersonalizedForm = document.getElementById("start-personalized-form");
  if (startPersonalizedForm) {
    startPersonalizedForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = document.getElementById("btn-start-personalized");
      const analysisId = document.getElementById("active_analysis_id").value;
      const jobTitle = document.getElementById("resume_job_title").value.trim() || "Software Developer";

      const payload = {
        interview_type: document.getElementById("p_interview_type").value,
        target_role: jobTitle,
        experience_level: "Intermediate",
        topic: jobTitle,
        difficulty: document.getElementById("p_difficulty").value,
        num_questions: parseInt(document.getElementById("p_num_questions").value, 10),
        resume_analysis_id: analysisId || null
      };

      btn.disabled = true;
      btn.innerHTML = `<span class="loading-spinner"></span> Personalizing AI Questions...`;

      try {
        const interview = await API.post("/api/interviews/start", payload);
        showToast("Personalized Interview Created!", "success");
        setTimeout(() => {
          window.location.href = `interview.html?id=${interview.id}`;
        }, 800);
      } catch (err) {
        btn.disabled = false;
        btn.innerHTML = "🚀 Start Personalized AI Interview →";
        showToast(err.message, "error");
      }
    });
  }

  // Standard Config Form Submission
  const standardForm = document.getElementById("interview-config-form");
  if (standardForm) {
    standardForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = standardForm.querySelector("button[type='submit']");
      const errEl = document.getElementById("config-error");
      if (errEl) errEl.textContent = "";

      const payload = {
        interview_type: document.getElementById("interview_type").value,
        target_role: document.getElementById("target_role").value,
        experience_level: document.getElementById("experience_level").value,
        topic: document.getElementById("topic").value,
        difficulty: document.getElementById("difficulty").value,
        num_questions: parseInt(document.getElementById("num_questions").value, 10)
      };

      btn.disabled = true;
      btn.innerHTML = `<span class="loading-spinner"></span> Generating AI Questions...`;

      try {
        const interview = await API.post("/api/interviews/start", payload);
        showToast("Interview created! Loading questions...", "success");
        setTimeout(() => {
          window.location.href = `interview.html?id=${interview.id}`;
        }, 800);
      } catch (err) {
        btn.disabled = false;
        btn.innerHTML = "Start Standard Interview →";
        if (errEl) errEl.textContent = err.message;
        showToast(err.message, "error");
      }
    });
  }
});
