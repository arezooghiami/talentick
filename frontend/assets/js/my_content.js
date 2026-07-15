// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «محتوای من» (کتابخانه‌ی کامل محتوا برای کارمند)
// ════════════════════════════════════════════════════════════════════

const MyContentPage = (() => {
  const state = { page: 1, pageSize: 12, search: '', type: '' };
  let searchTimer = null;

  async function load(page = state.page) {
    state.page = page;
    const grid = document.getElementById('mcGrid');
    grid.innerHTML = empSkeletonCards(state.pageSize);
    document.getElementById('mcPagination').innerHTML = '';

    const p = new URLSearchParams({ page, page_size: state.pageSize });
    if (state.search) p.set('search', state.search);
    if (state.type) p.set('type', state.type);

    try {
      const res = await api.get(`/me/contents?${p}`);
      setText('mcCount', `${numFa(res.total)} مورد`);
      if (!res.items.length) {
        grid.innerHTML = `<div class="emp-empty" style="grid-column:1/-1;"><div class="icon">📭</div><h3>${state.search || state.type ? 'موردی با این فیلتر یافت نشد' : 'هنوز محتوایی برای شما ثبت نشده'}</h3></div>`;
        return;
      }
      grid.innerHTML = res.items.map(renderContentCard).join('');
      renderEmpPagination('mcPagination', res.page, res.total_pages, load);
    } catch (e) {
      grid.innerHTML = `<div class="emp-empty" style="grid-column:1/-1;"><div class="icon">⚠️</div><h3>خطا در بارگذاری: ${esc(e.message)}</h3></div>`;
    }
  }

  function searchDebounced() {
    state.search = document.getElementById('mcSearch').value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => load(1), 400);
  }

  function setType(type, btnEl) {
    state.type = type;
    document.querySelectorAll('.emp-filter-pill').forEach(b => b.classList.remove('active'));
    btnEl.classList.add('active');
    load(1);
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  return { load, searchDebounced, setType };
})();
