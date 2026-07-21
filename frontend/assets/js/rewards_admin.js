// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «فروشگاه جایزه» (Reward Marketplace) — super_admin + org_admin
// ════════════════════════════════════════════════════════════════════
// super_admin: هر سازمانی یا سراسری (org_id خالی) می‌سازد.
// org_admin: همیشه فقط برای سازمان خودش — فیلد سازمان در فرم مخفی است.

const RewardsPage = (() => {
  const state = { items: [], page: 1, search: '', orgId: '' };
  let searchDebounce;

  const STATUS_LABEL_FA = { draft: 'پیش‌نویس', active: 'فعال', inactive: 'غیرفعال', archived: 'بایگانی‌شده' };
  const CATEGORY_LABEL_FA = {
    goods: 'کالا', gift_card: 'کارت هدیه', cash: 'جایزه نقدی', course: 'دوره آموزشی',
    benefit: 'مزایا و خدمات', special_access: 'دسترسی ویژه', leave: 'مرخصی تشویقی', custom: 'سایر',
  };

  async function load(page = 1) {
    state.page = page;
    await loadOrgFilter();
    const tbody = document.getElementById('rwTableBody');
    tbody.innerHTML = `<tr><td colspan="7" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const qs = new URLSearchParams({ page, page_size: 20 });
      if (state.search) qs.set('search', state.search);
      const orgId = document.getElementById('rwOrgFilter')?.value || '';
      if (orgId) qs.set('org_id', orgId);
      const res = await api.get(`/rewards?${qs}`);
      state.items = res.items;
      renderTable();
      renderPagination('rwPagination', res.page, res.total_pages, load);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function debouncedSearch() {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      state.search = document.getElementById('rwSearch').value.trim();
      load(1);
    }, 350);
  }

  async function loadOrgFilter() {
    if (!App.isSuperAdmin) return;
    const filterSel = document.getElementById('rwOrgFilter');
    const formSel = document.getElementById('rw-org');
    if ((!filterSel || filterSel.dataset.loaded) && (!formSel || formSel.dataset.loaded)) return;
    try {
      const orgs = OrgsPage.getCache()?.length ? OrgsPage.getCache() : await api.get('/orgs/');
      if (filterSel) { filterSel.innerHTML = `<option value="">همه (سراسری + سازمانی)</option>` + orgs.map(o => `<option value="${esc(o.id)}">${esc(o.name)}</option>`).join(''); filterSel.dataset.loaded = '1'; }
      if (formSel) { formSel.innerHTML = `<option value="">— سراسری (همه‌ی سازمان‌ها) —</option>` + orgs.map(o => `<option value="${esc(o.id)}">${esc(o.name)}</option>`).join(''); formSel.dataset.loaded = '1'; }
    } catch { /* اختیاری */ }
  }

  function renderTable() {
    const tbody = document.getElementById('rwTableBody');
    if (!state.items.length) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--gray-400);">هیچ جایزه‌ای ثبت نشده</td></tr>`;
      return;
    }
    tbody.innerHTML = state.items.map(r => `
      <tr>
        <td style="font-weight:500;">${esc(r.title)}</td>
        <td class="th-org" data-roles="super_admin">${r.org_name ? esc(r.org_name) : '<span style="color:var(--gray-400);">سراسری</span>'}</td>
        <td>${esc(r.category_label)}</td>
        <td>${numFa(r.cost_points)}</td>
        <td>${r.inventory_total == null ? 'نامحدود' : `${numFa(r.inventory_remaining)} / ${numFa(r.inventory_total)}`}</td>
        <td>${statusBadgeText(r.status)}</td>
        <td>
          <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" data-role="edit-reward" data-id="${r.id}">ویرایش</button>
          ${r.status !== 'archived' ? `<button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="archive-reward" data-id="${r.id}">بایگانی</button>` : ''}
        </td>
      </tr>`).join('');
  }

  function statusBadgeText(status) {
    const colors = { active: '#059669', draft: '#B45309', inactive: '#6B7280', archived: '#9CA3AF' };
    return `<span style="color:${colors[status] || '#6B7280'};font-weight:600;font-size:12.5px;">${STATUS_LABEL_FA[status] || status}</span>`;
  }

  async function openCreate() {
    await loadOrgFilter();
    document.getElementById('rewardModalTitle').textContent = 'جایزه جدید';
    document.getElementById('rw-id').value = '';
    document.getElementById('rw-org').value = '';
    document.getElementById('rw-title').value = '';
    document.getElementById('rw-desc').value = '';
    document.getElementById('rw-category').value = 'custom';
    document.getElementById('rw-cost').value = '';
    document.getElementById('rw-inventory').value = '';
    document.getElementById('rw-status').value = 'active';
    document.getElementById('rw-start').value = '';
    document.getElementById('rw-end').value = '';
    openModal('modal-reward');
  }

  function openEdit(id) {
    const r = state.items.find(x => x.id === id);
    if (!r) return;
    document.getElementById('rewardModalTitle').textContent = 'ویرایش جایزه';
    document.getElementById('rw-id').value = r.id;
    document.getElementById('rw-org').value = r.org_id || '';
    document.getElementById('rw-title').value = r.title;
    document.getElementById('rw-desc').value = r.description || '';
    document.getElementById('rw-category').value = r.category;
    document.getElementById('rw-cost').value = r.cost_points;
    document.getElementById('rw-inventory').value = r.inventory_total ?? '';
    document.getElementById('rw-status').value = r.status;
    document.getElementById('rw-start').value = r.start_date ? r.start_date.slice(0, 10) : '';
    document.getElementById('rw-end').value = r.end_date ? r.end_date.slice(0, 10) : '';
    openModal('modal-reward');
  }

  async function save() {
    const id = document.getElementById('rw-id').value;
    const title = document.getElementById('rw-title').value.trim();
    const costPoints = parseInt(document.getElementById('rw-cost').value, 10);
    if (!title) { toastError('عنوان را وارد کنید'); return; }
    if (isNaN(costPoints) || costPoints <= 0) { toastError('امتیاز لازم باید عددی مثبت باشد'); return; }

    const inventoryRaw = document.getElementById('rw-inventory').value;
    const startRaw = document.getElementById('rw-start').value;
    const endRaw = document.getElementById('rw-end').value;

    const payload = {
      title,
      description: document.getElementById('rw-desc').value.trim() || null,
      category: document.getElementById('rw-category').value,
      cost_points: costPoints,
      inventory_total: inventoryRaw === '' ? null : parseInt(inventoryRaw, 10),
      status: document.getElementById('rw-status').value,
      start_date: startRaw ? new Date(startRaw).toISOString() : null,
      end_date: endRaw ? new Date(endRaw).toISOString() : null,
    };
    if (!id) payload.org_id = document.getElementById('rw-org').value || null;

    const btn = document.getElementById('btn-save-reward');
    setLoading(btn, true);
    try {
      if (id) await api.patch(`/rewards/${id}`, payload);
      else await api.post('/rewards', payload);
      toastSuccess('جایزه ذخیره شد');
      closeModal('modal-reward');
      await load(state.page);
    } catch (e) {
      toastError(e.message);
    } finally {
      setLoading(btn, false);
    }
  }

  function archive(id) {
    confirmAction('آیا مطمئن هستید که می‌خواهید این جایزه را بایگانی کنید؟ دیگر در فروشگاه کارمندان نمایش داده نمی‌شود.', async () => {
      await api.delete(`/rewards/${id}`);
      toastSuccess('جایزه بایگانی شد');
      await load(state.page);
    });
  }

  document.getElementById('rwTableBody')?.addEventListener('click', (e) => {
    const editBtn = e.target.closest('[data-role="edit-reward"]');
    if (editBtn) { openEdit(editBtn.dataset.id); return; }
    const archiveBtn = e.target.closest('[data-role="archive-reward"]');
    if (archiveBtn) archive(archiveBtn.dataset.id);
  });

  return { load, debouncedSearch, openCreate, save };
})();
