/* Live Conversational AI Interview Controller - ChatGPT-Grade UX */

let currentInterview = null;
let activeQuestionIndex = 0;
let timerInterval = null;
let secondsRemaining = 1200; // 20 mins default
let isSubmitting = false;

document.addEventListener("DOMContentLoaded", async () => {
  if (typeof requireAuth === "function") {
    requireAuth();
  }

  const urlParams = new URLSearchParams(window.location.search);
  const interviewId = urlParams.get("id");

  if (!interviewId) {
    showToast("No interview ID provided. Redirecting to configurator...", "error");
    setTimeout(() => {
      window.location.href = "interview-config.html";
    }, 1200);
    return;
  }

  // Populate sidebar user details
  try {
    const user = API.getUser();
    if (user) {
      const avatarEl = document.getElementById("sidebar-user-avatar");
      const nameEl = document.getElementById("sidebar-user-name");
      if (nameEl) nameEl.textContent = user.name || user.email || "Candidate";
      if (avatarEl) avatarEl.textContent = (user.name ? user.name[0] : "U").toUpperCase();
    }
  } catch (e) {
    console.debug("User info load skipped", e);
  }

  // Mobile sidebar toggle handler
  const toggleBtn = document.getElementById("mobile-toggle-btn");
  const sidebar = document.getElementById("chat-sidebar");
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("open");
    });
  }

  await initializeInterviewSession(interviewId);
  setupComposerEvents();
  setupSidebarControls();
});

// Load interview data and render initial chat state
async function initializeInterviewSession(interviewId) {
  try {
    currentInterview = await API.get(`/api/interviews/${interviewId}`);

    if (!currentInterview || !currentInterview.id) {
      throw new Error("Interview not found or inaccessible.");
    }

    // Populate Sidebar & Topbar Metadata
    const roleText = currentInterview.target_role || currentInterview.role || "Software Engineer";
    const typeText = currentInterview.interview_type || "Technical";
    const diffText = currentInterview.difficulty || "Medium";
    const qCount = currentInterview.num_questions || (currentInterview.questions ? currentInterview.questions.length : 5);

    const sessionRoleEl = document.getElementById("session-role");
    if (sessionRoleEl) sessionRoleEl.textContent = roleText;

    const topbarTitleEl = document.getElementById("topbar-role-title");
    if (topbarTitleEl) topbarTitleEl.textContent = `${roleText} Interview`;

    const typeChip = document.getElementById("session-type-chip");
    if (typeChip) typeChip.textContent = typeText;

    const diffChip = document.getElementById("session-diff-chip");
    if (diffChip) diffChip.textContent = diffText;

    const qCountChip = document.getElementById("session-qcount-chip");
    if (qCountChip) qCountChip.textContent = `${qCount} Questions`;

    // Initialize Timer
    secondsRemaining = (currentInterview.duration_minutes || 25) * 60;
    startTimer();

    // Check if interview is already completed
    if (currentInterview.status === "completed") {
      renderCompletedInterviewHistory();
      return;
    }

    // Determine starting question index based on completed answers
    const completedCount = currentInterview.completed_questions || 0;
    activeQuestionIndex = completedCount < currentInterview.questions.length ? completedCount : 0;

    // Render Interviewer Welcome Message in Chat Feed
    renderInterviewerWelcome(currentInterview);

    // Render Question #1 (or active question)
    renderActiveQuestion();

    // Update Progress in Topbar
    updateProgressBar();

  } catch (err) {
    console.error("Session load failed:", err);
    showToast(`Failed to load interview: ${err.message}`, "error");
    const feed = document.getElementById("chat-feed");
    if (feed) {
      feed.innerHTML = `
        <div style="background:#FEE2E2; border:1px solid #FCA5A5; color:#991B1B; padding:24px; border-radius:12px; margin:40px auto; max-width:600px; text-align:center;">
          <h3 style="margin-bottom:8px;">⚠️ Failed to Load AI Interview Session</h3>
          <p style="margin-bottom:16px;">${err.message}</p>
          <a href="interview-config.html" class="btn btn-primary" style="display:inline-block; text-decoration:none;">Return to Configurator</a>
        </div>
      `;
    }
  }
}

// Render the AI Interviewer Welcome Card
function renderInterviewerWelcome(interview) {
  const feed = document.getElementById("chat-feed");
  if (!feed) return;

  const defaultIntro = `Hello and welcome! I am your AI Technical Interviewer powered by Gemini 3.8 Flash. Today, we will conduct a structured interview for the **${interview.target_role || "target"}** role, covering practical system implementation, technical depth, and trade-off evaluation. 

Take your time to structure your thoughts, explain edge cases, and share real-world examples. Let's begin!`;

  const introText = interview.interviewer_intro || defaultIntro;

  const introRow = document.createElement("div");
  introRow.className = "chat-message-row ai-row";
  introRow.innerHTML = `
    <div class="chat-avatar ai">🤖</div>
    <div class="chat-bubble ai">
      <div class="chat-bubble-header">
        <span class="chat-sender-name">AI Interviewer</span>
        <span class="chat-sender-role">Gemini 3.8 Flash</span>
      </div>
      <div class="chat-message-text">${escapeHtml(introText)}</div>
    </div>
  `;

  feed.appendChild(introRow);
}

// Render the current question in the conversation feed
function renderActiveQuestion() {
  const feed = document.getElementById("chat-feed");
  if (!feed || !currentInterview || !currentInterview.questions) return;

  const q = currentInterview.questions[activeQuestionIndex];
  if (!q) return;

  const total = currentInterview.num_questions || currentInterview.questions.length;

  const questionRow = document.createElement("div");
  questionRow.className = "chat-message-row ai-row";
  questionRow.id = `chat-question-row-${q.id}`;
  
  let adaptationBadge = "";
  const actionText = q.adaptive_action && q.adaptive_action !== "NEXT_TOPIC" ? q.adaptive_action.replace(/_/g, " ") : "";
  const reasonText = q.decision_rationale || q.adaptation_reason || "";
  const objText = q.assessment_objective ? `<div style="margin-top:3px; font-size:0.78rem; color:#1E3A8A;"><strong>Assessment Objective:</strong> ${escapeHtml(q.assessment_objective)}</div>` : "";

  if (actionText || reasonText) {
    adaptationBadge = `<div style="margin-top:10px; font-size:0.82rem; background:#EFF6FF; border:1px solid #BFDBFE; color:#1E40AF; padding:8px 12px; border-radius:6px; line-height:1.5;">
      <div style="font-weight:700; display:flex; align-items:center; gap:6px; margin-bottom:2px;">
        <span>🎯</span> Adaptive Action: ${escapeHtml(actionText || "Contextual Evolution")}
      </div>
      ${reasonText ? `<div style="color:#1E3A8A; font-size:0.8rem;">${escapeHtml(reasonText)}</div>` : ""}
      ${objText}
    </div>`;
  }

  questionRow.innerHTML = `
    <div class="chat-avatar ai">🤖</div>
    <div class="chat-bubble ai">
      <div class="chat-bubble-header">
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="chat-sender-name">AI Interviewer</span>
          <span style="font-size:0.75rem; background:#EEF2FF; color:#4338CA; font-weight:700; padding:2px 8px; border-radius:4px;">
            Question ${q.question_number} of ${total}
          </span>
          <span style="font-size:0.75rem; background:#F1F5F9; color:#475569; padding:2px 6px; border-radius:4px;">
            ${escapeHtml(q.difficulty || "Medium")}
          </span>
          ${q.category ? `<span style="font-size:0.75rem; color:#64748B;">• ${escapeHtml(q.category)}</span>` : ''}
        </div>
      </div>
      <div class="chat-message-text" style="font-size:1.02rem; font-weight:500; color:#0F172A; margin-top:4px;">
        ${escapeHtml(q.question_text || q.question || "")}
      </div>
      ${adaptationBadge}
      <div id="hint-container-${q.id}"></div>
    </div>
  `;

  feed.appendChild(questionRow);
  scrollToBottom();

  // Restore any draft answer from localStorage
  const textarea = document.getElementById("chat-input");
  if (textarea) {
    const savedDraft = localStorage.getItem(`draft_${currentInterview.id}_${q.id}`);
    textarea.value = savedDraft || "";
    adjustTextareaHeight(textarea);
    updateWordCount(textarea.value);
    textarea.focus();
  }
}

// Setup input composer listeners (Ctrl+Enter, auto-resize, hints)
function setupComposerEvents() {
  const textarea = document.getElementById("chat-input");
  const submitBtn = document.getElementById("btn-submit-answer");
  const clearBtn = document.getElementById("btn-clear-input");
  const hintBtn = document.getElementById("btn-request-hint");

  if (!textarea) return;

  // Auto-resize textarea as user types
  textarea.addEventListener("input", () => {
    adjustTextareaHeight(textarea);
    updateWordCount(textarea.value);
    
    // Save draft
    if (currentInterview && currentInterview.questions && currentInterview.questions[activeQuestionIndex]) {
      const q = currentInterview.questions[activeQuestionIndex];
      localStorage.setItem(`draft_${currentInterview.id}_${q.id}`, textarea.value);
    }
  });

  // Ctrl+Enter or Cmd+Enter to submit
  textarea.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmitAnswer();
    }
  });

  if (submitBtn) {
    submitBtn.addEventListener("click", () => {
      handleSubmitAnswer();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      textarea.value = "";
      adjustTextareaHeight(textarea);
      updateWordCount("");
      if (currentInterview && currentInterview.questions && currentInterview.questions[activeQuestionIndex]) {
        const q = currentInterview.questions[activeQuestionIndex];
        localStorage.removeItem(`draft_${currentInterview.id}_${q.id}`);
      }
      textarea.focus();
    });
  }

  if (hintBtn) {
    hintBtn.addEventListener("click", handleRequestHint);
  }
}

// Setup Sidebar Controls (Hint, Skip, End Session)
function setupSidebarControls() {
  const sideHintBtn = document.getElementById("sidebar-hint-btn");
  if (sideHintBtn) {
    sideHintBtn.addEventListener("click", handleRequestHint);
  }

  const skipBtn = document.getElementById("sidebar-skip-btn");
  if (skipBtn) {
    skipBtn.addEventListener("click", handleSkipQuestion);
  }

  const endBtn = document.getElementById("sidebar-end-btn");
  if (endBtn) {
    endBtn.addEventListener("click", handleEndInterview);
  }
}

// Submit Candidate Answer & Stream AI Evaluation
async function handleSubmitAnswer() {
  if (isSubmitting) return;

  const textarea = document.getElementById("chat-input");
  const submitBtn = document.getElementById("btn-submit-answer");
  const feed = document.getElementById("chat-feed");

  if (!textarea || !feed || !currentInterview || !currentInterview.questions) return;

  const answerText = textarea.value.trim();
  if (!answerText) {
    showToast("Please provide your answer before submitting.", "warning");
    textarea.focus();
    return;
  }

  const q = currentInterview.questions[activeQuestionIndex];
  if (!q) return;

  isSubmitting = true;
  submitBtn.disabled = true;
  textarea.disabled = true;

  // 1. Append User Answer Bubble in Chat
  const userRow = document.createElement("div");
  userRow.className = "chat-message-row user";
  userRow.innerHTML = `
    <div class="chat-avatar user">👤</div>
    <div class="chat-bubble user">
      <div class="chat-bubble-header">
        <span class="chat-sender-name">You (Candidate)</span>
        <span style="font-size:0.75rem; color:#6366F1;">Submitted</span>
      </div>
      <div class="chat-message-text">${escapeHtml(answerText)}</div>
    </div>
  `;
  feed.appendChild(userRow);

  // Clear composer & draft
  textarea.value = "";
  adjustTextareaHeight(textarea);
  updateWordCount("");
  localStorage.removeItem(`draft_${currentInterview.id}_${q.id}`);
  scrollToBottom();

  // 2. Show Typing Indicator Bubble ("AI Interviewer is evaluating...")
  const typingRow = document.createElement("div");
  typingRow.className = "chat-message-row ai-row";
  typingRow.id = "chat-eval-typing-row";
  typingRow.innerHTML = `
    <div class="chat-avatar ai">🤖</div>
    <div class="chat-bubble ai" style="border:none; box-shadow:none; padding:4px 0; background:transparent;">
      <div class="chat-typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <span style="font-size:0.8rem; color:#6366F1; font-weight:600; margin-left:8px;">Evaluating response against 5-dimension rubric...</span>
      </div>
    </div>
  `;
  feed.appendChild(typingRow);
  scrollToBottom();

  try {
    // Send API request to backend
    const evalResult = await API.post(`/api/interviews/${currentInterview.id}/answer`, {
      question_id: q.id,
      answer_text: answerText
    });

    // Remove typing indicator
    const typingEl = document.getElementById("chat-eval-typing-row");
    if (typingEl) typingEl.remove();

    // 3. Render In-Feed Evaluation Card
    renderInlineEvaluationCard(evalResult, q);

    // Append adaptive next question if returned
    if (evalResult.next_question_dict || evalResult.next_question) {
      const nextQ = evalResult.next_question_dict || evalResult.next_question;
      const exists = currentInterview.questions.some(item => item.id === nextQ.id);
      if (!exists) {
        currentInterview.questions.push(nextQ);
      }
    }

    // Update difficulty chip if dynamic adjustment occurred
    if (evalResult.current_difficulty) {
      const diffChip = document.getElementById("session-diff-chip");
      if (diffChip) diffChip.textContent = evalResult.current_difficulty;
    }

    // Check if interview is finished
    const totalQ = currentInterview.num_questions || currentInterview.questions.length;
    const isCompleted = evalResult.is_last_question || (activeQuestionIndex >= totalQ - 1);

    if (isCompleted) {
      renderInterviewCompletionCard();
    } else {
      // Advance to next question
      activeQuestionIndex++;
      updateProgressBar();

      // Render next question after a brief natural cadence
      setTimeout(() => {
        renderActiveQuestion();
      }, 600);
    }

  } catch (err) {
    console.error("Answer submission failed:", err);
    const typingEl = document.getElementById("chat-eval-typing-row");
    if (typingEl) typingEl.remove();

    showToast(`Evaluation failed: ${err.message}`, "error");

    // Render recoverable error message
    const errorRow = document.createElement("div");
    errorRow.className = "chat-message-row ai-row";
    errorRow.innerHTML = `
      <div class="chat-avatar ai" style="background:#EF4444;">⚠️</div>
      <div class="chat-bubble ai" style="border-color:#FCA5A5; background:#FEF2F2;">
        <div class="chat-sender-name" style="color:#B91C1C;">AI Evaluation Error</div>
        <div class="chat-message-text" style="color:#991B1B; font-size:0.9rem;">
          ${escapeHtml(err.message || "An error occurred connecting to the Gemini evaluation service.")}
        </div>
        <button onclick="this.closest('.chat-message-row').remove(); handleSubmitAnswer();" class="chat-action-btn" style="margin-top:10px; width:fit-content; background:#FEE2E2; color:#991B1B;">
          🔄 Retry Evaluation
        </button>
      </div>
    `;
    feed.appendChild(errorRow);
    scrollToBottom();

  } finally {
    isSubmitting = false;
    submitBtn.disabled = false;
    textarea.disabled = false;
    textarea.focus();
  }
}

// Render the 5-Dimension Rubric Card inside chat stream
function renderInlineEvaluationCard(evalResult, question) {
  const feed = document.getElementById("chat-feed");
  if (!feed) return;

  const score10 = evalResult.score_out_of_10 || (Math.round((evalResult.overall_score || 0) / 10.0 * 10) / 10);
  const scorePct = evalResult.overall_score || Math.round(score10 * 10);

  let pillClass = "mid";
  if (scorePct >= 75) pillClass = "high";
  else if (scorePct < 50) pillClass = "low";

  // Strengths list
  let strengthsHTML = "";
  const strengthsArr = Array.isArray(evalResult.strengths) ? evalResult.strengths : [];
  if (strengthsArr.length > 0) {
    strengthsHTML = `
      <div class="chat-eval-box strengths">
        <div style="font-weight:700; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
          <span>✅</span> Key Strengths
        </div>
        <ul style="margin:0; padding-left:18px;">
          ${strengthsArr.map(s => `<li>${escapeHtml(s)}</li>`).join("")}
        </ul>
      </div>
    `;
  }

  // Missing points / improvements
  let improvementsHTML = "";
  const missingArr = Array.isArray(evalResult.missing_concepts) && evalResult.missing_concepts.length > 0
    ? evalResult.missing_concepts
    : (Array.isArray(evalResult.improvements) ? evalResult.improvements : []);

  if (missingArr.length > 0) {
    improvementsHTML = `
      <div class="chat-eval-box missing">
        <div style="font-weight:700; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
          <span>💡</span> Missing Concepts & Opportunities
        </div>
        <ul style="margin:0; padding-left:18px;">
          ${missingArr.map(m => `<li>${escapeHtml(m)}</li>`).join("")}
        </ul>
      </div>
    `;
  }

  // Model answer or feedback
  let modelAnswerHTML = "";
  const modelAnswer = evalResult.model_answer || evalResult.ideal_answer || evalResult.improved_sample_answer;
  if (modelAnswer) {
    modelAnswerHTML = `
      <div class="chat-eval-box model-ans">
        <div style="font-weight:700; margin-bottom:6px; display:flex; align-items:center; gap:6px; color:#4338CA;">
          <span>📘</span> Senior Architectural Benchmark
        </div>
        <div style="font-size:0.85rem; line-height:1.6; color:#334155;">
          ${escapeHtml(modelAnswer)}
        </div>
      </div>
    `;
  }

  const evalRow = document.createElement("div");
  evalRow.className = "chat-message-row ai-row";
  evalRow.innerHTML = `
    <div class="chat-avatar ai" style="background:#4F46E5;">📊</div>
    <div class="chat-bubble ai" style="width:100%; max-width:820px;">
      
      <!-- Header with Score Pill -->
      <div class="chat-eval-header">
        <div>
          <div style="font-size:0.8rem; font-weight:700; text-transform:uppercase; color:#6366F1; letter-spacing:0.05em;">
            AI Rubric Assessment
          </div>
          <div style="font-size:1.05rem; font-weight:700; color:#0F172A;">
            Answer Evaluation — Question ${question.question_number}
          </div>
        </div>
        <div class="chat-score-pill ${pillClass}">
          <span>⭐ ${score10} / 10</span>
          <span style="font-size:0.75rem; font-weight:500; opacity:0.85;">(${scorePct}%)</span>
        </div>
      </div>

      <!-- Rubric Mini Progress Bars -->
      <div class="chat-rubric-grid">
        <div class="chat-rubric-item">
          <div class="chat-rubric-title">
            <span>Correctness</span>
            <strong>${evalResult.technical_correctness || scorePct}%</strong>
          </div>
          <div class="chat-rubric-mini-bar">
            <div class="chat-rubric-mini-fill" style="width:${evalResult.technical_correctness || scorePct}%;"></div>
          </div>
        </div>

        <div class="chat-rubric-item">
          <div class="chat-rubric-title">
            <span>Completeness</span>
            <strong>${evalResult.conceptual_completeness || scorePct}%</strong>
          </div>
          <div class="chat-rubric-mini-bar">
            <div class="chat-rubric-mini-fill" style="width:${evalResult.conceptual_completeness || scorePct}%;"></div>
          </div>
        </div>

        <div class="chat-rubric-item">
          <div class="chat-rubric-title">
            <span>Clarity</span>
            <strong>${evalResult.structural_clarity || scorePct}%</strong>
          </div>
          <div class="chat-rubric-mini-bar">
            <div class="chat-rubric-mini-fill" style="width:${evalResult.structural_clarity || scorePct}%;"></div>
          </div>
        </div>

        <div class="chat-rubric-item">
          <div class="chat-rubric-title">
            <span>Depth</span>
            <strong>${evalResult.depth_of_understanding || scorePct}%</strong>
          </div>
          <div class="chat-rubric-mini-bar">
            <div class="chat-rubric-mini-fill" style="width:${evalResult.depth_of_understanding || scorePct}%;"></div>
          </div>
        </div>
      </div>

      <!-- Adaptive Intelligence Engine Strategy -->
      ${(evalResult.adaptive_action || evalResult.decision_rationale || evalResult.adaptive_decision) ? `
        <div style="background:linear-gradient(135deg, #EEF2FF, #F0FDF4); border:1px solid #C7D2FE; border-radius:8px; padding:12px 14px; margin-bottom:12px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <div style="display:flex; align-items:center; gap:6px; font-weight:700; color:#3730A3; font-size:0.88rem;">
              <span>🧠</span> Adaptive Strategy: ${(evalResult.adaptive_action || (evalResult.adaptive_decision && evalResult.adaptive_decision.action) || "CONTINUE").replace(/_/g, " ")}
            </div>
            ${evalResult.current_difficulty || (evalResult.adaptive_decision && evalResult.adaptive_decision.updated_difficulty) ? `
              <span style="font-size:0.75rem; background:#E0E7FF; color:#3730A3; font-weight:700; padding:2px 8px; border-radius:4px;">
                Difficulty: ${evalResult.current_difficulty || evalResult.adaptive_decision.updated_difficulty}
              </span>
            ` : ''}
          </div>
          ${evalResult.decision_rationale || (evalResult.adaptive_decision && evalResult.adaptive_decision.decision_rationale) ? `
            <div style="font-size:0.84rem; color:#1E293B; margin-bottom:4px; line-height:1.5;">
              <strong>Interviewer Rationale:</strong> ${escapeHtml(evalResult.decision_rationale || evalResult.adaptive_decision.decision_rationale)}
            </div>
          ` : ''}
          ${evalResult.assessment_objective || (evalResult.adaptive_decision && evalResult.adaptive_decision.assessment_objective) ? `
            <div style="font-size:0.8rem; color:#475569;">
              <strong>Assessment Objective:</strong> ${escapeHtml(evalResult.assessment_objective || evalResult.adaptive_decision.assessment_objective)}
            </div>
          ` : ''}
          ${Array.isArray(evalResult.knowledge_gaps) && evalResult.knowledge_gaps.length > 0 ? `
            <div style="margin-top:6px; font-size:0.78rem; color:#DC2626;">
              <strong>Tracked Knowledge Gaps:</strong> ${evalResult.knowledge_gaps.map(g => `<span style="background:#FEE2E2; color:#B91C1C; padding:1px 6px; border-radius:4px; margin-right:4px;">${escapeHtml(g)}</span>`).join('')}
            </div>
          ` : ''}
        </div>
      ` : ''}

      <!-- Actionable Feedback Paragraph -->
      ${evalResult.actionable_feedback || evalResult.feedback ? `
        <div style="font-size:0.92rem; line-height:1.6; color:#334155; margin-bottom:12px; background:#F8FAFC; padding:12px 14px; border-radius:8px; border:1px solid #E2E8F0; white-space: pre-line;">
          <strong>Feedback & Guidance:</strong> ${escapeHtml(
            Array.isArray(evalResult.actionable_feedback)
              ? evalResult.actionable_feedback.map(item => `• ${item}`).join("\n")
              : (evalResult.actionable_feedback || evalResult.feedback)
          )}
        </div>
      ` : ''}

      <!-- Detailed Breakdown Box Grid -->
      <div class="chat-eval-points-group">
        ${strengthsHTML}
        ${improvementsHTML}
        ${modelAnswerHTML}
      </div>

    </div>
  `;

  feed.appendChild(evalRow);
  scrollToBottom();
}

// Request In-Session Hint without answering
async function handleRequestHint() {
  if (!currentInterview || !currentInterview.questions) return;
  const q = currentInterview.questions[activeQuestionIndex];
  if (!q) return;

  const hintBtn = document.getElementById("btn-request-hint");
  if (hintBtn) hintBtn.disabled = true;

  try {
    showToast("Requesting interviewer hint from Gemini...", "info");

    const res = await API.post(`/api/interviews/${currentInterview.id}/clarify`, {
      question_id: q.id,
      query: "Could you provide a helpful architectural hint or scope clarification for this problem?"
    });

    const hintContainer = document.getElementById(`hint-container-${q.id}`);
    const hintText = res.clarification || res.hint || "Focus on separation of concerns, idempotency, and handling latency bottlenecks.";

    if (hintContainer) {
      hintContainer.innerHTML = `
        <div class="chat-hint-card">
          <div class="chat-hint-header">
            <span>💡</span> Interviewer Guidance
          </div>
          <div>${escapeHtml(hintText)}</div>
        </div>
      `;
    } else {
      // Append to active feed
      const feed = document.getElementById("chat-feed");
      const hintRow = document.createElement("div");
      hintRow.className = "chat-message-row ai-row";
      hintRow.innerHTML = `
        <div class="chat-avatar ai" style="background:#F59E0B;">💡</div>
        <div class="chat-bubble ai">
          <div class="chat-hint-card" style="margin-top:0;">
            <div class="chat-hint-header">
              <span>💡</span> Interviewer Guidance / Hint
            </div>
            <div>${escapeHtml(hintText)}</div>
          </div>
        </div>
      `;
      feed.appendChild(hintRow);
    }

    scrollToBottom();
  } catch (err) {
    showToast(`Hint request failed: ${err.message}`, "error");
  } finally {
    if (hintBtn) hintBtn.disabled = false;
  }
}

// Skip Question and Adapt Next
async function handleSkipQuestion() {
  if (!currentInterview) return;
  const skipBtn = document.getElementById("sidebar-skip-btn");
  if (skipBtn && skipBtn.disabled) return;

  if (!confirm("Are you sure you want to pass on this question? The AI will adapt your next question accordingly.")) {
    return;
  }

  const activeQ = currentInterview.questions && currentInterview.questions[activeQuestionIndex];
  const qIdParam = activeQ && activeQ.id ? `?question_id=${encodeURIComponent(activeQ.id)}` : "";

  if (skipBtn) {
    skipBtn.disabled = true;
    skipBtn.setAttribute("data-orig-text", skipBtn.innerHTML);
    skipBtn.innerHTML = "<span>⏳</span> Skipping...";
  }

  try {
    const res = await API.post(`/api/interviews/${currentInterview.id}/next${qIdParam}`);
    const nextQ = res.next_question || (res.id && res.question_text ? res : null);
    const isCompleted = Boolean(res.interview_completed || res.status === "completed" || !nextQ);

    if (activeQ) {
      activeQ.is_skipped = true;
    }

    if (nextQ) {
      currentInterview.questions.push(nextQ);
      activeQuestionIndex++;
      updateProgressBar();
      renderActiveQuestion();
      showToast("Question skipped. Adapting to next topic...", "info");
    } else if (isCompleted) {
      renderInterviewCompletionCard();
      showToast("All questions completed. Compiling evaluation report...", "success");
    }
  } catch (err) {
    showToast(`Skip failed: ${err.message}`, "error");
  } finally {
    if (skipBtn) {
      skipBtn.disabled = false;
      const orig = skipBtn.getAttribute("data-orig-text");
      if (orig) skipBtn.innerHTML = orig;
    }
  }
}

// Manually Complete Interview
async function handleEndInterview() {
  if (!currentInterview || !confirm("End this interview session now? You will be taken to your comprehensive performance evaluation report.")) {
    return;
  }

  try {
    await API.post(`/api/interviews/${currentInterview.id}/complete`);
    window.location.href = `result.html?id=${currentInterview.id}`;
  } catch (err) {
    showToast(`End session failed: ${err.message}`, "error");
  }
}

// Render Completion Card in Chat Feed
function renderInterviewCompletionCard() {
  const feed = document.getElementById("chat-feed");
  if (!feed) return;

  // Mark complete on backend
  API.post(`/api/interviews/${currentInterview.id}/complete`).catch(e => console.debug("Auto-complete:", e));

  const compCard = document.createElement("div");
  compCard.className = "chat-complete-card";
  compCard.innerHTML = `
    <div style="font-size:3rem; margin-bottom:12px;">🎉</div>
    <h2 style="font-size:1.6rem; font-weight:800; color:#1E1B4B; margin-bottom:8px;">Interview Loop Complete!</h2>
    <p style="color:#4338CA; font-size:1rem; max-width:550px; margin:0 auto 24px; line-height:1.6;">
      All target interview questions have been evaluated by Gemini 3.8 Flash. Your comprehensive performance scorecard, hiring rubric breakdown, and growth roadmap are ready.
    </p>
    <a href="result.html?id=${currentInterview.id}" class="chat-submit-btn" style="text-decoration:none; display:inline-flex; padding:14px 32px; font-size:1.05rem; border-radius:12px; box-shadow: 0 4px 14px rgba(99,102,241,0.4);">
      <span>View Comprehensive Performance Report →</span>
    </a>
  `;

  feed.appendChild(compCard);
  scrollToBottom();

  // Hide or disable bottom composer
  const composer = document.querySelector(".chat-composer-container");
  if (composer) {
    composer.innerHTML = `
      <div style="max-width:900px; margin:0 auto; text-align:center; padding:12px; color:#64748B; font-weight:600; font-size:0.9rem;">
        ✅ Session completed. You can review your messages above or view your full report.
      </div>
    `;
  }
}

// Update Topbar Progress Indicator
function updateProgressBar() {
  if (!currentInterview) return;
  const total = currentInterview.num_questions || (currentInterview.questions ? currentInterview.questions.length : 5);
  const currentNum = activeQuestionIndex + 1;

  const label = document.getElementById("chat-progress-text");
  if (label) label.textContent = `QUESTION ${Math.min(currentNum, total)} OF ${total}`;

  const bar = document.getElementById("chat-progress-bar");
  if (bar) {
    const pct = Math.min((currentNum / total) * 100, 100);
    bar.style.width = `${pct}%`;
  }
}

// Countdown Timer Handler
function startTimer() {
  if (timerInterval) clearInterval(timerInterval);

  timerInterval = setInterval(() => {
    secondsRemaining--;
    if (secondsRemaining <= 0) {
      clearInterval(timerInterval);
      showToast("Time expired! Finalizing session...", "warning");
      renderInterviewCompletionCard();
      return;
    }

    const mins = Math.floor(secondsRemaining / 60);
    const secs = secondsRemaining % 60;
    const display = document.getElementById("chat-timer-display");
    if (display) {
      display.textContent = `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    }
  }, 1000);
}

// Helper: Auto-expand textarea
function adjustTextareaHeight(textarea) {
  textarea.style.height = "auto";
  const newHeight = Math.min(textarea.scrollHeight, 180);
  textarea.style.height = `${Math.max(newHeight, 50)}px`;
}

// Helper: Word count update
function updateWordCount(text) {
  const countEl = document.getElementById("chat-word-count");
  if (!countEl) return;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  countEl.textContent = `${words} ${words === 1 ? 'word' : 'words'}`;
}

// Helper: Auto scroll chat feed to bottom
function scrollToBottom() {
  const feed = document.getElementById("chat-feed");
  if (feed) {
    feed.scrollTop = feed.scrollHeight;
  }
}

// Helper: HTML entity escaping
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
