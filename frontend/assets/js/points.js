// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «امتیازات من» (کارمند)
// ════════════════════════════════════════════════════════════════════
// مجموع امتیاز + تاریخچه‌ی چرونولوژیک اتفاق‌هایی که امتیاز آورده‌اند.

const MyPointsPage = (() => {
  const state = { page: 1 };

  async function load(page = state.page) {
    state.page = page;
    loadSummary();
    await loadHistory(page);
  }

  async function loadSummary() {
    try {
      const res = await api.get('/me/points/summary');
      document.getElementById('ptTotal').textContent = numFa(res.total_points);
    } catch {
      document.getElementById('ptTotal').textContent = '—';
    }
  }

  async function loadHistory(page) {
    const list = document.getElementById('ptHistory');
    list.innerHTML = '<div class="emp-skeleton" style="height:60px;"></div><div class="emp-skeleton" style="height:60px;"></div><div class="emp-skeleton" style="height:60px;"></div>';
    try {
      const res = await api.get(`/me/points/history?page=${page}&page_size=20`);
      if (!res.items.length) {
        list.innerHTML = `<div class="emp-empty"><div class="icon">🏆</div><h3>هنوز امتیازی کسب نکرده‌اید</h3><p style="color:var(--gray-400);font-size:13px;margin-top:6px;">با تکمیل محتوا، قبولی در آزمون یا پیشرفت در آنبوردینگ شروع کنید</p></div>`;
        renderPagination('ptPagination', res.page, res.total_pages, load);
        return;
      }
      list.innerHTML = res.items.map(renderEntry).join('');
      renderPagination('ptPagination', res.page, res.total_pages, load);
    } catch (e) {
      list.innerHTML = `<div class="emp-empty"><div class="icon">⚠️</div><h3>خطا در بارگذاری: ${esc(e.message)}</h3></div>`;
    }
  }

  function renderEntry(e) {
    return `
      <div class="item-card" style="cursor:default;">
        <div class="item-card-icon">🏆</div>
        <div class="item-card-info">
          <div class="item-card-title">${esc(e.event_label)}</div>
          <div class="item-card-meta">${e.reference_title ? esc(e.reference_title) + ' • ' : ''}${fmtDate(e.created_at)}</div>
        </div>
        <span class="points-history-points">+${numFa(e.points)}</span>
      </div>`;
  }

  return { load };
})();
