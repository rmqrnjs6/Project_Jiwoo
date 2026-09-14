// Extracted from the original frontend/app.js for functional classification.
// This is a review/upload copy, not a standalone bundle. Shared helpers/state remain in 00_common/frontend.

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

