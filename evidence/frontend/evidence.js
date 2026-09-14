// Extracted from the original frontend/app.js for functional classification.
// This is a review/upload copy, not a standalone bundle. Shared helpers/state remain in 00_common/frontend.

function setCandidateBatch(batch) {
  state.candidates = batch?.candidates || [];
  state.candidateOrigin = batch?.origin || "NONE";
  state.candidateDisclaimer = batch?.disclaimer || "";
}

function sortedCandidates() {
  const items = [...state.candidates];
  const sort = $("candidateSort").value;
  if (sort === "newest") {
    return items.sort((a, b) => new Date(b.source_published_at || 0) - new Date(a.source_published_at || 0));
  }
  if (sort === "source") {
    return items.sort((a, b) => a.source_name.localeCompare(b.source_name, "ko"));
  }
  return items.sort((a, b) => b.reliability_score - a.reliability_score);
}

function renderCandidateDisclaimer() {
  const el = $("candidateDisclaimer");
  if (!state.candidateDisclaimer || !state.candidates.length) {
    el.classList.add("hidden");
    return;
  }
  el.textContent = state.candidateDisclaimer;
  el.className = `notice ${state.candidateOrigin === "DEMO" ? "demo" : "info"}`;
}

function renderCandidates() {
  const items = sortedCandidates();
  $("candidateCount").textContent = items.length;
  $("adoptedCount").textContent = state.currentCase?.evidence?.length || 0;
  $("candidateEmpty").classList.toggle("hidden", items.length > 0);

  const host = $("candidateList");
  if (!items.length) {
    host.innerHTML = "";
    return;
  }

  host.innerHTML = items.map(item => candidateCardHtml(item)).join("");
  bindCandidateActions(host);
}

function candidateCardHtml(item) {
  const pct = scorePct(item.reliability_score) ?? 0;
  const adopted = item.adopted_evidence_id != null;
  const components = item.score_components || {};
  const rep = item.is_representative;
  const attention = sourceNeedsAttention(item.source_verification_status);
  return `
    <article class="candidate-card ${rep ? "representative" : ""} ${scoreClass(item.reliability_score)}" data-candidate-id="${item.id}">
      <div class="candidate-score">
        <strong>${pct}%</strong>
        <span>${escapeHtml(scoreLabel(item.reliability_score))}</span>
        <div class="score-track" aria-label="신뢰도 ${pct}%"><i style="width:${pct}%"></i></div>
      </div>
      <div class="candidate-source">
        <div class="source-badge-row">
          <span class="source-name">${escapeHtml(item.source_name)}</span>
          ${item.origin === "DEMO" ? '<span class="meta-chip warn">예시</span>' : ""}
        </div>
        <a class="source-domain" href="${escapeAttr(item.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(urlDomain(item.source_url))} ↗</a>
        <span class="source-date">${formatDate(item.source_published_at, { withTime: false })}</span>
      </div>
      <div class="candidate-main">
        ${rep ? '<div class="representative-badge">★ 지금 가장 믿을 만한 근거</div>' : ""}
        <div class="candidate-main-top"><h3>${escapeHtml(item.title)}</h3></div>
        <div class="evidence-preview">
          <span class="preview-label">핵심 내용</span>
          <p>${escapeHtml(item.summary)}</p>
          <span class="preview-note">원문에서 지금 판단과 관련된 내용을 먼저 정리했습니다.</span>
        </div>
        ${attention ? `<div class="source-warning">⚠ ${escapeHtml(sourceStatusText(item.source_verification_status))} · ${escapeHtml(sourceStatusHint(item.source_verification_status))}</div>` : ""}
        <div class="meta-row compact-meta">
          <span class="meta-chip">${escapeHtml(SOURCE_LABELS[item.source_type] || item.source_type)}</span>
          <span class="meta-chip ${relationClass(item.relation_to_claim)}">${escapeHtml(RELATION_LABELS[item.relation_to_claim] || item.relation_to_claim)}</span>
          <span class="human-score-label">신뢰도 ${pct}% · ${escapeHtml(scoreLabel(item.reliability_score))}</span>
        </div>
        <div class="candidate-actions">
          <button type="button" class="${adopted ? "secondary adopted-button" : "primary"} adopt-candidate" data-id="${item.id}" ${adopted ? "disabled" : ""}>${adopted ? "✓ 고른 근거" : "이 근거 사용"}</button>
          <a href="${escapeAttr(item.source_url)}" target="_blank" rel="noreferrer">원문 보기 ↗</a>
        </div>
        <details class="score-details human-details">
          <summary>왜 이렇게 평가했나요?</summary>
          <div class="score-breakdown">
            <div class="source-check-summary ${verificationClass(item.source_verification_status)}">
              <strong>${escapeHtml(sourceStatusText(item.source_verification_status))}</strong>
              <span>${escapeHtml(sourceStatusHint(item.source_verification_status))}</span>
            </div>
            ${componentRow("출처 권위성", components.authority)}
            ${componentRow("원본성", components.originality)}
            ${componentRow("직접 관련성", components.directness)}
            ${componentRow("자료 시점", components.recency)}
            ${componentRow("다른 근거와 일치", components.corroboration)}
            <p class="rationale"><strong>살펴본 이유:</strong> ${escapeHtml(item.rationale)}</p>
            <p class="technical-note">신뢰도는 사실일 확률이 아니라 현재 확인된 조건을 종합한 평가값입니다.</p>
          </div>
        </details>
      </div>
    </article>
  `;
}

function componentRow(label, value) {
  const pct = scorePct(value) ?? 0;
  return `
    <div class="component-row">
      <span>${escapeHtml(label)}</span>
      <div class="component-track"><i style="width:${pct}%"></i></div>
      <strong>${pct}%</strong>
    </div>
  `;
}

function bindCandidateActions(host) {
  host.querySelectorAll(".adopt-candidate").forEach(button => {
    button.addEventListener("click", () => adoptCandidate(Number(button.dataset.id)));
  });
}

function renderCompare() {
  const items = [...state.candidates].sort((a, b) => b.reliability_score - a.reliability_score);
  const host = $("compareBody");
  if (!items.length) {
    host.innerHTML = '<tr><td colspan="6">아직 비교할 근거가 없어요.</td></tr>';
    return;
  }
  host.innerHTML = items.map((item, index) => `
    <tr class="${item.is_representative ? "representative-row" : ""}">
      <td>${item.is_representative ? "★" : index + 1}</td>
      <td><strong>${escapeHtml(item.source_name)}</strong><br><span class="subtle">${escapeHtml(item.title)}</span></td>
      <td><strong>${scorePct(item.reliability_score)}%</strong></td>
      <td>${escapeHtml(RELATION_LABELS[item.relation_to_claim] || item.relation_to_claim)}</td>
      <td>${escapeHtml(sourceStatusText(item.source_verification_status))}</td>
      <td>${item.adopted_evidence_id ? "고름" : "아직 안 고름"}</td>
    </tr>
  `).join("");
}

function renderEvidence(items) {
  $("adoptedCount").textContent = items.length;
  const host = $("evidenceList");
  if (!items.length) {
    host.innerHTML = '<div class="small-empty">아직 고른 근거가 없어요. 먼저 내용을 읽어보고, 판단에 도움이 된다고 느껴지는 자료만 골라주세요.</div>';
    return;
  }

  host.innerHTML = items.map(item => {
    const isDemo = item.reliability_source === "DEMO_CANDIDATE";
    const pct = scorePct(item.reliability_score);
    const attention = sourceNeedsAttention(item.source_verification_status);
    return `
      <article class="evidence-card ${isDemo ? "demo" : ""}">
        <div class="evidence-card-top">
          <div class="adopted-content">
            <span class="evidence-id">근거 #${item.id}</span>
            <p>${escapeHtml(item.content)}</p>
          </div>
          <div class="adopted-score">
            <strong>${pct == null ? "미평가" : pct + "%"}</strong>
            ${pct == null ? "" : `<span>${escapeHtml(scoreLabel(item.reliability_score))}</span>`}
          </div>
        </div>
        ${attention ? `<div class="source-warning">⚠ ${escapeHtml(sourceStatusText(item.source_verification_status))} · ${escapeHtml(sourceStatusHint(item.source_verification_status))}</div>` : ""}
        <div class="meta-row compact-meta">
          ${isDemo ? '<span class="meta-chip warn">예시 · 실제 판단 사용 불가</span>' : ""}
          <span class="meta-chip">${escapeHtml(SOURCE_LABELS[item.claimed_source_type] || item.claimed_source_type)}</span>
          ${item.source_url ? `<a class="evidence-source-link" href="${escapeAttr(item.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(urlDomain(item.source_url))} ↗</a>` : ""}
        </div>
        <div class="evidence-actions">
          <button class="secondary review-one" data-id="${item.id}" data-has-url="${item.source_url ? "1" : "0"}" data-demo="${isDemo ? "1" : "0"}" type="button">다시 확인</button>
          ${item.source_url ? `<a class="secondary-link" href="${escapeAttr(item.source_url)}" target="_blank" rel="noreferrer">원문 보기 ↗</a>` : ""}
        </div>
        <details class="adopted-details">
          <summary>조금 더 자세히 보기</summary>
          <div class="adopted-detail-body">
            <div><strong>출처 상태</strong><span>${escapeHtml(sourceStatusText(item.source_verification_status))}</span></div>
            <div><strong>신뢰도</strong><span>${pct == null ? "아직 평가하지 않음" : `${pct}% · ${escapeHtml(scoreLabel(item.reliability_score))}`}</span></div>
            <p>${escapeHtml(sourceStatusHint(item.source_verification_status))}</p>
          </div>
        </details>
      </article>
    `;
  }).join("");

  host.querySelectorAll(".review-one").forEach(button => button.addEventListener("click", () => reviewOne(
    Number(button.dataset.id),
    button.dataset.hasUrl === "1",
    button.dataset.demo === "1",
  )));
}

function renderRepresentative() {
  const representative = state.candidates.find(item => item.is_representative);
  $("representativeEmpty").classList.toggle("hidden", Boolean(representative));
  const view = $("representativeView");
  if (!representative) {
    view.classList.add("hidden");
    view.innerHTML = "";
    return;
  }
  const pct = scorePct(representative.reliability_score);
  view.classList.remove("hidden");
  view.innerHTML = `
    <div class="representative-card">
      <div class="rep-score">
        <span class="rep-source">${escapeHtml(representative.source_name)}</span>
        <div class="rep-score-human"><strong>${pct}%</strong><span>${escapeHtml(scoreLabel(representative.reliability_score))}</span></div>
      </div>
      <h3>${escapeHtml(representative.title)}</h3>
      <div class="rep-preview"><span>핵심 내용</span><p>${escapeHtml(representative.summary)}</p></div>
      ${sourceNeedsAttention(representative.source_verification_status) ? `<div class="source-warning compact">⚠ ${escapeHtml(sourceStatusText(representative.source_verification_status))}</div>` : ""}
      <div class="candidate-actions">
        <a href="${escapeAttr(representative.source_url)}" target="_blank" rel="noreferrer">원문 보기 ↗</a>
      </div>
    </div>
  `;
}

function adoptedRepresentative() {
  if (state.candidateOrigin === "DEMO") return null;
  return state.candidates.find(item => item.is_representative && item.adopted_evidence_id != null) || null;
}

async function discoverCandidates({ demo = false }

async function adoptCandidate(candidateId) {
  try {
    const candidate = state.candidates.find(item => item.id === candidateId);
    const { body, status } = await api(`/cases/${state.currentCaseId}/evidence-candidates/${candidateId}/adopt`, { method: "POST" });
    if (body?.id && body?.source_url && candidate?.origin !== "DEMO") {
      await api(`/cases/${state.currentCaseId}/evidence/${body.id}/verify-source`, { method: "POST" });
    }
    showToast(candidate?.origin === "DEMO"
      ? "예시 근거를 골랐어요. 실제 AI 판단에는 사용되지 않습니다."
      : status === 200 ? "이미 고른 근거예요." : "이 근거를 현재 판단에 사용하도록 골랐어요.");
    await refreshCurrentCase();
  } catch (error) {
    showToast(error.message, true);
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

function switchEvidenceTab(tab, rerender = true) {
  state.evidenceTab = tab;
  document.querySelectorAll("[data-evidence-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.evidenceTab === tab);
    button.setAttribute("aria-selected", button.dataset.evidenceTab === tab ? "true" : "false");
  });
  $("candidatePanel").classList.toggle("hidden", tab !== "candidates");
  $("adoptedPanel").classList.toggle("hidden", tab !== "adopted");
  $("comparePanel").classList.toggle("hidden", tab !== "compare");
  if (rerender) {
    if (tab === "candidates") renderCandidates();
    if (tab === "compare") renderCompare();
  }
}

