// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «تیکت‌ها» (پشتیبانی/بازخورد کارکنان) — مدیریتی
// ════════════════════════════════════════════════════════════════════
// دسترسی پیش‌فرض: org_admin (سازمان خودش) + super_admin (همه‌جا) — فراتر
// از آن، فقط با مجوز صریح super_admin (نقش یا کاربر خاص) که در این
// صفحه (تب «دسترسی‌ها») مدیریت می‌شود.

const TicketsPage = (() => {
  const STATUS_LABEL = { open: 'باز', answered: 'پاسخ داده‌شده', closed: 'بسته‌شده' };
  const STATUS_BADGE = { open: 'badge-ticket-open', answered: 'badge-ticket-answered', closed: 'badge-ticket-closed' };
  const GRANT_ROLE_LABEL = { manager: 'منیجر', employee: 'کارمند' };

  const state = {
    page: 1, search: '', searchTimer: null, items: [],
    categoriesLoaded: false, orgFilterLoaded: false,
    currentTicketId: null,
    grantOrgsLoaded: false, grantUserSearchTimer: null, selectedGrantUser: null,
  };

  // ─── لیست تیکت‌ها ─────────────────────────────────────────────────────

  async function load(page = state.page) {
    state.page = page;
    await Promise.all([loadCategoryFilterOptions(), App.isSuperAdmin ? loadOrgFilterOptions() : Promise.resolve()]);

    const tbody = document.getElementById('tkTableBody');
    tbody.innerHTML = `<tr><td colspan="8" class="loading-row">در حال بارگذاری...</td></tr>`;

    const p = new URLSearchParams({ page, page_size: 20 });
    if (state.search) p.set('search', state.search);
    const statusFilter = document.getElementById('tkStatusFilter')?.value;
    if (statusFilter) p.set('status', statusFilter);
    const categoryFilter = document.getElementById('tkCategoryFilter')?.value;
    if (categoryFilter) p.set('category_id', categoryFilter);
    const orgFilter = document.getElementById('tkOrgFilter')?.value;
    if (App.isSuperAdmin && orgFilter) p.set('org_id', orgFilter);

    try {
      const res = await api.get(`/tickets?${p}`);
      state.items = res.items || [];
      setText('tkTotalLabel', `مجموع ${numFa(res.total)} تیکت`);
      if (!state.items.length) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:40px;color:var(--gray-400);">تیکتی ثبت نشده</td></tr>`;
        renderPagination('tkPagination', res.page, res.total_pages, load);
        return;
      }
      renderTable();
      renderPagination('tkPagination', res.page, res.total_pages, load);
      Router.applyRoleVisibility(App.currentUser.role);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function renderTable() {
    document.getElementById('tkTableBody').innerHTML = state.items.map(t => `
      <tr>
        <td style="font-weight:500;">${esc(t.subject)}</td>
        <td class="th-org" data-roles="super_admin" style="color:var(--gray-500);">${esc(t.org_name || '—')}</td>
        <td>${t.category_name ? esc(t.category_name) : '<span style="color:var(--gray-400);">—</span>'}</td>
        <td>${esc(t.created_by_name || '—')}</td>
        <td>${numFa(t.message_count)}</td>
        <td><span class="badge ${STATUS_BADGE[t.status] || ''}">${STATUS_LABEL[t.status] || t.status}</span></td>
        <td style="color:var(--gray-500);font-size:12px;">${fmtDate(t.updated_at)}</td>
        <td><button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" data-role="open-ticket" data-id="${t.id}">مشاهده</button></td>
      </tr>`).join('');
  }

  function searchDebounced() {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => { state.search = document.getElementById('tkSearch').value.trim(); load(1); }, 350);
  }

  async function loadCategoryFilterOptions() {
    const sel = document.getElementById('tkCategoryFilter');
    if (!sel || state.categoriesLoaded) return;
    try {
      const cats = await api.get('/ticket-categories?active_only=false');
      sel.innerHTML = '<option value="">همه‌ی دسته‌بندی‌ها</option>' +
        cats.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
      state.categoriesLoaded = true;
    } catch { /* غیرحیاتی — فقط فیلتر است */ }
  }

  async function loadOrgFilterOptions() {
    const sel = document.getElementById('tkOrgFilter');
    if (!sel || state.orgFilterLoaded) return;
    try {
      const res = await api.get('/orgs/');
      const orgs = Array.isArray(res) ? res : (res.items || []);
      sel.innerHTML = '<option value="">همه سازمان‌ها</option>' +
        orgs.map(o => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
      state.orgFilterLoaded = true;
    } catch { /* غیرحیاتی */ }
  }

  // ─── جزئیات تیکت + ترد پاسخ ───────────────────────────────────────────

  async function openDetail(ticketId) {
    state.currentTicketId = ticketId;
    document.getElementById('tk-reply-body').value = '';
    openModal('modal-ticket-detail');
    document.getElementById('tkDetailSubject').textContent = 'در حال بارگذاری...';
    document.getElementById('tkThread').innerHTML = '';
    try {
      const t = await api.get(`/tickets/${ticketId}`);
      renderDetail(t);
    } catch (e) {
      toastError(e.message);
      closeModal('modal-ticket-detail');
    }
  }

  function renderDetail(t) {
    document.getElementById('tkDetailSubject').textContent = t.subject;
    const metaParts = [
      `<span>سازمان: <b>${esc(t.org_name || '—')}</b></span>`,
      `<span>کارمند: <b>${esc(t.created_by_name || '—')}</b></span>`,
      `<span>دسته‌بندی: <b>${t.category_name ? esc(t.category_name) : '—'}</b></span>`,
      `<span>وضعیت: <span class="badge ${STATUS_BADGE[t.status] || ''}">${STATUS_LABEL[t.status] || t.status}</span></span>`,
    ];
    if (t.related_content_title) {
      metaParts.push(`<span>محتوای مرتبط: <b>${esc(t.related_content_title)}</b></span>`);
    }
    if (t.satisfaction_rating) {
      metaParts.push(`<span>رضایت کارمند: <span class="ticket-rating-stars">${[1, 2, 3, 4, 5].map(i => `<span class="${i > t.satisfaction_rating ? 'empty' : ''}">★</span>`).join('')}</span></span>`);
    }
    document.getElementById('tkDetailMeta').innerHTML = metaParts.join('');

    document.getElementById('tkThread').innerHTML = (t.messages || []).map(m => {
      const isCreator = m.sender_id === t.created_by;
      return `
        <div class="ticket-msg ${isCreator ? 'creator' : 'staff'}">
          <div class="ticket-msg-head"><span>${esc(m.sender_name || 'کاربر حذف‌شده')}</span><span>${fmtDate(m.created_at)}</span></div>
          <div class="ticket-msg-body">${esc(m.body)}</div>
        </div>`;
    }).join('');
    const thread = document.getElementById('tkThread');
    thread.scrollTop = thread.scrollHeight;

    const isClosed = t.status === 'closed';
    document.getElementById('btn-tk-force-close').classList.toggle('hidden', isClosed);
    document.getElementById('btn-tk-reply').classList.toggle('hidden', isClosed);
    document.getElementById('tk-reply-body').classList.toggle('hidden', isClosed);
  }

  async function sendReply() {
    const body = document.getElementById('tk-reply-body').value.trim();
    if (!body) { toastError('متن پاسخ نمی‌تواند خالی باشد'); return; }
    const btn = document.getElementById('btn-tk-reply');
    setLoading(btn, true);
    try {
      await api.post(`/tickets/${state.currentTicketId}/messages`, { body });
      document.getElementById('tk-reply-body').value = '';
      const t = await api.get(`/tickets/${state.currentTicketId}`);
      renderDetail(t);
      await load(state.page);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function forceClose() {
    confirmAction('آیا مطمئن هستید که می‌خواهید این تیکت را بدون امتیازدهی کارمند ببندید؟', async () => {
      try {
        await api.post(`/tickets/${state.currentTicketId}/close`);
        toastSuccess('تیکت بسته شد');
        const t = await api.get(`/tickets/${state.currentTicketId}`);
        renderDetail(t);
        await load(state.page);
      } catch (e) { toastError(e.message); }
    });
  }

  // ─── دسته‌بندی‌ها (super_admin) ────────────────────────────────────────

  async function openCategories() {
    openModal('modal-ticket-categories');
    document.getElementById('tkc-name').value = '';
    document.getElementById('tkc-order').value = '0';
    await loadCategoriesTable();
  }

  async function loadCategoriesTable() {
    const tbody = document.getElementById('tkCategoriesTableBody');
    tbody.innerHTML = `<tr><td colspan="4" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const cats = await api.get('/ticket-categories?active_only=false');
      if (!cats.length) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--gray-400);">دسته‌بندی‌ای ثبت نشده</td></tr>`;
        return;
      }
      tbody.innerHTML = cats.map(c => `
        <tr>
          <td>${esc(c.name)}</td>
          <td>${numFa(c.order_index)}</td>
          <td>${statusBadge(c.is_active)}</td>
          <td>
            <div style="display:flex;gap:4px;flex-wrap:wrap;">
              <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" data-role="toggle-category" data-id="${c.id}" data-active="${c.is_active}">${c.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی'}</button>
              <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-category" data-id="${c.id}" data-title="${esc(c.name)}">حذف</button>
            </div>
          </td>
        </tr>`).join('');
      state.categoriesLoaded = false; // فیلتر لیست اصلی هم باید رفرش شود
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--danger);">خطا: ${esc(e.message)}</td></tr>`;
    }
  }

  async function addCategory() {
    const name = document.getElementById('tkc-name').value.trim();
    if (!name) { toastError('نام دسته‌بندی اجباری است'); return; }
    const order_index = parseInt(document.getElementById('tkc-order').value, 10) || 0;
    try {
      await api.post('/ticket-categories', { name, order_index, is_active: true });
      toastSuccess('دسته‌بندی ثبت شد');
      document.getElementById('tkc-name').value = '';
      document.getElementById('tkc-order').value = '0';
      await loadCategoriesTable();
    } catch (e) { toastError(e.message); }
  }

  async function toggleCategoryActive(id, currentlyActive) {
    try {
      await api.patch(`/ticket-categories/${id}`, { is_active: !currentlyActive });
      await loadCategoriesTable();
    } catch (e) { toastError(e.message); }
  }

  function removeCategory(id, title) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید دسته‌بندی "${title}" را حذف کنید؟`, async () => {
      try {
        await api.delete(`/ticket-categories/${id}`);
        toastSuccess('دسته‌بندی حذف شد');
        await loadCategoriesTable();
      } catch (e) { toastError(e.message); }
    });
  }

  // ─── مجوزهای دسترسی (super_admin) ─────────────────────────────────────

  async function openAccessGrants() {
    openModal('modal-ticket-access-grants');
    document.getElementById('tkg-type').value = 'role';
    document.getElementById('tkg-role').value = 'manager';
    document.getElementById('tkg-user-search').value = '';
    document.getElementById('tkgUserResults').innerHTML = '<div class="checkbox-scroll-box-empty">برای جستجو تایپ کنید</div>';
    state.selectedGrantUser = null;
    onGrantTypeChange();
    if (!state.grantOrgsLoaded) {
      try {
        const res = await api.get('/orgs/');
        const orgs = Array.isArray(res) ? res : (res.items || []);
        document.getElementById('tkg-org-id').innerHTML = '<option value="">— انتخاب سازمان —</option>' +
          orgs.map(o => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
        state.grantOrgsLoaded = true;
      } catch { /* ignore */ }
    }
    await loadGrantsTable();
  }

  function onGrantOrgChange() {
    document.getElementById('tkg-user-search').value = '';
    document.getElementById('tkgUserResults').innerHTML = '<div class="checkbox-scroll-box-empty">برای جستجو تایپ کنید</div>';
    state.selectedGrantUser = null;
    loadGrantsTable();
  }

  function onGrantTypeChange() {
    const isRole = document.getElementById('tkg-type').value === 'role';
    document.getElementById('tkg-role-wrap').classList.toggle('hidden', !isRole);
    document.getElementById('tkg-user-wrap').classList.toggle('hidden', isRole);
  }

  function grantUserSearchDebounced() {
    clearTimeout(state.grantUserSearchTimer);
    state.grantUserSearchTimer = setTimeout(runGrantUserSearch, 350);
  }

  async function runGrantUserSearch() {
    const box = document.getElementById('tkgUserResults');
    const orgId = document.getElementById('tkg-org-id').value;
    const q = document.getElementById('tkg-user-search').value.trim();
    if (!orgId) { box.innerHTML = '<div class="checkbox-scroll-box-empty">ابتدا سازمان را انتخاب کنید</div>'; return; }
    if (!q) { box.innerHTML = '<div class="checkbox-scroll-box-empty">برای جستجو تایپ کنید</div>'; return; }
    box.innerHTML = '<div class="checkbox-scroll-box-empty">در حال جستجو...</div>';
    try {
      const res = await api.get(`/users/?org_id=${orgId}&search=${encodeURIComponent(q)}&per_page=20`);
      const results = res.items || [];
      box.innerHTML = !results.length
        ? '<div class="checkbox-scroll-box-empty">کاربری یافت نشد</div>'
        : results.map(u => `
          <label class="checkbox-row">
            <input type="radio" name="tkg-user-radio" data-role="select-grant-user" data-id="${u.id}" data-name="${esc(`${u.full_name} (${u.email})`)}" ${state.selectedGrantUser?.id === u.id ? 'checked' : ''}>
            ${esc(u.full_name)}
            <span class="checkbox-row-meta">${esc(u.email)}</span>
          </label>`).join('');
    } catch { box.innerHTML = '<div class="checkbox-scroll-box-empty">خطا در جستجو</div>'; }
  }

  async function addGrant() {
    const orgId = document.getElementById('tkg-org-id').value;
    if (!orgId) { toastError('انتخاب سازمان اجباری است'); return; }
    const grantType = document.getElementById('tkg-type').value;
    const payload = { org_id: orgId, grant_type: grantType };
    if (grantType === 'role') {
      payload.role = document.getElementById('tkg-role').value;
    } else {
      if (!state.selectedGrantUser) { toastError('یک کاربر را از نتایج جستجو انتخاب کنید'); return; }
      payload.user_id = state.selectedGrantUser.id;
    }
    try {
      await api.post('/tickets/access-grants', payload);
      toastSuccess('مجوز دسترسی ثبت شد');
      state.selectedGrantUser = null;
      document.getElementById('tkg-user-search').value = '';
      document.getElementById('tkgUserResults').innerHTML = '<div class="checkbox-scroll-box-empty">برای جستجو تایپ کنید</div>';
      await loadGrantsTable();
    } catch (e) { toastError(e.message); }
  }

  async function loadGrantsTable() {
    const tbody = document.getElementById('tkGrantsTableBody');
    tbody.innerHTML = `<tr><td colspan="5" class="loading-row">در حال بارگذاری...</td></tr>`;
    const orgId = document.getElementById('tkg-org-id').value;
    try {
      const grants = await api.get(orgId ? `/tickets/access-grants?org_id=${orgId}` : '/tickets/access-grants');
      if (!grants.length) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--gray-400);">مجوزی ثبت نشده</td></tr>`;
        return;
      }
      tbody.innerHTML = grants.map(g => `
        <tr>
          <td>${esc(g.org_name || '—')}</td>
          <td>${g.grant_type === 'role' ? 'نقش' : 'کاربر'}</td>
          <td>${g.grant_type === 'role' ? esc(GRANT_ROLE_LABEL[g.role] || g.role) : esc(g.user_name || '—')}</td>
          <td style="color:var(--gray-500);font-size:12px;">${esc(g.granted_by_name || '—')}</td>
          <td><button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-grant" data-id="${g.id}">حذف</button></td>
        </tr>`).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--danger);">خطا: ${esc(e.message)}</td></tr>`;
    }
  }

  function removeGrant(id) {
    confirmAction('آیا مطمئن هستید که می‌خواهید این مجوز دسترسی را حذف کنید؟', async () => {
      try {
        await api.delete(`/tickets/access-grants/${id}`);
        toastSuccess('مجوز حذف شد');
        await loadGrantsTable();
      } catch (e) { toastError(e.message); }
    });
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  // ─── Delegated Row Actions — به‌جای onclick اینلاین با متن کاربر ────────
  document.getElementById('tkTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="open-ticket"]');
    if (btn) openDetail(btn.dataset.id);
  });
  document.getElementById('tkCategoriesTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role]');
    if (!btn) return;
    const { role, id, title, active } = btn.dataset;
    if (role === 'toggle-category') toggleCategoryActive(id, active === 'true');
    else if (role === 'delete-category') removeCategory(id, title);
  });
  document.getElementById('tkGrantsTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-grant"]');
    if (btn) removeGrant(btn.dataset.id);
  });
  document.getElementById('tkgUserResults')?.addEventListener('change', (e) => {
    const input = e.target.closest('[data-role="select-grant-user"]');
    if (!input) return;
    state.selectedGrantUser = { id: input.dataset.id, name: input.dataset.name };
  });

  return {
    load, searchDebounced, openDetail, sendReply, forceClose,
    openCategories, addCategory,
    openAccessGrants, onGrantOrgChange, onGrantTypeChange, grantUserSearchDebounced, addGrant,
  };
})();
