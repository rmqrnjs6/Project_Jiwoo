// Extracted from the original frontend/app.js for functional classification.
// This is a review/upload copy, not a standalone bundle. Shared helpers/state remain in 00_common/frontend.

function clarityOpenPoint(latest) {
  if (!latest) return "근거를 고른 뒤 현재 확인 가능한 범위를 정리합니다.";
  if (latest.waiting_for) return latest.waiting_for;
  if (latest.unresolved_reason) return latest.unresolved_reason;
  return "현재 고른 근거 기준으로 별도 대기 항목은 없어요. 새로운 자료가 나오면 다시 확인할 수 있습니다.";
}

function clarityCalmNote(latest) {
  if (!latest) return "확실한 것은 분명하게, 아직 모르는 것은 그대로 남길게요.";
  if (latest.resolution_state === "RESOLVED") {
    return "현재 확인 가능한 범위는 여기까지예요. 더 궁금할 때만 근거를 펼쳐보세요.";
  }
  if (latest.resolution_state === "PENDING") {
    return "지금은 기다릴 정보가 있어요. 아직 결론을 서두르지 않아도 됩니다.";
  }
  return "자료가 엇갈리거나 부족한 부분은 억지로 채우지 않고 그대로 남겨둘게요.";
}

function renderClaritySummary() {
  const latest = latestJudgment();
  const evidenceCount = state.currentCase?.evidence?.length || 0;
  const title = $("clarityTitle");
  const status = $("clarityStatus");
  const summary = $("claritySummary");
  const boundary = $("clarityBoundary");
  const openPoint = $("clarityOpenPoint");
  const calmNote = $("clarityCalmNote");
  const shareButton = $("copyShareSummary");

  if (!latest) {
    title.textContent = "아직 핵심을 정리할 단계는 아니에요.";
    status.textContent = evidenceCount ? "근거를 고르는 중" : "근거 확인 중";
    status.className = "clarity-status pending";
    summary.textContent = "근거를 살펴보면 확인된 것과 아직 모르는 것을 나눠서 보여드릴게요.";
    boundary.textContent = evidenceCount
      ? `현재 ${evidenceCount}개의 근거를 골랐어요. 확인 결과를 만들기 전입니다.`
      : "아직 판단에 사용할 근거가 정리되지 않았어요.";
    openPoint.textContent = "근거를 고른 뒤 현재 확인 가능한 범위를 정리합니다.";
    calmNote.textContent = clarityCalmNote(null);
    shareButton.disabled = true;
    return;
  }

  title.textContent = CLARITY_HEADLINES[latest.conclusion] || CONCLUSION_LABELS[latest.conclusion] || "현재 확인 결과를 정리했어요.";
  status.textContent = CLARITY_STATUS[latest.resolution_state] || "현재 상태 확인";
  status.className = `clarity-status ${latest.resolution_state === "RESOLVED" ? "resolved" : "pending"}`;
  summary.textContent = latest.reasoning_summary || "현재 고른 근거를 바탕으로 확인 결과를 정리했습니다.";
  boundary.textContent = evidenceCount
    ? `현재 고른 근거 ${evidenceCount}개를 기준으로 정리한 결과입니다.`
    : "현재 고른 근거를 기준으로 정리한 결과입니다.";
  openPoint.textContent = clarityOpenPoint(latest);
  calmNote.textContent = clarityCalmNote(latest);
  shareButton.disabled = false;
}

function buildShareSummary() {
  const latest = latestJudgment();
  if (!latest || !state.currentCase) return "";
  const representative = adoptedRepresentative();
  const parts = [
    `[현재 확인된 핵심] ${CLARITY_HEADLINES[latest.conclusion] || CONCLUSION_LABELS[latest.conclusion] || latest.position_text}`,
    "",
    `[확인한 이야기] ${state.currentCase.original_input}`,
    `[현재 정리] ${latest.reasoning_summary}`,
    `[아직 확인이 필요한 부분] ${clarityOpenPoint(latest)}`,
  ];
  if (representative) {
    parts.push(
      "",
      `[가장 믿을 만한 근거] ${representative.source_name} - ${representative.title}`,
      `${representative.source_url}`,
    );
  }
  parts.push(
    "",
    `[확인 시점] ${formatDate(state.currentCase.updated_at)}`,
    "새로운 근거가 나오면 내용이 달라질 수 있습니다.",
  );
  return parts.join("\n");
}

async function copyShareSummary() {
  const text = buildShareSummary();
  if (!text) {
    showToast("공유할 확인 결과가 아직 없어요.", true);
    return;
  }
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    showToast("현재 확인된 핵심을 공유하기 좋은 형태로 복사했어요.");
  } catch (error) {
    showToast("요약을 복사하지 못했어요. 브라우저 권한을 확인해주세요.", true);
  }
}

