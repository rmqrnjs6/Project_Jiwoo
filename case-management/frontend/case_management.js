// Extracted from the original frontend/app.js for functional classification.
// This is a review/upload copy, not a standalone bundle. Shared helpers/state remain in 00_common/frontend.

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

async function refreshCurrentCase() {
  if (state.currentCaseId) await selectCase(state.currentCaseId);
}

