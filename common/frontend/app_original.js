const state = {
  cases: [],
  currentCaseId: null,
  currentCase: null,
  ai: null,
  candidates: [],
  candidateOrigin: "NONE",
  candidateDisclaimer: "",
  caseFilter: "ALL",
  evidenceTab: "candidates",
};

const $ = (id) => document.getElementById(id);

const SOURCE_LABELS = {
  PRIMARY: "1차 자료",
  OFFICIAL: "공식 발표",
  INSTITUTIONAL: "기관 자료",
  NEWS: "언론 보도",
  WEB: "웹 자료",
  USER: "사용자 자료",
  AI: "AI 생성",
  UNKNOWN: "출처 미상",
};

const VERIFICATION_LABELS = {
  UNVERIFIED: "미검증",
  PARTIALLY_VERIFIED: "부분 검증",
  VERIFIED: "검증 완료",
  DISPUTED: "검증 충돌",
  INVALID: "출처 무효",
};

const RELATION_LABELS = {
  SUPPORT: "주장을 지지",
  CONTRADICT: "주장과 충돌",
  CONTEXT: "맥락 보강",
  UNKNOWN: "관계 불명",
};


const RESOLUTION_LABELS = {
  RESOLVED: "현재 근거로 판단할 수 있어요",
  PENDING: "조금 더 기다릴 정보가 있어요",
  UNRESOLVED: "현재 자료만으로는 결론이 어려워요",
};

const TRIGGER_LABELS = {
  INITIAL: "처음 확인",
  USER_REQUEST: "다시 확인 요청",
  NEW_EVIDENCE: "새 근거 추가",
  INPUT_CHANGED: "확인할 주장 변경",
  SOURCE_REVIEWED: "출처 다시 확인",
  SOURCE_VERIFIED: "출처 확인 완료",
  SOURCE_DISPROVED: "출처 문제 확인",
  RULE_CHANGED: "판단 기준 변경",
  MODEL_CHANGED: "AI 모델 변경",
  GRACE_PERIOD_EXPIRED: "기다림 기간 종료",
};

const CONCLUSION_LABELS = {
  SUPPORTED: "현재 근거는 주장을 지지합니다.",
  CONTRADICTED: "현재 근거는 주장과 충돌합니다.",
  UNCERTAIN: "현재 근거만으로는 불확실합니다.",
  INSUFFICIENT_EVIDENCE: "판단할 근거가 아직 부족합니다.",
};

const CLARITY_HEADLINES = {
  SUPPORTED: "현재 확인된 근거는 이 이야기를 뒷받침해요.",
  CONTRADICTED: "현재 확인된 근거는 이 이야기와 맞지 않아요.",
  UNCERTAIN: "지금은 어느 쪽도 분명하다고 말하기 어려워요.",
  INSUFFICIENT_EVIDENCE: "아직 명확하게 말할 근거가 부족해요.",
};

const CLARITY_STATUS = {
  RESOLVED: "현재 범위 정리됨",
  PENDING: "조금 더 기다려야 해요",
  UNRESOLVED: "아직 열려 있어요",
};

function showToast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.className = `toast${isError ? " error" : ""}`;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => el.classList.add("hidden"), 3600);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === "string"
      ? detail
      : detail?.message || detail?.code || `HTTP ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    error.body = body;
    throw error;
  }
  return { body, status: response.status };
}

function formatDate(value, { withTime = true } = {}) {
  if (!value) return "날짜 미상";
  const options = withTime
    ? { year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit" }
    : { year: "numeric", month: "numeric", day: "numeric" };
  return new Intl.DateTimeFormat("ko-KR", options).format(new Date(value));
}

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

async function loadCases(selectId = null) {
  const { body } = await api("/cases");
  state.cases = body;
  renderCaseList();
  if (selectId) await selectCase(selectId);
}

function renderCaseList() {
  const total = state.cases.length;
  const open = state.cases.filter(item => item.status === "OPEN").length;
  const closed = state.cases.filter(item => item.status === "CLOSED").length;
  $("countAll").textContent = total;
  $("countOpen").textContent = open;
  $("countClosed").textContent = closed;

  const query = $("caseSearch").value.trim().toLowerCase();
  let items = state.cases.filter(item => {
    const matchesFilter = state.caseFilter === "ALL" || item.status === state.caseFilter;
    const matchesQuery = !query || item.title.toLowerCase().includes(query) || String(item.id).includes(query);
    return matchesFilter && matchesQuery;
  });

  const sort = $("caseSort").value;
  items = [...items].sort((a, b) => {
    if (sort === "oldest") return new Date(a.created_at) - new Date(b.created_at);
    if (sort === "title") return a.title.localeCompare(b.title, "ko");
    return new Date(b.created_at) - new Date(a.created_at);
  });

  const host = $("caseList");
  if (!items.length) {
    host.innerHTML = '<div class="small-empty">조건에 맞는 판단이 없습니다.</div>';
    return;
  }
  host.innerHTML = items.map(item => `
    <button class="case-item ${item.id === state.currentCaseId ? "active" : ""}" data-id="${item.id}" type="button">
      <span class="case-item-title">${escapeHtml(item.title)}</span>
      <span class="case-item-meta">
        <span>#${item.id} · ${formatDate(item.created_at, { withTime: false })}</span>
        <span class="status-pill ${item.status === "OPEN" ? "info" : "good"}">${item.status === "OPEN" ? "진행 중" : "완료"}</span>
      </span>
    </button>
  `).join("");
  host.querySelectorAll(".case-item").forEach(button => {
    button.addEventListener("click", () => selectCase(Number(button.dataset.id)));
  });
}

async function selectCase(caseId) {
  state.currentCaseId = caseId;
  const [caseResult, candidateResult] = await Promise.all([
    api(`/cases/${caseId}`),
    api(`/cases/${caseId}/evidence-candidates`),
  ]);
  state.currentCase = caseResult.body;
  setCandidateBatch(candidateResult.body);
  renderCaseList();
  renderCase();
  await loadTimeline();
}

function setCandidateBatch(batch) {
  state.candidates = batch?.candidates || [];
  state.candidateOrigin = batch?.origin || "NONE";
  state.candidateDisclaimer = batch?.disclaimer || "";
}

function renderCase() {
  const data = state.currentCase;
  if (!data) return;
  $("emptyState").classList.add("hidden");
  $("caseView").classList.remove("hidden");
  $("caseNumber").textContent = `#${data.id}`;
  $("caseViewTitle").textContent = data.title;
  $("caseStatus").textContent = data.status === "OPEN" ? "진행 중" : "완료";
  $("caseStatus").className = `status-pill ${data.status === "OPEN" ? "info" : "good"}`;
  $("caseUpdated").textContent = `마지막 수정: ${formatDate(data.updated_at)}`;
  $("caseOriginalInput").textContent = data.original_input;

  renderCandidates();
  renderEvidence(data.evidence || []);
  renderCompare();
  renderRepresentative();
  renderLatestJudgment(data.judgments || []);
  renderClaritySummary();
  renderCandidateDisclaimer();
  updateJudgeAvailability();
  switchEvidenceTab(state.evidenceTab, false);
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

function adoptedRepresentative() {
  if (state.candidateOrigin === "DEMO") return null;
  return state.candidates.find(item => item.is_representative && item.adopted_evidence_id != null) || null;
}

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

async function loadTimeline() {
  if (!state.currentCaseId) return;
  const { body } = await api(`/cases/${state.currentCaseId}/timeline`);
  const host = $("timeline");
  if (!body.length) {
    host.innerHTML = '<div class="small-empty">아직 함께 확인한 기록이 없어요. 근거를 살펴보면 변화가 차곡차곡 남습니다.</div>';
    return;
  }
  const recent = [...body].reverse().slice(0, 8);
  host.innerHTML = recent.map(item => `
    <article class="timeline-item">
      <h3>${escapeHtml(item.title)}</h3>
      <p>${escapeHtml(item.summary)}</p>
      <time>${formatDate(item.occurred_at)}</time>
    </article>
  `).join("");
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

async function refreshCurrentCase() {
  if (state.currentCaseId) await selectCase(state.currentCaseId);
}

async function discoverCandidates({ demo = false } = {}) {
  if (!state.currentCaseId) return;
  if (!demo) {
    if (!state.ai?.configured) {
      showToast("API Key가 아직 없어서 실제 웹 근거 찾기는 사용할 수 없어요. 예시 보기는 바로 사용할 수 있습니다.", true);
      return;
    }
    const ok = window.confirm("실제 웹에서 근거를 찾기 위해 OpenAI API를 사용합니다. 비용이 발생할 수 있어요. 근거 6개를 찾아볼까요?");
    if (!ok) return;
  }

  const button = demo ? $("demoCandidatesButton") : $("discoverCandidatesButton");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = demo ? "예시 준비 중..." : "근거를 찾는 중...";
  try {
    const endpoint = demo
      ? `/cases/${state.currentCaseId}/evidence-candidates/demo`
      : `/cases/${state.currentCaseId}/evidence-candidates/discover`;
    const { body } = await api(endpoint, {
      method: "POST",
      body: JSON.stringify({ limit: 6 }),
    });
    setCandidateBatch(body);
    state.evidenceTab = "candidates";
    renderCase();
    await loadTimeline();
    showToast(demo ? "예시를 준비했어요. 편하게 둘러보세요." : "근거를 찾았어요. 내용을 먼저 읽어보고 필요한 자료만 골라주세요.");
  } catch (error) {
    const code = error.body?.detail?.code;
    showToast(code ? `${code}: ${error.message}` : error.message, true);
  } finally {
    button.disabled = demo ? false : !state.ai?.configured;
    button.textContent = original;
  }
}

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

$("toggleCaseForm").addEventListener("click", () => {
  $("caseForm").classList.toggle("hidden");
  if (!$("caseForm").classList.contains("hidden")) $("caseTitle").focus();
});
$("cancelCaseForm").addEventListener("click", () => {
  $("caseForm").reset();
  $("caseForm").classList.add("hidden");
});

$("caseForm").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const { body } = await api("/cases", {
      method: "POST",
      body: JSON.stringify({ title: $("caseTitle").value, original_input: $("caseInput").value }),
    });
    event.target.reset();
    event.target.classList.add("hidden");
    showToast("새 확인을 시작했어요. 이제 근거부터 같이 살펴볼 수 있습니다.");
    await loadCases(body.id);
  } catch (error) {
    showToast(error.message, true);
  }
});

$("evidenceForm").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const sourceUrl = $("sourceUrl").value.trim();
    const { body: createdEvidence } = await api(`/cases/${state.currentCaseId}/evidence`, {
      method: "POST",
      body: JSON.stringify({
        content: $("evidenceContent").value,
        source_type: $("sourceType").value,
        source_url: sourceUrl || null,
        is_primary_source: $("isPrimary").checked,
        reliability_score: null,
      }),
    });
    if (createdEvidence?.id) {
      if (sourceUrl) {
        await api(`/cases/${state.currentCaseId}/evidence/${createdEvidence.id}/verify-source`, { method: "POST" });
      } else {
        await api(`/cases/${state.currentCaseId}/evidence/${createdEvidence.id}/assess-reliability`, { method: "POST" });
      }
    }
    event.target.reset();
    state.evidenceTab = "adopted";
    showToast("직접 준비한 근거를 추가했어요.");
    await refreshCurrentCase();
  } catch (error) {
    if (error.status === 409 && error.body?.detail?.code === "DUPLICATE_EVIDENCE") {
      showToast(`이미 같은 근거가 있어요. 기존 근거 번호: ${error.body.detail.existing_evidence_id}`, true);
    } else {
      showToast(error.message, true);
    }
  }
});

$("assessAllButton").addEventListener("click", async () => {
  try {
    const items = state.currentCase?.evidence || [];
    if (!items.length) {
      showToast("아직 다시 확인할 근거가 없어요.", true);
      return;
    }
    for (const item of items) {
      const isDemo = item.reliability_source === "DEMO_CANDIDATE";
      if (item.source_url && !isDemo) {
        await api(`/cases/${state.currentCaseId}/evidence/${item.id}/verify-source`, { method: "POST" });
      } else {
        await api(`/cases/${state.currentCaseId}/evidence/${item.id}/assess-reliability`, { method: "POST" });
      }
    }
    showToast("고른 근거들을 다시 살펴봤어요. 현재 평가를 반영했습니다.");
    await refreshCurrentCase();
  } catch (error) {
    showToast(error.message, true);
  }
});

$("discoverCandidatesButton").addEventListener("click", () => discoverCandidates({ demo: false }));
$("demoCandidatesButton").addEventListener("click", () => discoverCandidates({ demo: true }));
$("judgeButton").addEventListener("click", () => runJudge(false));
$("forceJudgeButton").addEventListener("click", () => runJudge(true));
$("refreshTimeline").addEventListener("click", () => loadTimeline().catch(error => showToast(error.message, true)));
$("copyShareSummary").addEventListener("click", () => copyShareSummary());
$("refreshCases").addEventListener("click", () => loadCases().catch(error => showToast(error.message, true)));
$("caseSearch").addEventListener("input", renderCaseList);
$("caseSort").addEventListener("change", renderCaseList);
$("candidateSort").addEventListener("change", () => {
  renderCandidates();
  renderCompare();
});

document.querySelectorAll("[data-case-filter]").forEach(button => {
  button.addEventListener("click", () => {
    state.caseFilter = button.dataset.caseFilter;
    document.querySelectorAll("[data-case-filter]").forEach(item => item.classList.toggle("active", item === button));
    renderCaseList();
  });
});

document.querySelectorAll("[data-evidence-tab]").forEach(button => {
  button.addEventListener("click", () => switchEvidenceTab(button.dataset.evidenceTab));
});

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  })[char]);
}

function escapeAttr(value) {
  return escapeHtml(value);
}

Promise.all([loadAiStatus(), loadCases()]).catch(error => showToast(error.message, true));
