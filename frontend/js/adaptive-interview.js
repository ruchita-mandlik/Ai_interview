/* Advanced Adaptive AI Interview Controller - Real-Time Dynamic Intelligence */

let currentInterview = null;
let currentQuestion = null;
let pendingNextQuestion = null;
let isInterviewCompleted = false;
let timerInterval = null;
let secondsRemaining = 1200; // 20 mins default
let accumulatedGaps = [];

// Helper functions for chip buttons & form synchronization
function applyRoleChip(value, el) {
  const input = document.getElementById("target_role");
  if (input) {
    input.value = value;
    input.classList.remove("is-invalid");
    input.focus();
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }
  const chips = document.querySelectorAll("#role-chips .chip-btn");
  chips.forEach(c => c.classList.remove("selected", "active"));
  if (el) {
    el.classList.add("selected", "active");
  }
}

function applySeniorityChip(value, el) {
  const input = document.getElementById("experience_level");
  if (input) {
    input.value = value;
    input.classList.remove("is-invalid");
    input.focus();
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }
  const chips = document.querySelectorAll("#seniority-chips .chip-btn");
  chips.forEach(c => c.classList.remove("selected", "active"));
  if (el) {
    el.classList.add("selected", "active");
  }
}

function toggleTechChip(skillName, el) {
  const input = document.getElementById("skills_input");
  if (!input) return;

  const currentRaw = input.value.trim();
  let currentList = currentRaw
    ? currentRaw.split(",").map(s => s.trim()).filter(Boolean)
    : [];

  const cleanSkill = skillName.replace(/^\+\s*/, "").trim();
  const lowerTarget = cleanSkill.toLowerCase();
  const existingIdx = currentList.findIndex(s => s.toLowerCase() === lowerTarget);

  if (existingIdx >= 0) {
    // Already present: toggle off (remove without duplicates)
    currentList.splice(existingIdx, 1);
    if (el) el.classList.remove("selected", "active");
  } else {
    // Not present: append skill
    currentList.push(cleanSkill);
    if (el) el.classList.add("selected", "active");
  }

  input.value = currentList.join(", ");
  input.focus();
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function applyChip(fieldId, value) {
  const input = document.getElementById(fieldId);
  if (input) {
    input.value = value;
    input.classList.remove("is-invalid");
    input.focus();
    input.dispatchEvent(new Event("input", { bubbles: true }));
    if (fieldId === "target_role") syncRoleChips();
    if (fieldId === "experience_level") syncSeniorityChips();
  }
}

function appendSkill(skillName) {
  toggleTechChip(skillName);
}

function syncRoleChips() {
  const input = document.getElementById("target_role");
  if (!input) return;
  const currentVal = input.value.trim().toLowerCase();
  const chips = document.querySelectorAll("#role-chips .chip-btn");
  chips.forEach(chip => {
    const chipText = chip.textContent.trim().toLowerCase();
    if (currentVal && (chipText === currentVal || currentVal.includes(chipText))) {
      chip.classList.add("selected", "active");
    } else {
      chip.classList.remove("selected", "active");
    }
  });
}

function syncSeniorityChips() {
  const input = document.getElementById("experience_level");
  if (!input) return;
  const currentVal = input.value.trim().toLowerCase();
  const chips = document.querySelectorAll("#seniority-chips .chip-btn");
  chips.forEach(chip => {
    const chipText = chip.textContent.trim().toLowerCase();
    const cleanVal = currentVal.replace(/[^a-z0-9]/g, "");
    const cleanChip = chipText.replace(/[^a-z0-9]/g, "");
    if (cleanVal && (cleanVal === cleanChip || cleanVal.includes(cleanChip) || cleanChip.includes(cleanVal))) {
      chip.classList.add("selected", "active");
    } else {
      chip.classList.remove("selected", "active");
    }
  });
}

function syncTechChips() {
  const input = document.getElementById("skills_input");
  if (!input) return;
  const currentRaw = input.value.trim();
  const currentList = currentRaw
    ? currentRaw.split(",").map(s => s.trim().toLowerCase()).filter(Boolean)
    : [];

  const chips = document.querySelectorAll("#tech-chips .chip-btn");
  chips.forEach(chip => {
    const cleanChipText = chip.textContent.replace(/^\+\s*/, "").trim().toLowerCase();
    if (currentList.some(s => s === cleanChipText || cleanChipText.includes(s) || s.includes(cleanChipText))) {
      chip.classList.add("selected", "active");
    } else {
      chip.classList.remove("selected", "active");
    }
  });
}

function selectQuestionLimit(num) {
  const hiddenInput = document.getElementById("num_questions");
  if (hiddenInput) hiddenInput.value = num;

  [3, 5, 7].forEach(n => {
    const btn = document.getElementById(`q-limit-${n}`);
    if (btn) {
      if (n === num) {
        btn.classList.add("selected", "active");
      } else {
        btn.classList.remove("selected", "active");
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  if (typeof requireAuth === "function") {
    requireAuth();
  }

  // Populate sidebar user info
  try {
    const user = API.getUser();
    if (user) {
      const avatarEl = document.getElementById("sidebar-avatar");
      const nameEl = document.getElementById("sidebar-user-name");
      const roleEl = document.getElementById("sidebar-user-role");
      if (nameEl) nameEl.textContent = user.name || user.email || "Candidate";
      if (avatarEl) avatarEl.textContent = (user.name ? user.name[0] : "A").toUpperCase();
      if (roleEl && user.target_role) roleEl.textContent = user.target_role;
    }
  } catch (e) {
    console.debug("User info load skipped", e);
  }

  // Check URL params
  const urlParams = new URLSearchParams(window.location.search);
  const interviewId = urlParams.get("id");

  if (interviewId) {
    await loadExistingSession(interviewId);
  } else {
    // Show configuration view
    document.getElementById("adaptive-config-view").style.display = "block";
    document.getElementById("adaptive-session-view").style.display = "none";
    document.getElementById("adaptive-report-view").style.display = "none";
  }

  setupConfigForm();
  setupSessionControls();
});

let isSubmittingAdaptive = false;

// Setup Config Form Submission
function setupConfigForm() {
  const form = document.getElementById("adaptive-interview-form");
  if (!form) return;

  const roleInput = document.getElementById("target_role");
  const expInput = document.getElementById("experience_level");
  const skillsInput = document.getElementById("skills_input");

  if (roleInput) {
    roleInput.addEventListener("input", () => {
      roleInput.classList.remove("is-invalid");
      syncRoleChips();
    });
  }
  if (expInput) {
    expInput.addEventListener("input", () => {
      expInput.classList.remove("is-invalid");
      syncSeniorityChips();
    });
  }
  if (skillsInput) {
    skillsInput.addEventListener("input", () => {
      syncTechChips();
    });
  }

  // Initial chip sync
  syncRoleChips();
  syncSeniorityChips();
  syncTechChips();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (isSubmittingAdaptive) {
      console.warn("Adaptive interview launch already in progress.");
      return;
    }

    const targetRole = document.getElementById("target_role")?.value?.trim();
    const experienceLevel = document.getElementById("experience_level")?.value?.trim();
    const skillsRaw = document.getElementById("skills_input")?.value?.trim() || "";
    const jobDescription = document.getElementById("job_description")?.value?.trim() || "";
    const difficulty = document.getElementById("difficulty")?.value || "Medium";
    const numQuestions = parseInt(document.getElementById("num_questions")?.value || "5", 10);

    const errorBanner = document.getElementById("adaptive-error-banner");
    if (errorBanner) errorBanner.style.display = "none";

    // Required field validation
    if (!targetRole) {
      if (roleInput) {
        roleInput.classList.add("is-invalid");
        roleInput.focus();
      }
      showToast("Please enter or select a Target Role.", "error");
      return;
    }

    if (!experienceLevel) {
      if (expInput) {
        expInput.classList.add("is-invalid");
        expInput.focus();
      }
      showToast("Please enter or select a Target Seniority.", "error");
      return;
    }

    const skillsList = skillsRaw
      ? skillsRaw.split(",").map(s => s.trim()).filter(Boolean)
      : [targetRole];

    const launchBtn = document.getElementById("btn-launch-adaptive");

    isSubmittingAdaptive = true;
    if (launchBtn) {
      launchBtn.disabled = true;
      launchBtn.innerHTML = `
        <div style="display:inline-block; width:18px; height:18px; border:2px solid #fff; border-top-color:transparent; border-radius:50%; animation:spin 0.8s linear infinite;"></div>
        <span>Initializing Gemini AI Adaptive Engine...</span>
      `;
    }

    const payload = {
      target_role: targetRole,
      role: targetRole,
      experience_level: experienceLevel,
      topic: skillsList[0] || targetRole,
      topics: skillsList,
      skills: skillsList,
      job_description: jobDescription || null,
      interview_type: "Adaptive AI",
      difficulty: difficulty,
      num_questions: numQuestions,
      total_questions: numQuestions,
      is_adaptive: true,
      mode: "adaptive"
    };

    try {
      const interview = await API.post("/api/interviews/adaptive/start", payload);

      if (!interview || !interview.id) {
        throw new Error("Server did not return a valid interview ID.");
      }

      showToast("Adaptive AI Interview Initialized!", "success");

      // Update URL without full page reload
      window.history.pushState({}, "", `adaptive-interview.html?id=${interview.id}`);
      await loadExistingSession(interview.id);

    } catch (err) {
      console.error("Failed to launch adaptive interview:", err);
      if (launchBtn) {
        launchBtn.disabled = false;
        launchBtn.innerHTML = `<span>🧠 Launch Adaptive AI Interview Session →</span>`;
      }
      if (errorBanner) {
        errorBanner.innerHTML = `
          <strong>Failed to start Adaptive AI Interview:</strong> ${err.message || "An unexpected error occurred."}<br>
          <span style="font-size:0.85rem; font-weight:400; color:#B91C1C;">
            Please verify network connectivity and ensure valid Gemini API credentials.
          </span>
        `;
        errorBanner.style.display = "block";
        errorBanner.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      showToast(err.message || "Failed to start interview", "error");
    } finally {
      isSubmittingAdaptive = false;
    }
  });
}

// Load and Render Active Session
async function loadExistingSession(interviewId) {
  const configView = document.getElementById("adaptive-config-view");
  const sessionView = document.getElementById("adaptive-session-view");
  const reportView = document.getElementById("adaptive-report-view");
  const errorBanner = document.getElementById("adaptive-error-banner");

  try {
    currentInterview = await API.get(`/api/interviews/${interviewId}`);

    if (!currentInterview || !currentInterview.id) {
      throw new Error("Interview session not found.");
    }

    if (currentInterview.status === "completed") {
      // Show Final Report View
      configView.style.display = "none";
      sessionView.style.display = "none";
      reportView.style.display = "block";
      await renderFinalReport(currentInterview);
      return;
    }

    // Show Session View
    configView.style.display = "none";
    sessionView.style.display = "block";
    reportView.style.display = "none";

    // Populate HUD
    const roleText = currentInterview.target_role || currentInterview.role || "Software Engineer";
    const hudRole = document.getElementById("hud-role");
    if (hudRole) hudRole.textContent = roleText;

    const diff = currentInterview.current_difficulty || currentInterview.difficulty || "Medium";
    updateDifficultyHUD(diff);

    // Identify active question
    const questions = currentInterview.questions || [];
    const completedCount = currentInterview.completed_questions || 0;
    
    // Pick the latest unanswered question
    currentQuestion = questions[questions.length - 1] || null;
    if (!currentQuestion && questions.length > 0) {
      currentQuestion = questions[0];
    }

    const totalQ = currentInterview.num_questions || 5;
    const currentQNum = currentQuestion ? currentQuestion.question_number : (completedCount + 1);
    const hudProg = document.getElementById("hud-progress");
    if (hudProg) hudProg.textContent = `Question ${currentQNum} of ${totalQ}`;

    // Timer
    secondsRemaining = (currentInterview.duration_minutes || 25) * 60;
    startTimer();

    // Render Question & Action details
    renderQuestionDetails(currentQuestion);

    // Render Knowledge Gaps
    if (currentInterview.knowledge_gaps) {
      accumulatedGaps = Array.isArray(currentInterview.knowledge_gaps)
        ? currentInterview.knowledge_gaps
        : [];
      renderKnowledgeGaps(accumulatedGaps);
    }

  } catch (err) {
    console.error("Session load failed:", err);
    if (errorBanner) {
      errorBanner.innerHTML = `
        <strong>Error loading interview session:</strong> ${err.message}<br>
        <a href="adaptive-interview.html" style="color:#B91C1C; text-decoration:underline; font-size:0.85rem; margin-top:4px; display:inline-block;">Return to Adaptive Setup</a>
      `;
      errorBanner.style.display = "block";
    }
  }
}

// Update Difficulty Badge in HUD
function updateDifficultyHUD(diff) {
  const badge = document.getElementById("hud-difficulty-badge");
  if (!badge) return;

  const d = (diff || "Medium").toUpperCase();
  badge.textContent = d;
  badge.className = "diff-pill";

  if (d === "EASY") {
    badge.classList.add("diff-easy");
  } else if (d === "HARD") {
    badge.classList.add("diff-hard");
  } else {
    badge.classList.add("diff-medium");
  }
}

// Render Active Question Details
function renderQuestionDetails(q) {
  if (!q) return;

  const textEl = document.getElementById("current-question-text");
  if (textEl) textEl.textContent = q.question_text || q.question || "Formulating technical question...";

  const catChip = document.getElementById("q-category-chip");
  if (catChip) catChip.textContent = q.category || q.skill || currentInterview?.topic || "Technical";

  const objEl = document.getElementById("q-objective");
  if (objEl) {
    objEl.textContent = q.assessment_objective || `Evaluating ${q.skill || 'candidate reasoning'}`;
  }

  // Update Action Intent Banner
  const actionHeader = document.getElementById("action-heading");
  const actionText = document.getElementById("action-rationale");
  const actionIcon = document.getElementById("action-icon");

  const action = (q.adaptive_action || "NEXT_TOPIC").toUpperCase();
  const rationale = q.adaptation_reason || "Adaptive question formulated based on target role requirements.";

  if (actionHeader && actionText) {
    actionText.textContent = rationale;

    if (action.includes("CHALLENG")) {
      actionHeader.textContent = "⚔️ CHALLENGING REASONING & EDGE CASES";
      if (actionIcon) actionIcon.textContent = "⚔️";
    } else if (action.includes("FOLLOW")) {
      actionHeader.textContent = "🔍 TARGETED DEEP-DIVE PROBE";
      if (actionIcon) actionIcon.textContent = "🔍";
    } else if (action.includes("INCREASE") || action.includes("HARD")) {
      actionHeader.textContent = "📈 ESCALATING ARCHITECTURAL COMPLEXITY";
      if (actionIcon) actionIcon.textContent = "📈";
    } else if (action.includes("SIMPLIF") || action.includes("EASY")) {
      actionHeader.textContent = "📉 FOUNDATIONAL REINFORCEMENT";
      if (actionIcon) actionIcon.textContent = "📉";
    } else if (action.includes("CLARIF")) {
      actionHeader.textContent = "❓ CLARIFYING CANDIDATE REASONING";
      if (actionIcon) actionIcon.textContent = "❓";
    } else if (action.includes("REVISIT") || action.includes("WEAKNESS")) {
      actionHeader.textContent = "🔄 REASSESSING PRIOR KNOWLEDGE GAP";
      if (actionIcon) actionIcon.textContent = "🔄";
    } else {
      actionHeader.textContent = "🎯 STRATEGIC TOPIC PROGRESSION";
      if (actionIcon) actionIcon.textContent = "🎯";
    }
  }

  // Reset answer input and hide evaluation card
  const input = document.getElementById("candidate-answer-input");
  if (input) {
    input.value = "";
    input.disabled = false;
  }
  const wordCount = document.getElementById("word-count-badge");
  if (wordCount) wordCount.textContent = "0 words";

  const evalCard = document.getElementById("evaluation-result-card");
  if (evalCard) evalCard.style.display = "none";

  const hintBox = document.getElementById("hint-display-box");
  if (hintBox) hintBox.style.display = "none";

  const submitBtn = document.getElementById("btn-submit-answer");
  if (submitBtn) {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<span>Submit Answer for AI Evaluation →</span>`;
  }
}

// Render Knowledge Gaps
function renderKnowledgeGaps(gaps) {
  const drawer = document.getElementById("gaps-drawer");
  const list = document.getElementById("gaps-list");
  if (!drawer || !list) return;

  if (!gaps || gaps.length === 0) {
    drawer.style.display = "none";
    return;
  }

  drawer.style.display = "block";
  list.innerHTML = gaps.map(g => `
    <span class="gap-pill">
      <span>⚠️</span>
      <span>${escapeHTML(g)}</span>
    </span>
  `).join("");
}

// Setup In-Session Interactive Controls
function setupSessionControls() {
  // Word count listener
  const answerInput = document.getElementById("candidate-answer-input");
  if (answerInput) {
    answerInput.addEventListener("input", () => {
      const text = answerInput.value.trim();
      const count = text ? text.split(/\s+/).length : 0;
      const badge = document.getElementById("word-count-badge");
      if (badge) badge.textContent = `${count} word${count === 1 ? '' : 's'}`;
    });
  }

  // Submit Answer
  const submitBtn = document.getElementById("btn-submit-answer");
  if (submitBtn) {
    submitBtn.addEventListener("click", async () => {
      const answerText = answerInput?.value?.trim();
      if (!answerText) {
        showToast("Please enter your answer before submitting.", "warning");
        return;
      }
      if (!currentInterview || !currentQuestion) return;

      submitBtn.disabled = true;
      submitBtn.innerHTML = `
        <div style="display:inline-block; width:16px; height:16px; border:2px solid #fff; border-top-color:transparent; border-radius:50%; animation:spin 0.8s linear infinite;"></div>
        <span>Evaluating with Gemini AI...</span>
      `;

      try {
        const res = await API.post(
          `/api/interviews/${currentInterview.id}/answer?question_id=${currentQuestion.id}`,
          { answer: answerText }
        );

        if (!res) throw new Error("No evaluation response received from server.");

        // Render evaluation result card
        renderEvaluationResult(res);

      } catch (err) {
        console.error("Evaluation submission failed:", err);
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>Submit Answer for AI Evaluation →</span>`;
        showToast(err.message || "Evaluation failed. Please retry.", "error");
      }
    });
  }

  // Proceed to Next / Follow-Up Challenge
  const proceedBtn = document.getElementById("btn-proceed-adaptive");
  if (proceedBtn) {
    proceedBtn.addEventListener("click", async () => {
      if (isInterviewCompleted) {
        // Show report view
        document.getElementById("adaptive-session-view").style.display = "none";
        document.getElementById("adaptive-report-view").style.display = "block";
        await renderFinalReport(currentInterview?.id);
        return;
      }

      if (pendingNextQuestion) {
        currentQuestion = pendingNextQuestion;
        pendingNextQuestion = null;

        const totalQ = currentInterview?.num_questions || 5;
        const hudProg = document.getElementById("hud-progress");
        if (hudProg) hudProg.textContent = `Question ${currentQuestion.question_number} of ${totalQ}`;

        renderQuestionDetails(currentQuestion);
        window.scrollTo({ top: 120, behavior: "smooth" });
      } else {
        // Reload session to sync state
        loadExistingSession(currentInterview.id);
      }
    });
  }

  // Clarification / Hint Button
  const hintBtn = document.getElementById("btn-ask-hint");
  if (hintBtn) {
    hintBtn.addEventListener("click", async () => {
      if (!currentInterview || !currentQuestion) return;
      const hintBox = document.getElementById("hint-display-box");
      if (hintBox) {
        hintBox.style.display = "block";
        hintBox.innerHTML = `<em>Consulting AI interviewer for clarifying directives...</em>`;
      }

      try {
        const res = await API.post(`/api/interviews/${currentInterview.id}/clarify`, {
          question_id: currentQuestion.id,
          query: "Please provide scope clarification, key trade-offs to address, and a diagnostic hint."
        });

        if (hintBox) {
          hintBox.innerHTML = `
            <strong>Interviewer Clarification:</strong> ${escapeHTML(res.clarification || "Address the core architectural trade-offs.")}<br>
            ${res.hint ? `<span style="display:inline-block; margin-top:6px; color:#1D4ED8;">💡 <strong>Guiding Hint:</strong> ${escapeHTML(res.hint)}</span>` : ""}
          `;
        }
      } catch (err) {
        if (hintBox) hintBox.innerHTML = `<span style="color:#DC2626;">Clarification temporarily unavailable.</span>`;
      }
    });
  }

  // Skip Question
  const skipBtn = document.getElementById("btn-skip-q");
  if (skipBtn) {
    skipBtn.addEventListener("click", async () => {
      if (!currentInterview || !currentQuestion) return;
      if (!confirm("Are you sure you want to pass on this question? The AI will adaptively recalibrate.")) return;

      try {
        const res = await API.post(`/api/interviews/${currentInterview.id}/next?question_id=${currentQuestion.id}`);
        if (res.interview_completed || res.status === "completed") {
          isInterviewCompleted = true;
          if (res.total_score !== undefined && currentInterview) {
            currentInterview.total_score = res.total_score;
          }
          document.getElementById("adaptive-session-view").style.display = "none";
          document.getElementById("adaptive-report-view").style.display = "block";
          await renderFinalReport(currentInterview?.id);
        } else if (res.next_question) {
          currentQuestion = res.next_question;
          renderQuestionDetails(currentQuestion);
          showToast("Question skipped. Adaptive focus recalibrated.", "info");
        }
      } catch (err) {
        showToast("Failed to skip question.", "error");
      }
    });
  }

  // End Interview Now
  const endBtn = document.getElementById("btn-end-interview");
  if (endBtn) {
    endBtn.addEventListener("click", async () => {
      if (!confirm("Conclude this adaptive interview session and generate your final diagnostic evaluation report?")) return;
      try {
        const res = await API.post(`/api/interviews/${currentInterview.id}/complete`);
        isInterviewCompleted = true;
        if (res && res.total_score !== undefined && currentInterview) {
          currentInterview.total_score = res.total_score;
        }
        document.getElementById("adaptive-session-view").style.display = "none";
        document.getElementById("adaptive-report-view").style.display = "block";
        await renderFinalReport(currentInterview?.id);
      } catch (err) {
        showToast("Failed to finalize interview.", "error");
      }
    });
  }
}

// Render Evaluation Card
function renderEvaluationResult(res) {
  const card = document.getElementById("evaluation-result-card");
  if (!card) return;

  card.style.display = "block";
  card.scrollIntoView({ behavior: "smooth", block: "start" });

  const overall = Math.round(res.overall_score || (res.evaluation ? res.evaluation.score : 0) || 0);
  const scoreEl = document.getElementById("eval-score-display");
  if (scoreEl) scoreEl.textContent = `${overall}%`;

  // Update bars
  const tech = Math.round(res.technical_correctness || (res.evaluation ? res.evaluation.correctness : overall) || overall);
  const comp = Math.round(res.conceptual_completeness || (res.evaluation ? res.evaluation.completeness : overall) || overall);
  const clar = Math.round(res.structural_clarity || (res.evaluation ? res.evaluation.clarity : overall) || overall);
  const depth = Math.round(res.depth_of_understanding || (res.evaluation ? res.evaluation.technical_depth : overall) || overall);

  setMeter("bar-correctness", "val-correctness", tech);
  setMeter("bar-completeness", "val-completeness", comp);
  setMeter("bar-clarity", "val-clarity", clar);
  setMeter("bar-depth", "val-depth", depth);

  // Strengths
  const strengths = res.strengths || (res.evaluation ? res.evaluation.strengths : []) || [];
  const strengthsEl = document.getElementById("eval-strengths-list");
  if (strengthsEl) {
    strengthsEl.innerHTML = strengths.length > 0
      ? strengths.map(s => `<li>${escapeHTML(s)}</li>`).join("")
      : `<li>Demonstrated baseline engagement with problem context.</li>`;
  }

  // Improvements / Missing Concepts
  const missing = res.missing_concepts || res.improvements || (res.evaluation ? res.evaluation.weaknesses : []) || [];
  const improvementsEl = document.getElementById("eval-improvements-list");
  if (improvementsEl) {
    improvementsEl.innerHTML = missing.length > 0
      ? missing.map(m => `<li>${escapeHTML(m)}</li>`).join("")
      : `<li>No critical technical omissions detected.</li>`;
  }

  // Model Answer
  const modelEl = document.getElementById("eval-model-answer");
  if (modelEl) {
    modelEl.textContent = res.model_answer || (res.evaluation ? res.evaluation.ideal_answer : "") || "Demonstrate concrete trade-offs and edge-case handling.";
  }

  // Check Knowledge Gaps from response
  if (res.knowledge_gaps && Array.isArray(res.knowledge_gaps)) {
    accumulatedGaps = res.knowledge_gaps;
    renderKnowledgeGaps(accumulatedGaps);
  }

  // Update HUD difficulty if modified
  if (res.current_difficulty) {
    updateDifficultyHUD(res.current_difficulty);
  }

  // Store Next Question / Terminal state
  const isLast = Boolean(res.is_last_question || res.interview_completed);
  isInterviewCompleted = isLast;

  if (res.total_score !== undefined && res.total_score !== null) {
    if (currentInterview) {
      currentInterview.total_score = res.total_score;
      currentInterview.status = "completed";
    }
  }

  const nextActionPreview = document.getElementById("next-action-preview-text");
  const proceedBtn = document.getElementById("btn-proceed-adaptive");

  if (isLast) {
    if (nextActionPreview) nextActionPreview.textContent = "Interview Completed: Ready for Final Report";
    if (proceedBtn) proceedBtn.innerHTML = `<span>View Final Diagnostic Report →</span>`;
    pendingNextQuestion = null;
  } else {
    const nextQ = res.next_question || res.follow_up_question;
    pendingNextQuestion = nextQ;
    const nextAct = (res.adaptive_action || "NEXT_TOPIC").replace(/_/g, " ");
    if (nextActionPreview) nextActionPreview.textContent = `Adaptive Decision: ${nextAct}`;
    if (proceedBtn) proceedBtn.innerHTML = `<span>Proceed to AI Follow-Up Challenge →</span>`;
  }
}

function setMeter(barId, valId, score) {
  const bar = document.getElementById(barId);
  const val = document.getElementById(valId);
  if (bar) bar.style.width = `${Math.min(100, Math.max(0, score))}%`;
  if (val) val.textContent = `${score}%`;
}

// Render Final Report View
async function renderFinalReport(interviewOrId) {
  let interview = typeof interviewOrId === "object" && interviewOrId !== null ? interviewOrId : null;
  const interviewId = interview ? interview.id : interviewOrId;

  // Always fetch latest session data from backend to ensure synchronized database state
  if (interviewId) {
    try {
      const refreshed = await API.get(`/api/interviews/${interviewId}`);
      if (refreshed && refreshed.id) {
        interview = refreshed;
        currentInterview = refreshed;
      }
    } catch (err) {
      console.warn("Could not fetch refreshed interview for final report:", err);
    }
  }

  if (!interview) {
    interview = currentInterview || { id: interviewId, total_score: 0, num_questions: 5 };
  }

  const totalQEl = document.getElementById("final-total-q");
  if (totalQEl) totalQEl.textContent = interview.num_questions || 5;

  const rawScore = interview.total_score != null ? interview.total_score : (interview.overall_score != null ? interview.overall_score : 0);
  const score = Math.round(rawScore);
  const scoreVal = document.getElementById("final-score-val");
  if (scoreVal) scoreVal.textContent = `${score}%`;

  const metaEl = document.getElementById("final-summary-meta");
  if (metaEl) {
    if (score >= 80) {
      metaEl.textContent = "Senior / Staff Technical Bar Surpassed";
      metaEl.style.color = "#10B981";
    } else if (score >= 60) {
      metaEl.textContent = "Competent Foundations — Targeted Growth Areas Identified";
      metaEl.style.color = "#F59E0B";
    } else {
      metaEl.textContent = "Foundational Knowledge Gaps Requiring Focused Preparation";
      metaEl.style.color = "#EF4444";
    }
  }

  const analysisBtn = document.getElementById("btn-view-deep-analysis");
  if (analysisBtn && interview.id) {
    analysisBtn.href = `analysis.html?id=${interview.id}`;
  }

  const roadmapBtn = document.getElementById("btn-view-roadmap");
  if (roadmapBtn && interview.id) {
    roadmapBtn.href = `roadmap.html?id=${interview.id}`;
  }
}

// Timer countdown
function startTimer() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    if (secondsRemaining <= 0) {
      clearInterval(timerInterval);
      return;
    }
    secondsRemaining--;
    const mins = Math.floor(secondsRemaining / 60);
    const secs = secondsRemaining % 60;
    const timerEl = document.getElementById("hud-timer");
    if (timerEl) {
      timerEl.textContent = `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    }
  }, 1000);
}

function escapeHTML(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
