/* AI Technical & Adaptive Interview Controller */
let currentInterview = null;
let currentQuestionIndex = 0;
let timerInterval = null;
let secondsRemaining = 1200;

document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();

  const urlParams = new URLSearchParams(window.location.search);
  const interviewId = urlParams.get("id");

  if (!interviewId) {
    showToast("No interview ID provided", "error");
    window.location.href = "dashboard.html";
    return;
  }

  await loadInterview(interviewId);
  setupAnswerEvents();
});

async function loadInterview(interviewId) {
  try {
    currentInterview = await API.get(`/api/interviews/${interviewId}`);
    
    // Update Header and Metadata
    const titleEl = document.getElementById("interview-title");
    if (titleEl) titleEl.textContent = currentInterview.title;

    const roleTagEl = document.getElementById("header-role-tag");
    if (roleTagEl) roleTagEl.textContent = `${currentInterview.target_role} • ${currentInterview.interview_type}`;

    // Start Countdown Timer
    secondsRemaining = (currentInterview.duration_minutes || 20) * 60;
    startTimer();

    // Render First Question
    renderQuestion(0);

  } catch (err) {
    showToast(`Failed to load interview: ${err.message}`, "error");
    setTimeout(() => { window.location.href = "dashboard.html"; }, 2000);
  }
}

function renderQuestion(index) {
  if (!currentInterview || !currentInterview.questions || currentInterview.questions.length === 0) return;

  currentQuestionIndex = index;
  const q = currentInterview.questions[index];

  // Update Progress
  const total = currentInterview.num_questions || currentInterview.questions.length;
  const progressText = document.getElementById("question-progress-text");
  if (progressText) progressText.textContent = `QUESTION ${q.question_number} OF ${total}`;

  const progressFill = document.getElementById("question-progress-fill");
  if (progressFill) progressFill.style.width = `${(q.question_number / total) * 100}%`;

  const footerCounter = document.getElementById("footer-page-counter");
  if (footerCounter) footerCounter.textContent = `${q.question_number} / ${total}`;

  // Update Difficulty Badge
  const diffBadge = document.getElementById("difficulty-badge");
  if (diffBadge) {
    diffBadge.textContent = q.difficulty || "Medium";
    const diffLower = (q.difficulty || "medium").toLowerCase();
    diffBadge.className = `badge ${
      diffLower === 'easy' ? 'badge-success' :
      diffLower === 'hard' ? 'badge-danger' : 'badge-warning'
    }`;
  }

  // Update Question Box
  const qTextEl = document.getElementById("question-text");
  if (qTextEl) qTextEl.textContent = q.question_text;

  const qHintEl = document.getElementById("question-hint");
  if (qHintEl) {
    let hintHTML = "";
    if (q.adaptation_reason) {
      hintHTML += `<div style="font-weight:700; color:var(--primary); margin-bottom:4px;">🤖 Adaptive AI Engine: ${q.adaptation_reason}</div>`;
    }
    if (q.additional_instruction) {
      hintHTML += `<div>💡 Hint: ${q.additional_instruction}</div>`;
    }
    if (hintHTML) {
      qHintEl.innerHTML = hintHTML;
      qHintEl.style.display = "block";
    } else {
      qHintEl.style.display = "none";
    }
  }

  // Update Answer Box
  const textarea = document.getElementById("answer-textarea");
  if (textarea) {
    textarea.value = localStorage.getItem(`draft_${currentInterview.id}_${q.id}`) || "";
    updateWordCount();
  }

  // Navigation state
  const prevBtn = document.getElementById("prev-btn");
  if (prevBtn) prevBtn.disabled = (index === 0);

  const nextBtn = document.getElementById("next-btn");
  if (nextBtn) nextBtn.disabled = (index >= currentInterview.questions.length - 1);
}

function setupAnswerEvents() {
  const textarea = document.getElementById("answer-textarea");
  if (textarea) {
    textarea.addEventListener("input", () => {
      updateWordCount();
      if (currentInterview && currentInterview.questions[currentQuestionIndex]) {
        const q = currentInterview.questions[currentQuestionIndex];
        localStorage.setItem(`draft_${currentInterview.id}_${q.id}`, textarea.value);
      }
    });
  }

  const clearBtn = document.getElementById("clear-btn");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      if (textarea) {
        textarea.value = "";
        updateWordCount();
        if (currentInterview && currentInterview.questions[currentQuestionIndex]) {
          const q = currentInterview.questions[currentQuestionIndex];
          localStorage.removeItem(`draft_${currentInterview.id}_${q.id}`);
        }
      }
    });
  }

  const submitBtn = document.getElementById("submit-answer-btn");
  if (submitBtn) {
    submitBtn.addEventListener("click", submitCurrentAnswer);
  }

  const prevBtn = document.getElementById("prev-btn");
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (currentQuestionIndex > 0) renderQuestion(currentQuestionIndex - 1);
    });
  }

  const nextBtn = document.getElementById("next-btn");
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (currentQuestionIndex < currentInterview.questions.length - 1) renderQuestion(currentQuestionIndex + 1);
    });
  }
}

function updateWordCount() {
  const textarea = document.getElementById("answer-textarea");
  const wordCountEl = document.getElementById("word-count-display");
  if (!textarea || !wordCountEl) return;

  const text = textarea.value.trim();
  const words = text ? text.split(/\s+/).length : 0;
  wordCountEl.textContent = `${words} words`;
}

async function submitCurrentAnswer() {
  const textarea = document.getElementById("answer-textarea");
  const answerText = textarea ? textarea.value.trim() : "";

  if (!answerText) {
    showToast("Please type your answer before submitting.", "warning");
    return;
  }

  const q = currentInterview.questions[currentQuestionIndex];
  const submitBtn = document.getElementById("submit-answer-btn");

  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span class="loading-spinner"></span> Evaluating...`;

  try {
    showLoadingModal("Evaluating answer & adapting next question...");

    const evalResult = await API.post(`/api/interviews/${currentInterview.id}/answer`, {
      question_id: q.id,
      answer_text: answerText
    });

    hideLoadingModal();
    submitBtn.disabled = false;
    submitBtn.innerHTML = "Submit Answer";

    // Append next question to currentInterview if generated adaptively
    if (evalResult.next_question) {
      const exists = currentInterview.questions.some(qItem => qItem.id === evalResult.next_question.id);
      if (!exists) {
        currentInterview.questions.push(evalResult.next_question);
      }
    }

    // Show Evaluation & Adaptive Feedback Modal
    showEvaluationModal(evalResult);

  } catch (err) {
    hideLoadingModal();
    submitBtn.disabled = false;
    submitBtn.innerHTML = "Submit Answer";
    showToast(err.message, "error");
  }
}

function showEvaluationModal(evalResult) {
  let modal = document.getElementById("eval-result-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "eval-result-modal";
    modal.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(6px);
      z-index: 9999; display: flex; align-items: center; justify-content: center; padding: 20px;
    `;
    document.body.appendChild(modal);
  }

  const isLast = evalResult.is_last_question;
  const nextQ = evalResult.next_question;

  modal.innerHTML = `
    <div style="background: #FFFFFF; width: 100%; max-width: 650px; max-height: 90vh; overflow-y: auto; border-radius: 16px; padding: 32px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.2);">
      
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid var(--border-color); padding-bottom: 16px; margin-bottom: 20px;">
        <div>
          <span class="badge badge-success">AI Evaluation Result</span>
          <h3 style="margin-top:6px; font-size:1.3rem;">Question Score: <span style="color:var(--primary); font-weight:800;">${evalResult.overall_score}%</span></h3>
        </div>
        <div style="font-size:2rem;">${evalResult.overall_score >= 80 ? '🌟' : evalResult.overall_score >= 60 ? '👍' : '💡'}</div>
      </div>

      ${nextQ && nextQ.adaptation_reason ? `
        <div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:10px; padding:12px 16px; margin-bottom:20px; font-size:0.9rem; color:#1E40AF;">
          <strong>🤖 Adaptive AI Decision:</strong> ${nextQ.adaptation_reason}
        </div>
      ` : ''}

      <div style="margin-bottom:20px;">
        <h4 style="font-size:0.9rem; color:var(--text-muted); margin-bottom:8px;">RUBRIC BREAKDOWN</h4>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; font-size:0.85rem;">
          <div>Technical Correctness: <strong>${evalResult.technical_correctness}%</strong></div>
          <div>Conceptual Completeness: <strong>${evalResult.conceptual_completeness}%</strong></div>
          <div>Response Relevance: <strong>${evalResult.response_relevance}%</strong></div>
          <div>Structural Clarity: <strong>${evalResult.structural_clarity}%</strong></div>
        </div>
      </div>

      <div style="margin-bottom:20px;">
        <h4 style="font-size:0.9rem; color:var(--text-muted); margin-bottom:6px;">FEEDBACK</h4>
        <p style="font-size:0.95rem; line-height:1.5; color:var(--text-main);">${evalResult.feedback}</p>
      </div>

      <div style="display:flex; justify-content:flex-end; gap:12px; margin-top:24px; border-top:1px solid var(--border-color); padding-top:16px;">
        ${isLast ? `
          <button id="modal-action-btn" class="btn btn-primary" style="padding:12px 24px;">
            Complete Interview & View Final Results →
          </button>
        ` : `
          <button id="modal-action-btn" class="btn btn-primary" style="padding:12px 24px;">
            Next Adaptive Question →
          </button>
        `}
      </div>
    </div>
  `;

  modal.style.display = "flex";

  document.getElementById("modal-action-btn").onclick = async () => {
    modal.style.display = "none";
    if (isLast) {
      await API.post(`/api/interviews/${currentInterview.id}/complete`);
      window.location.href = `result.html?id=${currentInterview.id}`;
    } else {
      renderQuestion(currentQuestionIndex + 1);
    }
  };
}

function startTimer() {
  if (timerInterval) clearInterval(timerInterval);

  timerInterval = setInterval(() => {
    secondsRemaining--;
    if (secondsRemaining <= 0) {
      clearInterval(timerInterval);
      showToast("Time expired! Submitting interview...", "warning");
      setTimeout(() => {
        if (currentInterview) window.location.href = `result.html?id=${currentInterview.id}`;
      }, 1500);
    }

    const mins = Math.floor(secondsRemaining / 60);
    const secs = secondsRemaining % 60;
    const timerDisplay = document.getElementById("timer-display");
    if (timerDisplay) {
      timerDisplay.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
  }, 1000);
}

function showLoadingModal(msg) {
  let modal = document.getElementById("eval-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "eval-modal";
    modal.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.7); backdrop-filter: blur(4px);
      z-index: 9999; display: flex; align-items: center; justify-content: center;
    `;
    modal.innerHTML = `
      <div style="background: #FFFFFF; padding: 32px 48px; border-radius: 16px; text-align: center; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);">
        <div class="loading-spinner" style="width: 40px; height: 40px; border-color: #2563EB; border-top-color: transparent; margin: 0 auto 16px;"></div>
        <h3 id="eval-modal-msg" style="color: #0F172A; font-size: 1.2rem; margin-bottom: 8px;">${msg}</h3>
        <p style="color: #64748B; font-size: 0.9rem;">Analysing correctness, clarity & computing adaptive next question...</p>
      </div>
    `;
    document.body.appendChild(modal);
  } else {
    document.getElementById("eval-modal-msg").textContent = msg;
    modal.style.display = "flex";
  }
}

function hideLoadingModal() {
  const modal = document.getElementById("eval-modal");
  if (modal) modal.style.display = "none";
}
