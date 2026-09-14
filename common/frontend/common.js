// Extracted from frontend/app.js for upload classification.
// These functions depend on the original shared runtime state.

function showToast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.className = `toast${isError ? " error" : ""}`;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => el.classList.add("hidden"), 3600);
}

async function api(path, options = {}

function formatDate(value, { withTime = true }

async function loadAiStatus() {
  try {
    const { body } = await api("/ai/status");
    state.ai = body;
    const el = $("aiStatus");
    if (body.configured) {
      el.textContent = `AI 준비됨 · ${body.model}`;
      el.className = "status-pill good";
    } else {
      el.textContent = "AI 키 미설정";
      el.className = "status-pill warn";
    }
    $("discoverCandidatesButton").disabled = !body.configured;
    updateJudgeAvailability();
  } catch (error) {
    $("aiStatus").textContent = "AI 상태 확인 실패";
    $("discoverCandidatesButton").disabled = true;
  }
}

function escapeAttr(value) {
  return escapeHtml(value);
}

