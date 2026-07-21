// ════════════════════════════════════════════════════════════════════
// Talentick — صف بررسی «درخواست‌های تبدیل امتیاز» — super_admin + org_admin
// ════════════════════════════════════════════════════════════════════
// بخش ششم اسپک — گردش: submitted → under_review → approved/rejected →
// (approved) delivered. کسر امتیاز و کاهش انبار در approve انجام می‌شود.

const RedemptionsPage = (() => {
  const state = { items: [], page: 1, pendingAction: null };

  const STATUS_LABEL_FA = {
    draft: 'پیش‌نویس', submitted: 'ثبت‌شده', under_review: 'در حال بررسی',
    approved: 'تایید شده', rejected: 'رد شده', delivered: 'تحویل داده شده', cancelled: 'لغو شده',
  };
  const STATUS_COLOR = {
    submitted: '#B45309', under_review: '#B45309', approved: '#4F46E5',
    delivered: '#059669', rejected: '#DC2626', cancelled: '#6B7280', draft: '#6B7280',
  };

  async function load(page = 1) {
    state.page = page;
    await loadOrgFilter();
    const tbody = document.getElementById('rdTableBody');
    tbody.innerHTML = `<tr><td colspan="6" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const qs = new URLSearchParams({ page, page_size: 20 });
      const statusFilter = document.getElementById('rdStatusFilter')?.value || '';
      if (statusFilter) qs.set('status', statusFilter);
      const orgId = document.getElementById('rdOrgFilter')?.value || '';
      if (orgId) qs.set('org_id', orgId);
      const res = await api.get(`/redemptions?${qs}`);
      state.items = res.items;
      renderTable();
      renderPagination('rdPagination', res.page, res.total_pages, load);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  async function loadOrgFilter() {
    if (!App.isSuperAdmin) return;
    const sel = document.getElementById('rdOrgFilter');
    if (!sel || sel.dataset.loaded) return;
    try {
      const orgs = OrgsPage.getCache()?.length ? OrgsPage.getCache() : await api.get('/orgs/');
      sel.innerHTML = `<option value="">همه سازمان‌ها</option>` + orgs.map(o => `<option value="${esc(o.id)}">${esc(o.name)}</option>`).join('');
      sel.dataset.loaded = '1';
    } catch { /* اختیاری */ }
  }

  function renderTable() {
    const tbody = document.getElementById('rdTableBody');
    if (!state.items.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--gray-400);">درخواستی یافت نشد</td></tr>`;
      return;
    }
    tbody.innerHTML = state.items.map(r => `
      <tr>
        <td style="font-weight:500;">${esc(r.user_name || '—')}</td>
        <td>${esc(r.reward_title || '—')}</td>
        <td>${numFa(r.cost_points_snapshot)}</td>
        <td><span style="color:${STATUS_COLOR[r.status] || '#6B7280'};font-weight:600;font-size:12.5px;">${esc(r.status_label)}</span></td>
        <td>${fmtDate(r.created_at)}</td>
        <td>${renderActions(r)}</td>
      </tr>`).join('');
  }

  function renderActions(r) {
    const btn = (role, label, bg, color) => `<button class="btn-action" style="background:${bg};color:${color};" data-role="${role}" data-id="${r.id}">${label}</button>`;
    if (r.status === 'submitted') {
      return btn('under-review', 'بررسی', 'var(--gray-100)', 'var(--gray-700)')
        + btn('approve', 'تایید', '#D1FAE5', '#047857')
        + btn('reject', 'رد', '#FEF2F2', '#DC2626');
    }
    if (r.status === 'under_review') {
      return btn('approve', 'تایید', '#D1FAE5', '#047857') + btn('reject', 'رد', '#FEF2F2', '#DC2626');
    }
    if (r.status === 'approved') {
      return btn('deliver', 'ثبت تحویل', 'var(--primary-light)', 'var(--primary)');
    }
    return '<span style="color:var(--gray-300);">—</span>';
  }

  function openDecision(id, action) {
    state.pendingAction = { id, action };
    const titles = { 'under-review': 'انتقال به «در حال بررسی»', approve: 'تایید درخواست', reject: 'رد درخواست' };
    document.getElementById('rdDecisionTitle').textContent = titles[action] || 'تصمیم';
    document.getElementById('rd-note').value = '';
    openModal('modal-redemption-decision');
  }

  async function confirmDecision() {
    if (!state.pendingAction) return;
    const { id, action } = state.pendingAction;
    const note = document.getElementById('rd-note').value.trim() || null;
    const btn = document.getElementById('btn-confirm-redemption-decision');
    setLoading(btn, true);
    try {
      await api.patch(`/redemptions/${id}/${action}`, { admin_note: note });
      toastSuccess('ثبت شد');
      closeModal('modal-redemption-decision');
      await load(state.page);
    } catch (e) {
      toastError(e.message);
    } finally {
      setLoading(btn, false);
      state.pendingAction = null;
    }
  }

  function deliver(id) {
    confirmAction('آیا تحویل این جایزه به کارمند را تایید می‌کنید؟', async () => {
      await api.patch(`/redemptions/${id}/deliver`);
      toastSuccess('تحویل ثبت شد');
      await load(state.page);
    });
  }

  document.getElementById('rdTableBody')?.addEventListener('click', (e) => {
    const b = e.target.closest('[data-role]');
    if (!b) return;
    if (b.dataset.role === 'deliver') deliver(b.dataset.id);
    else openDecision(b.dataset.id, b.dataset.role);
  });

  return { load, confirmDecision };
})();
