// Extracted from the original frontend/app.js for functional classification.
// This is a review/upload copy, not a standalone bundle. Shared helpers/state remain in 00_common/frontend.

function scorePct(value) {
  if (value == null || Number.isNaN(Number(value))) return null;
  return Math.round(Number(value) * 100);
}

function scoreClass(value) {
  const pct = scorePct(value) ?? 0;
  if (pct >= 85) return "score-high";
  if (pct >= 60) return "score-mid";
  return "score-low";
}

function scoreLabel(value) {
  const pct = scorePct(value) ?? 0;
  if (pct >= 90) return "매우 높음";
  if (pct >= 80) return "높음";
  if (pct >= 65) return "보통";
  if (pct >= 45) return "주의";
  return "낮음";
}

function sourceStatusText(value) {
  if (value === "VERIFIED") return "출처 확인됨";
  if (value === "PARTIALLY_VERIFIED") return "출처 일부 확인";
  if (value === "DISPUTED") return "출처 확인 필요";
  if (value === "INVALID") return "출처에 문제가 있음";
  return "출처 미확인";
}

function sourceStatusHint(value) {
  if (value === "VERIFIED") return "주소와 출처 정보가 현재 확인 기준을 통과했습니다.";
  if (value === "PARTIALLY_VERIFIED") return "주소 형식은 확인했지만 출처의 모든 내용이 사실이라는 뜻은 아닙니다.";
  if (value === "DISPUTED") return "출처 정보에 서로 맞지 않는 부분이 있어 원문 확인이 필요합니다.";
  if (value === "INVALID") return "공개 출처로 사용하기 어려운 주소이거나 형식상 문제가 있습니다.";
  return "아직 출처 상태를 확인하지 않았습니다.";
}

function sourceNeedsAttention(value) {
  return value === "UNVERIFIED" || value === "DISPUTED" || value === "INVALID";
}

function verificationClass(value) {
  if (value === "VERIFIED") return "good";
  if (value === "PARTIALLY_VERIFIED") return "warn";
  if (value === "DISPUTED" || value === "INVALID") return "danger";
  return "";
}

function relationClass(value) {
  if (value === "SUPPORT") return "good";
  if (value === "CONTRADICT") return "danger";
  if (value === "CONTEXT") return "info";
  return "";
}

function urlDomain(value) {
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return value || "출처 URL 없음";
  }
}

async function assessOne(evidenceId) {
  try {
    await api(`/cases/${state.currentCaseId}/evidence/${evidenceId}/assess-reliability`, { method: "POST" });
    showToast("근거를 다시 살펴봤어요. 현재 평가는 화면에 반영했습니다.");
    await refreshCurrentCase();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function reviewOne(evidenceId, hasUrl, isDemo = false) {
  try {
    if (hasUrl && !isDemo) {
      await api(`/cases/${state.currentCaseId}/evidence/${evidenceId}/verify-source`, { method: "POST" });
    } else {
      await api(`/cases/${state.currentCaseId}/evidence/${evidenceId}/assess-reliability`, { method: "POST" });
    }
    showToast(isDemo ? "예시 근거의 표시 점수를 다시 확인했어요." : "출처와 신뢰도를 다시 살펴봤어요.");
    await refreshCurrentCase();
  } catch (error) {
    showToast(error.message, true);
  }
}

