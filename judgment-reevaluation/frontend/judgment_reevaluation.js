// Extracted from the original frontend/app.js for functional classification.
// This is a review/upload copy, not a standalone bundle. Shared helpers/state remain in 00_common/frontend.

function latestJudgment(items = state.currentCase?.judgments || []) {
  return [...items].sort((a, b) => b.revision_no - a.revision_no)[0] || null;
}

function renderLatestJudgment(items) {
  const latest = latestJudgment(items);
  if (!latest) {
    $("judgmentEmpty").classList.remove("hidden");
    $("judgmentView").classList.add("hidden");
    return;
  }
  $("judgmentEmpty").classList.add("hidden");
  $("judgmentView").classList.remove("hidden");
  $("judgmentConclusion").textContent = latest.conclusion;
  $("judgmentPosition").textContent = CONCLUSION_LABELS[latest.conclusion] || latest.position_text;
  $("judgmentConfidence").textContent = `${scorePct(latest.confidence)}%`;
  $("judgmentReason").textContent = latest.reasoning_summary;
  $("judgmentMeta").innerHTML = [
    `${latest.revision_no === 1 ? "첫 판단" : `${latest.revision_no}번째 판단`}`,
    RESOLUTION_LABELS[latest.resolution_state] || latest.resolution_state,
    TRIGGER_LABELS[latest.reevaluation_trigger || "INITIAL"] || latest.reevaluation_trigger || "처음 확인",
  ].map(value => `<span class="meta-chip">${escapeHtml(String(value))}</span>`).join("");

  const icon = $("judgmentIcon");
  if (latest.conclusion === "CONTRADICTED") {
    icon.textContent = "×";
    icon.style.background = "var(--red-soft)";
    icon.style.color = "var(--red)";
  } else if (["UNCERTAIN", "INSUFFICIENT_EVIDENCE"].includes(latest.conclusion)) {
    icon.textContent = "?";
    icon.style.background = "var(--amber-soft)";
    icon.style.color = "var(--amber)";
  } else {
    icon.textContent = "✓";
    icon.style.background = "var(--green-soft)";
    icon.style.color = "var(--green)";
  }
}

function updateJudgeAvailability() {
  const evidence = state.currentCase?.evidence || [];
  const noEvidence = evidence.length === 0;
  const noAi = !state.ai?.configured;
  const hasDemo = evidence.some(item => item.reliability_source === "DEMO_CANDIDATE");
  $("judgeButton").disabled = noEvidence || noAi || hasDemo;
  $("forceJudgeButton").disabled = noEvidence || noAi || hasDemo;

  if (noAi) {
    $("judgeMessage").textContent = "실제 AI 판단을 사용하려면 먼저 API Key가 필요해요. 예시와 근거 검토는 계속할 수 있습니다.";
  } else if (noEvidence) {
    $("judgeMessage").textContent = "먼저 근거를 읽어보고, 판단에 사용할 자료를 하나 이상 골라주세요.";
  } else if (hasDemo) {
    $("judgeMessage").textContent = "예시 근거는 화면을 체험하기 위한 자료예요. 실제 판단에는 사용되지 않습니다.";
  } else {
    $("judgeMessage").textContent = "달라진 것이 없다면 이전 판단을 그대로 이어갑니다. 불필요한 AI 호출도 하지 않아요.";
  }
}

async function runJudge(force = false) {
  if (!state.currentCaseId) return;
  const button = force ? $("forceJudgeButton") : $("judgeButton");
  button.disabled = true;
  $("judgeMessage").textContent = force ? "새로 확인하고 있어요..." : "고른 근거를 바탕으로 확인하고 있어요...";
  try {
    const { status } = await api(`/cases/${state.currentCaseId}/judge${force ? "?force=true" : ""}`, { method: "POST" });
    showToast(status === 200
      ? "달라진 내용이 없어 이전 판단을 그대로 이어갑니다. 새 AI 호출은 하지 않았어요."
      : "현재 확인 결과를 새로 정리했어요.");
    await refreshCurrentCase();
  } catch (error) {
    const code = error.body?.detail?.code;
    showToast(code ? `${code}: ${error.message}` : error.message, true);
    await loadTimeline().catch(() => {});
  } finally {
    updateJudgeAvailability();
  }
}

