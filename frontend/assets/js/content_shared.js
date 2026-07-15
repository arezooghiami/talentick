// ════════════════════════════════════════════════════════════════════
// Talentick — ثابت‌ها و کامپوننت‌های مشترک بین صفحات پرتال کارمند
// (home.js, my_content.js, content_detail.js)
// ════════════════════════════════════════════════════════════════════

const TYPE_LABEL_FA = { course: 'دوره', article: 'مقاله', podcast: 'پادکست', book: 'کتاب' };
const TYPE_ICON = { course: '🎓', article: '📰', podcast: '🎙️', book: '📚' };
const STATUS_LABEL_FA = { not_started: 'شروع‌نشده', in_progress: 'در حال یادگیری', completed: 'تکمیل‌شده' };
const ITEM_TYPE_ICON_FA = { text: '📄', video: '🎬', pdf: '📕', image: '🖼️', link: '🔗', file: '📎', quiz_ref: '📝' };
const ITEM_TYPE_LABEL_FA = { text: 'متن', video: 'ویدیو', pdf: 'PDF', image: 'تصویر', link: 'لینک', file: 'فایل', quiz_ref: 'آزمون' };

function renderContentCard(c) {
  const pct = c.my_progress_pct || 0;
  return `
    <a class="content-card" href="/content/detail.html?id=${c.id}">
      <div class="content-card-thumb">
        ${c.thumbnail_url ? `<img src="${esc(c.thumbnail_url)}" alt="">` : (TYPE_ICON[c.type] || '📄')}
        <span class="content-card-type">${TYPE_LABEL_FA[c.type] || c.type}</span>
      </div>
      <div class="content-card-body">
        <div class="content-card-title">${esc(c.title)}</div>
        <div class="content-card-meta"><span class="status-chip ${c.my_status}">${STATUS_LABEL_FA[c.my_status] || c.my_status}</span></div>
        <div class="content-card-progress">
          <div class="progress-track"><div class="progress-fill ${pct >= 100 ? 'done' : ''}" style="width:${pct}%;"></div></div>
          <div class="content-card-progress-label"><span>${numFa(pct)}٪</span><span>${numFa(c.total_items_count)} آیتم</span></div>
        </div>
      </div>
    </a>`;
}

function empSkeletonCards(n) {
  return Array.from({ length: n }).map(() => `<div class="emp-skeleton" style="height:210px;"></div>`).join('');
}

/** صفحه‌بندی سبک برای صفحات پرتال کارمند (کلاس‌های emp-page-btn). */
function renderEmpPagination(containerId, cur, total, onPage) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (total <= 1) { el.innerHTML = ''; return; }
  const s = Math.max(1, cur - 2), e = Math.min(total, cur + 2);
  let btns = '';
  const pageBtn = (p, active) => `<button class="emp-page-btn${active ? ' active' : ''}" data-page="${p}">${numFa(p)}</button>`;
  if (s > 1) btns += pageBtn(1, false);
  if (s > 2) btns += `<span style="padding:0 4px;color:var(--gray-400)">…</span>`;
  for (let p = s; p <= e; p++) btns += pageBtn(p, p === cur);
  if (e < total - 1) btns += `<span style="padding:0 4px;color:var(--gray-400)">…</span>`;
  if (e < total) btns += pageBtn(total, false);
  el.innerHTML = `
    <button class="emp-page-btn" data-page="${cur - 1}" ${cur <= 1 ? 'disabled' : ''}>›</button>
    ${btns}
    <button class="emp-page-btn" data-page="${cur + 1}" ${cur >= total ? 'disabled' : ''}>‹</button>`;
  el.querySelectorAll('[data-page]').forEach(btn => {
    btn.addEventListener('click', () => {
      const p = parseInt(btn.dataset.page, 10);
      if (p >= 1 && p <= total) onPage(p);
    });
  });
}
